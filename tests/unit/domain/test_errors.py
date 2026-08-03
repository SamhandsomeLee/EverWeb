"""Unit tests for internal failure records."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from everweb.domain import ErrorCode, FailureRecord


def test_error_code_uses_internal_namespace() -> None:
    adapter = TypeAdapter(ErrorCode)

    assert adapter.validate_python("  everweb.input.invalid  ") == "everweb.input.invalid"


@pytest.mark.parametrize(
    "code",
    ["SUCCESS", "FAIL", "invalid_input", "everweb.SUCCESS", "everweb.invalid-input"],
)
def test_error_code_rejects_status_like_or_unscoped_values(code: str) -> None:
    with pytest.raises(ValidationError):
        FailureRecord(code=code, message="Rejected")


def test_failure_record_normalizes_and_round_trips() -> None:
    failure = FailureRecord(
        code="everweb.input.invalid",
        message="  Task identity is missing  ",
    )

    assert failure.message == "Task identity is missing"
    assert FailureRecord.model_validate_json(failure.model_dump_json()) == failure


def test_failure_record_is_frozen_and_forbids_extra_fields() -> None:
    failure = FailureRecord(code="everweb.input.invalid", message="Rejected")

    with pytest.raises(ValidationError):
        setattr(failure, "message", "Changed")

    with pytest.raises(ValidationError):
        FailureRecord.model_validate(
            {
                "code": "everweb.input.invalid",
                "message": "Rejected",
                "status": "FAIL",
            }
        )
