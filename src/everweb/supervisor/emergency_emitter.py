"""Parent-side EmergencyEmitter from persisted Snapshot/Trace/Evidence."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from everweb.domain import (
    ArtifactRef,
    EmergencySnapshot,
    InternalTerminalState,
    OfficialOutputDraft,
    Receipt,
)
from everweb.ports import ClockPort
from everweb.report import (
    EvidenceCorruptionError,
    EvidenceReadResult,
    SerializeRequest,
    TraceCorruptionError,
    TraceReadResult,
    read_evidence,
    read_trace,
    serialize,
)
from everweb.supervisor.emergency_snapshot import EmergencySnapshotStore

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class StatusMapper(Protocol):
    """Narrow status-mapping surface used during emergency emit.

    Implemented by competition adapters without supervisor importing competition.
    """

    def map_status(self, state: InternalTerminalState) -> str | None: ...

EMIT_DIRECTORY = "emergency_emit"
DRAFT_FILENAME = "official_output_draft.json"
REPORT_FILENAME = "emergency_report.json"
RECEIPT_FILENAME = "output_receipt.json"
TRACE_FILENAME = "trace.jsonl"
EVIDENCE_FILENAME = "evidence.jsonl"


class EmergencyEmitError(RuntimeError):
    """Base error for emergency emit failures."""


class EmergencyEmitValidationError(EmergencyEmitError):
    """Emit inputs or persisted facts violate the contract."""


class EmergencyEmitCorruptionError(EmergencyEmitError):
    """On-disk emergency emit artifacts are incomplete or malformed."""


class EmergencyEmitReceipt(Receipt):
    """Immutable fact produced after a successful emergency emit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_id: NonEmptyString
    task_id: NonEmptyString
    internal_terminal_state: InternalTerminalState
    mapped_status: str | None
    draft_relative_path: NonEmptyString
    report_relative_path: NonEmptyString
    receipt_relative_path: NonEmptyString
    draft_sha256: Annotated[str, StringConstraints(min_length=64, max_length=64)]
    draft_byte_size: Annotated[int, Field(ge=0)]
    emitted_at: datetime
    idempotent: bool


class EmergencyReport(BaseModel):
    """Internal emergency report facts (not an official competition schema)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_id: NonEmptyString
    task_id: NonEmptyString
    forced_internal_terminal_state: InternalTerminalState
    mapped_status: str | None
    snapshot_last_persisted_event_seq: Annotated[int, Field(ge=0)]
    snapshot_internal_terminal_state: InternalTerminalState | None
    best_candidate_ref: ArtifactRef | None
    trace_event_count: Annotated[int, Field(ge=0)]
    evidence_count: Annotated[int, Field(ge=0)]
    trace_recovery_warning_count: Annotated[int, Field(ge=0)]
    evidence_recovery_warning_count: Annotated[int, Field(ge=0)]
    emitted_at: datetime


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
        raise EmergencyEmitValidationError(
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


def _artifact_refs_from_snapshot(snapshot: EmergencySnapshot) -> tuple[ArtifactRef, ...]:
    refs: list[ArtifactRef] = []
    if snapshot.best_candidate_ref is not None:
        refs.append(snapshot.best_candidate_ref)
    if (
        snapshot.last_screenshot_ref is not None
        and snapshot.last_screenshot_ref != snapshot.best_candidate_ref
    ):
        refs.append(snapshot.last_screenshot_ref)
    return tuple(refs)


def _urls_from_snapshot(snapshot: EmergencySnapshot) -> tuple[str, ...]:
    if snapshot.last_url is None:
        return ()
    return (snapshot.last_url,)


class EmergencyEmitter:
    """Assemble and atomically persist internal emergency output on Worker death."""

    def __init__(
        self,
        *,
        snapshot_store: EmergencySnapshotStore,
        run_directory: Path,
        clock: ClockPort,
        status_mapper: StatusMapper,
        max_event_bytes: int,
    ) -> None:
        if not isinstance(snapshot_store, EmergencySnapshotStore):
            raise TypeError("snapshot_store must be an EmergencySnapshotStore")
        if not isinstance(run_directory, Path):
            raise TypeError("run_directory must be a Path")
        if not run_directory.exists():
            raise EmergencyEmitValidationError("run_directory must exist")
        if not run_directory.is_dir() or _is_link_or_junction(run_directory):
            raise EmergencyEmitValidationError(
                "run_directory must be a real directory"
            )
        if max_event_bytes <= 0:
            raise EmergencyEmitValidationError("max_event_bytes must be positive")
        if not hasattr(status_mapper, "map_status"):
            raise TypeError("status_mapper must provide map_status")

        self._snapshot_store = snapshot_store
        self._run_directory = run_directory.resolve(strict=True)
        self._clock = clock
        self._status_mapper = status_mapper
        self._max_event_bytes = max_event_bytes

    @property
    def run_directory(self) -> Path:
        return self._run_directory

    def emit_directory_for(self, execution_id: str) -> Path:
        _validate_execution_id(execution_id)
        return self._run_directory / execution_id / EMIT_DIRECTORY

    def emit(self, execution_id: str) -> EmergencyEmitReceipt:
        """Load persisted facts; serialize WORKER_CRASHED draft; atomic write."""

        _validate_execution_id(execution_id)
        existing = self._load_existing_receipt(execution_id)
        if existing is not None:
            return existing

        snapshot = self._snapshot_store.load(execution_id)
        if snapshot is None:
            raise EmergencyEmitValidationError(
                "emergency snapshot is required for emit"
            )
        if snapshot.execution_id != execution_id:
            raise EmergencyEmitValidationError(
                "snapshot execution_id does not match emit target"
            )

        trace = self._read_trace(execution_id, snapshot)
        evidence = self._read_evidence(execution_id)
        if snapshot.last_persisted_event_seq > len(trace.events):
            raise EmergencyEmitValidationError(
                "snapshot last_persisted_event_seq exceeds recovered trace events"
            )

        forced_terminal = InternalTerminalState.WORKER_CRASHED
        mapped_status = self._status_mapper.map_status(forced_terminal)
        if mapped_status is not None:
            raise EmergencyEmitValidationError(
                "status mapper must not invent official status during "
                "emergency emit"
            )

        draft = serialize(
            SerializeRequest(
                task_identity=snapshot.task_identity,
                internal_terminal_state=forced_terminal,
                agent_answer="",
                urls=_urls_from_snapshot(snapshot),
                actions=(),
                decision_summaries=("emergency_emit", "worker_crashed"),
                artifact_refs=_artifact_refs_from_snapshot(snapshot),
                capture_ref=None,
                terminal_screenshot_ref=snapshot.last_screenshot_ref,
            )
        )
        if draft.mapped_status is not None:
            raise EmergencyEmitValidationError(
                "emergency draft mapped_status must remain None"
            )

        emitted_at = self._now()
        report = EmergencyReport(
            execution_id=execution_id,
            task_id=snapshot.task_identity.task_id,
            forced_internal_terminal_state=forced_terminal,
            mapped_status=mapped_status,
            snapshot_last_persisted_event_seq=snapshot.last_persisted_event_seq,
            snapshot_internal_terminal_state=snapshot.internal_terminal_state,
            best_candidate_ref=snapshot.best_candidate_ref,
            trace_event_count=len(trace.events),
            evidence_count=len(evidence.evidence),
            trace_recovery_warning_count=len(trace.recovery_warnings),
            evidence_recovery_warning_count=len(evidence.recovery_warnings),
            emitted_at=emitted_at,
        )

        draft_bytes = draft.model_dump_json().encode("utf-8")
        report_bytes = report.model_dump_json().encode("utf-8")
        draft_sha256 = _sha256_hex(draft_bytes)
        receipt = EmergencyEmitReceipt(
            execution_id=execution_id,
            task_id=snapshot.task_identity.task_id,
            internal_terminal_state=forced_terminal,
            mapped_status=mapped_status,
            draft_relative_path=f"{EMIT_DIRECTORY}/{DRAFT_FILENAME}",
            report_relative_path=f"{EMIT_DIRECTORY}/{REPORT_FILENAME}",
            receipt_relative_path=f"{EMIT_DIRECTORY}/{RECEIPT_FILENAME}",
            draft_sha256=draft_sha256,
            draft_byte_size=len(draft_bytes),
            emitted_at=emitted_at,
            idempotent=False,
        )
        receipt_bytes = receipt.model_dump_json().encode("utf-8")

        emit_directory = self.emit_directory_for(execution_id)
        emit_directory.mkdir(parents=True, exist_ok=True)
        self._validate_emit_directory(emit_directory, execution_id)

        self._atomic_write_bytes(emit_directory / DRAFT_FILENAME, draft_bytes)
        self._atomic_write_bytes(emit_directory / REPORT_FILENAME, report_bytes)
        self._atomic_write_bytes(emit_directory / RECEIPT_FILENAME, receipt_bytes)

        self._verify_written_draft(emit_directory / DRAFT_FILENAME, draft)
        return receipt

    def _load_existing_receipt(self, execution_id: str) -> EmergencyEmitReceipt | None:
        receipt_path = self.emit_directory_for(execution_id) / RECEIPT_FILENAME
        if not receipt_path.exists():
            return None
        if not receipt_path.is_file() or _is_link_or_junction(receipt_path):
            raise EmergencyEmitCorruptionError(
                "emergency emit receipt path is not a regular file"
            )
        try:
            raw = receipt_path.read_bytes()
            receipt = EmergencyEmitReceipt.model_validate_json(raw)
        except (OSError, ValidationError) as exc:
            raise EmergencyEmitCorruptionError(
                "emergency emit receipt is malformed"
            ) from exc
        if receipt.execution_id != execution_id:
            raise EmergencyEmitCorruptionError(
                "emergency emit receipt execution_id mismatch"
            )
        draft_path = self.emit_directory_for(execution_id) / DRAFT_FILENAME
        if not draft_path.is_file():
            raise EmergencyEmitCorruptionError(
                "emergency emit receipt exists without draft"
            )
        try:
            draft_bytes = draft_path.read_bytes()
            OfficialOutputDraft.model_validate_json(draft_bytes)
        except (OSError, ValidationError) as exc:
            raise EmergencyEmitCorruptionError(
                "emergency emit draft is malformed"
            ) from exc
        if _sha256_hex(draft_bytes) != receipt.draft_sha256:
            raise EmergencyEmitCorruptionError(
                "emergency emit draft digest does not match receipt"
            )
        return receipt.model_copy(update={"idempotent": True})

    def _read_trace(
        self,
        execution_id: str,
        snapshot: EmergencySnapshot,
    ) -> TraceReadResult:
        path = self._run_directory / execution_id / TRACE_FILENAME
        if not path.exists():
            if snapshot.last_persisted_event_seq == 0:
                return TraceReadResult(events=(), recovery_warnings=())
            raise EmergencyEmitValidationError(
                "trace.jsonl is required when snapshot records persisted events"
            )
        try:
            return read_trace(path, max_event_bytes=self._max_event_bytes)
        except TraceCorruptionError as exc:
            raise EmergencyEmitCorruptionError(
                "failed to recover trace for emergency emit"
            ) from exc

    def _read_evidence(self, execution_id: str) -> EvidenceReadResult:
        path = self._run_directory / execution_id / EVIDENCE_FILENAME
        if not path.exists():
            return EvidenceReadResult(evidence=(), recovery_warnings=())
        try:
            return read_evidence(
                path,
                execution_id=execution_id,
                max_event_bytes=self._max_event_bytes,
            )
        except EvidenceCorruptionError as exc:
            raise EmergencyEmitCorruptionError(
                "failed to recover evidence for emergency emit"
            ) from exc

    def _atomic_write_bytes(self, target: Path, payload: bytes) -> None:
        directory = target.parent
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
            raise EmergencyEmitError(
                f"failed to persist {target.name}"
            ) from exc
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

    def _verify_written_draft(
        self,
        path: Path,
        expected: OfficialOutputDraft,
    ) -> None:
        try:
            raw = path.read_bytes()
            loaded = OfficialOutputDraft.model_validate_json(raw)
        except (OSError, ValidationError) as exc:
            raise EmergencyEmitCorruptionError(
                "failed to read back emergency draft"
            ) from exc
        if loaded != expected:
            raise EmergencyEmitCorruptionError(
                "emergency draft read-back does not match written draft"
            )
        if loaded.mapped_status is not None:
            raise EmergencyEmitCorruptionError(
                "emergency draft read-back invented mapped_status"
            )

    def _validate_emit_directory(self, emit_directory: Path, execution_id: str) -> None:
        if _is_link_or_junction(emit_directory):
            raise EmergencyEmitValidationError(
                "emergency_emit directory must not be a link or junction"
            )
        resolved = emit_directory.resolve(strict=True)
        expected_root = (self._run_directory / execution_id).resolve(strict=True)
        if not resolved.is_relative_to(expected_root):
            raise EmergencyEmitValidationError(
                "emergency_emit directory escapes execution directory"
            )

    def _now(self) -> datetime:
        value = self._clock.now()
        if not isinstance(value, datetime):
            raise EmergencyEmitValidationError(
                "ClockPort.now() must return a datetime"
            )
        if value.tzinfo is None:
            raise EmergencyEmitValidationError(
                "ClockPort.now() must return an aware datetime"
            )
        return value
