"""Spawn-only worker process ownership and lifecycle."""

from __future__ import annotations

import math
import multiprocessing
import threading
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.process import BaseProcess
from typing import Annotated, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from everweb.domain import Receipt, TaskIdentity

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
PositiveInteger = Annotated[int, Field(gt=0)]
TERMINATE_GRACE_S = 1.0


class WorkerAssignment(BaseModel):
    """One immutable task and CDP lease assigned to one Worker."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_id: NonEmptyString
    task_identity: TaskIdentity
    cdp_url: NonEmptyString


class WorkerHandle(BaseModel):
    """Parent-visible identity for one active Worker process."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_id: NonEmptyString
    task_id: NonEmptyString
    cdp_url: NonEmptyString
    pid: PositiveInteger


class WorkerExitReceipt(Receipt):
    """Minimal immutable fact produced after Parent reaps a Worker."""

    execution_id: NonEmptyString
    task_id: NonEmptyString
    pid: PositiveInteger
    exit_code: int


WorkerEntrypoint = Callable[[WorkerAssignment], None]


class _SpawnContext(Protocol):
    def get_start_method(self) -> str: ...

    def Process(
        self,
        *,
        target: WorkerEntrypoint,
        args: tuple[WorkerAssignment],
        daemon: bool,
        name: str,
    ) -> BaseProcess: ...


class WorkerLifecycleError(RuntimeError):
    """Base error for Parent-owned Worker lifecycle failures."""


class WorkerLeaseConflictError(WorkerLifecycleError):
    """A task, execution, or CDP URL already has an active lease."""


class WorkerNotFoundError(WorkerLifecycleError):
    """No active Worker exists for the requested execution."""


class WorkerStartError(WorkerLifecycleError):
    """The spawn Process could not be started safely."""


@dataclass(slots=True)
class _WorkerSlot:
    assignment: WorkerAssignment
    process: BaseProcess


def _default_worker_entrypoint(assignment: WorkerAssignment) -> None:
    """No-op child target used until the runtime loop is wired."""


class SpawnWorkerPool:
    """Own spawn Processes and exclusive execution/task/CDP leases."""

    def __init__(
        self,
        *,
        entrypoint: WorkerEntrypoint = _default_worker_entrypoint,
    ) -> None:
        if not callable(entrypoint):
            raise TypeError("entrypoint must be callable")
        self._context = cast(
            _SpawnContext,
            multiprocessing.get_context("spawn"),
        )
        self._entrypoint = entrypoint
        self._slots: dict[str, _WorkerSlot] = {}
        self._task_leases: set[str] = set()
        self._cdp_leases: set[str] = set()
        self._lock = threading.RLock()

    @property
    def start_method(self) -> str:
        return self._context.get_start_method()

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._slots)

    def start(self, assignment: WorkerAssignment) -> WorkerHandle:
        """Spawn one Process after atomically reserving its leases."""

        if not isinstance(assignment, WorkerAssignment):
            raise TypeError("assignment must be a WorkerAssignment")

        with self._lock:
            self._reserve(assignment)
            process: BaseProcess | None = None
            try:
                process = self._context.Process(
                    target=self._entrypoint,
                    args=(assignment,),
                    daemon=False,
                    name=f"everweb-worker-{assignment.execution_id}",
                )
                process.start()
                if process.pid is None:
                    raise WorkerStartError("spawned Worker has no pid")
                handle = WorkerHandle(
                    execution_id=assignment.execution_id,
                    task_id=assignment.task_identity.task_id,
                    cdp_url=assignment.cdp_url,
                    pid=process.pid,
                )
                self._slots[assignment.execution_id] = _WorkerSlot(
                    assignment=assignment,
                    process=process,
                )
                return handle
            except Exception as exc:
                self._slots.pop(assignment.execution_id, None)
                if process is not None and process.pid is not None:
                    if not self._terminate_and_join(process):
                        self._slots[assignment.execution_id] = _WorkerSlot(
                            assignment=assignment,
                            process=process,
                        )
                        raise WorkerStartError(
                            "failed Worker could not be stopped safely"
                        ) from exc
                    self._release_assignment(assignment)
                    process.close()
                else:
                    self._release_assignment(assignment)
                if isinstance(exc, WorkerStartError):
                    raise
                raise WorkerStartError("failed to spawn Worker process") from exc

    def reap(
        self,
        execution_id: str,
        *,
        timeout_s: float | None = None,
    ) -> WorkerExitReceipt | None:
        """Join one Worker and release leases only after confirmed exit."""

        self._validate_timeout(timeout_s)
        with self._lock:
            slot = self._slots.get(execution_id)
            if slot is None:
                raise WorkerNotFoundError(
                    f"no active Worker for execution {execution_id!r}"
                )

            slot.process.join(timeout=timeout_s)
            if slot.process.is_alive():
                return None
            return self._finalize_slot(execution_id, slot)

    def shutdown(self) -> tuple[WorkerExitReceipt, ...]:
        """Terminate, join, and reap every owned Worker."""

        with self._lock:
            slots = tuple(self._slots.items())
            receipts: list[WorkerExitReceipt] = []
            unresponsive: list[str] = []
            for execution_id, slot in slots:
                if self._terminate_and_join(slot.process):
                    receipts.append(self._finalize_slot(execution_id, slot))
                else:
                    unresponsive.append(execution_id)
            if unresponsive:
                joined = ", ".join(sorted(unresponsive))
                raise WorkerLifecycleError(
                    f"Workers could not be stopped: {joined}"
                )
            return tuple(receipts)

    def _reserve(self, assignment: WorkerAssignment) -> None:
        execution_id = assignment.execution_id
        task_id = assignment.task_identity.task_id
        cdp_url = assignment.cdp_url
        if execution_id in self._slots:
            raise WorkerLeaseConflictError(
                f"execution {execution_id!r} already has an active Worker"
            )
        if task_id in self._task_leases:
            raise WorkerLeaseConflictError(
                f"task {task_id!r} already has an active Worker"
            )
        if cdp_url in self._cdp_leases:
            raise WorkerLeaseConflictError(
                f"CDP URL {cdp_url!r} already has an active Worker"
            )

        self._task_leases.add(task_id)
        self._cdp_leases.add(cdp_url)

    def _finalize_slot(
        self,
        execution_id: str,
        slot: _WorkerSlot,
    ) -> WorkerExitReceipt:
        pid = slot.process.pid
        exit_code = slot.process.exitcode
        if pid is None or exit_code is None:
            raise WorkerLifecycleError(
                "Worker must have pid and exit code before reaping"
            )

        receipt = WorkerExitReceipt(
            execution_id=execution_id,
            task_id=slot.assignment.task_identity.task_id,
            pid=pid,
            exit_code=exit_code,
        )
        self._slots.pop(execution_id)
        self._release_assignment(slot.assignment)
        slot.process.close()
        return receipt

    def _release_assignment(self, assignment: WorkerAssignment) -> None:
        self._task_leases.discard(assignment.task_identity.task_id)
        self._cdp_leases.discard(assignment.cdp_url)

    @staticmethod
    def _terminate_and_join(process: BaseProcess) -> bool:
        if not process.is_alive():
            process.join()
            return True

        try:
            process.terminate()
        except OSError:
            pass
        process.join(timeout=TERMINATE_GRACE_S)
        if process.is_alive():
            try:
                process.kill()
            except OSError:
                pass
            process.join(timeout=TERMINATE_GRACE_S)
        return not process.is_alive()

    @staticmethod
    def _validate_timeout(timeout_s: float | None) -> None:
        if timeout_s is None:
            return
        if (
            type(timeout_s) is not float
            or not math.isfinite(timeout_s)
            or timeout_s < 0.0
        ):
            raise ValueError("timeout_s must be a finite non-negative float")

    def __enter__(self) -> SpawnWorkerPool:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.shutdown()
