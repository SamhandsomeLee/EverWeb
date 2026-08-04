"""Unit tests for the pure SERIALIZE assembler."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from everweb.domain import (
    ArtifactRef,
    InternalTerminalState,
    OfficialOutputDraft,
    TaskIdentity,
)
from everweb.report import SerializeRequest, serialize


def artifact_ref(*, artifact_id: str = "artifact-001") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="document",
        relative_path="documents/artifact-001.json",
        sha256="d" * 64,
        byte_size=4,
        mime_type="application/json",
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
        redacted=False,
    )


def make_request(
    *,
    urls: tuple[str, ...] | None = None,
    actions: tuple[str, ...] | None = None,
) -> SerializeRequest:
    return SerializeRequest(
        task_identity=TaskIdentity(task_id="task-001"),
        internal_terminal_state=InternalTerminalState.BEST_EFFORT,
        agent_answer="answer",
        urls=(
            urls
            if urls is not None
            else ("https://a.example", "https://b.example")
        ),
        actions=actions if actions is not None else ("navigate", "click"),
        decision_summaries=("stop with best effort",),
        artifact_refs=(artifact_ref(),),
        capture_ref=artifact_ref(artifact_id="capture-001"),
        terminal_screenshot_ref=artifact_ref(artifact_id="shot-001"),
    )


def test_serialize_assembles_draft_with_mapped_status_none() -> None:
    request = make_request()
    draft = serialize(request)

    assert isinstance(draft, OfficialOutputDraft)
    assert draft.mapped_status is None
    assert draft.task_identity == request.task_identity
    assert draft.agent_answer == "answer"
    assert draft.urls == ("https://a.example", "https://b.example")
    assert draft.actions == ("navigate", "click")
    assert draft.decision_summaries == ("stop with best effort",)
    assert draft.artifact_refs == request.artifact_refs
    assert draft.capture_ref == request.capture_ref
    assert draft.terminal_screenshot_ref == request.terminal_screenshot_ref
    assert "internal_terminal_state" not in OfficialOutputDraft.model_fields


def test_serialize_preserves_order_and_allows_empty_sequences() -> None:
    request = make_request(
        urls=("https://z.example", "https://a.example"),
        actions=(),
    )
    draft = serialize(request)

    assert draft.urls == ("https://z.example", "https://a.example")
    assert draft.actions == ()


def test_serialize_isolates_draft_from_input_list_mutation() -> None:
    urls = ["https://a.example"]
    actions = ["click"]
    request = SerializeRequest.model_validate(
        {
            "task_identity": TaskIdentity(task_id="task-001"),
            "internal_terminal_state": InternalTerminalState.VERIFIED_SUCCESS,
            "agent_answer": "ok",
            "urls": urls,
            "actions": actions,
            "decision_summaries": [],
            "artifact_refs": [],
            "capture_ref": None,
            "terminal_screenshot_ref": None,
        }
    )
    draft = serialize(request)

    urls.append("https://forged.example")
    actions.append("forged")

    assert draft.urls == ("https://a.example",)
    assert draft.actions == ("click",)
    with pytest.raises(ValidationError):
        draft.urls = ("https://forged.example",)


def test_serialize_rejects_non_request_and_invalid_elements() -> None:
    with pytest.raises(TypeError):
        serialize("not-a-request")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        SerializeRequest.model_validate(
            {
                "task_identity": TaskIdentity(task_id="task-001"),
                "internal_terminal_state": InternalTerminalState.BEST_EFFORT,
                "agent_answer": "answer",
                "urls": [1],
                "actions": [],
                "decision_summaries": [],
                "artifact_refs": [],
                "capture_ref": None,
                "terminal_screenshot_ref": None,
            }
        )
