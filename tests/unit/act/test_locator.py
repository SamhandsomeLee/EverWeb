"""Unit tests for PageView ref → role+name locator resolution."""

from __future__ import annotations

import pytest

from everweb.act import StaleRefError, TargetNotFoundError, resolve_role_name_locator
from everweb.domain import (
    FrameIdentity,
    InteractiveTarget,
    PageIdentity,
    PageView,
    ProtectedState,
)


def _page_view(*, epoch: int = 3) -> PageView:
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
        page_signature="abc",
        snapshot_epoch=epoch,
        interactive_targets=(
            InteractiveTarget(
                ref=f"{epoch}:1",
                role="button",
                name="Submit",
                frame_id="frame-main",
                source="ax",
            ),
        ),
        open_pages=(page,),
        visible_headings=(),
        protected_state=ProtectedState(current_page=page, current_frame=frame),
        unknowns=(),
    )


def test_resolve_role_name_locator_hits_target() -> None:
    locator = resolve_role_name_locator(_page_view(), "3:1")
    assert locator.strategy == "role_name"
    assert locator.role == "button"
    assert locator.name == "Submit"
    assert locator.frame_id == "frame-main"
    assert locator.ref == "3:1"


def test_resolve_missing_ref_is_target_not_found() -> None:
    with pytest.raises(TargetNotFoundError):
        resolve_role_name_locator(_page_view(), "3:99")


def test_resolve_epoch_mismatch_is_stale_ref() -> None:
    with pytest.raises(StaleRefError):
        resolve_role_name_locator(_page_view(epoch=3), "2:1")
