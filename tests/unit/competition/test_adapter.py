"""Unit tests for the pending-template CompetitionAdapter."""

from __future__ import annotations

import pytest

from everweb.competition import (
    CompetitionCapabilities,
    NullCompetitionAdapter,
    PendingTemplateError,
)
from everweb.domain import (
    InternalTerminalState,
    OfficialOutputDraft,
    TaskIdentity,
)


def test_null_adapter_map_status_is_always_none() -> None:
    adapter = NullCompetitionAdapter(
        CompetitionCapabilities(schema_version="internal-v0")
    )

    for state in InternalTerminalState:
        assert adapter.map_status(state) is None


def test_null_adapter_capabilities_preserve_pending_p2_fields() -> None:
    capabilities = CompetitionCapabilities(schema_version="internal-v0")
    adapter = NullCompetitionAdapter(capabilities)

    returned = adapter.capabilities()
    assert returned is capabilities
    assert returned.official_output_schema is None
    assert returned.official_status_values is None


def test_null_adapter_map_output_raises_pending_template() -> None:
    adapter = NullCompetitionAdapter(
        CompetitionCapabilities(schema_version="internal-v0")
    )
    draft = OfficialOutputDraft(
        task_identity=TaskIdentity(task_id="task-001"),
        mapped_status=None,
        agent_answer="answer",
        urls=(),
        actions=(),
        decision_summaries=(),
        artifact_refs=(),
        capture_ref=None,
        terminal_screenshot_ref=None,
    )

    with pytest.raises(PendingTemplateError, match="map_output"):
        adapter.map_output(draft)


def test_null_adapter_load_tasks_and_count_step_are_pending() -> None:
    adapter = NullCompetitionAdapter(
        CompetitionCapabilities(schema_version="internal-v0")
    )

    with pytest.raises(PendingTemplateError, match="load_tasks"):
        adapter.load_tasks("tasks.json")

    with pytest.raises(PendingTemplateError, match="count_step"):
        adapter.count_step(object(), object())  # type: ignore[arg-type]


def test_null_adapter_map_status_rejects_non_terminal_state() -> None:
    adapter = NullCompetitionAdapter(
        CompetitionCapabilities(schema_version="internal-v0")
    )

    with pytest.raises(TypeError, match="InternalTerminalState"):
        adapter.map_status("verified_success")  # type: ignore[arg-type]
