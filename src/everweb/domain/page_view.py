"""W1-003 PageView slice: identities, epoch refs, targets, protected state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _PageViewValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PageIdentity(_PageViewValue):
    """Identity of one browser page."""

    page_id: str
    opener_page_id: str | None
    current_url: str
    is_active: bool


class FrameIdentity(_PageViewValue):
    """Identity of one frame within a page."""

    frame_id: str
    page_id: str
    parent_frame_id: str | None
    origin: str | None


class InteractiveTarget(_PageViewValue):
    """Epoch-scoped interactive target derived from AX and/or DOM."""

    ref: str
    role: str
    name: str | None
    href: str | None = None
    selected: bool | None = None
    checked: bool | None = None
    expanded: bool | None = None
    disabled: bool | None = None
    frame_id: str
    source: Literal["ax", "dom"]
    bbox: tuple[float, float, float, float] | None = None


class ProtectedState(_PageViewValue):
    """Never-trimmed PageView subset for W1-003."""

    current_page: PageIdentity
    current_frame: FrameIdentity
    missing_fields: tuple[str, ...] = ()
    active_filter_labels: tuple[str, ...] = ()


class PageView(_PageViewValue):
    """Minimal PageView for AX + DOM perceive (not full §12.5)."""

    page_identity: PageIdentity
    frame_identity: FrameIdentity
    current_url: str
    title: str
    page_signature: str
    snapshot_epoch: int = Field(ge=0)
    interactive_targets: tuple[InteractiveTarget, ...]
    open_pages: tuple[PageIdentity, ...]
    visible_headings: tuple[str, ...]
    protected_state: ProtectedState
    unknowns: tuple[str, ...]
