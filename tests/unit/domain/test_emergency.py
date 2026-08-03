"""Unit tests for EmergencySnapshot domain facts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from everweb.domain import (
    ArtifactRef,
    EmergencySnapshot,
    FailureRecord,
    GateReceipt,
    InternalTerminalState,
    TaskIdentity,
)

EXPECTED_FIELDS = {
    "execution_id",
    "task_identity",
    "last_persisted_event_seq",
    "internal_terminal_state",
    "best_candidate_ref",
    "last_url",
    "last_screenshot_ref",
    "navigation_gate",
    "answer_gate",
    "failure",
    "updated_at",
}


def artifact_ref(*, artifact_id: str = "artifact-001") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="candidate",
        relative_path="documents/candidate.json",
        sha256="a" * 64,
        byte_size=12,
        mime_type="application/json",
        created_at=datetime(2026, 8, 3, tzinfo=UTC),
        redacted=False,
    )


def snapshot_values() -> dict[str, Any]:
    return {
        "execution_id": "execution-001",
        "task_identity": TaskIdentity(task_id="task-001"),
        "last_persisted_event_seq": 7,
        "internal_terminal_state": InternalTerminalState.BEST_EFFORT,
        "best_candidate_ref": artifact_ref(),
        "last_url": "https://example.com",
        "last_screenshot_ref": artifact_ref(artifact_id="screenshot-001"),
        "navigation_gate": GateReceipt(accepted=True),
        "answer_gate": GateReceipt(accepted=False),
        "failure": FailureRecord(
            code="everweb.worker.crashed",
            message="worker exit",
        ),
        "updated_at": datetime(2026, 8, 3, 8, 0, tzinfo=UTC),
    }


def test_emergency_snapshot_contract_is_exact_and_round_trips() -> None:
    value = EmergencySnapshot.model_validate(snapshot_values())

    assert set(EmergencySnapshot.model_fields) == EXPECTED_FIELDS
    assert EmergencySnapshot.model_validate_json(value.model_dump_json()) == value

    with pytest.raises(ValidationError):
        value.last_persisted_event_seq = 8
    with pytest.raises(ValidationError):
        EmergencySnapshot.model_validate(
            {**snapshot_values(), "unexpected": True}
        )


def test_emergency_snapshot_allows_nullable_optional_fields() -> None:
    value = EmergencySnapshot(
        execution_id="execution-001",
        task_identity=TaskIdentity(task_id="task-001"),
        last_persisted_event_seq=0,
        internal_terminal_state=None,
        best_candidate_ref=None,
        last_url=None,
        last_screenshot_ref=None,
        navigation_gate=None,
        answer_gate=None,
        failure=None,
        updated_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert value.internal_terminal_state is None
    assert value.best_candidate_ref is None
    assert value.failure is None


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("execution_id", ""),
        ("execution_id", 1),
        ("task_identity", "task-001"),
        ("last_persisted_event_seq", -1),
        ("last_persisted_event_seq", True),
        ("internal_terminal_state", "best_effort"),
        ("updated_at", datetime(2026, 8, 3)),
        ("navigation_gate", True),
        ("failure", "everweb.worker.crashed"),
    ],
)
def test_emergency_snapshot_rejects_invalid_or_coerced_fields(
    field_name: str,
    value: Any,
) -> None:
    values = snapshot_values()
    values[field_name] = value

    with pytest.raises(ValidationError):
        EmergencySnapshot.model_validate(values)
