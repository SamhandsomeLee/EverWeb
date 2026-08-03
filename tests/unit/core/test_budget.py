"""Unit tests for pure task-budget assessment."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from everweb.core import Budget, BudgetAssessment

EXPECTED_BUDGET_FIELDS = {
    "max_official_steps",
    "max_model_calls",
    "task_wall_clock_s",
    "convergence_step_ratio",
    "seal_steps_remaining",
    "emergency_emit_reserve_s",
    "serialize_reserve_s",
}


def budget(*, task_wall_clock_s: int | None = None) -> Budget:
    return Budget(
        max_official_steps=100,
        max_model_calls=60,
        task_wall_clock_s=task_wall_clock_s,
    )


def assess(
    value: Budget,
    *,
    official_steps_used: int,
    model_calls_used: int = 0,
    elapsed_s: float = 0.0,
) -> BudgetAssessment:
    return value.assess(
        official_steps_used=official_steps_used,
        model_calls_used=model_calls_used,
        elapsed_s=elapsed_s,
    )


def test_budget_schema_defaults_round_trip_and_freezing() -> None:
    value = budget()

    assert set(Budget.model_fields) == EXPECTED_BUDGET_FIELDS
    assert value.convergence_step_ratio == 0.20
    assert value.seal_steps_remaining == 8
    assert value.emergency_emit_reserve_s == 20
    assert value.serialize_reserve_s == 10
    assert value.task_wall_clock_s is None
    assert Budget.model_validate_json(value.model_dump_json()) == value

    with pytest.raises(ValidationError):
        setattr(value, "max_official_steps", 200)
    with pytest.raises(ValidationError):
        Budget.model_validate({**value.model_dump(), "guessed_limit": 1})


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("max_official_steps", 0),
        ("max_official_steps", True),
        ("max_model_calls", -1),
        ("task_wall_clock_s", 0),
        ("task_wall_clock_s", "600"),
        ("convergence_step_ratio", 1),
        ("convergence_step_ratio", 0.0),
        ("convergence_step_ratio", 1.0),
        ("convergence_step_ratio", float("nan")),
        ("seal_steps_remaining", -1),
        ("emergency_emit_reserve_s", -1),
        ("serialize_reserve_s", -1),
    ],
)
def test_budget_rejects_invalid_or_coerced_configuration(
    field_name: str,
    invalid_value: Any,
) -> None:
    values: dict[str, Any] = {
        "max_official_steps": 100,
        "max_model_calls": 60,
        "task_wall_clock_s": None,
        field_name: invalid_value,
    }

    with pytest.raises(ValidationError):
        Budget.model_validate(values)


def test_convergence_line_uses_strict_remaining_ratio() -> None:
    value = budget()

    at_boundary = assess(value, official_steps_used=80)
    below_boundary = assess(value, official_steps_used=81)

    assert at_boundary.remaining_official_steps == 20
    assert at_boundary.convergence_line_reached is False
    assert below_boundary.remaining_official_steps == 19
    assert below_boundary.convergence_line_reached is True


def test_seal_line_uses_strict_step_threshold() -> None:
    value = budget()

    at_boundary = assess(value, official_steps_used=92)
    below_boundary = assess(value, official_steps_used=93)

    assert at_boundary.remaining_official_steps == 8
    assert at_boundary.seal_line_reached is False
    assert below_boundary.remaining_official_steps == 7
    assert below_boundary.seal_line_reached is True


def test_wall_clock_reserve_and_hard_stop_lines() -> None:
    value = budget(task_wall_clock_s=100)

    before_reserve = assess(
        value,
        official_steps_used=0,
        elapsed_s=69.0,
    )
    at_reserve = assess(
        value,
        official_steps_used=0,
        elapsed_s=70.0,
    )
    exhausted = assess(
        value,
        official_steps_used=0,
        elapsed_s=100.0,
    )

    assert before_reserve.remaining_wall_clock_s == 31.0
    assert before_reserve.seal_line_reached is False
    assert at_reserve.remaining_wall_clock_s == 30.0
    assert at_reserve.seal_line_reached is True
    assert at_reserve.hard_stop_line_reached is False
    assert exhausted.remaining_wall_clock_s == 0.0
    assert exhausted.hard_stop_line_reached is True


def test_unknown_wall_clock_does_not_invent_time_lines() -> None:
    assessment = assess(
        budget(),
        official_steps_used=0,
        elapsed_s=10_000.0,
    )

    assert assessment.remaining_wall_clock_s is None
    assert assessment.seal_line_reached is False
    assert assessment.hard_stop_line_reached is False


def test_model_call_exhaustion_is_separate_from_hard_stop() -> None:
    assessment = assess(
        budget(),
        official_steps_used=0,
        model_calls_used=60,
    )

    assert assessment.remaining_model_calls == 0
    assert assessment.model_calls_exhausted is True
    assert assessment.hard_stop_line_reached is False


def test_excess_usage_clamps_remaining_values_to_zero() -> None:
    assessment = assess(
        budget(task_wall_clock_s=100),
        official_steps_used=101,
        model_calls_used=61,
        elapsed_s=101.0,
    )

    assert assessment.remaining_official_steps == 0
    assert assessment.remaining_model_calls == 0
    assert assessment.remaining_wall_clock_s == 0.0
    assert assessment.hard_stop_line_reached is True


@pytest.mark.parametrize(
    "usage",
    [
        {
            "official_steps_used": -1,
            "model_calls_used": 0,
            "elapsed_s": 0.0,
        },
        {
            "official_steps_used": True,
            "model_calls_used": 0,
            "elapsed_s": 0.0,
        },
        {
            "official_steps_used": 0,
            "model_calls_used": 1.0,
            "elapsed_s": 0.0,
        },
        {
            "official_steps_used": 0,
            "model_calls_used": 0,
            "elapsed_s": 0,
        },
        {
            "official_steps_used": 0,
            "model_calls_used": 0,
            "elapsed_s": float("inf"),
        },
        {
            "official_steps_used": 0,
            "model_calls_used": 0,
            "elapsed_s": -0.1,
        },
    ],
)
def test_assessment_rejects_invalid_usage_inputs(
    usage: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        budget().assess(**usage)


def test_assessment_is_frozen_and_round_trips() -> None:
    assessment = assess(budget(), official_steps_used=1)

    assert (
        BudgetAssessment.model_validate_json(assessment.model_dump_json())
        == assessment
    )
    with pytest.raises(ValidationError):
        setattr(assessment, "remaining_official_steps", 0)
