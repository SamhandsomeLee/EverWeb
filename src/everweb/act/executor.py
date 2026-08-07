"""Execute click/type/scroll TypedActions via BrowserPort."""

from __future__ import annotations

from everweb.act.errors import (
    ActError,
    InvalidActionError,
    UnsupportedActionKindError,
)
from everweb.act.locator import resolve_role_name_locator
from everweb.domain import (
    ActionKind,
    ActionReceipt,
    PageView,
    ScrollMode,
    TypedAction,
)
from everweb.ports import BrowserPort

_SUPPORTED_KINDS = frozenset(
    {ActionKind.CLICK, ActionKind.TYPE, ActionKind.SCROLL}
)


def _fail_receipt(action: TypedAction, error: ActError) -> ActionReceipt:
    return ActionReceipt(
        action_id=action.action_id,
        kind=action.kind,
        ok=False,
        target_ref=action.target_ref,
        error_code=error.error_code,
    )


class TypedActionExecutor:
    """Resolve PageView refs then dispatch structured actions to BrowserPort."""

    def execute(
        self,
        browser: BrowserPort,
        page_view: PageView,
        action: TypedAction,
    ) -> ActionReceipt:
        if not isinstance(browser, BrowserPort):
            raise TypeError("browser must implement BrowserPort")
        if not isinstance(page_view, PageView):
            raise TypeError("page_view must be a PageView")
        if not isinstance(action, TypedAction):
            raise TypeError("action must be a TypedAction")

        if action.kind not in _SUPPORTED_KINDS:
            return _fail_receipt(
                action,
                UnsupportedActionKindError(
                    f"action kind {action.kind.value!r} is not supported in W1-004"
                ),
            )

        if action.target_ref is None or not action.target_ref.strip():
            return _fail_receipt(
                action,
                InvalidActionError("target_ref is required for click/type/scroll"),
            )

        if action.kind is ActionKind.TYPE and (
            action.text is None or action.text == ""
        ):
            return _fail_receipt(
                action,
                InvalidActionError("text is required for TYPE actions"),
            )

        scroll_mode = action.scroll_mode
        if action.kind is ActionKind.SCROLL:
            if scroll_mode is None:
                scroll_mode = ScrollMode.INTO_VIEW
            elif scroll_mode is not ScrollMode.INTO_VIEW:
                return _fail_receipt(
                    action,
                    InvalidActionError("only scroll_mode=into_view is supported"),
                )

        try:
            locator = resolve_role_name_locator(page_view, action.target_ref)
        except ActError as exc:
            return _fail_receipt(action, exc)

        resolved = TypedAction(
            action_id=action.action_id,
            kind=action.kind,
            target_ref=action.target_ref,
            text=action.text,
            scroll_mode=scroll_mode,
            locator=locator,
        )
        receipt = browser.execute(resolved)
        if not isinstance(receipt, ActionReceipt):
            raise TypeError("browser.execute must return ActionReceipt")
        if (
            receipt.action_id is None
            and receipt.kind is None
            and receipt.target_ref is None
            and receipt.locator_strategy is None
        ):
            # Preserve FakeBrowser empty defaults while still auditing when possible.
            return ActionReceipt(
                action_id=resolved.action_id,
                kind=resolved.kind,
                ok=receipt.ok,
                target_ref=resolved.target_ref,
                locator_strategy=locator.strategy,
                locator_role=locator.role,
                locator_name=locator.name,
                error_code=receipt.error_code,
            )
        return receipt
