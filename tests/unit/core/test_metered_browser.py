"""Unit tests for MeteredBrowser execute→StepMeter coupling."""

from __future__ import annotations

import pytest

from everweb.core import (
    InvalidStepDeltaError,
    MeteredBrowser,
    StepAccountingMode,
    StepMeter,
)
from everweb.domain import (
    ActionKind,
    ActionReceipt,
    CaptureRequest,
    ObservationRequest,
    Task,
    TypedAction,
)
from everweb.harness import FakeBrowser
from everweb.ports import BrowserPort


def test_metered_browser_implements_browser_port() -> None:
    browser = MeteredBrowser(
        FakeBrowser(),
        StepMeter(mode=StepAccountingMode.ACTION_BASED),
    )
    assert isinstance(browser, BrowserPort)


def test_execute_records_one_step_per_action() -> None:
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED)
    browser = MeteredBrowser(FakeBrowser(), meter)

    first = browser.execute(TypedAction(action_id="a1", kind=ActionKind.CLICK))
    second = browser.execute(TypedAction(action_id="a2", kind=ActionKind.TYPE, text="x"))

    assert isinstance(first, ActionReceipt)
    assert isinstance(second, ActionReceipt)
    assert meter.recorded_total == 2
    assert browser.last_step_receipt is not None
    assert browser.last_step_receipt.action_id == "a2"
    assert browser.last_step_receipt.recorded_total == 2


def test_failed_receipt_still_records() -> None:
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED)
    browser = MeteredBrowser(
        FakeBrowser(
            script={
                "execute": (
                    ActionReceipt(
                        action_id="a1",
                        kind=ActionKind.CLICK,
                        ok=False,
                        error_code="MISSING_LOCATOR",
                    ),
                )
            }
        ),
        meter,
    )

    receipt = browser.execute(TypedAction(action_id="a1", kind=ActionKind.CLICK))
    assert receipt.ok is False
    assert meter.recorded_total == 1


def test_non_execute_methods_do_not_count_steps() -> None:
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED)
    browser = MeteredBrowser(FakeBrowser(), meter)

    browser.capabilities()
    browser.create_task_session(Task())
    browser.observe(ObservationRequest())
    browser.capture(CaptureRequest())
    browser.close_task_session()

    assert meter.recorded_total == 0
    assert browser.last_step_receipt is None


def test_invalid_step_delta_propagates_after_inner_execute() -> None:
    class BadPolicy:
        def count(self, action: TypedAction, receipt: ActionReceipt) -> int:
            return -1

    inner = FakeBrowser()
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED, policy=BadPolicy())
    browser = MeteredBrowser(inner, meter)

    with pytest.raises(InvalidStepDeltaError):
        browser.execute(TypedAction(action_id="a1", kind=ActionKind.CLICK))

    assert len([c for c in inner.calls if c.op == "execute"]) == 1
    assert meter.recorded_total == 0


def test_rejects_non_browser_port() -> None:
    with pytest.raises(TypeError, match="BrowserPort"):
        MeteredBrowser(object(), StepMeter(mode=StepAccountingMode.ACTION_BASED))  # type: ignore[arg-type]
