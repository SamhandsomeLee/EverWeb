"""Unit tests for the receipt contract base."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from everweb.domain import Receipt


class SampleReceipt(Receipt):
    receipt_id: str
    accepted: bool


def test_receipt_subclass_round_trips() -> None:
    receipt = SampleReceipt(receipt_id="receipt-001", accepted=True)

    assert SampleReceipt.model_validate_json(receipt.model_dump_json()) == receipt


def test_receipt_subclass_inherits_strict_frozen_contract() -> None:
    receipt = SampleReceipt(receipt_id="receipt-001", accepted=True)

    with pytest.raises(ValidationError):
        setattr(receipt, "accepted", False)

    with pytest.raises(ValidationError):
        SampleReceipt.model_validate(
            {
                "receipt_id": "receipt-001",
                "accepted": True,
                "status": "SUCCESS",
            }
        )

    with pytest.raises(ValidationError):
        SampleReceipt.model_validate(
            {"receipt_id": "receipt-001", "accepted": "true"}
        )
