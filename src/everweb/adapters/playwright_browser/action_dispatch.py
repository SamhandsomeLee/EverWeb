"""Dispatch click/type/scroll TypedActions via Playwright Locator APIs only."""

from __future__ import annotations

from typing import Any

from everweb.domain import ActionKind, ActionReceipt, TypedAction


def _receipt(action: TypedAction, *, ok: bool, error_code: str | None) -> ActionReceipt:
    locator = action.locator
    return ActionReceipt(
        action_id=action.action_id,
        kind=action.kind,
        ok=ok,
        target_ref=action.target_ref,
        locator_strategy=None if locator is None else locator.strategy,
        locator_role=None if locator is None else locator.role,
        locator_name=None if locator is None else locator.name,
        error_code=error_code,
    )


def _resolve_locator(page: Any, action: TypedAction) -> Any:
    locator = action.locator
    assert locator is not None
    get_by_role = getattr(page, "get_by_role", None)
    if not callable(get_by_role):
        raise RuntimeError("page does not support get_by_role")
    if locator.name is None:
        return get_by_role(locator.role)
    return get_by_role(locator.role, name=locator.name)


def dispatch_typed_action(page: Any, action: TypedAction) -> ActionReceipt:
    """Execute click/type/scroll via Locator API only (no JS eval, no HTTP)."""

    if action.kind not in {ActionKind.CLICK, ActionKind.TYPE, ActionKind.SCROLL}:
        return _receipt(action, ok=False, error_code="UNSUPPORTED_KIND")
    if action.locator is None:
        return _receipt(action, ok=False, error_code="MISSING_LOCATOR")

    try:
        target = _resolve_locator(page, action)
        if action.kind is ActionKind.CLICK:
            click = getattr(target, "click", None)
            if not callable(click):
                raise RuntimeError("locator.click is unavailable")
            click()
        elif action.kind is ActionKind.TYPE:
            if action.text is None:
                return _receipt(action, ok=False, error_code="INVALID_ACTION")
            fill = getattr(target, "fill", None)
            if not callable(fill):
                raise RuntimeError("locator.fill is unavailable")
            fill(action.text)
        else:
            scroll = getattr(target, "scroll_into_view_if_needed", None)
            if not callable(scroll):
                raise RuntimeError("locator.scroll_into_view_if_needed is unavailable")
            scroll()
    except Exception:
        return _receipt(action, ok=False, error_code="TARGET_NOT_FOUND")
    return _receipt(action, ok=True, error_code=None)
