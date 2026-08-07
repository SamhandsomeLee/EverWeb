"""Resolve PageView epoch refs into auditable role+name locators."""

from __future__ import annotations

from everweb.act.errors import StaleRefError, TargetNotFoundError
from everweb.domain import PageView, RoleNameLocator


def _epoch_prefix(target_ref: str) -> int | None:
    head, separator, _tail = target_ref.partition(":")
    if separator != ":" or not head.isdigit():
        return None
    return int(head)


def resolve_role_name_locator(page_view: PageView, target_ref: str) -> RoleNameLocator:
    """Map a PageView ref to §13.3 first-tier role+name locator facts."""

    if not isinstance(page_view, PageView):
        raise TypeError("page_view must be a PageView")
    if not isinstance(target_ref, str) or not target_ref.strip():
        raise TargetNotFoundError("target_ref must be a non-empty str")

    ref = target_ref.strip()
    epoch = _epoch_prefix(ref)
    if epoch is None or epoch != page_view.snapshot_epoch:
        raise StaleRefError(
            f"target_ref {ref!r} does not match snapshot_epoch "
            f"{page_view.snapshot_epoch}"
        )

    for target in page_view.interactive_targets:
        if target.ref == ref:
            return RoleNameLocator(
                role=target.role,
                name=target.name,
                frame_id=target.frame_id,
                ref=target.ref,
            )

    raise TargetNotFoundError(f"no interactive target for ref {ref!r}")
