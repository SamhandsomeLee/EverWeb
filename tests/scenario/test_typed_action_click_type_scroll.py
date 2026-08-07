"""Scenario: click/type/scroll via TypedActionExecutor + FakeBrowser."""

from __future__ import annotations

import ast
from pathlib import Path

from everweb.act import TypedActionExecutor
from everweb.core import MeteredBrowser, StepAccountingMode, StepMeter
from everweb.domain import (
    ActionKind,
    FrameIdentity,
    InteractiveTarget,
    PageIdentity,
    PageView,
    ProtectedState,
    TypedAction,
)
from everweb.harness import FakeBrowser

ACT_ROOT = Path(__file__).resolve().parents[2] / "src" / "everweb" / "act"
ADAPTER_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "everweb"
    / "adapters"
    / "playwright_browser"
)


def _page_view() -> PageView:
    page = PageIdentity(
        page_id="page-1",
        opener_page_id=None,
        current_url="https://example.com/form",
        is_active=True,
    )
    frame = FrameIdentity(
        frame_id="frame-main",
        page_id="page-1",
        parent_frame_id=None,
        origin="https://example.com",
    )
    return PageView(
        page_identity=page,
        frame_identity=frame,
        current_url=page.current_url,
        title="Form",
        page_signature="sig",
        snapshot_epoch=2,
        interactive_targets=(
            InteractiveTarget(
                ref="2:1",
                role="textbox",
                name="Email",
                frame_id="frame-main",
                source="ax",
            ),
            InteractiveTarget(
                ref="2:2",
                role="button",
                name="Submit",
                frame_id="frame-main",
                source="ax",
            ),
            InteractiveTarget(
                ref="2:3",
                role="link",
                name="Docs",
                frame_id="frame-main",
                source="ax",
            ),
        ),
        open_pages=(page,),
        visible_headings=("Form",),
        protected_state=ProtectedState(current_page=page, current_frame=frame),
        unknowns=(),
    )


def test_click_type_scroll_receipts_are_auditable() -> None:
    inner = FakeBrowser()
    meter = StepMeter(mode=StepAccountingMode.ACTION_BASED)
    browser = MeteredBrowser(inner, meter)
    executor = TypedActionExecutor()
    page_view = _page_view()

    typed = executor.execute(
        browser,
        page_view,
        TypedAction(
            action_id="type-1",
            kind=ActionKind.TYPE,
            target_ref="2:1",
            text="a@example.com",
        ),
    )
    clicked = executor.execute(
        browser,
        page_view,
        TypedAction(action_id="click-1", kind=ActionKind.CLICK, target_ref="2:2"),
    )
    scrolled = executor.execute(
        browser,
        page_view,
        TypedAction(action_id="scroll-1", kind=ActionKind.SCROLL, target_ref="2:3"),
    )

    assert typed.ok and clicked.ok and scrolled.ok
    assert typed.locator_strategy == "role_name"
    assert typed.locator_role == "textbox"
    assert typed.locator_name == "Email"
    assert typed.target_ref == "2:1"
    assert clicked.locator_role == "button"
    assert scrolled.locator_role == "link"
    assert meter.recorded_total == 3
    assert [entry.op for entry in inner.calls if entry.op == "execute"] == [
        "execute",
        "execute",
        "execute",
    ]


def test_act_and_adapter_forbid_evaluate_js() -> None:
    for root in (ACT_ROOT, ADAPTER_ROOT):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    assert "evaluate" not in ast.dump(node.func).lower()
                if isinstance(node, ast.Attribute) and node.attr == "evaluate":
                    raise AssertionError(f"{path} references .evaluate")
