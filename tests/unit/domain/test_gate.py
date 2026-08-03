"""Unit tests for the minimal GateReceipt placeholder."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from everweb.domain import GateReceipt


def test_gate_receipt_is_strict_frozen_and_round_trips() -> None:
    receipt = GateReceipt(accepted=True)

    assert set(GateReceipt.model_fields) == {"accepted"}
    assert GateReceipt.model_validate_json(receipt.model_dump_json()) == receipt

    with pytest.raises(ValidationError):
        receipt.accepted = False
    with pytest.raises(ValidationError):
        GateReceipt.model_validate({"accepted": True, "score": 1.0})


@pytest.mark.parametrize("value", [1, "true", None])
def test_gate_receipt_rejects_invalid_or_coerced_accepted(value: Any) -> None:
    with pytest.raises(ValidationError):
        GateReceipt.model_validate({"accepted": value})
