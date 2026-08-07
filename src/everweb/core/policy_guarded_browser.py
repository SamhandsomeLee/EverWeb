"""BrowserPort wrapper that enforces PolicyGate before execute (INV-10)."""

from __future__ import annotations

from everweb.core.policy import POLICY_REJECTED, PolicyDecision, PolicyGate
from everweb.domain import (
    ActionReceipt,
    BrowserCapabilities,
    BrowserSession,
    CaptureReceipt,
    CaptureRequest,
    CloseReceipt,
    ObservationReceipt,
    ObservationRequest,
    Task,
    TypedAction,
)
from everweb.ports import BrowserPort


class PolicyGuardedBrowser:
    """Deny Policy-rejected actions before they reach the inner BrowserPort."""

    def __init__(self, browser: BrowserPort, policy_gate: PolicyGate) -> None:
        if not isinstance(browser, BrowserPort):
            raise TypeError("browser must implement BrowserPort")
        if not isinstance(policy_gate, PolicyGate):
            raise TypeError("policy_gate must be a PolicyGate")
        self._browser = browser
        self._policy_gate = policy_gate
        self._last_decision: PolicyDecision | None = None

    @property
    def policy_gate(self) -> PolicyGate:
        return self._policy_gate

    @property
    def last_decision(self) -> PolicyDecision | None:
        return self._last_decision

    def capabilities(self) -> BrowserCapabilities:
        return self._browser.capabilities()

    def create_task_session(self, task: Task) -> BrowserSession:
        return self._browser.create_task_session(task)

    def observe(self, req: ObservationRequest) -> ObservationReceipt:
        return self._browser.observe(req)

    def execute(self, action: TypedAction) -> ActionReceipt:
        if not isinstance(action, TypedAction):
            raise TypeError("action must be a TypedAction")
        decision = self._policy_gate.evaluate(action)
        self._last_decision = decision
        if not decision.allowed:
            return ActionReceipt(
                action_id=action.action_id,
                kind=action.kind,
                ok=False,
                target_ref=action.target_ref,
                error_code=decision.error_code or POLICY_REJECTED,
            )
        return self._browser.execute(action)

    def capture(self, req: CaptureRequest) -> CaptureReceipt:
        return self._browser.capture(req)

    def close_task_session(self) -> CloseReceipt:
        return self._browser.close_task_session()
