"""Unit tests for typed action facts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from everweb.domain import ActionKind, RoleNameLocator, ScrollMode, TypedAction

EXPECTED_ACTION_KINDS = {
    "CLICK": "click",
    "TYPE": "type",
    "SELECT": "select",
    "CHECK": "check",
    "SCROLL": "scroll",
    "HOVER": "hover",
    "KEYPRESS": "keypress",
    "NAVIGATE": "navigate",
    "BACK": "back",
    "SWITCH_PAGE": "switch_page",
    "SWITCH_FRAME": "switch_frame",
    "WAIT_FOR": "wait_for",
    "TRIGGER_DOWNLOAD": "trigger_download",
}


def test_action_kind_matches_canonical_values() -> None:
    assert {member.name: member.value for member in ActionKind} == EXPECTED_ACTION_KINDS
    assert json.loads(json.dumps(ActionKind.CLICK)) == "click"


def test_typed_action_has_click_type_scroll_fields_and_round_trips() -> None:
    action = TypedAction(
        action_id="action-001",
        kind=ActionKind.TYPE,
        target_ref="3:1",
        text="hello",
        locator=RoleNameLocator(
            role="textbox",
            name="Email",
            frame_id="frame-main",
            ref="3:1",
        ),
    )

    assert set(TypedAction.model_fields) == {
        "action_id",
        "kind",
        "target_ref",
        "text",
        "scroll_mode",
        "locator",
    }
    assert TypedAction.model_validate_json(action.model_dump_json()) == action
    assert ScrollMode.INTO_VIEW.value == "into_view"


def test_typed_action_is_strict_and_forbids_freeform_locator_field() -> None:
    with pytest.raises(ValidationError):
        TypedAction.model_validate({"action_id": 1, "kind": ActionKind.CLICK})

    with pytest.raises(ValidationError):
        TypedAction.model_validate({"action_id": "action-001", "kind": "click"})

    with pytest.raises(ValidationError):
        TypedAction.model_validate(
            {
                "action_id": "action-001",
                "kind": ActionKind.CLICK,
                "css": "#submit",
            }
        )


def test_typed_action_is_frozen() -> None:
    action = TypedAction(action_id="action-001", kind=ActionKind.CLICK)

    with pytest.raises(ValidationError):
        setattr(action, "kind", ActionKind.TYPE)
