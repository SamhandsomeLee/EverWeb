"""Contract tests for atomic EmergencySnapshot checkpoint persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from everweb.domain import (
    ArtifactRef,
    EmergencySnapshot,
    FailureRecord,
    GateReceipt,
    InternalTerminalState,
    TaskIdentity,
)
from everweb.supervisor import (
    CheckpointReason,
    EmergencySnapshotCorruptionError,
    EmergencySnapshotError,
    EmergencySnapshotStore,
    EmergencySnapshotValidationError,
)


@dataclass
class FakeClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return 100.0


def artifact_ref(*, artifact_id: str = "artifact-001") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="candidate",
        relative_path="documents/candidate.json",
        sha256="b" * 64,
        byte_size=4,
        mime_type="application/json",
        created_at=datetime(2026, 8, 3, tzinfo=UTC),
        redacted=False,
    )


def make_snapshot(
    *,
    execution_id: str = "execution-001",
    seq: int = 1,
    updated_at: datetime | None = None,
) -> EmergencySnapshot:
    return EmergencySnapshot(
        execution_id=execution_id,
        task_identity=TaskIdentity(task_id="task-001"),
        last_persisted_event_seq=seq,
        internal_terminal_state=InternalTerminalState.BEST_EFFORT,
        best_candidate_ref=artifact_ref(),
        last_url="https://example.com",
        last_screenshot_ref=artifact_ref(artifact_id="shot-001"),
        navigation_gate=GateReceipt(accepted=True),
        answer_gate=None,
        failure=FailureRecord(
            code="everweb.budget.exhausted",
            message="near hard stop",
        ),
        updated_at=updated_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_checkpoint_reasons_cover_all_required_moments() -> None:
    assert {reason.value for reason in CheckpointReason} == {
        "analyze_complete",
        "successful_action",
        "evidence_ledger_update",
        "candidate_update",
        "before_prepare_final_state",
        "after_terminal_decision",
    }


@pytest.mark.parametrize("reason", list(CheckpointReason))
def test_each_checkpoint_reason_can_persist_and_load(
    tmp_path: Path,
    reason: CheckpointReason,
) -> None:
    clock = FakeClock(datetime(2026, 8, 3, 9, 0, tzinfo=UTC))
    store = EmergencySnapshotStore(tmp_path, clock=clock)
    snapshot = make_snapshot(seq=3)

    persisted = store.persist(snapshot, reason=reason)
    loaded = store.load(snapshot.execution_id)

    assert persisted.updated_at == clock.current
    assert loaded == persisted
    assert store.path_for(snapshot.execution_id).is_file()


def test_persist_overwrites_previous_snapshot_and_uses_clock(
    tmp_path: Path,
) -> None:
    clock = FakeClock(datetime(2026, 8, 3, 10, 0, tzinfo=UTC))
    store = EmergencySnapshotStore(tmp_path, clock=clock)
    first = store.persist(
        make_snapshot(seq=1),
        reason=CheckpointReason.ANALYZE_COMPLETE,
    )

    clock.current = datetime(2026, 8, 3, 10, 5, tzinfo=UTC)
    second = store.persist(
        make_snapshot(seq=9, updated_at=datetime(2020, 1, 1, tzinfo=UTC)),
        reason=CheckpointReason.CANDIDATE_UPDATE,
    )
    loaded = store.load("execution-001")

    assert first.last_persisted_event_seq == 1
    assert second.last_persisted_event_seq == 9
    assert loaded == second
    assert loaded is not None
    assert loaded.updated_at == datetime(2026, 8, 3, 10, 5, tzinfo=UTC)


def test_load_missing_snapshot_returns_none(tmp_path: Path) -> None:
    store = EmergencySnapshotStore(
        tmp_path,
        clock=FakeClock(datetime(2026, 8, 3, tzinfo=UTC)),
    )

    assert store.load("execution-missing") is None


def test_load_rejects_truncated_or_malformed_snapshot(tmp_path: Path) -> None:
    store = EmergencySnapshotStore(
        tmp_path,
        clock=FakeClock(datetime(2026, 8, 3, tzinfo=UTC)),
    )
    path = store.path_for("execution-001")
    path.parent.mkdir(parents=True)
    path.write_text('{"execution_id":"execution-001"', encoding="utf-8")

    with pytest.raises(EmergencySnapshotCorruptionError):
        store.load("execution-001")

    path.write_bytes(b"")
    with pytest.raises(EmergencySnapshotCorruptionError):
        store.load("execution-001")


@pytest.mark.parametrize(
    "execution_id",
    ["", "a/b", "..", "bad:name", "bad*name", "trailing."],
)
def test_store_rejects_invalid_execution_id(
    tmp_path: Path,
    execution_id: str,
) -> None:
    store = EmergencySnapshotStore(
        tmp_path,
        clock=FakeClock(datetime(2026, 8, 3, tzinfo=UTC)),
    )

    with pytest.raises(EmergencySnapshotValidationError):
        store.path_for(execution_id)


def test_store_rejects_symlink_run_directory(tmp_path: Path) -> None:
    target = tmp_path / "real-run"
    target.mkdir()
    link = tmp_path / "linked-run"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(EmergencySnapshotValidationError):
        EmergencySnapshotStore(
            link,
            clock=FakeClock(datetime(2026, 8, 3, tzinfo=UTC)),
        )


def test_store_rejects_naive_clock_datetime(tmp_path: Path) -> None:
    store = EmergencySnapshotStore(
        tmp_path,
        clock=FakeClock(datetime(2026, 8, 3)),
    )

    with pytest.raises(EmergencySnapshotValidationError, match="aware"):
        store.persist(
            make_snapshot(),
            reason=CheckpointReason.ANALYZE_COMPLETE,
        )


def test_supervisor_exports_snapshot_surface_without_emitter() -> None:
    import everweb.supervisor as supervisor

    assert supervisor.EmergencySnapshotStore is EmergencySnapshotStore
    assert supervisor.CheckpointReason is CheckpointReason
    assert issubclass(EmergencySnapshotCorruptionError, EmergencySnapshotError)
    assert not hasattr(supervisor, "EmergencyEmitter")
    assert not hasattr(supervisor, "emergency_emitter")
