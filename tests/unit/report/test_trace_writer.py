"""Unit tests for append-only trace JSONL persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from everweb.report import (
    TraceDurability,
    TraceEventTooLargeError,
    TraceSerializationError,
    TraceWriter,
    TraceWriterClosedError,
    read_trace,
)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 3, 3, 15, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1.0


def create_writer(
    tmp_path: Path,
    *,
    execution_id: str = "execution-001",
    max_event_bytes: int = 4096,
) -> TraceWriter:
    return TraceWriter(
        run_root=tmp_path / "run",
        execution_id=execution_id,
        schema_version="internal-v0",
        max_event_bytes=max_event_bytes,
        clock=FixedClock(),
    )


def test_writer_uses_canonical_layout_sequence_checksum_and_jsonl(
    tmp_path: Path,
) -> None:
    with create_writer(tmp_path) as writer:
        first = writer.append(
            "page_observed",
            {"title": "中文页面", "ready": True},
        )
        second = writer.append(
            "action_recorded",
            {"action_id": "action-001"},
            TraceDurability.FLUSH,
        )

        result = read_trace(writer.path, max_event_bytes=4096)
        raw = writer.path.read_bytes()

    assert writer.path == tmp_path / "run" / "execution-001" / "trace.jsonl"
    assert [first.seq, second.seq] == [1, 2]
    assert first.schema_version == second.schema_version == "internal-v0"
    assert first.execution_id == second.execution_id == "execution-001"
    assert first.timestamp == second.timestamp == FixedClock().now()
    assert result.events == (first, second)
    assert result.recovery_warnings == ()
    assert raw.count(b"\n") == 2
    assert b"\r\n" not in raw
    assert "中文页面".encode() in raw

    unsigned = first.model_dump(mode="json", exclude={"checksum"})
    canonical = json.dumps(
        unsigned,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    assert first.checksum == f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def test_writer_rejects_existing_trace_and_invalid_configuration(
    tmp_path: Path,
) -> None:
    writer = create_writer(tmp_path)
    writer.close()

    with pytest.raises(FileExistsError):
        create_writer(tmp_path)

    for execution_id in (
        "",
        ".",
        "..",
        "../escape",
        "nested/path",
        r"nested\path",
        r"C:\escape",
        "C:relative",
        "bad?name",
        "bad*name",
        "bad|name",
        "trailing.",
        "trailing ",
        "line\nbreak",
    ):
        with pytest.raises(ValueError):
            create_writer(tmp_path, execution_id=execution_id)

    with pytest.raises(ValueError):
        TraceWriter(
            run_root=tmp_path,
            execution_id="valid",
            schema_version="",
            max_event_bytes=100,
            clock=FixedClock(),
        )

    with pytest.raises(ValueError):
        create_writer(tmp_path, execution_id="other", max_event_bytes=0)


def test_writer_rejects_closed_writer() -> None:
    writer = TraceWriter.__new__(TraceWriter)
    writer._closed = True

    with pytest.raises(TraceWriterClosedError):
        writer.append("event", {})


@pytest.mark.parametrize(
    "payload",
    [
        {"not_json": object()},
        {"not_finite": float("nan")},
        {"not_array": (1, 2)},
        {1: "not_a_string_key"},
    ],
)
def test_serialization_failure_does_not_write_or_consume_sequence(
    tmp_path: Path,
    payload: Any,
) -> None:
    with create_writer(tmp_path) as writer:
        with pytest.raises(TraceSerializationError):
            writer.append("invalid", payload)

        assert writer.path.read_bytes() == b""
        event = writer.append("valid", {}, TraceDurability.FLUSH)

    assert event.seq == 1


def test_writer_detaches_persisted_payload_from_caller_mutation(
    tmp_path: Path,
) -> None:
    values = [1]
    payload = {"nested": {"values": values}}

    with create_writer(tmp_path) as writer:
        event = writer.append("event", payload, TraceDurability.FLUSH)
        values.append(2)
        result = read_trace(writer.path, max_event_bytes=4096)

    assert event.payload == {"nested": {"values": [1]}}
    assert result.events == (event,)


def test_size_failure_does_not_write_or_consume_sequence(tmp_path: Path) -> None:
    with create_writer(tmp_path, max_event_bytes=512) as writer:
        with pytest.raises(TraceEventTooLargeError):
            writer.append("oversized", {"text": "x" * 4096})

        assert writer.path.read_bytes() == b""
        event = writer.append("valid", {}, TraceDurability.FLUSH)

    assert event.seq == 1


def test_durability_flushes_before_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fsync_line_counts: list[int] = []

    with create_writer(tmp_path) as writer:
        monkeypatch.setattr(
            "everweb.report.trace_writer.os.fsync",
            lambda _fd: fsync_line_counts.append(
                writer.path.read_bytes().count(b"\n")
            ),
        )

        writer.append("buffered", {}, TraceDurability.BUFFERED)
        assert fsync_line_counts == []

        writer.append("flushed", {}, TraceDurability.FLUSH)
        assert len(read_trace(writer.path, max_event_bytes=4096).events) == 2
        assert fsync_line_counts == []

        writer.append("synced", {}, TraceDurability.FSYNC)
        assert fsync_line_counts == [3]


def test_context_manager_closes_writer(tmp_path: Path) -> None:
    with create_writer(tmp_path) as writer:
        writer.append("event", {})

    with pytest.raises(TraceWriterClosedError):
        writer.append("late_event", {})
