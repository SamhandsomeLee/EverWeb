"""Contract tests for EmergencyEmitter purity and atomic internal emit."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Never

from everweb.competition import (
    CompetitionCapabilities,
    NullCompetitionAdapter,
    PendingTemplateError,
)
from everweb.domain import (
    EmergencySnapshot,
    InternalTerminalState,
    OfficialOutputDraft,
    TaskIdentity,
)
from everweb.supervisor import (
    CheckpointReason,
    EmergencyEmitReceipt,
    EmergencyEmitter,
    EmergencySnapshotStore,
)
from everweb.supervisor import emergency_emitter as emergency_emitter_module

EMITTER_PATH = Path(emergency_emitter_module.__file__).resolve()
FORBIDDEN_IMPORT_ROOTS = (
    "everweb.adapters",
    "everweb.answer",
    "everweb.perceive",
    "everweb.act",
    "everweb.competition",
    "httpx",
    "playwright",
)


@dataclass
class FakeClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return 100.0


class SpyAdapter(NullCompetitionAdapter):
    def __init__(self) -> None:
        super().__init__(CompetitionCapabilities(schema_version="internal-v0"))
        self.map_status_calls = 0
        self.map_output_calls = 0

    def map_status(self, state: InternalTerminalState) -> str | None:
        self.map_status_calls += 1
        return super().map_status(state)

    def map_output(self, draft: OfficialOutputDraft) -> Never:
        self.map_output_calls += 1
        raise PendingTemplateError("map_output must not be used in W0-014")


def make_snapshot(execution_id: str = "execution-001") -> EmergencySnapshot:
    return EmergencySnapshot(
        execution_id=execution_id,
        task_identity=TaskIdentity(task_id="task-001"),
        last_persisted_event_seq=0,
        internal_terminal_state=InternalTerminalState.BEST_EFFORT,
        best_candidate_ref=None,
        last_url="https://example.com/path",
        last_screenshot_ref=None,
        navigation_gate=None,
        answer_gate=None,
        failure=None,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_supervisor_exports_emergency_emitter() -> None:
    import everweb.supervisor as supervisor

    assert supervisor.EmergencyEmitter is EmergencyEmitter
    assert supervisor.EmergencyEmitReceipt is EmergencyEmitReceipt


def test_emergency_emitter_module_forbids_runtime_side_imports() -> None:
    tree = ast.parse(EMITTER_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)

    for module_name in imported:
        assert not any(
            module_name == root or module_name.startswith(f"{root}.")
            for root in FORBIDDEN_IMPORT_ROOTS
        ), module_name


def test_emit_calls_map_status_not_map_output_and_writes_atomically(
    tmp_path: Path,
) -> None:
    clock = FakeClock(datetime(2026, 8, 4, 15, 0, tzinfo=UTC))
    store = EmergencySnapshotStore(tmp_path, clock=clock)
    store.persist(
        make_snapshot(),
        reason=CheckpointReason.BEFORE_PREPARE_FINAL_STATE,
    )
    adapter = SpyAdapter()
    emitter = EmergencyEmitter(
        snapshot_store=store,
        run_directory=tmp_path,
        clock=clock,
        status_mapper=adapter,
        max_event_bytes=65536,
    )

    receipt = emitter.emit("execution-001")
    emit_dir = tmp_path / "execution-001" / "emergency_emit"

    assert adapter.map_status_calls == 1
    assert adapter.map_output_calls == 0
    assert receipt.mapped_status is None
    assert receipt.internal_terminal_state is InternalTerminalState.WORKER_CRASHED
    assert (emit_dir / "official_output_draft.json").is_file()
    assert (emit_dir / "emergency_report.json").is_file()
    assert (emit_dir / "output_receipt.json").is_file()
    assert list(emit_dir.glob("*.tmp")) == []

    draft = OfficialOutputDraft.model_validate_json(
        (emit_dir / "official_output_draft.json").read_bytes()
    )
    assert draft.mapped_status is None
    assert draft.urls == ("https://example.com/path",)
    assert draft.actions == ()
