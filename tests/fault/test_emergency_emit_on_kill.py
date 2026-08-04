"""Fault test: Worker forced death then Parent EmergencyEmit."""

from __future__ import annotations

import os
import signal
import time
from datetime import UTC, datetime
from pathlib import Path

from everweb.competition import CompetitionCapabilities, NullCompetitionAdapter
from everweb.domain import (
    EmergencySnapshot,
    InternalTerminalState,
    OfficialOutputDraft,
    TaskIdentity,
)
from everweb.supervisor import (
    CheckpointReason,
    EmergencyEmitter,
    EmergencySnapshotStore,
    SpawnWorkerPool,
    WorkerAssignment,
)


class WorkerClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 4, 16, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1.0


def snapshot_then_hang_worker(assignment: WorkerAssignment) -> None:
    """Worker persists checkpoint facts, then hangs until Parent kills it."""

    run_root = Path(assignment.cdp_url)
    clock = WorkerClock()
    store = EmergencySnapshotStore(run_root, clock=clock)
    snapshot = EmergencySnapshot(
        execution_id=assignment.execution_id,
        task_identity=assignment.task_identity,
        last_persisted_event_seq=0,
        internal_terminal_state=InternalTerminalState.BEST_EFFORT,
        best_candidate_ref=None,
        last_url="https://fault.example/page",
        last_screenshot_ref=None,
        navigation_gate=None,
        answer_gate=None,
        failure=None,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    store.persist(snapshot, reason=CheckpointReason.SUCCESSFUL_ACTION)
    execution_dir = run_root / assignment.execution_id
    (execution_dir / "trace.jsonl").write_bytes(b"")
    (execution_dir / "evidence.jsonl").write_bytes(b"")
    (run_root / "worker-ready").write_text("ready", encoding="utf-8")
    while True:
        time.sleep(1.0)


def test_parent_emergency_emit_after_forced_worker_death(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    ready_path = run_root / "worker-ready"
    value = WorkerAssignment(
        execution_id="execution-fault",
        task_identity=TaskIdentity(task_id="task-fault"),
        cdp_url=str(run_root),
    )
    pool = SpawnWorkerPool(entrypoint=snapshot_then_hang_worker)
    handle = pool.start(value)
    deadline = time.monotonic() + 10.0

    try:
        while not ready_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready_path.exists(), "worker did not persist checkpoint before hang"

        if os.name == "nt":
            pool.shutdown()
        else:
            os.kill(handle.pid, signal.SIGKILL)
            receipt = pool.reap(value.execution_id, timeout_s=10.0)
            assert receipt is not None
            assert receipt.exit_code != 0
    finally:
        if pool.active_count:
            pool.shutdown()

    clock = WorkerClock()
    emitter = EmergencyEmitter(
        snapshot_store=EmergencySnapshotStore(run_root, clock=clock),
        run_directory=run_root,
        clock=clock,
        status_mapper=NullCompetitionAdapter(
            CompetitionCapabilities(schema_version="internal-v0")
        ),
        max_event_bytes=65536,
    )
    emit_receipt = emitter.emit(value.execution_id)
    draft_path = (
        run_root
        / value.execution_id
        / "emergency_emit"
        / "official_output_draft.json"
    )
    draft = OfficialOutputDraft.model_validate_json(draft_path.read_bytes())

    assert emit_receipt.internal_terminal_state is InternalTerminalState.WORKER_CRASHED
    assert emit_receipt.mapped_status is None
    assert draft.mapped_status is None
    assert draft.urls == ("https://fault.example/page",)
    assert draft.actions == ()
    assert draft.decision_summaries == ("emergency_emit", "worker_crashed")
