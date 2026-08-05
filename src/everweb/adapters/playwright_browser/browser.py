"""Playwright BrowserPort implementation connected over CDP."""

from __future__ import annotations

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

_SESSION_CAPABILITIES = BrowserCapabilities(
    can_create_context=True,
    can_close_created_context=True,
    can_create_cdp_session=True,
    can_capture_ax_tree=False,
    can_download=False,
    can_open_popup=False,
    can_set_storage_state=False,
    can_clear_permissions=False,
    supports_service_worker_cleanup=False,
)

_NO_SESSION_CAPABILITIES = BrowserCapabilities(
    can_create_context=False,
    can_close_created_context=False,
    can_create_cdp_session=False,
    can_capture_ax_tree=False,
    can_download=False,
    can_open_popup=False,
    can_set_storage_state=False,
    can_clear_permissions=False,
    supports_service_worker_cleanup=False,
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

    @property
    def cdp_url(self) -> str:
        return self._cdp_url

    def capabilities(self) -> BrowserCapabilities:
        if self._connected is None:
            return _NO_SESSION_CAPABILITIES
        return _SESSION_CAPABILITIES

    def create_task_session(self, task: Task) -> BrowserSession:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if self._connected is not None:
            raise BrowserSessionError("task session already active")
        self._connected = self._connector.connect(self._cdp_url)
        return BrowserSession()

    def observe(self, req: ObservationRequest) -> ObservationReceipt:
        if not isinstance(req, ObservationRequest):
            raise TypeError("req must be an ObservationRequest")
        self._require_session()
        return ObservationReceipt()

    def execute(self, action: TypedAction) -> ActionReceipt:
        if not isinstance(action, TypedAction):
            raise TypeError("action must be a TypedAction")
        self._require_session()
        if action.kind is ActionKind.NAVIGATE:
            raise UnsupportedNavigationError(
                "TypedAction NAVIGATE requires a URL payload; use goto(url) until W1-004"
            )
        return ActionReceipt()

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
