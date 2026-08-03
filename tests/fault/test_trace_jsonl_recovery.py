"""Fault tests for trace JSONL corruption and tail recovery."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from everweb.domain import TraceEnvelope
from everweb.report import (
    TraceCorruptionError,
    TraceDurability,
    TraceWriter,
    compute_trace_checksum,
    read_trace,
)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 3, 3, 15, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1.0


def complete_trace(tmp_path: Path) -> Path:
    with TraceWriter(
        run_root=tmp_path / "run",
        execution_id="execution-001",
        schema_version="internal-v0",
        max_event_bytes=4096,
        clock=FixedClock(),
    ) as writer:
        writer.append("first", {"value": 1})
        writer.append("second", {"value": 2}, TraceDurability.FLUSH)
        return writer.path


def test_reader_ignores_half_line_and_reports_recovery_warning(
    tmp_path: Path,
) -> None:
    path = complete_trace(tmp_path)
    partial_tail = b'{"seq":3,"event_type":"unfinished"'
    original = path.read_bytes() + partial_tail
    path.write_bytes(original)

    result = read_trace(path, max_event_bytes=4096)

    assert [event.seq for event in result.events] == [1, 2]
    assert len(result.recovery_warnings) == 1
    warning = result.recovery_warnings[0]
    assert warning.code == "truncated_tail"
    assert warning.line_number == 3
    assert warning.discarded_bytes == len(partial_tail)
    assert path.read_bytes() == original


def test_reader_ignores_complete_json_without_final_lf(tmp_path: Path) -> None:
    path = complete_trace(tmp_path)
    complete_but_uncommitted = b'{"seq":3}'
    path.write_bytes(path.read_bytes() + complete_but_uncommitted)

    result = read_trace(path, max_event_bytes=4096)

    assert [event.seq for event in result.events] == [1, 2]
    assert result.recovery_warnings[0].discarded_bytes == len(
        complete_but_uncommitted
    )


def test_reader_rejects_complete_malformed_line(tmp_path: Path) -> None:
    path = complete_trace(tmp_path)
    path.write_bytes(path.read_bytes() + b"{malformed}\n")

    with pytest.raises(TraceCorruptionError, match="line 3"):
        read_trace(path, max_event_bytes=4096)


def test_reader_rejects_record_over_explicit_size_limit(tmp_path: Path) -> None:
    path = complete_trace(tmp_path)

    with pytest.raises(TraceCorruptionError, match="exceeds 64 bytes at line 1"):
        read_trace(path, max_event_bytes=64)


def test_reader_rejects_sequence_gap(tmp_path: Path) -> None:
    path = complete_trace(tmp_path)
    lines = path.read_bytes().splitlines()
    second = json.loads(lines[1])
    second["seq"] = 3
    lines[1] = json.dumps(
        second,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    path.write_bytes(b"\n".join(lines) + b"\n")

    with pytest.raises(TraceCorruptionError, match="expected seq 2, found 3"):
        read_trace(path, max_event_bytes=4096)


def test_reader_rejects_checksum_tampering(tmp_path: Path) -> None:
    path = complete_trace(tmp_path)
    lines = path.read_bytes().splitlines()
    first = json.loads(lines[0])
    first["payload"]["value"] = 999
    lines[0] = json.dumps(
        first,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    path.write_bytes(b"\n".join(lines) + b"\n")

    with pytest.raises(TraceCorruptionError, match="checksum mismatch at line 1"):
        read_trace(path, max_event_bytes=4096)


@pytest.mark.parametrize("non_finite", [b"NaN", b"Infinity", b"-Infinity"])
def test_reader_rejects_non_canonical_json_numbers(
    tmp_path: Path,
    non_finite: bytes,
) -> None:
    path = complete_trace(tmp_path)
    first_value = json.loads(path.read_bytes().splitlines()[0])
    first_value["payload"] = {"value": None}
    unsigned = TraceEnvelope.model_validate_json(json.dumps(first_value))
    first_value["checksum"] = compute_trace_checksum(unsigned)
    canonical_null = json.dumps(
        first_value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    tampered = canonical_null.replace(b"null", non_finite)
    path.write_bytes(tampered + b"\n")

    with pytest.raises(TraceCorruptionError, match="non-canonical payload"):
        read_trace(path, max_event_bytes=4096)
