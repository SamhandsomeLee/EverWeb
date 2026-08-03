"""Append-only JSONL persistence for evidence facts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

from pydantic import ValidationError

from everweb.domain import EvidenceAtom
from everweb.domain.sensitive import contains_sensitive_content
from everweb.report._persistence import (
    CanonicalJsonError,
    canonical_json_bytes,
    normalize_json_value,
    validate_single_path_segment,
)
from everweb.report.trace_writer import TraceDurability


class EvidenceError(Exception):
    """Base error for evidence persistence failures."""


class EvidenceSerializationError(EvidenceError):
    """An evidence atom is not strict canonical JSON."""


class EvidenceEventTooLargeError(EvidenceError):
    """An encoded evidence line exceeds the explicit size limit."""


class EvidenceSensitiveContentError(EvidenceError):
    """Evidence contains a secret or provider reasoning marker."""


class EvidenceWriterClosedError(EvidenceError):
    """An append was attempted after the writer was closed."""


class EvidenceConflictError(EvidenceError):
    """Evidence identity conflicts with the append-only ledger."""


class EvidenceCorruptionError(EvidenceError):
    """A complete evidence record is invalid or inconsistent."""


@dataclass(frozen=True, slots=True)
class EvidenceRecoveryWarning:
    """Recoverable damage found only in an incomplete final record."""

    code: Literal["truncated_tail"]
    line_number: int
    discarded_bytes: int


@dataclass(frozen=True, slots=True)
class EvidenceReadResult:
    """Validated evidence records and tail recovery warnings."""

    evidence: tuple[EvidenceAtom, ...]
    recovery_warnings: tuple[EvidenceRecoveryWarning, ...]


def _detached_evidence(atom: EvidenceAtom) -> EvidenceAtom:
    try:
        raw_value = normalize_json_value(atom.raw_value)
        normalized_value = normalize_json_value(atom.normalized_value)
    except CanonicalJsonError as exc:
        raise EvidenceSerializationError(
            "evidence values must be strict JSON"
        ) from exc
    return atom.model_copy(
        update={
            "raw_value": raw_value,
            "normalized_value": normalized_value,
            "parents": list(atom.parents),
        }
    )


def encode_evidence_line(atom: EvidenceAtom) -> bytes:
    """Encode one detached evidence atom as deterministic UTF-8 JSONL."""

    detached = _detached_evidence(atom)
    try:
        value = detached.model_dump(mode="json")
        line = canonical_json_bytes(value) + b"\n"
    except (CanonicalJsonError, TypeError, ValueError) as exc:
        raise EvidenceSerializationError(
            "evidence atom is not JSON serializable"
        ) from exc
    if contains_sensitive_content(line):
        raise EvidenceSensitiveContentError(
            "evidence contains sensitive persisted content"
        )
    return line


def read_evidence(
    path: Path,
    *,
    execution_id: str,
    max_event_bytes: int,
) -> EvidenceReadResult:
    """Read an evidence prefix and ignore only an incomplete final line."""

    validate_single_path_segment(execution_id, field_name="execution_id")
    if max_event_bytes <= 0:
        raise ValueError("max_event_bytes must be positive")

    evidence: list[EvidenceAtom] = []
    warnings: list[EvidenceRecoveryWarning] = []
    evidence_ids: set[str] = set()
    with path.open("rb") as evidence_file:
        line_number = 0
        while chunk := evidence_file.readline(max_event_bytes + 1):
            line_number += 1
            if len(chunk) > max_event_bytes:
                raise EvidenceCorruptionError(
                    f"evidence record exceeds {max_event_bytes} bytes "
                    f"at line {line_number}"
                )
            if not chunk.endswith(b"\n"):
                warnings.append(
                    EvidenceRecoveryWarning(
                        code="truncated_tail",
                        line_number=line_number,
                        discarded_bytes=len(chunk),
                    )
                )
                break
            if contains_sensitive_content(chunk):
                raise EvidenceCorruptionError(
                    f"sensitive evidence record at line {line_number}"
                )

            try:
                atom = EvidenceAtom.model_validate_json(chunk)
                atom = _detached_evidence(atom)
            except (ValidationError, EvidenceSerializationError) as exc:
                raise EvidenceCorruptionError(
                    f"invalid complete evidence record at line {line_number}"
                ) from exc

            if atom.execution_id != execution_id:
                raise EvidenceCorruptionError(
                    f"execution_id mismatch at line {line_number}"
                )
            if atom.evidence_id in evidence_ids:
                raise EvidenceCorruptionError(
                    f"duplicate evidence_id at line {line_number}"
                )
            evidence_ids.add(atom.evidence_id)
            evidence.append(atom)

        if warnings and evidence_file.read(1):
            raise EvidenceCorruptionError(
                f"incomplete non-final evidence record at line {line_number}"
            )

    return EvidenceReadResult(
        evidence=tuple(evidence),
        recovery_warnings=tuple(warnings),
    )


class EvidenceWriter:
    """Own one append-only evidence ledger for a task execution."""

    def __init__(
        self,
        *,
        run_root: Path,
        execution_id: str,
        max_event_bytes: int,
    ) -> None:
        validate_single_path_segment(execution_id, field_name="execution_id")
        if max_event_bytes <= 0:
            raise ValueError("max_event_bytes must be positive")

        run_directory = run_root / execution_id
        run_directory.mkdir(parents=True, exist_ok=True)
        resolved_root = run_root.resolve(strict=True)
        resolved_run_directory = run_directory.resolve(strict=True)
        if (
            run_directory.is_symlink()
            or run_directory.is_junction()
            or not resolved_run_directory.is_relative_to(resolved_root)
        ):
            raise ValueError("execution directory escapes run_root")
        self.path = run_directory / "evidence.jsonl"
        self._execution_id = execution_id
        self._max_event_bytes = max_event_bytes
        self._evidence_ids: set[str] = set()
        self._file: BinaryIO = self.path.open("xb")
        self._closed = False

    def append(
        self,
        atom: EvidenceAtom,
        durability: TraceDurability = TraceDurability.BUFFERED,
    ) -> EvidenceAtom:
        """Append one immutable evidence fact."""

        if self._closed:
            raise EvidenceWriterClosedError("evidence writer is closed")
        if not isinstance(durability, TraceDurability):
            raise TypeError("durability must be a TraceDurability")
        if atom.execution_id != self._execution_id:
            raise EvidenceConflictError("evidence execution_id does not match writer")
        if atom.evidence_id in self._evidence_ids:
            raise EvidenceConflictError("evidence_id already exists")

        detached = _detached_evidence(atom)
        line = encode_evidence_line(detached)
        if len(line) > self._max_event_bytes:
            raise EvidenceEventTooLargeError(
                f"evidence event is {len(line)} bytes; "
                f"limit is {self._max_event_bytes}"
            )

        self._file.write(line)
        self._evidence_ids.add(detached.evidence_id)

        if durability is TraceDurability.FLUSH:
            self._file.flush()
        elif durability is TraceDurability.FSYNC:
            self._file.flush()
            os.fsync(self._file.fileno())

        return detached

    def close(self) -> None:
        if not self._closed:
            self._file.close()
            self._closed = True

    def __enter__(self) -> EvidenceWriter:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()
