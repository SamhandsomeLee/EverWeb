"""Contract tests for OutputContract draft mapping from TraceProjection."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from inspect import signature
from pathlib import Path

import pytest

from everweb.competition import (
    CompetitionCapabilities,
    NullCompetitionAdapter,
    OutputContractDraftMapper,
    PendingTemplateError,
)
from everweb.domain import (
    ArtifactRef,
    InternalTerminalState,
    OfficialOutputDraft,
    TaskIdentity,
    TraceProjection,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_CONTRACT_PATH = (
    ROOT / "src" / "everweb" / "competition" / "output_contract.py"
)
FORBIDDEN_IMPORT_ROOTS = ("everweb.report", "everweb.answer", "everweb.adapters")


def artifact_ref(*, artifact_id: str = "artifact-001") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="document",
        relative_path=f"documents/{artifact_id}.json",
        sha256="d" * 64,
        byte_size=4,
        mime_type="application/json",
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
        redacted=False,
    )


def make_projection(
    *,
    urls: tuple[str, ...] = ("https://a.example", "https://b.example"),
    actions: tuple[str, ...] = ("navigate", "click"),
) -> TraceProjection:
    return TraceProjection(
        urls=urls,
        actions=actions,
        artifact_refs=(artifact_ref(),),
        capture_ref=artifact_ref(artifact_id="capture-001"),
        terminal_screenshot_ref=artifact_ref(artifact_id="shot-001"),
    )


def test_map_draft_copies_projection_fields_without_reordering() -> None:
    projection = make_projection(
        urls=("https://z.example", "https://a.example"),
        actions=("scroll", "type"),
    )
    draft = OutputContractDraftMapper().map_draft(
        task_identity=TaskIdentity(task_id="task-001"),
        trace_projection=projection,
        agent_answer="answer",
        decision_summaries=("stop",),
    )

    assert isinstance(draft, OfficialOutputDraft)
    assert draft.mapped_status is None
    assert draft.urls == ("https://z.example", "https://a.example")
    assert draft.actions == ("scroll", "type")
    assert draft.capture_ref == projection.capture_ref
    assert draft.terminal_screenshot_ref == projection.terminal_screenshot_ref
    assert draft.artifact_refs == projection.artifact_refs
    assert draft.agent_answer == "answer"
    assert draft.decision_summaries == ("stop",)


def test_map_draft_allows_empty_projection_sequences() -> None:
    draft = OutputContractDraftMapper().map_draft(
        task_identity=TaskIdentity(task_id="task-001"),
        trace_projection=TraceProjection(),
        agent_answer="",
    )

    assert draft.urls == ()
    assert draft.actions == ()
    assert draft.capture_ref is None
    assert draft.terminal_screenshot_ref is None
    assert draft.mapped_status is None


def test_mapper_api_cannot_inject_trajectory_outside_projection() -> None:
    parameters = signature(OutputContractDraftMapper.map_draft).parameters

    assert "urls" not in parameters
    assert "actions" not in parameters
    assert "capture_ref" not in parameters
    assert "terminal_screenshot_ref" not in parameters
    assert "mapped_status" not in parameters
    assert "trace_projection" in parameters


def test_adapter_map_status_and_draft_status_remain_none() -> None:
    adapter = NullCompetitionAdapter(
        CompetitionCapabilities(schema_version="internal-v0")
    )
    draft = OutputContractDraftMapper().map_draft(
        task_identity=TaskIdentity(task_id="task-001"),
        trace_projection=make_projection(),
        agent_answer="answer",
    )

    assert draft.mapped_status is None
    assert adapter.map_status(InternalTerminalState.VERIFIED_SUCCESS) is None


def test_capabilities_do_not_guess_p2_schema_or_status_enums() -> None:
    capabilities = CompetitionCapabilities(schema_version="internal-v0")
    adapter = NullCompetitionAdapter(capabilities)

    assert capabilities.official_output_schema is None
    assert capabilities.official_status_values is None
    assert adapter.capabilities().official_output_schema is None
    with pytest.raises(PendingTemplateError):
        adapter.map_output(
            OutputContractDraftMapper().map_draft(
                task_identity=TaskIdentity(task_id="task-001"),
                trace_projection=TraceProjection(),
                agent_answer="x",
            )
        )


def test_output_contract_module_does_not_import_report_answer_or_adapters() -> None:
    tree = ast.parse(OUTPUT_CONTRACT_PATH.read_text(encoding="utf-8"))
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
