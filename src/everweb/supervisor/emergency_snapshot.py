"""Atomic EmergencySnapshot checkpoint persistence."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath

from pydantic import ValidationError

from everweb.domain import EmergencySnapshot
from everweb.ports import ClockPort

SNAPSHOT_FILENAME = "emergency_snapshot.json"


class CheckpointReason(StrEnum):
    """Canonical Worker checkpoint moments that may persist a snapshot."""

    ANALYZE_COMPLETE = "analyze_complete"
    SUCCESSFUL_ACTION = "successful_action"
    EVIDENCE_LEDGER_UPDATE = "evidence_ledger_update"
    CANDIDATE_UPDATE = "candidate_update"
    BEFORE_PREPARE_FINAL_STATE = "before_prepare_final_state"
    AFTER_TERMINAL_DECISION = "after_terminal_decision"


class EmergencySnapshotError(RuntimeError):
    """Base error for emergency snapshot persistence failures."""


class EmergencySnapshotValidationError(EmergencySnapshotError):
    """Snapshot path, directory, or input contract is invalid."""


class EmergencySnapshotCorruptionError(EmergencySnapshotError):
    """An on-disk snapshot is incomplete, malformed, or altered."""


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
        raise EmergencySnapshotValidationError(
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


class EmergencySnapshotStore:
    """Persist and load one replaceable emergency snapshot per execution."""

    def __init__(self, run_directory: Path, *, clock: ClockPort) -> None:
        if not isinstance(run_directory, Path):
            raise TypeError("run_directory must be a Path")
        if not run_directory.exists():
            raise EmergencySnapshotValidationError("run_directory must exist")
        if not run_directory.is_dir() or _is_link_or_junction(run_directory):
            raise EmergencySnapshotValidationError(
                "run_directory must be a real directory"
            )
        self._run_directory = run_directory.resolve(strict=True)
        self._clock = clock

    @property
    def run_directory(self) -> Path:
        return self._run_directory

    def path_for(self, execution_id: str) -> Path:
        _validate_execution_id(execution_id)
        execution_directory = self._run_directory / execution_id
        return execution_directory / SNAPSHOT_FILENAME

    def persist(
        self,
        snapshot: EmergencySnapshot,
        *,
        reason: CheckpointReason,
    ) -> EmergencySnapshot:
        if not isinstance(snapshot, EmergencySnapshot):
            raise TypeError("snapshot must be an EmergencySnapshot")
        if not isinstance(reason, CheckpointReason):
            raise TypeError("reason must be a CheckpointReason")

        now = self._now()
        stamped = snapshot.model_copy(update={"updated_at": now})
        target = self.path_for(stamped.execution_id)
        execution_directory = target.parent
        execution_directory.mkdir(parents=True, exist_ok=True)
        self._validate_execution_directory(execution_directory)

        payload = stamped.model_dump_json().encode("utf-8")
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=execution_directory,
                prefix=".emergency_snapshot.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, target)
            temporary_name = None
            _fsync_directory(execution_directory)
        except OSError as exc:
            raise EmergencySnapshotError(
                "failed to persist emergency snapshot"
            ) from exc
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

        return stamped

    def load(self, execution_id: str) -> EmergencySnapshot | None:
        path = self.path_for(execution_id)
        if not path.exists():
            return None
        if not path.is_file() or _is_link_or_junction(path):
            raise EmergencySnapshotCorruptionError(
                "emergency snapshot path is not a regular file"
            )
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise EmergencySnapshotCorruptionError(
                "failed to read emergency snapshot"
            ) from exc
        if not raw:
            raise EmergencySnapshotCorruptionError("emergency snapshot is empty")
        try:
            return EmergencySnapshot.model_validate_json(raw)
        except ValidationError as exc:
            raise EmergencySnapshotCorruptionError(
                "emergency snapshot is malformed"
            ) from exc

    def _validate_execution_directory(self, execution_directory: Path) -> None:
        if _is_link_or_junction(execution_directory):
            raise EmergencySnapshotValidationError(
                "execution directory must not be a link or junction"
            )
        resolved = execution_directory.resolve(strict=True)
        if not resolved.is_relative_to(self._run_directory):
            raise EmergencySnapshotValidationError(
                "execution directory escapes run_directory"
            )

    def _now(self) -> datetime:
        value = self._clock.now()
        if not isinstance(value, datetime):
            raise EmergencySnapshotValidationError(
                "ClockPort.now() must return a datetime"
            )
        if value.tzinfo is None:
            raise EmergencySnapshotValidationError(
                "ClockPort.now() must return an aware datetime"
            )
        return value
