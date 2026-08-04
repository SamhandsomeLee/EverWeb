"""Unit tests for Parent EmergencyEmitter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from everweb.competition import CompetitionCapabilities, NullCompetitionAdapter
from everweb.domain import (
    ArtifactRef,
    EmergencySnapshot,
    InternalTerminalState,
    OfficialOutputDraft,
    TaskIdentity,
)
from everweb.supervisor import (
    CheckpointReason,
    EmergencyEmitter,
    EmergencyEmitValidationError,
    EmergencySnapshotStore,
)


@dataclass
class FakeClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return 100.0


def artifact_ref(*, artifact_id: str = "candidate-001") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="candidate",
        relative_path=f"documents/{artifact_id}.json",
        sha256="b" * 64,
        byte_size=4,
        mime_type="application/json",
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
        redacted=False,
    )


def make_snapshot(
    *,
    execution_id: str = "execution-001",
    seq: int = 0,
    last_url: str | None = "https://example.com",
    terminal: InternalTerminalState | None = InternalTerminalState.BEST_EFFORT,
) -> EmergencySnapshot:
    return EmergencySnapshot(
        execution_id=execution_id,
        task_identity=TaskIdentity(task_id="task-001"),
        last_persisted_event_seq=seq,
        internal_terminal_state=terminal,
        best_candidate_ref=artifact_ref(),
        last_url=last_url,
        last_screenshot_ref=artifact_ref(artifact_id="shot-001"),
        navigation_gate=None,
        answer_gate=None,
        failure=None,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def make_emitter(tmp_path: Path, *, clock: FakeClock | None = None) -> EmergencyEmitter:
    active_clock = clock or FakeClock(datetime(2026, 8, 4, 12, 0, tzinfo=UTC))
    store = EmergencySnapshotStore(tmp_path, clock=active_clock)
    return EmergencyEmitter(
        snapshot_store=store,
        run_directory=tmp_path,
        clock=active_clock,
        status_mapper=NullCompetitionAdapter(
            CompetitionCapabilities(schema_version="internal-v0")
        ),
        max_event_bytes=65536,
    )


def test_emit_maps_snapshot_fields_and_forces_worker_crashed(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 8, 4, 12, 0, tzinfo=UTC))
    store = EmergencySnapshotStore(tmp_path, clock=clock)
    store.persist(
        make_snapshot(seq=0),
        reason=CheckpointReason.SUCCESSFUL_ACTION,
    )
    emitter = make_emitter(tmp_path, clock=clock)

    receipt = emitter.emit("execution-001")
    draft_path = tmp_path / "execution-001" / "emergency_emit" / (
        "official_output_draft.json"
    )
    draft = OfficialOutputDraft.model_validate_json(draft_path.read_bytes())

    assert receipt.internal_terminal_state is InternalTerminalState.WORKER_CRASHED
    assert receipt.mapped_status is None
    assert draft.mapped_status is None
    assert draft.urls == ("https://example.com",)
    assert draft.actions == ()
    assert draft.agent_answer == ""
    assert draft.decision_summaries == ("emergency_emit", "worker_crashed")
    assert draft.capture_ref is None
    assert draft.terminal_screenshot_ref == artifact_ref(artifact_id="shot-001")
    assert draft.artifact_refs == (
        artifact_ref(),
        artifact_ref(artifact_id="shot-001"),
    )


def test_emit_rejects_missing_snapshot(tmp_path: Path) -> None:
    emitter = make_emitter(tmp_path)

    with pytest.raises(EmergencyEmitValidationError, match="snapshot"):
        emitter.emit("execution-001")


def test_emit_rejects_seq_ahead_of_trace(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 8, 4, 12, 0, tzinfo=UTC))
    store = EmergencySnapshotStore(tmp_path, clock=clock)
    store.persist(
        make_snapshot(seq=2),
        reason=CheckpointReason.SUCCESSFUL_ACTION,
    )
    (tmp_path / "execution-001" / "trace.jsonl").write_bytes(b"")
    emitter = make_emitter(tmp_path, clock=clock)

    with pytest.raises(EmergencyEmitValidationError, match="last_persisted_event_seq"):
        emitter.emit("execution-001")


def test_emit_idempotent_when_receipt_already_present(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 8, 4, 12, 0, tzinfo=UTC))
    store = EmergencySnapshotStore(tmp_path, clock=clock)
    store.persist(
        make_snapshot(seq=0, last_url=None),
        reason=CheckpointReason.ANALYZE_COMPLETE,
    )
    emitter = make_emitter(tmp_path, clock=clock)

    first = emitter.emit("execution-001")
    second = emitter.emit("execution-001")

    assert first.idempotent is False
    assert second.idempotent is True
    assert second.draft_sha256 == first.draft_sha256
