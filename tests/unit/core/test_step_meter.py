"""Unit tests for the sole step-accounting entry point."""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from everweb.core import (
    ActionBasedStepCountPolicy,
    InvalidStepDeltaError,
    PendingStepSemanticsError,
    StepAccountingMode,
    StepCountPolicy,
    StepMeter,
    StepReceipt,
)
from everweb.domain import ActionKind, ActionReceipt, TypedAction

EXPECTED_STEP_RECEIPT_FIELDS = {
    "action_id",
    "mode",
    "step_delta",
    "recorded_total",
}


def action(action_id: str = "action-001") -> TypedAction:
    return TypedAction(action_id=action_id, kind=ActionKind.CLICK)


class FixedPolicy:
    def __init__(self, delta: Any) -> None:
        self.delta = delta
        self.calls: list[tuple[TypedAction, ActionReceipt]] = []

    def count(self, action: TypedAction, receipt: ActionReceipt) -> int:
        self.calls.append((action, receipt))
        return cast(int, self.delta)


def test_action_based_mode_counts_each_recorded_action_once() -> None:
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED)

    first = meter.record(action(), ActionReceipt())
    second = meter.record(action("action-002"), ActionReceipt())

    assert first == StepReceipt(
        action_id="action-001",
        mode=StepAccountingMode.ACTION_BASED,
        step_delta=1,
        recorded_total=1,
    )
    assert second.recorded_total == 2
    assert meter.recorded_total == 2
    assert meter.mode is StepAccountingMode.ACTION_BASED


def test_injected_policy_is_the_counting_authority() -> None:
    policy = FixedPolicy(2)
    meter = StepMeter(
        mode=StepAccountingMode.ITERATION_BASED,
        policy=policy,
    )
    recorded_action = action()
    recorded_receipt = ActionReceipt()

    result = meter.record(recorded_action, recorded_receipt)

    assert result.step_delta == 2
    assert result.recorded_total == 2
    assert policy.calls == [(recorded_action, recorded_receipt)]


@pytest.mark.parametrize(
    "mode",
    [
        StepAccountingMode.ITERATION_BASED,
        StepAccountingMode.OFFICIAL_ADAPTER,
    ],
)
def test_pending_modes_require_explicit_policy(
    mode: StepAccountingMode,
) -> None:
    with pytest.raises(PendingStepSemanticsError, match=mode.value):
        StepMeter(mode=mode)


def test_official_adapter_mode_accepts_injected_policy_without_guessing() -> None:
    meter = StepMeter(
        mode=StepAccountingMode.OFFICIAL_ADAPTER,
        policy=FixedPolicy(0),
    )

    receipt = meter.record(action(), ActionReceipt())

    assert receipt.mode is StepAccountingMode.OFFICIAL_ADAPTER
    assert receipt.step_delta == 0
    assert receipt.recorded_total == 0


@pytest.mark.parametrize("delta", [-1, True, 1.0, "1", None])
def test_invalid_policy_delta_is_rejected_without_mutating_total(
    delta: Any,
) -> None:
    meter = StepMeter(
        mode=StepAccountingMode.ACTION_BASED,
        policy=FixedPolicy(delta),
    )

    with pytest.raises(InvalidStepDeltaError):
        meter.record(action(), ActionReceipt())

    assert meter.recorded_total == 0


def test_mode_requires_enum_instead_of_coercing_string() -> None:
    with pytest.raises(TypeError):
        StepMeter(mode="action_based")  # type: ignore[arg-type]


def test_step_receipt_contract_is_strict_frozen_and_round_trips() -> None:
    receipt = StepMeter(mode=StepAccountingMode.ACTION_BASED).record(
        action(),
        ActionReceipt(),
    )

    assert set(StepReceipt.model_fields) == EXPECTED_STEP_RECEIPT_FIELDS
    assert StepReceipt.model_validate_json(receipt.model_dump_json()) == receipt

    with pytest.raises(ValidationError):
        setattr(receipt, "recorded_total", 2)
    with pytest.raises(ValidationError):
        StepReceipt.model_validate(
            {
                **receipt.model_dump(),
                "step_delta": "1",
            }
        )
    with pytest.raises(ValidationError):
        StepReceipt.model_validate(
            {
                **receipt.model_dump(),
                "official_status": "SUCCESS",
            }
        )


def test_record_is_the_only_public_mutating_method() -> None:
    public_methods = {
        name
        for name, value in vars(StepMeter).items()
        if not name.startswith("_") and callable(value)
    }
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED)

    assert public_methods == {"record"}
    with pytest.raises(AttributeError):
        setattr(meter, "recorded_total", 10)
    with pytest.raises(AttributeError):
        setattr(meter, "mode", StepAccountingMode.ITERATION_BASED)


def test_default_policy_conforms_to_static_protocol() -> None:
    policy: StepCountPolicy = ActionBasedStepCountPolicy()

    assert policy.count(action(), ActionReceipt()) == 1
