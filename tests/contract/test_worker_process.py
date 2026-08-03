"""Contract tests for spawn-only Worker process ownership."""

from __future__ import annotations

import os
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from everweb.domain import Receipt, TaskIdentity
from everweb.supervisor import (
    HeartbeatStatus,
    SpawnWorkerPool,
    WorkerAssignment,
    WorkerExitReceipt,
    WorkerHandle,
    WorkerHeartbeat,
    WorkerLeaseConflictError,
    WorkerNotFoundError,
    WorkerStartError,
)

EXPECTED_ASSIGNMENT_FIELDS = {
    "execution_id",
    "task_identity",
    "cdp_url",
}
EXPECTED_HANDLE_FIELDS = {
    "execution_id",
    "task_id",
    "cdp_url",
    "pid",
}
EXPECTED_EXIT_RECEIPT_FIELDS = {
    "execution_id",
    "task_id",
    "pid",
    "exit_code",
}


def slow_worker(assignment: WorkerAssignment) -> None:
    time.sleep(5.0)


def failing_worker(assignment: WorkerAssignment) -> None:
    raise RuntimeError(f"injected failure for {assignment.execution_id}")


def sigterm_ignoring_worker(assignment: WorkerAssignment) -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(assignment.cdp_url).write_text("ready", encoding="utf-8")
    while True:
        time.sleep(1.0)


class FailOnceEntrypoint:
    def __init__(self) -> None:
        self.pickling_attempts = 0

    def __call__(self, assignment: WorkerAssignment) -> None:
        return None

    def __reduce__(
        self,
    ) -> tuple[type[FailOnceEntrypoint], tuple[()]]:
        self.pickling_attempts += 1
        if self.pickling_attempts == 1:
            raise TypeError("injected first spawn failure")
        return FailOnceEntrypoint, ()


class MutableClock:
    def __init__(self) -> None:
        self.monotonic_value = 100.0

    def now(self) -> datetime:
        return datetime(2026, 8, 3, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.monotonic_value


def assignment(
    *,
    execution_id: str = "execution-001",
    task_id: str = "task-001",
    cdp_url: str = "ws://browser-001",
) -> WorkerAssignment:
    return WorkerAssignment(
        execution_id=execution_id,
        task_identity=TaskIdentity(task_id=task_id),
        cdp_url=cdp_url,
    )


def reap_required(
    pool: SpawnWorkerPool,
    execution_id: str,
) -> WorkerExitReceipt:
    receipt = pool.reap(execution_id, timeout_s=10.0)
    assert receipt is not None
    return receipt


def test_pool_always_uses_spawn_context() -> None:
    pool = SpawnWorkerPool()

    assert pool.start_method == "spawn"
    assert pool.active_count == 0


def test_default_worker_starts_exits_and_is_reaped() -> None:
    value = assignment()
    with SpawnWorkerPool() as pool:
        handle = pool.start(value)
        receipt = reap_required(pool, value.execution_id)

        assert handle.execution_id == value.execution_id
        assert handle.task_id == value.task_identity.task_id
        assert handle.cdp_url == value.cdp_url
        assert handle.pid > 0
        assert receipt == WorkerExitReceipt(
            execution_id=value.execution_id,
            task_id=value.task_identity.task_id,
            pid=handle.pid,
            exit_code=0,
        )
        assert pool.active_count == 0


def test_real_queue_heartbeat_is_validated_and_retained_after_exit() -> None:
    value = assignment()
    clock = MutableClock()
    pool = SpawnWorkerPool(entrypoint=slow_worker, clock=clock)
    handle = pool.start(value)
    deadline = time.monotonic() + 5.0
    received: tuple[WorkerHeartbeat, ...] = ()

    try:
        while not received and time.monotonic() < deadline:
            received = pool.drain_heartbeats(value.execution_id)
            if not received:
                time.sleep(0.01)

        assert received
        latest = pool.latest_heartbeat(value.execution_id)
        assert latest is not None
        assert latest.execution_id == value.execution_id
        assert latest.pid == handle.pid
        assert (
            pool.heartbeat_status(value.execution_id)
            is HeartbeatStatus.ALIVE
        )

        clock.monotonic_value += 6.001
        assert (
            pool.heartbeat_status(value.execution_id)
            is HeartbeatStatus.EXPIRED
        )
    finally:
        pool.shutdown()

    assert pool.latest_heartbeat(value.execution_id) is not None
    assert (
        pool.heartbeat_status(value.execution_id)
        is HeartbeatStatus.EXITED
    )


@pytest.mark.parametrize(
    ("second", "message"),
    [
        (
            assignment(
                task_id="task-002",
                cdp_url="ws://browser-002",
            ),
            "execution",
        ),
        (
            assignment(
                execution_id="execution-002",
                cdp_url="ws://browser-002",
            ),
            "task",
        ),
        (
            assignment(
                execution_id="execution-002",
                task_id="task-002",
            ),
            "CDP URL",
        ),
    ],
)
def test_active_leases_reject_duplicate_assignment_before_spawn(
    second: WorkerAssignment,
    message: str,
) -> None:
    with SpawnWorkerPool() as pool:
        pool.start(assignment())

        with pytest.raises(WorkerLeaseConflictError, match=message):
            pool.start(second)

        assert pool.active_count == 1


def test_reap_timeout_preserves_leases_until_worker_exits() -> None:
    value = assignment()
    with SpawnWorkerPool(entrypoint=slow_worker) as pool:
        pool.start(value)

        assert pool.reap(value.execution_id, timeout_s=0.0) is None
        with pytest.raises(WorkerLeaseConflictError, match="CDP URL"):
            pool.start(
                assignment(
                    execution_id="execution-002",
                    task_id="task-002",
                )
            )
        assert pool.active_count == 1


def test_reaped_assignment_can_be_started_again() -> None:
    value = assignment()
    with SpawnWorkerPool() as pool:
        first = pool.start(value)
        first_receipt = reap_required(pool, value.execution_id)
        second = pool.start(value)
        second_receipt = reap_required(pool, value.execution_id)

    assert first_receipt.exit_code == 0
    assert second_receipt.exit_code == 0
    assert first.task_id == second.task_id


def test_injected_entrypoint_nonzero_exit_is_receipted() -> None:
    value = assignment()
    with SpawnWorkerPool(entrypoint=failing_worker) as pool:
        handle = pool.start(value)
        receipt = reap_required(pool, value.execution_id)

    assert receipt.pid == handle.pid
    assert receipt.exit_code != 0


def test_shutdown_terminates_and_reaps_all_workers() -> None:
    pool = SpawnWorkerPool(entrypoint=slow_worker)
    first = pool.start(assignment())
    second = pool.start(
        assignment(
            execution_id="execution-002",
            task_id="task-002",
            cdp_url="ws://browser-002",
        )
    )

    receipts = pool.shutdown()

    assert {receipt.pid for receipt in receipts} == {first.pid, second.pid}
    assert all(receipt.exit_code != 0 for receipt in receipts)
    assert pool.active_count == 0


@pytest.mark.skipif(os.name == "nt", reason="SIGTERM escalation is POSIX-only")
def test_shutdown_escalates_when_worker_ignores_sigterm(
    tmp_path: Path,
) -> None:
    ready_path = tmp_path / "worker-ready"
    pool = SpawnWorkerPool(entrypoint=sigterm_ignoring_worker)
    pool.start(assignment(cdp_url=str(ready_path)))
    readiness_deadline = time.monotonic() + 5.0

    try:
        while not ready_path.exists() and time.monotonic() < readiness_deadline:
            time.sleep(0.01)
        assert ready_path.exists()
        shutdown_started = time.monotonic()
        receipts = pool.shutdown()
    finally:
        if pool.active_count:
            pool.shutdown()

    assert time.monotonic() - shutdown_started < 4.0
    assert len(receipts) == 1
    assert receipts[0].exit_code != 0


def test_context_manager_shutdown_cleans_live_worker() -> None:
    pool = SpawnWorkerPool(entrypoint=slow_worker)
    with pool:
        pool.start(assignment())
        assert pool.active_count == 1

    assert pool.active_count == 0


def test_spawn_failure_rolls_back_active_slot() -> None:
    pool = SpawnWorkerPool(entrypoint=FailOnceEntrypoint())
    value = assignment()

    with pytest.raises(WorkerStartError):
        pool.start(value)

    assert pool.active_count == 0
    handle = pool.start(value)
    receipt = reap_required(pool, value.execution_id)
    assert receipt.pid == handle.pid
    assert receipt.exit_code == 0


def test_unstoppable_start_failure_keeps_heartbeat_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = SpawnWorkerPool(entrypoint=slow_worker)
    value = assignment()
    real_register = pool._heartbeat_monitor.register
    real_terminate = SpawnWorkerPool.__dict__["_terminate_and_join"]

    def register_then_fail(execution_id: str, pid: int) -> None:
        real_register(execution_id, pid)
        raise RuntimeError("injected post-register failure")

    monkeypatch.setattr(pool._heartbeat_monitor, "register", register_then_fail)
    monkeypatch.setattr(
        SpawnWorkerPool,
        "_terminate_and_join",
        staticmethod(lambda process: False),
    )

    with pytest.raises(WorkerStartError, match="could not be stopped safely"):
        pool.start(value)

    assert pool.active_count == 1
    assert (
        pool.heartbeat_status(value.execution_id) is HeartbeatStatus.ALIVE
    )

    monkeypatch.setattr(SpawnWorkerPool, "_terminate_and_join", real_terminate)
    pool.shutdown()
    assert pool.active_count == 0


def test_reap_rejects_unknown_worker_and_invalid_timeout() -> None:
    pool = SpawnWorkerPool()

    with pytest.raises(WorkerNotFoundError):
        pool.reap("missing", timeout_s=0.0)
    with pytest.raises(ValueError):
        pool.reap("missing", timeout_s=0)
    with pytest.raises(ValueError):
        pool.reap("missing", timeout_s=float("nan"))


def test_worker_value_contracts_are_strict_frozen_and_round_trip() -> None:
    assigned = assignment()
    handle = WorkerHandle(
        execution_id=assigned.execution_id,
        task_id=assigned.task_identity.task_id,
        cdp_url=assigned.cdp_url,
        pid=123,
    )
    receipt = WorkerExitReceipt(
        execution_id=assigned.execution_id,
        task_id=assigned.task_identity.task_id,
        pid=123,
        exit_code=0,
    )

    assert set(WorkerAssignment.model_fields) == EXPECTED_ASSIGNMENT_FIELDS
    assert set(WorkerHandle.model_fields) == EXPECTED_HANDLE_FIELDS
    assert set(WorkerExitReceipt.model_fields) == EXPECTED_EXIT_RECEIPT_FIELDS
    assert issubclass(WorkerExitReceipt, Receipt)
    assert (
        WorkerAssignment.model_validate_json(assigned.model_dump_json())
        == assigned
    )
    assert WorkerHandle.model_validate_json(handle.model_dump_json()) == handle
    assert (
        WorkerExitReceipt.model_validate_json(receipt.model_dump_json())
        == receipt
    )

    with pytest.raises(ValidationError):
        setattr(assigned, "cdp_url", "ws://other")
    with pytest.raises(ValidationError):
        WorkerAssignment.model_validate(
            {
                **assigned.model_dump(),
                "heartbeat_interval_s": 3,
            }
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("execution_id", ""),
        ("execution_id", 1),
        ("task_identity", "task-001"),
        ("cdp_url", " "),
    ],
)
def test_assignment_rejects_invalid_or_coerced_values(
    field_name: str,
    value: Any,
) -> None:
    values: dict[str, Any] = {
        "execution_id": "execution-001",
        "task_identity": TaskIdentity(task_id="task-001"),
        "cdp_url": "ws://browser-001",
        field_name: value,
    }

    with pytest.raises(ValidationError):
        WorkerAssignment.model_validate(values)


def test_pool_exposes_only_approved_lifecycle_methods() -> None:
    public_methods = {
        name
        for name, value in vars(SpawnWorkerPool).items()
        if not name.startswith("_") and callable(value)
    }

    assert public_methods == {
        "drain_heartbeats",
        "heartbeat_status",
        "latest_heartbeat",
        "reap",
        "shutdown",
        "start",
    }
