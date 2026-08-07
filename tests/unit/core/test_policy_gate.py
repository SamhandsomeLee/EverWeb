"""Unit tests: PolicyGate rejects model overreach (INV-9 / INV-10)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from everweb.core import (
    POLICY_REJECTED,
    Budget,
    MeteredBrowser,
    PolicyDecision,
    PolicyGate,
    PolicyGuardedBrowser,
    SideEffectRisk,
    StepAccountingMode,
    StepMeter,
)
from everweb.domain import ActionKind, ActionReceipt, RoleNameLocator, TypedAction
from everweb.harness import FakeBrowser
from everweb.ports import BrowserPort

SRC_ROOT = Path(__file__).resolve().parents[3] / "src" / "everweb"


def _click(**kwargs: object) -> TypedAction:
    defaults: dict[str, object] = {
        "action_id": "a1",
        "kind": ActionKind.CLICK,
        "target_ref": "1:1",
    }
    defaults.update(kwargs)
    return TypedAction(**defaults)  # type: ignore[arg-type]


def test_policy_gate_allows_click_type_scroll() -> None:
    gate = PolicyGate()
    locator = RoleNameLocator(
        role="button", name="Go", frame_id="f1", ref="1:1"
    )
    click = gate.evaluate(_click(locator=locator))
    typed = gate.evaluate(
        TypedAction(
            action_id="a2",
            kind=ActionKind.TYPE,
            target_ref="1:2",
            text="hi",
            locator=RoleNameLocator(
                role="textbox", name="Q", frame_id="f1", ref="1:2"
            ),
        )
    )
    scroll = gate.evaluate(
        TypedAction(action_id="a3", kind=ActionKind.SCROLL, target_ref="1:3")
    )
    assert click.allowed and typed.allowed and scroll.allowed
    assert click.side_effect_risk is SideEffectRisk.REVERSIBLE_UI
    assert typed.side_effect_risk is SideEffectRisk.REVERSIBLE_UI
    assert scroll.side_effect_risk is SideEffectRisk.READ_ONLY


def test_policy_gate_rejects_unsupported_kinds_and_missing_target() -> None:
    gate = PolicyGate()
    hover = gate.evaluate(
        TypedAction(action_id="a1", kind=ActionKind.HOVER, target_ref="1:1")
    )
    navigate = gate.evaluate(TypedAction(action_id="a1", kind=ActionKind.NAVIGATE))
    no_ref = gate.evaluate(TypedAction(action_id="a1", kind=ActionKind.CLICK))
    assert hover.allowed is False and hover.error_code == POLICY_REJECTED
    assert navigate.allowed is False and navigate.error_code == POLICY_REJECTED
    assert no_ref.allowed is False and no_ref.error_code == POLICY_REJECTED


def test_policy_gate_rejects_missing_text_and_bad_scroll_mode() -> None:
    gate = PolicyGate()
    no_text = gate.evaluate(
        TypedAction(action_id="a1", kind=ActionKind.TYPE, target_ref="1:1")
    )
    assert no_text.allowed is False
    # ScrollMode only has INTO_VIEW; use model_construct for illegal mode.
    bad_scroll = TypedAction.model_construct(
        action_id="a1",
        kind=ActionKind.SCROLL,
        target_ref="1:1",
        scroll_mode="page_down",
        text=None,
        locator=None,
    )
    denied = gate.evaluate(bad_scroll)
    assert denied.allowed is False
    assert denied.error_code == POLICY_REJECTED


def test_policy_gate_rejects_non_role_name_locator() -> None:
    gate = PolicyGate()
    action = TypedAction.model_construct(
        action_id="a1",
        kind=ActionKind.CLICK,
        target_ref="1:1",
        text=None,
        scroll_mode=None,
        locator=SimpleNamespace(strategy="css", role="button", name="x"),
    )
    decision = gate.evaluate(action)
    assert decision.allowed is False
    assert "role_name" in decision.reason


def test_policy_gate_does_not_accept_or_mutate_budget() -> None:
    signature = inspect.signature(PolicyGate.evaluate)
    assert "budget" not in signature.parameters
    assert "Budget" not in signature.parameters

    budget = Budget(max_official_steps=10, max_model_calls=5, task_wall_clock_s=60)
    before = budget.model_dump(mode="json")
    PolicyGate().evaluate(_click())
    assert budget.model_dump(mode="json") == before
    with pytest.raises(Exception):
        setattr(budget, "max_official_steps", 99)


def test_policy_decision_has_no_status_fields() -> None:
    fields = set(PolicyDecision.model_fields)
    assert "status" not in fields
    assert "mapped_status" not in fields
    source = (SRC_ROOT / "core" / "policy.py").read_text(encoding="utf-8")
    assert "map_status" not in source
    assert "competition" not in source


def test_policy_guarded_browser_denies_without_inner_execute() -> None:
    inner = FakeBrowser()
    browser = PolicyGuardedBrowser(inner, PolicyGate())
    assert isinstance(browser, BrowserPort)

    receipt = browser.execute(
        TypedAction(action_id="a1", kind=ActionKind.HOVER, target_ref="1:1")
    )
    assert receipt.ok is False
    assert receipt.error_code == POLICY_REJECTED
    assert [c.op for c in inner.calls if c.op == "execute"] == []
    assert browser.last_decision is not None
    assert browser.last_decision.allowed is False


def test_policy_guarded_deny_does_not_count_steps() -> None:
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED)
    inner = FakeBrowser()
    browser = PolicyGuardedBrowser(MeteredBrowser(inner, meter), PolicyGate())

    receipt = browser.execute(
        TypedAction(action_id="a1", kind=ActionKind.NAVIGATE)
    )
    assert receipt.ok is False
    assert meter.recorded_total == 0
    assert [c.op for c in inner.calls if c.op == "execute"] == []


def test_policy_guarded_allow_passes_through() -> None:
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED)
    inner = FakeBrowser()
    browser = PolicyGuardedBrowser(MeteredBrowser(inner, meter), PolicyGate())

    receipt = browser.execute(_click())
    assert isinstance(receipt, ActionReceipt)
    assert receipt.ok is True
    assert meter.recorded_total == 1
    assert browser.last_decision is not None
    assert browser.last_decision.allowed is True


def test_single_policy_gate_class_in_production() -> None:
    classes: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "PolicyGate":
                classes.append(path.relative_to(SRC_ROOT.parent).as_posix())
    assert classes == ["everweb/core/policy.py"]
