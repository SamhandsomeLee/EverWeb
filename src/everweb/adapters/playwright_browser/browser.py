"""Playwright BrowserPort implementation connected over CDP."""

from __future__ import annotations

from everweb.adapters.playwright_browser.action_dispatch import dispatch_typed_action
from everweb.adapters.playwright_browser.capability_probe import (
    empty_browser_capabilities,
    probe_connected_browser,
)
from everweb.adapters.playwright_browser.connector import (
    CdpConnector,
    ConnectedBrowser,
    default_playwright_connector,
)
from everweb.adapters.playwright_browser.errors import (
    BrowserSessionError,
    UnsupportedNavigationError,
)
from everweb.adapters.playwright_browser.navigation_policy import (
    assert_navigation_allowed,
)
from everweb.domain import (
    ActionKind,
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


class PlaywrightCdpBrowser:
    """BrowserPort backed by Playwright `connect_over_cdp` plus controlled goto."""

    def __init__(
        self,
        *,
        cdp_url: str,
        connector: CdpConnector | None = None,
    ) -> None:
        if not isinstance(cdp_url, str) or not cdp_url.strip():
            raise ValueError("cdp_url must be a non-empty str")
        self._cdp_url = cdp_url.strip()
        self._connector = (
            connector if connector is not None else default_playwright_connector()
        )
        self._connected: ConnectedBrowser | None = None
        self._probed_capabilities: BrowserCapabilities = empty_browser_capabilities()

    @property
    def cdp_url(self) -> str:
        return self._cdp_url

    def capabilities(self) -> BrowserCapabilities:
        if self._connected is None:
            return empty_browser_capabilities()
        return self._probed_capabilities

    def create_task_session(self, task: Task) -> BrowserSession:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if self._connected is not None:
            raise BrowserSessionError("task session already active")
        connected = self._connector.connect(self._cdp_url)
        self._connected = connected
        self._probed_capabilities = probe_connected_browser(connected)
        return BrowserSession()

    def observe(self, req: ObservationRequest) -> ObservationReceipt:
        if not isinstance(req, ObservationRequest):
            raise TypeError("req must be an ObservationRequest")
        self._require_session()
        return ObservationReceipt()

    def execute(self, action: TypedAction) -> ActionReceipt:
        if not isinstance(action, TypedAction):
            raise TypeError("action must be a TypedAction")
        connected = self._require_session()
        if action.kind is ActionKind.NAVIGATE:
            raise UnsupportedNavigationError(
                "TypedAction NAVIGATE requires a URL payload; use goto(url)"
            )
        if action.kind in {ActionKind.CLICK, ActionKind.TYPE, ActionKind.SCROLL}:
            return dispatch_typed_action(connected.page, action)
        return ActionReceipt(
            action_id=action.action_id,
            kind=action.kind,
            ok=False,
            target_ref=action.target_ref,
            error_code="UNSUPPORTED_KIND",
        )

    def capture(self, req: CaptureRequest) -> CaptureReceipt:
        if not isinstance(req, CaptureRequest):
            raise TypeError("req must be a CaptureRequest")
        self._require_session()
        return CaptureReceipt()

    def goto(self, url: str) -> None:
        """Sole target-site navigation entry for this adapter slice."""

        connected = self._require_session()
        allowed = assert_navigation_allowed(url)
        connected.page.goto(allowed)

    def close_task_session(self) -> CloseReceipt:
        connected = self._connected
        if connected is None:
            return CloseReceipt()
        self._connected = None
        self._probed_capabilities = empty_browser_capabilities()
        errors: list[str] = []
        for closer in (
            connected.context.close,
            connected.browser.close,
            connected.playwright.stop,
        ):
            try:
                closer()
            except Exception as exc:  # pragma: no cover - best-effort teardown
                errors.append(f"{closer.__qualname__}: {exc}")
        if errors:
            raise BrowserSessionError(
                "failed to close task session cleanly: " + "; ".join(errors)
            )
        return CloseReceipt()

    def _require_session(self) -> ConnectedBrowser:
        if self._connected is None:
            raise BrowserSessionError("task session is not active")
        return self._connected
