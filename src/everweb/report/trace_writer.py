"""Crash-conscious append-only JSONL trace persistence."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO, Literal

from pydantic import ValidationError

from everweb.domain import TraceEnvelope
from everweb.ports import ClockPort


class TraceError(Exception):
    """Base error for trace persistence failures."""


class TraceSerializationError(TraceError):
    """A trace event cannot be represented as canonical JSON."""


class TraceEventTooLargeError(TraceError):
    """A canonical trace line exceeds the configured byte limit."""


class TraceWriterClosedError(TraceError):
    """A write was attempted after the writer was closed."""


class TraceCorruptionError(TraceError):
    """A complete trace record is malformed, reordered, or altered."""


class TraceDurability(StrEnum):
    """Durability requested for one appended event."""

    BUFFERED = "buffered"
    FLUSH = "flush"
    FSYNC = "fsync"


@dataclass(frozen=True, slots=True)
class TraceRecoveryWarning:
    """Recoverable damage found only in an incomplete final record."""

    code: Literal["truncated_tail"]
    line_number: int
    discarded_bytes: int


@dataclass(frozen=True, slots=True)
class TraceReadResult:
    """Validated trace events and non-fatal tail recovery warnings."""

    events: tuple[TraceEnvelope, ...]
    recovery_warnings: tuple[TraceRecoveryWarning, ...]


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TraceSerializationError("trace event is not canonical JSON") from exc


def _normalize_json_value(
    value: Any,
    *,
    seen: set[int] | None = None,
) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TraceSerializationError("trace JSON numbers must be finite")
        return value

    active = set() if seen is None else seen
    if isinstance(value, list):
        identity = id(value)
        if identity in active:
            raise TraceSerializationError("trace JSON must not contain cycles")
        active.add(identity)
        try:
            return [_normalize_json_value(item, seen=active) for item in value]
        finally:
            active.remove(identity)

    if isinstance(value, dict):
        identity = id(value)
        if identity in active:
            raise TraceSerializationError("trace JSON must not contain cycles")
        active.add(identity)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TraceSerializationError(
                        "trace JSON object keys must be strings"
                    )
                normalized[key] = _normalize_json_value(item, seen=active)
            return normalized
        finally:
            active.remove(identity)

    raise TraceSerializationError(
        f"trace JSON value has unsupported type {type(value).__name__}"
    )


def _envelope_value(
    envelope: TraceEnvelope,
    *,
    include_checksum: bool,
) -> dict[str, Any]:
    try:
        excluded = None if include_checksum else {"checksum"}
        value = envelope.model_dump(mode="json", exclude=excluded)
    except (TypeError, ValueError) as exc:
        raise TraceSerializationError("trace event is not JSON serializable") from exc
    return value


def compute_trace_checksum(envelope: TraceEnvelope) -> str:
    """Compute SHA-256 over canonical envelope fields excluding checksum."""

    _normalize_json_value(envelope.payload)
    canonical = _canonical_json_bytes(
        _envelope_value(envelope, include_checksum=False)
    )
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def encode_trace_line(envelope: TraceEnvelope) -> bytes:
    """Encode one deterministic UTF-8 JSONL record."""

    return (
        _canonical_json_bytes(_envelope_value(envelope, include_checksum=True))
        + b"\n"
    )


def read_trace(path: Path, *, max_event_bytes: int) -> TraceReadResult:
    """Read a valid trace prefix and ignore only an incomplete final line."""

    if max_event_bytes <= 0:
        raise ValueError("max_event_bytes must be positive")

    warnings: list[TraceRecoveryWarning] = []
    events: list[TraceEnvelope] = []
    with path.open("rb") as trace_file:
        line_number = 0
        while chunk := trace_file.readline(max_event_bytes + 1):
            line_number += 1
            if len(chunk) > max_event_bytes:
                raise TraceCorruptionError(
                    f"trace record exceeds {max_event_bytes} bytes "
                    f"at line {line_number}"
                )
            if not chunk.endswith(b"\n"):
                warnings.append(
                    TraceRecoveryWarning(
                        code="truncated_tail",
                        line_number=line_number,
                        discarded_bytes=len(chunk),
                    )
                )
                break

            try:
                envelope = TraceEnvelope.model_validate_json(chunk)
            except ValidationError as exc:
                raise TraceCorruptionError(
                    f"invalid complete trace record at line {line_number}"
                ) from exc

            if envelope.seq != line_number:
                raise TraceCorruptionError(
                    f"expected seq {line_number}, found {envelope.seq}"
                )

            try:
                expected_checksum = compute_trace_checksum(envelope)
            except TraceSerializationError as exc:
                raise TraceCorruptionError(
                    f"non-canonical payload at line {line_number}"
                ) from exc
            if not hmac.compare_digest(envelope.checksum, expected_checksum):
                raise TraceCorruptionError(
                    f"checksum mismatch at line {line_number}"
                )
            events.append(envelope)

        if warnings and trace_file.read(1):
            raise TraceCorruptionError(
                f"incomplete non-final trace record at line {line_number}"
            )

    return TraceReadResult(
        events=tuple(events),
        recovery_warnings=tuple(warnings),
    )


class TraceWriter:
    """Own one append-only trace file and assign its event sequence."""

    def __init__(
        self,
        *,
        run_root: Path,
        execution_id: str,
        schema_version: str,
        max_event_bytes: int,
        clock: ClockPort,
    ) -> None:
        posix_id = PurePosixPath(execution_id)
        windows_id = PureWindowsPath(execution_id)
        has_windows_invalid_character = any(
            character in '<>:"/\\|?*' or ord(character) < 32
            for character in execution_id
        )
        invalid_path = (
            not execution_id
            or "\x00" in execution_id
            or has_windows_invalid_character
            or execution_id.endswith((".", " "))
            or posix_id.is_absolute()
            or windows_id.is_absolute()
            or bool(windows_id.drive)
            or len(posix_id.parts) != 1
            or len(windows_id.parts) != 1
            or windows_id.is_reserved()
        )
        if invalid_path:
            raise ValueError("execution_id must be one non-empty path segment")
        if execution_id in {".", ".."}:
            raise ValueError("execution_id must not be a relative path marker")
        if not schema_version:
            raise ValueError("schema_version must be non-empty")
        if max_event_bytes <= 0:
            raise ValueError("max_event_bytes must be positive")

        run_directory = run_root / execution_id
        run_directory.mkdir(parents=True, exist_ok=True)

        self.path = run_directory / "trace.jsonl"
        self._execution_id = execution_id
        self._schema_version = schema_version
        self._max_event_bytes = max_event_bytes
        self._clock = clock
        self._next_seq = 1
        self._file: BinaryIO = self.path.open("xb")
        self._closed = False

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        durability: TraceDurability = TraceDurability.BUFFERED,
    ) -> TraceEnvelope:
        """Append one fully encoded event without rewriting prior bytes."""

        if self._closed:
            raise TraceWriterClosedError("trace writer is closed")
        if not isinstance(durability, TraceDurability):
            raise TypeError("durability must be a TraceDurability")
        normalized_payload = _normalize_json_value(payload)
        if not isinstance(normalized_payload, dict):
            raise TraceSerializationError("trace payload must be a JSON object")

        unsigned = TraceEnvelope(
            seq=self._next_seq,
            schema_version=self._schema_version,
            execution_id=self._execution_id,
            event_type=event_type,
            payload=normalized_payload,
            timestamp=self._clock.now(),
            checksum="",
        )
        envelope = unsigned.model_copy(
            update={"checksum": compute_trace_checksum(unsigned)}
        )
        line = encode_trace_line(envelope)
        if len(line) > self._max_event_bytes:
            raise TraceEventTooLargeError(
                f"trace event is {len(line)} bytes; "
                f"limit is {self._max_event_bytes}"
            )

        self._file.write(line)
        self._next_seq += 1

        if durability is TraceDurability.FLUSH:
            self._file.flush()
        elif durability is TraceDurability.FSYNC:
            self._file.flush()
            os.fsync(self._file.fileno())

        return envelope

    def close(self) -> None:
        """Close the owned file handle."""

        if not self._closed:
            self._file.close()
            self._closed = True

    def __enter__(self) -> TraceWriter:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()
