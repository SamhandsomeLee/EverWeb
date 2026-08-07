"""Model-external Policy Gate for TypedActions (INV-10)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from everweb.domain import (
    ActionKind,
    ScrollMode,
    SideEffectRisk,
    TypedAction,
)

POLICY_REJECTED = "POLICY_REJECTED"

_ALLOWED_KINDS = frozenset({ActionKind.CLICK, ActionKind.TYPE, ActionKind.SCROLL})

_KIND_RISK: dict[ActionKind, SideEffectRisk] = {
    ActionKind.CLICK: SideEffectRisk.REVERSIBLE_UI,
    ActionKind.TYPE: SideEffectRisk.REVERSIBLE_UI,
    ActionKind.SCROLL: SideEffectRisk.READ_ONLY,
}


class PolicyDecision(BaseModel):
    """Immutable Policy outcome; never carries Budget or official status."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    allowed: bool
    error_code: str | None = None
    reason: str = Field(min_length=1)
    side_effect_risk: SideEffectRisk | None = None


class PolicyGate:
    """Pure TypedAction authority that runs outside the model."""

    def evaluate(self, action: TypedAction) -> PolicyDecision:
        if not isinstance(action, TypedAction):
            raise TypeError("action must be a TypedAction")

        if action.kind not in _ALLOWED_KINDS:
            return PolicyDecision(
                allowed=False,
                error_code=POLICY_REJECTED,
                reason=f"action kind {action.kind.value!r} is not allowed by Policy",
            )

        if action.target_ref is None or not action.target_ref.strip():
            return PolicyDecision(
                allowed=False,
                error_code=POLICY_REJECTED,
                reason="target_ref is required",
            )

        if action.kind is ActionKind.TYPE and (
            action.text is None or action.text == ""
        ):
            return PolicyDecision(
                allowed=False,
                error_code=POLICY_REJECTED,
                reason="text is required for TYPE",
            )

        if action.kind is ActionKind.SCROLL and action.scroll_mode is not None:
            if action.scroll_mode is not ScrollMode.INTO_VIEW:
                return PolicyDecision(
                    allowed=False,
                    error_code=POLICY_REJECTED,
                    reason="only scroll_mode=into_view is allowed",
                )

        if action.locator is not None:
            strategy = getattr(action.locator, "strategy", None)
            if strategy != "role_name":
                return PolicyDecision(
                    allowed=False,
                    error_code=POLICY_REJECTED,
                    reason="only role_name locator strategy is allowed",
                )

        return PolicyDecision(
            allowed=True,
            error_code=None,
            reason="allowed",
            side_effect_risk=_KIND_RISK[action.kind],
        )
