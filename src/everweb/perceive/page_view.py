"""Assemble W1-003 PageView from AX + minimal DOM facts."""

from everweb.domain.page_view import PageIdentity


from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from everweb.domain import (
    FrameIdentity,
    InteractiveTarget,
    PageIdentity,
    PageView,
    ProtectedState,
)
from everweb.perceive.ax_snapshot import normalize_ax_snapshot
from everweb.perceive.dom_extract import extract_dom_targets


def compute_page_signature(*, current_url: str, title: str, snapshot_epoch: int) -> str:
    payload = f"{current_url}\n{title}\n{snapshot_epoch}".encode()
    return hashlib.sha256(payload).hexdigest()


def _target_key(target: InteractiveTarget) -> tuple[str, str | None, str]:
    return (target.role, target.name, target.frame_id)


def merge_targets(
    ax_targets: Sequence[InteractiveTarget],
    dom_targets: Sequence[InteractiveTarget],
) -> tuple[InteractiveTarget, ...]:
    """Prefer AX targets; append DOM targets that fill role/name/frame gaps."""

    merged: list[InteractiveTarget] = list(ax_targets)
    seen = {_target_key(target) for target in ax_targets}
    for target in dom_targets:
        key = _target_key(target)
        if key in seen:
            continue
        merged.append(target)
        seen.add(key)
    return tuple(merged)


def build_page_view(
    *,
    page_identity: PageIdentity,
    frame_identity: FrameIdentity,
    title: str,
    snapshot_epoch: int,
    ax_root: Mapping[str, Any] | None,
    dom_nodes: Sequence[Mapping[str, Any]] | None = None,
    open_pages: Sequence[PageIdentity] | None = None,
    missing_fields: Sequence[str] = (),
    active_filter_labels: Sequence[str] = (),
) -> PageView:
    """Build a PageView slice from AX snapshot + optional DOM supplements."""

    if page_identity.page_id != frame_identity.page_id:
        raise ValueError("frame_identity.page_id must match page_identity.page_id")

    ax = normalize_ax_snapshot(
        ax_root,
        snapshot_epoch=snapshot_epoch,
        frame_id=frame_identity.frame_id,
    )
    next_local_id = len(ax.targets) + 1
    dom = extract_dom_targets(
        dom_nodes,
        snapshot_epoch=snapshot_epoch,
        frame_id=frame_identity.frame_id,
        start_local_id=next_local_id,
    )
    targets = merge_targets(ax.targets, dom.targets)

    unknowns: list[str] = []
    if ax_root is None or (not ax.targets and not ax.headings):
        unknowns.append("ax_empty")
    if ax.truncated:
        unknowns.append("ax_truncated")

    pages = tuple[PageIdentity, ...](open_pages) if open_pages is not None else (page_identity,)
    signature = compute_page_signature(
        current_url=page_identity.current_url,
        title=title,
        snapshot_epoch=snapshot_epoch,
    )
    protected = ProtectedState(
        current_page=page_identity,
        current_frame=frame_identity,
        missing_fields=tuple(missing_fields),
        active_filter_labels=tuple(active_filter_labels),
    )
    return PageView(
        page_identity=page_identity,
        frame_identity=frame_identity,
        current_url=page_identity.current_url,
        title=title,
        page_signature=signature,
        snapshot_epoch=snapshot_epoch,
        interactive_targets=targets,
        open_pages=pages,
        visible_headings=ax.headings,
        protected_state=protected,
        unknowns=tuple(unknowns),
    )
