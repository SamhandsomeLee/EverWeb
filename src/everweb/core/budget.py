"""Pure budget facts and three-line assessment."""

from __future__ import annotations

import math
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

PositiveInteger = Annotated[int, Field(gt=0)]
NonNegativeInteger = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]


class BudgetAssessment(BaseModel):
    """Immutable resource facts calculated from one usage snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    remaining_official_steps: NonNegativeInteger
    remaining_model_calls: NonNegativeInteger
    remaining_wall_clock_s: NonNegativeFloat | None
    convergence_line_reached: bool
    seal_line_reached: bool
    hard_stop_line_reached: bool
    model_calls_exhausted: bool


class Budget(BaseModel):
    """Configured task limits with pure three-line evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_official_steps: PositiveInteger
    max_model_calls: PositiveInteger
    task_wall_clock_s: PositiveInteger | None
    convergence_step_ratio: float = Field(default=0.20, gt=0.0, lt=1.0)
    seal_steps_remaining: NonNegativeInteger = 8
    emergency_emit_reserve_s: NonNegativeInteger = 20
    serialize_reserve_s: NonNegativeInteger = 10

    @field_validator("convergence_step_ratio", mode="before")
    @classmethod
    def _require_float_ratio(cls, value: Any) -> Any:
        if type(value) is not float:
            raise ValueError("convergence_step_ratio must be a float")
        if not math.isfinite(value):
            raise ValueError("convergence_step_ratio must be finite")
        return value

    def assess(
        self,
        *,
        official_steps_used: int,
        model_calls_used: int,
        elapsed_s: float,
    ) -> BudgetAssessment:
        """Return budget-line facts without causing runtime side effects."""

        self._require_non_negative_int(
            "official_steps_used",
            official_steps_used,
        )
        self._require_non_negative_int(
            "model_calls_used",
            model_calls_used,
        )
        self._require_non_negative_float("elapsed_s", elapsed_s)

        remaining_steps = max(
            self.max_official_steps - official_steps_used,
            0,
        )
        remaining_model_calls = max(
            self.max_model_calls - model_calls_used,
            0,
        )
        remaining_wall_clock_s = (
            None
            if self.task_wall_clock_s is None
            else max(float(self.task_wall_clock_s) - elapsed_s, 0.0)
        )

        convergence_reached = (
            remaining_steps / self.max_official_steps
            < self.convergence_step_ratio
        )
        wall_clock_reserve_s = (
            self.emergency_emit_reserve_s + self.serialize_reserve_s
        )
        seal_reached = (
            remaining_steps < self.seal_steps_remaining
            or (
                remaining_wall_clock_s is not None
                and remaining_wall_clock_s <= wall_clock_reserve_s
            )
        )
        hard_stop_reached = remaining_steps == 0 or (
            remaining_wall_clock_s is not None
            and remaining_wall_clock_s == 0.0
        )

        return BudgetAssessment(
            remaining_official_steps=remaining_steps,
            remaining_model_calls=remaining_model_calls,
            remaining_wall_clock_s=remaining_wall_clock_s,
            convergence_line_reached=convergence_reached,
            seal_line_reached=seal_reached,
            hard_stop_line_reached=hard_stop_reached,
            model_calls_exhausted=remaining_model_calls == 0,
        )

    @staticmethod
    def _require_non_negative_int(name: str, value: int) -> None:
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative int")

    @staticmethod
    def _require_non_negative_float(name: str, value: float) -> None:
        if (
            type(value) is not float
            or not math.isfinite(value)
            or value < 0.0
        ):
            raise ValueError(f"{name} must be a finite non-negative float")
