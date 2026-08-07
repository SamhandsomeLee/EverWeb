"""Typed action facts owned by the domain layer."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class ScrollMode(StrEnum):
    """Minimal scroll modes for W1-004."""

    INTO_VIEW = "into_view"


class SideEffectRisk(StrEnum):
    """§13.2 side-effect risk classes for Policy auditing."""

    READ_ONLY = "read_only"
    REVERSIBLE_UI = "reversible_ui"
    NETWORK_READ = "network_read"
    POTENTIAL_WRITE = "potential_write"
    CONFIRMED_WRITE = "confirmed_write"
    UNKNOWN = "unknown"


class RoleNameLocator(BaseModel):
    """Auditable §13.3 first-tier locator: role + accessible name."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    strategy: Literal["role_name"] = "role_name"
    role: str = Field(min_length=1)
    name: str | None = None
    frame_id: str = Field(min_length=1)
    ref: str = Field(min_length=1)


class TypedAction(BaseModel):
    """Typed action with minimal click/type/scroll parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    action_id: str
    kind: ActionKind
    target_ref: str | None = None
    text: str | None = None
    scroll_mode: ScrollMode | None = None
    locator: RoleNameLocator | None = None
