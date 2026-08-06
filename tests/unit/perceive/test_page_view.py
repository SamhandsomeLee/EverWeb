"""Unit tests for PageView assembly from AX + DOM fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from everweb.domain import FrameIdentity, PageIdentity
from everweb.perceive import build_page_view, compute_page_signature

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def _load_list(name: str) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        json.loads((FIXTURES / name).read_text(encoding="utf-8")),
    )


def _identities() -> tuple[PageIdentity, FrameIdentity]:
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
    return page, frame


def test_build_page_view_includes_identities_targets_and_protected_state() -> None:
    page, frame = _identities()
    view = build_page_view(
        page_identity=page,
        frame_identity=frame,
        title="Simple Form",
        snapshot_epoch=3,
        ax_root=_load("simple_form_ax.json"),
        dom_nodes=_load_list("simple_form_dom.json"),
        missing_fields=("email",),
        active_filter_labels=("year=2024",),
    )

    assert view.page_identity == page
    assert view.frame_identity == frame
    assert view.protected_state.current_page == page
    assert view.protected_state.current_frame == frame
    assert view.protected_state.missing_fields == ("email",)
    assert view.protected_state.active_filter_labels == ("year=2024",)
    assert view.visible_headings == ("Contact",)
    assert view.snapshot_epoch == 3
    roles = [target.role for target in view.interactive_targets]
    assert roles == ["textbox", "button", "link", "checkbox"]
    assert view.interactive_targets[-1].source == "dom"
    assert view.interactive_targets[-1].ref == "3:4"
    assert "ax_empty" not in view.unknowns


def test_dom_does_not_override_matching_ax_target() -> None:
    page, frame = _identities()
    view = build_page_view(
        page_identity=page,
        frame_identity=frame,
        title="Wrapped",
        snapshot_epoch=1,
        ax_root=_load("wrapped_controls_ax.json"),
        dom_nodes=_load_list("wrapped_controls_dom.json"),
    )

    save_targets = [target for target in view.interactive_targets if target.name == "Save"]
    assert len(save_targets) == 1
    assert save_targets[0].source == "ax"
    assert save_targets[0].ref == "1:1"
    token = [target for target in view.interactive_targets if target.name == "Token"]
    assert len(token) == 1
    assert token[0].source == "dom"


def test_page_signature_is_stable() -> None:
    first = compute_page_signature(
        current_url="https://example.com/form",
        title="Simple Form",
        snapshot_epoch=3,
    )
    second = compute_page_signature(
        current_url="https://example.com/form",
        title="Simple Form",
        snapshot_epoch=3,
    )
    assert first == second
    assert len(first) == 64


def test_empty_ax_marks_unknown() -> None:
    page, frame = _identities()
    view = build_page_view(
        page_identity=page,
        frame_identity=frame,
        title="Empty",
        snapshot_epoch=0,
        ax_root=None,
        dom_nodes=None,
    )
    assert view.interactive_targets == ()
    assert view.unknowns == ("ax_empty",)
