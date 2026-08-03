"""Unit tests for task identity."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from everweb.domain import TaskIdentity


def test_task_identity_normalizes_and_round_trips() -> None:
    identity = TaskIdentity(task_id="  task-001  ")

    assert identity.task_id == "task-001"
    assert TaskIdentity.model_validate_json(identity.model_dump_json()) == identity


@pytest.mark.parametrize("task_id", ["", "  ", "\t"])
def test_task_identity_rejects_empty_values(task_id: str) -> None:
    with pytest.raises(ValidationError):
        TaskIdentity(task_id=task_id)


def test_task_identity_is_strict_and_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TaskIdentity.model_validate({"task_id": 1})

    with pytest.raises(ValidationError):
        TaskIdentity.model_validate({"task_id": "task-001", "task_idx": 1})


def test_task_identity_is_frozen() -> None:
    identity = TaskIdentity(task_id="task-001")

    with pytest.raises(ValidationError):
        setattr(identity, "task_id", "task-002")
