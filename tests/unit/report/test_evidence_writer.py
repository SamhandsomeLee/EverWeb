"""Unit tests for append-only evidence JSONL persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from everweb.domain import EvidenceAtom
from everweb.report import (
    EvidenceConflictError,
    EvidenceEventTooLargeError,
    EvidenceSensitiveContentError,
    EvidenceSerializationError,
    EvidenceWriter,
    EvidenceWriterClosedError,
    TraceDurability,
    read_evidence,
)


def evidence_atom(
    *,
    evidence_id: str = "evidence-001",
    execution_id: str = "execution-001",
    raw_value: Any = None,
    normalized_value: Any = None,
) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        execution_id=execution_id,
        iteration_id=1,
        action_id="action-001",
        claim_key="price",
        raw_value={"text": "$10"} if raw_value is None else raw_value,
        normalized_value=(
            {"amount": 10, "currency": "USD"}
            if normalized_value is None
            else normalized_value
        ),
        source_kind="dom_text",
        source_uri="https://example.test/item",
        source_digest="sha256:source",
        snapshot_ref=None,
        locator_or_span="#price",
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


def create_writer(
    tmp_path: Path,
    *,
    max_event_bytes: int = 4096,
) -> EvidenceWriter:
    return EvidenceWriter(
        run_root=tmp_path / "run",
        execution_id="execution-001",
        max_event_bytes=max_event_bytes,
    )


def test_writer_appends_direct_atoms_and_reads_them_in_order(
    tmp_path: Path,
) -> None:
    with create_writer(tmp_path) as writer:
        first = writer.append(evidence_atom())
        second = writer.append(
            evidence_atom(evidence_id="evidence-002"),
            TraceDurability.FLUSH,
        )
        result = read_evidence(
            writer.path,
            execution_id="execution-001",
            max_event_bytes=4096,
        )

    assert writer.path == tmp_path / "run" / "execution-001" / "evidence.jsonl"
    assert result.evidence == (first, second)
    assert result.recovery_warnings == ()
    raw = writer.path.read_bytes()
    assert raw.count(b"\n") == 2
    assert b"\r\n" not in raw


def test_writer_detaches_mutable_evidence_values(tmp_path: Path) -> None:
    values = [1]
    atom = evidence_atom(raw_value={"values": values})

    with create_writer(tmp_path) as writer:
        persisted = writer.append(atom, TraceDurability.FLUSH)
        values.append(2)
        result = read_evidence(
            writer.path,
            execution_id="execution-001",
            max_event_bytes=4096,
        )

    assert persisted.raw_value == {"values": [1]}
    assert result.evidence == (persisted,)


def test_conflicts_do_not_append_or_reserve_new_identity(tmp_path: Path) -> None:
    with create_writer(tmp_path) as writer:
        writer.append(evidence_atom(), TraceDurability.FLUSH)
        before = writer.path.read_bytes()

        with pytest.raises(EvidenceConflictError):
            writer.append(evidence_atom())
        with pytest.raises(EvidenceConflictError):
            writer.append(
                evidence_atom(
                    evidence_id="evidence-002",
                    execution_id="other-execution",
                )
            )

        assert writer.path.read_bytes() == before
        accepted = writer.append(
            evidence_atom(evidence_id="evidence-002"),
            TraceDurability.FLUSH,
        )

    assert accepted.evidence_id == "evidence-002"


@pytest.mark.parametrize(
    "raw_value",
    [
        {"object": object()},
        {"not_finite": float("nan")},
        {"tuple": (1, 2)},
        {1: "non-string-key"},
    ],
)
def test_invalid_json_does_not_write_or_reserve_identity(
    tmp_path: Path,
    raw_value: Any,
) -> None:
    with create_writer(tmp_path) as writer:
        with pytest.raises(EvidenceSerializationError):
            writer.append(evidence_atom(raw_value=raw_value))

        assert writer.path.read_bytes() == b""
        accepted = writer.append(
            evidence_atom(),
            TraceDurability.FLUSH,
        )

    assert accepted.evidence_id == "evidence-001"


def test_oversized_event_does_not_write_or_reserve_identity(
    tmp_path: Path,
) -> None:
    with create_writer(tmp_path, max_event_bytes=1024) as writer:
        with pytest.raises(EvidenceEventTooLargeError):
            writer.append(evidence_atom(raw_value={"text": "x" * 4096}))

        assert writer.path.read_bytes() == b""
        accepted = writer.append(evidence_atom(), TraceDurability.FLUSH)

    assert accepted.evidence_id == "evidence-001"


def test_sensitive_evidence_does_not_write_or_reserve_identity(
    tmp_path: Path,
) -> None:
    with create_writer(tmp_path) as writer:
        with pytest.raises(EvidenceSensitiveContentError):
            writer.append(
                evidence_atom(raw_value={"accessToken": "secret"})
            )

        assert writer.path.read_bytes() == b""
        accepted = writer.append(evidence_atom(), TraceDurability.FLUSH)

    assert accepted.evidence_id == "evidence-001"


def test_fsync_follows_flush(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fsync_line_counts: list[int] = []

    with create_writer(tmp_path) as writer:
        monkeypatch.setattr(
            "everweb.report.evidence_writer.os.fsync",
            lambda _fd: fsync_line_counts.append(
                writer.path.read_bytes().count(b"\n")
            ),
        )
        writer.append(evidence_atom(), TraceDurability.FSYNC)

    assert fsync_line_counts == [1]


def test_writer_rejects_existing_file_and_append_after_close(
    tmp_path: Path,
) -> None:
    writer = create_writer(tmp_path)
    writer.close()

    with pytest.raises(FileExistsError):
        create_writer(tmp_path)
    with pytest.raises(EvidenceWriterClosedError):
        writer.append(evidence_atom())


def test_writer_rejects_execution_directory_escape(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (run_root / "execution-001").symlink_to(
            outside,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("symbolic links are unavailable on this platform")

    with pytest.raises(ValueError, match="escapes run_root"):
        create_writer(tmp_path)

    assert list(outside.iterdir()) == []
