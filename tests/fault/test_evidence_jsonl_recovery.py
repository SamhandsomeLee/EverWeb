"""Fault tests for evidence JSONL recovery and corruption handling."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from everweb.domain import EvidenceAtom
from everweb.report import (
    EvidenceCorruptionError,
    EvidenceReadResult,
    EvidenceWriter,
    TraceDurability,
    read_evidence,
)


def atom(evidence_id: str) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        execution_id="execution-001",
        iteration_id=1,
        action_id=None,
        claim_key="value",
        raw_value={"value": 1},
        normalized_value=1,
        source_kind="dom_text",
        source_uri=None,
        source_digest="sha256:source",
        snapshot_ref=None,
        locator_or_span="#value",
        page_id="page-001",
        frame_id=None,
        network_request_id=None,
        document_page=None,
        screenshot_ref=None,
        observed_at=datetime(2026, 8, 3, 3, 30, tzinfo=UTC),
        extraction_method="text_content",
        normalization_version="internal-v0",
        trust_level="direct",
    )


def complete_evidence(tmp_path: Path) -> Path:
    with EvidenceWriter(
        run_root=tmp_path / "run",
        execution_id="execution-001",
        max_event_bytes=4096,
    ) as writer:
        writer.append(atom("evidence-001"))
        writer.append(atom("evidence-002"), TraceDurability.FLUSH)
        return writer.path


def read(path: Path, *, max_event_bytes: int = 4096) -> EvidenceReadResult:
    return read_evidence(
        path,
        execution_id="execution-001",
        max_event_bytes=max_event_bytes,
    )


def test_reader_ignores_half_line_and_reports_warning(tmp_path: Path) -> None:
    path = complete_evidence(tmp_path)
    partial = b'{"evidence_id":"unfinished"'
    original = path.read_bytes() + partial
    path.write_bytes(original)

    result = read(path)

    assert [item.evidence_id for item in result.evidence] == [
        "evidence-001",
        "evidence-002",
    ]
    assert len(result.recovery_warnings) == 1
    warning = result.recovery_warnings[0]
    assert warning.code == "truncated_tail"
    assert warning.line_number == 3
    assert warning.discarded_bytes == len(partial)
    assert path.read_bytes() == original


def test_reader_rejects_complete_bad_line(tmp_path: Path) -> None:
    path = complete_evidence(tmp_path)
    path.write_bytes(path.read_bytes() + b"{bad}\n")

    with pytest.raises(EvidenceCorruptionError, match="line 3"):
        read(path)


def test_reader_rejects_duplicate_evidence_id(tmp_path: Path) -> None:
    path = complete_evidence(tmp_path)
    lines = path.read_bytes().splitlines()
    path.write_bytes(lines[0] + b"\n" + lines[0] + b"\n")

    with pytest.raises(EvidenceCorruptionError, match="duplicate evidence_id"):
        read(path)


def test_reader_rejects_execution_mismatch(tmp_path: Path) -> None:
    path = complete_evidence(tmp_path)
    first = json.loads(path.read_bytes().splitlines()[0])
    first["execution_id"] = "other-execution"
    path.write_bytes(
        json.dumps(first, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    )

    with pytest.raises(EvidenceCorruptionError, match="execution_id mismatch"):
        read(path)


def test_reader_rejects_non_finite_value(tmp_path: Path) -> None:
    path = complete_evidence(tmp_path)
    first = path.read_bytes().splitlines()[0].replace(
        b'"raw_value":{"value":1}',
        b'"raw_value":{"value":NaN}',
    )
    path.write_bytes(first + b"\n")

    with pytest.raises(EvidenceCorruptionError, match="line 1"):
        read(path)


def test_reader_rejects_sensitive_complete_record(tmp_path: Path) -> None:
    path = complete_evidence(tmp_path)
    first = path.read_bytes().splitlines()[0].replace(
        b'"raw_value":{"value":1}',
        b'"raw_value":{"accessToken":"secret"}',
    )
    path.write_bytes(first + b"\n")

    with pytest.raises(EvidenceCorruptionError, match="sensitive"):
        read(path)


def test_reader_rejects_explicit_size_limit(tmp_path: Path) -> None:
    path = complete_evidence(tmp_path)

    with pytest.raises(EvidenceCorruptionError, match="exceeds 64 bytes"):
        read(path, max_event_bytes=64)
