"""Unit tests for typed action facts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from everweb.domain import ActionKind, TypedAction

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


def test_typed_action_has_only_minimal_fields_and_round_trips() -> None:
    action = TypedAction(action_id="action-001", kind=ActionKind.CLICK)

    assert set(TypedAction.model_fields) == {"action_id", "kind"}
    assert TypedAction.model_validate_json(action.model_dump_json()) == action


def test_typed_action_is_strict_and_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TypedAction.model_validate({"action_id": 1, "kind": ActionKind.CLICK})

    with pytest.raises(ValidationError):
        TypedAction.model_validate({"action_id": "action-001", "kind": "click"})

    with pytest.raises(ValidationError):
        TypedAction.model_validate(
            {
                "action_id": "action-001",
                "kind": ActionKind.CLICK,
                "locator": "#submit",
            }
        )


def test_typed_action_is_frozen() -> None:
    action = TypedAction(action_id="action-001", kind=ActionKind.CLICK)

    with pytest.raises(ValidationError):
        setattr(action, "kind", ActionKind.TYPE)
