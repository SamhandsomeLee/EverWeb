"""Runtime probes for the nine BrowserCapabilities flags over a connected CDP session."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from everweb.adapters.playwright_browser.connector import ConnectedBrowser
from everweb.domain import BrowserCapabilities

_UNAVAILABLE = BrowserCapabilities(
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


def empty_browser_capabilities() -> BrowserCapabilities:
    return _UNAVAILABLE


def _try(probe: Callable[[], None]) -> bool:
    try:
        probe()
    except Exception:
        return False
    return True


def _probe_cdp_session(connected: ConnectedBrowser) -> bool:
    context = connected.context
    page = connected.page
    new_cdp_session = getattr(context, "new_cdp_session", None)
    if not callable(new_cdp_session):
        return False

    def run() -> None:
        session: Any = new_cdp_session(page)
        detach = getattr(session, "detach", None)
        if callable(detach):
            detach()

    return _try(run)


def _probe_ax_tree(connected: ConnectedBrowser) -> bool:
    page = connected.page
    accessibility = getattr(page, "accessibility", None)
    if accessibility is None:
        return False
    snapshot = getattr(accessibility, "snapshot", None)
    if not callable(snapshot):
        return False
    return _try(lambda: snapshot())


def _probe_storage_state(connected: ConnectedBrowser) -> bool:
    storage_state = getattr(connected.context, "storage_state", None)
    if not callable(storage_state):
        return False
    return _try(lambda: storage_state())


def _probe_clear_permissions(connected: ConnectedBrowser) -> bool:
    clear_permissions = getattr(connected.context, "clear_permissions", None)
    if not callable(clear_permissions):
        return False
    return _try(lambda: clear_permissions())


def probe_connected_browser(connected: ConnectedBrowser) -> BrowserCapabilities:
    """Probe a live ConnectedBrowser; never raise; never pretend unsupported APIs exist."""

    can_create_context = connected.context is not None
    can_close_created_context = callable(getattr(connected.context, "close", None))
    return BrowserCapabilities(
        can_create_context=can_create_context,
        can_close_created_context=can_close_created_context,
        can_create_cdp_session=_probe_cdp_session(connected),
        can_capture_ax_tree=_probe_ax_tree(connected),
        can_download=False,
        can_open_popup=False,
        can_set_storage_state=_probe_storage_state(connected),
        can_clear_permissions=_probe_clear_permissions(connected),
        supports_service_worker_cleanup=False,
    )
