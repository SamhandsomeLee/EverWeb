"""Week 0 Fault DoD: truncated JSONL recovery through EmergencyEmit + CI gates."""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path

import yaml

from everweb.competition import CompetitionCapabilities, NullCompetitionAdapter
from everweb.domain import (
    EmergencySnapshot,
    EvidenceAtom,
    InternalTerminalState,
    OfficialOutputDraft,
    TaskIdentity,
)
from everweb.report import EvidenceWriter, TraceDurability, TraceWriter
from everweb.supervisor import (
    CheckpointReason,
    EmergencyEmitter,
    EmergencyReport,
    EmergencySnapshotStore,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = ROOT / "pyproject.toml"
MAX_EVENT_BYTES = 4096


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 5, 10, 15, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1.0


def evidence_atom(*, evidence_id: str, execution_id: str) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        execution_id=execution_id,
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
        observed_at=datetime(2026, 8, 5, 10, 15, tzinfo=UTC),
        extraction_method="text_content",
        normalization_version="internal-v0",
        trust_level="direct",
    )


def test_emergency_emit_recovers_truncated_jsonl_tails(tmp_path: Path) -> None:
    """INV-6 ∩ INV-7: half-line JSONL tails must not block EmergencyEmit."""

    run_root = tmp_path / "run"
    run_root.mkdir()
    execution_id = "execution-week0-fault"
    clock = FixedClock()
    store = EmergencySnapshotStore(run_root, clock=clock)

    with TraceWriter(
        run_root=run_root,
        execution_id=execution_id,
        schema_version="internal-v0",
        max_event_bytes=MAX_EVENT_BYTES,
        clock=clock,
    ) as trace_writer:
        trace_writer.append("runtime.phase", {"phase": "analyze"}, TraceDurability.FSYNC)
        trace_writer.append(
            "runtime.phase",
            {"phase": "navigate"},
            TraceDurability.FSYNC,
        )
        complete_trace_count = 2
        trace_path = trace_writer.path

    with EvidenceWriter(
        run_root=run_root,
        execution_id=execution_id,
        max_event_bytes=MAX_EVENT_BYTES,
    ) as evidence_writer:
        evidence_writer.append(
            evidence_atom(evidence_id="evidence-001", execution_id=execution_id),
            TraceDurability.FSYNC,
        )
        evidence_path = evidence_writer.path

    store.persist(
        EmergencySnapshot(
            execution_id=execution_id,
            task_identity=TaskIdentity(task_id="task-week0-fault"),
            last_persisted_event_seq=complete_trace_count,
            internal_terminal_state=InternalTerminalState.BEST_EFFORT,
            best_candidate_ref=None,
            last_url="https://week0.fault.example/page",
            last_screenshot_ref=None,
            navigation_gate=None,
            answer_gate=None,
            failure=None,
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        reason=CheckpointReason.SUCCESSFUL_ACTION,
    )

    trace_partial = b'{"seq":3,"event_type":"unfinished"'
    evidence_partial = b'{"evidence_id":"unfinished"'
    trace_path.write_bytes(trace_path.read_bytes() + trace_partial)
    evidence_path.write_bytes(evidence_path.read_bytes() + evidence_partial)

    emitter = EmergencyEmitter(
        snapshot_store=store,
        run_directory=run_root,
        clock=clock,
        status_mapper=NullCompetitionAdapter(
            CompetitionCapabilities(schema_version="internal-v0")
        ),
        max_event_bytes=MAX_EVENT_BYTES,
    )
    receipt = emitter.emit(execution_id)

    assert receipt.internal_terminal_state is InternalTerminalState.WORKER_CRASHED
    assert receipt.mapped_status is None
    assert receipt.idempotent is False

    emit_dir = run_root / execution_id / "emergency_emit"
    draft = OfficialOutputDraft.model_validate_json(
        (emit_dir / "official_output_draft.json").read_bytes()
    )
    report = EmergencyReport.model_validate_json(
        (emit_dir / "emergency_report.json").read_bytes()
    )

    assert draft.mapped_status is None
    assert draft.urls == ("https://week0.fault.example/page",)
    assert report.forced_internal_terminal_state is (
        InternalTerminalState.WORKER_CRASHED
    )
    assert report.trace_event_count == complete_trace_count
    assert report.evidence_count == 1
    assert report.trace_recovery_warning_count >= 1
    assert report.evidence_recovery_warning_count >= 1


def test_week0_ci_dod_requires_keyless_ten_minute_gate() -> None:
    """Week 0 DoD: no-key CI must hard-cap at 10 minutes."""

    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    quality = workflow["jobs"]["quality"]
    workflow_text = WORKFLOW.read_text(encoding="utf-8").casefold()
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    assert quality["timeout-minutes"] == 10
    assert quality["runs-on"] == "ubuntu-latest"
    for forbidden in (
        "secrets.",
        "moonshot_api_key",
        "deepseek_api_key",
        "playwright",
        "cdp",
        "evalset/sealed",
    ):
        assert forbidden not in workflow_text
    assert project["project"]["dependencies"] == ["pydantic>=2,<3"]
