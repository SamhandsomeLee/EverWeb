"""Minimal in-process runtime loop for Fake / no-key Week 0 runs."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from everweb.core.budget import Budget
from everweb.domain import (
    Deadline,
    InternalRunManifest,
    InternalTerminalState,
    ModelRequest,
    ObservationRequest,
    OfficialOutputDraft,
    Receipt,
    RuntimePhase,
    Task,
    TaskIdentity,
)
from everweb.ports import BrowserPort, ClockPort, ModelPort
from everweb.report import (
    SerializeRequest,
    TraceDurability,
    TraceWriter,
    serialize,
)

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]

INTERNAL_SCHEMA_VERSION = "internal-v0"
PHASE_EVENT_TYPE = "runtime.phase"
BUDGET_EVENT_TYPE = "runtime.budget"
DEFAULT_MAX_EVENT_BYTES = 65_536

EMIT_DIRECTORY = "emit"
DRAFT_FILENAME = "official_output_draft.json"
RECEIPT_FILENAME = "output_receipt.json"
MANIFEST_FILENAME = "run_manifest.json"
RUN_SUMMARY_FILENAME = "run.json"

MINIMAL_PHASES: tuple[RuntimePhase, ...] = (
    RuntimePhase.ANALYZE,
    RuntimePhase.NAVIGATE,
    RuntimePhase.PREPARE_FINAL_STATE,
    RuntimePhase.TERMINAL_DECISION,
    RuntimePhase.SERIALIZE,
    RuntimePhase.EMIT,
)


class MinimalRuntimeError(RuntimeError):
    """Base error for minimal runtime failures."""


class MinimalRuntimeValidationError(MinimalRuntimeError):
    """Minimal runtime inputs or configuration violate the contract."""


class MinimalEmitReceipt(Receipt):
    """Immutable fact produced after happy-path internal emit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_id: NonEmptyString
    draft_relative_path: NonEmptyString
    receipt_relative_path: NonEmptyString
    draft_sha256: Annotated[str, StringConstraints(min_length=64, max_length=64)]
    draft_byte_size: Annotated[int, Field(ge=0)]
    success: bool


class MinimalRunSummary(BaseModel):
    """Persisted run.json summary for one minimal Fake run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_id: NonEmptyString
    task_id: NonEmptyString
    phases: tuple[RuntimePhase, ...]
    browser_capabilities_called: bool
    model_capabilities_called: bool
    model_complete_called: bool
    internal_terminal_state: InternalTerminalState
    draft_relative_path: NonEmptyString
    mapped_status: str | None


@dataclass(frozen=True, slots=True)
class MinimalRunResult:
    """In-memory result of one completed minimal run."""

    execution_id: str
    manifest: InternalRunManifest
    draft: OfficialOutputDraft
    summary: MinimalRunSummary
    emit_receipt: MinimalEmitReceipt
    run_directory: Path


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _validate_execution_id(execution_id: str) -> None:
    posix_value = PurePosixPath(execution_id)
    windows_value = PureWindowsPath(execution_id)
    has_windows_invalid_character = any(
        character in '<>:"/\\|?*' or ord(character) < 32 for character in execution_id
    )
    invalid = (
        not execution_id
        or "\x00" in execution_id
        or has_windows_invalid_character
        or execution_id.endswith((".", " "))
        or posix_value.is_absolute()
        or windows_value.is_absolute()
        or bool(windows_value.drive)
        or len(posix_value.parts) != 1
        or len(windows_value.parts) != 1
        or windows_value.is_reserved()
        or execution_id in {".", ".."}
    )
    if invalid:
        raise MinimalRuntimeValidationError(
            "execution_id must be one portable path segment"
        )


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write_bytes(target: Path, payload: bytes) -> None:
    directory = target.parent
    directory.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, target)
        temporary_name = None
        _fsync_directory(directory)
    except OSError as exc:
        raise MinimalRuntimeError(f"failed to persist {target.name}") from exc
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


class MinimalRuntime:
    """Drive a fixed short phase path with injected ports and report writers."""

    def __init__(
        self,
        *,
        browser: BrowserPort,
        model: ModelPort,
        clock: ClockPort,
        run_root: Path,
        budget: Budget | None = None,
        max_event_bytes: int = DEFAULT_MAX_EVENT_BYTES,
        schema_version: str = INTERNAL_SCHEMA_VERSION,
    ) -> None:
        if not isinstance(run_root, Path):
            raise TypeError("run_root must be a Path")
        if not run_root.exists():
            raise MinimalRuntimeValidationError("run_root must exist")
        if not run_root.is_dir() or _is_link_or_junction(run_root):
            raise MinimalRuntimeValidationError("run_root must be a real directory")
        if max_event_bytes <= 0:
            raise MinimalRuntimeValidationError("max_event_bytes must be positive")
        if not schema_version:
            raise MinimalRuntimeValidationError("schema_version must be non-empty")
        if budget is not None and not isinstance(budget, Budget):
            raise TypeError("budget must be a Budget or None")

        self._browser = browser
        self._model = model
        self._clock = clock
        self._run_root = run_root.resolve(strict=True)
        self._budget = budget
        self._max_event_bytes = max_event_bytes
        self._schema_version = schema_version

    @property
    def run_root(self) -> Path:
        return self._run_root

    def run(
        self,
        *,
        execution_id: str,
        task_identity: TaskIdentity,
    ) -> MinimalRunResult:
        """Execute the minimal Fake-capable phase path for one task."""

        _validate_execution_id(execution_id)
        if not isinstance(task_identity, TaskIdentity):
            raise TypeError("task_identity must be a TaskIdentity")

        started_at = self._now()
        run_directory = self._run_root / execution_id
        run_directory.mkdir(parents=True, exist_ok=True)

        browser_capabilities_called = False
        model_capabilities_called = False
        model_complete_called = False
        recorded_phases: list[RuntimePhase] = []

        with TraceWriter(
            run_root=self._run_root,
            execution_id=execution_id,
            schema_version=self._schema_version,
            max_event_bytes=self._max_event_bytes,
            clock=self._clock,
        ) as trace:
            self._enter_phase(trace, RuntimePhase.ANALYZE, recorded_phases)
            self._browser.capabilities()
            browser_capabilities_called = True
            self._model.capabilities()
            model_capabilities_called = True
            if self._budget is not None:
                assessment = self._budget.assess(
                    official_steps_used=0,
                    model_calls_used=0,
                    elapsed_s=0.0,
                )
                trace.append(
                    BUDGET_EVENT_TYPE,
                    assessment.model_dump(mode="json"),
                    TraceDurability.FSYNC,
                )

            self._enter_phase(trace, RuntimePhase.NAVIGATE, recorded_phases)
            self._browser.create_task_session(Task())
            self._browser.observe(ObservationRequest())
            self._model.complete(ModelRequest(), Deadline())
            model_complete_called = True
            self._browser.close_task_session()

            self._enter_phase(
                trace,
                RuntimePhase.PREPARE_FINAL_STATE,
                recorded_phases,
            )
            self._enter_phase(
                trace,
                RuntimePhase.TERMINAL_DECISION,
                recorded_phases,
            )
            terminal = InternalTerminalState.BEST_EFFORT

            self._enter_phase(trace, RuntimePhase.SERIALIZE, recorded_phases)
            draft = serialize(
                SerializeRequest(
                    task_identity=task_identity,
                    internal_terminal_state=terminal,
                    agent_answer="",
                    urls=(),
                    actions=(),
                    decision_summaries=("minimal_runtime", "best_effort"),
                    artifact_refs=(),
                    capture_ref=None,
                    terminal_screenshot_ref=None,
                )
            )
            if draft.mapped_status is not None:
                raise MinimalRuntimeValidationError(
                    "minimal runtime draft mapped_status must remain None"
                )

            self._enter_phase(trace, RuntimePhase.EMIT, recorded_phases)
            ended_at = self._now()
            phases = tuple(recorded_phases)
            if phases != MINIMAL_PHASES:
                raise MinimalRuntimeValidationError(
                    "minimal runtime recorded unexpected phase sequence"
                )

            manifest = InternalRunManifest(
                schema_version=self._schema_version,
                execution_id=execution_id,
                task_identity=task_identity,
                started_at=started_at,
                ended_at=ended_at,
                internal_terminal_state=terminal,
                phases=phases,
            )
            draft_relative = f"{EMIT_DIRECTORY}/{DRAFT_FILENAME}"
            receipt_relative = f"{EMIT_DIRECTORY}/{RECEIPT_FILENAME}"
            summary = MinimalRunSummary(
                execution_id=execution_id,
                task_id=task_identity.task_id,
                phases=phases,
                browser_capabilities_called=browser_capabilities_called,
                model_capabilities_called=model_capabilities_called,
                model_complete_called=model_complete_called,
                internal_terminal_state=terminal,
                draft_relative_path=draft_relative,
                mapped_status=None,
            )

            draft_bytes = draft.model_dump_json().encode("utf-8")
            draft_sha256 = _sha256_hex(draft_bytes)
            emit_receipt = MinimalEmitReceipt(
                execution_id=execution_id,
                draft_relative_path=draft_relative,
                receipt_relative_path=receipt_relative,
                draft_sha256=draft_sha256,
                draft_byte_size=len(draft_bytes),
                success=True,
            )

            emit_directory = run_directory / EMIT_DIRECTORY
            emit_directory.mkdir(parents=True, exist_ok=True)
            _atomic_write_bytes(run_directory / MANIFEST_FILENAME, manifest.model_dump_json().encode("utf-8"))
            _atomic_write_bytes(
                run_directory / RUN_SUMMARY_FILENAME,
                summary.model_dump_json().encode("utf-8"),
            )
            _atomic_write_bytes(emit_directory / DRAFT_FILENAME, draft_bytes)
            _atomic_write_bytes(
                emit_directory / RECEIPT_FILENAME,
                emit_receipt.model_dump_json().encode("utf-8"),
            )
            self._verify_written_draft(emit_directory / DRAFT_FILENAME, draft)

        return MinimalRunResult(
            execution_id=execution_id,
            manifest=manifest,
            draft=draft,
            summary=summary,
            emit_receipt=emit_receipt,
            run_directory=run_directory,
        )

    def _enter_phase(
        self,
        trace: TraceWriter,
        phase: RuntimePhase,
        recorded_phases: list[RuntimePhase],
    ) -> None:
        recorded_phases.append(phase)
        trace.append(
            PHASE_EVENT_TYPE,
            {"phase": phase.value},
            TraceDurability.FSYNC,
        )

    def _verify_written_draft(
        self,
        path: Path,
        expected: OfficialOutputDraft,
    ) -> None:
        try:
            loaded = OfficialOutputDraft.model_validate_json(path.read_bytes())
        except (OSError, ValidationError) as exc:
            raise MinimalRuntimeError(
                "failed to read back official output draft"
            ) from exc
        if loaded != expected:
            raise MinimalRuntimeError(
                "official output draft read-back does not match"
            )

    def _now(self) -> datetime:
        value = self._clock.now()
        if not isinstance(value, datetime):
            raise MinimalRuntimeValidationError(
                "ClockPort.now() must return a datetime"
            )
        if value.tzinfo is None:
            raise MinimalRuntimeValidationError(
                "ClockPort.now() must return an aware datetime"
            )
        return value
