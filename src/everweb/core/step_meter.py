"""Single authoritative boundary for task step accounting."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import Field

from everweb.domain import ActionReceipt, Receipt, TypedAction

NonNegativeInteger = Annotated[int, Field(ge=0)]


class StepAccountingMode(StrEnum):
    """Available local and template-owned accounting modes."""

    ITERATION_BASED = "iteration_based"
    ACTION_BASED = "action_based"
    OFFICIAL_ADAPTER = "official_adapter"


class PendingStepSemanticsError(ValueError):
    """The selected mode has no approved counting policy."""


class InvalidStepDeltaError(ValueError):
    """A counting policy returned an invalid step delta."""


class StepCountPolicy(Protocol):
    """Injected authority that maps an executed action to a step delta."""

    def count(self, action: TypedAction, receipt: ActionReceipt) -> int: ...


class ActionBasedStepCountPolicy:
    """Local approximation that counts each recorded browser action once."""

    def count(self, action: TypedAction, receipt: ActionReceipt) -> int:
        return 1


class StepReceipt(Receipt):
    """Immutable fact emitted by the sole step-accounting entry point."""

    action_id: str
    mode: StepAccountingMode
    step_delta: NonNegativeInteger
    recorded_total: NonNegativeInteger


class StepMeter:
    """Accumulate step deltas only through record()."""

    def __init__(
        self,
        *,
        mode: StepAccountingMode,
        policy: StepCountPolicy | None = None,
    ) -> None:
        if not isinstance(mode, StepAccountingMode):
            raise TypeError("mode must be a StepAccountingMode")
        if policy is None:
            if mode is not StepAccountingMode.ACTION_BASED:
                raise PendingStepSemanticsError(
                    f"{mode.value} requires an explicitly injected policy"
                )
            policy = ActionBasedStepCountPolicy()

        self._mode = mode
        self._policy = policy
        self._recorded_total = 0

    @property
    def mode(self) -> StepAccountingMode:
        return self._mode

    @property
    def recorded_total(self) -> int:
        return self._recorded_total

    def record(
        self,
        action: TypedAction,
        receipt: ActionReceipt,
    ) -> StepReceipt:
        """Record one executed action using the configured authority."""

        delta = self._policy.count(action, receipt)
        if type(delta) is not int or delta < 0:
            raise InvalidStepDeltaError(
                "step policy must return a non-negative int"
            )

        self._recorded_total += delta
        return StepReceipt(
            action_id=action.action_id,
            mode=self._mode,
            step_delta=delta,
            recorded_total=self._recorded_total,
        )
