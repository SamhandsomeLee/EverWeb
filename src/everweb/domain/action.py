"""Typed action facts owned by the domain layer."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ActionKind(StrEnum):
    """Closed set of actions a model may propose."""

    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    CHECK = "check"
    SCROLL = "scroll"
    HOVER = "hover"
    KEYPRESS = "keypress"
    NAVIGATE = "navigate"
    BACK = "back"
    SWITCH_PAGE = "switch_page"
    SWITCH_FRAME = "switch_frame"
    WAIT_FOR = "wait_for"
    TRIGGER_DOWNLOAD = "trigger_download"


class TypedAction(BaseModel):
    """Minimal typed action pending per-kind parameter contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    action_id: str
    kind: ActionKind
