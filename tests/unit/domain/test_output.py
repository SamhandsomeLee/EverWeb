"""Unit tests for OfficialOutputDraft domain facts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from everweb.domain import ArtifactRef, OfficialOutputDraft, TaskIdentity

EXPECTED_FIELDS = {
    "task_identity",
    "mapped_status",
    "agent_answer",
    "urls",
    "actions",
    "decision_summaries",
    "artifact_refs",
    "capture_ref",
    "terminal_screenshot_ref",
}


def artifact_ref(*, artifact_id: str = "artifact-001") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="document",
        relative_path="documents/artifact-001.json",
        sha256="c" * 64,
        byte_size=8,
        mime_type="application/json",
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
        redacted=False,
    )


def draft_values() -> dict[str, Any]:
    return {
        "task_identity": TaskIdentity(task_id="task-001"),
        "mapped_status": None,
        "agent_answer": "42",
        "urls": ["https://example.com"],
        "actions": ["click#1"],
        "decision_summaries": ["chose best effort"],
        "artifact_refs": [artifact_ref()],
        "capture_ref": artifact_ref(artifact_id="capture-001"),
        "terminal_screenshot_ref": artifact_ref(artifact_id="shot-001"),
    }


def test_official_output_draft_contract_is_exact_and_round_trips() -> None:
    draft = OfficialOutputDraft.model_validate(draft_values())

    assert set(OfficialOutputDraft.model_fields) == EXPECTED_FIELDS
    assert draft.urls == ("https://example.com",)
    assert draft.actions == ("click#1",)
    assert OfficialOutputDraft.model_validate_json(draft.model_dump_json()) == draft

    with pytest.raises(ValidationError):
        draft.agent_answer = "changed"
    with pytest.raises(ValidationError):
        OfficialOutputDraft.model_validate({**draft_values(), "extra": True})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("task_identity", "task-001"),
        ("mapped_status", 1),
        ("agent_answer", True),
        ("urls", ["https://example.com", 1]),
        ("actions", "click#1"),
        ("artifact_refs", ["artifact-001"]),
        ("capture_ref", "capture-001"),
    ],
)
def test_official_output_draft_rejects_invalid_or_coerced_fields(
    field_name: str,
    value: Any,
) -> None:
    values = draft_values()
    values[field_name] = value

    with pytest.raises(ValidationError):
        OfficialOutputDraft.model_validate(values)
