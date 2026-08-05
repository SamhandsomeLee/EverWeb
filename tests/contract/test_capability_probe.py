"""Contract tests for adapter runtime probe + perceive report alignment."""

from __future__ import annotations

from everweb.adapters.playwright_browser import (
    ConnectedBrowser,
    PlaywrightCdpBrowser,
)
from everweb.domain import (
    BROWSER_CAPABILITY_NAMES,
    Task,
)
from everweb.perceive import BrowserCapabilityProbe

CDP_URL = "http://127.0.0.1:9222"


class _CdpSession:
    def __init__(self) -> None:
        self.detached = False

    def detach(self) -> None:
        self.detached = True


class _Accessibility:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    def snapshot(self) -> dict[str, object]:
        if self._fail:
            raise RuntimeError("ax unavailable")
        return {"role": "RootWebArea"}


class ProbePage:
    def __init__(self, *, ax_fail: bool = False) -> None:
        self.goto_urls: list[str] = []
        self.accessibility = _Accessibility(fail=ax_fail)

    def goto(self, url: str) -> None:
        self.goto_urls.append(url)


class ProbeContext:
    def __init__(
        self,
        page: ProbePage,
        *,
        cdp_fail: bool = False,
        storage_fail: bool = False,
        permissions_fail: bool = False,
    ) -> None:
        self._page = page
        self._cdp_fail = cdp_fail
        self._storage_fail = storage_fail
        self._permissions_fail = permissions_fail
        self.closed = False

    def new_page(self) -> ProbePage:
        return self._page

    def close(self) -> None:
        self.closed = True

    def new_cdp_session(self, page: ProbePage) -> _CdpSession:
        if self._cdp_fail:
            raise RuntimeError("cdp session unavailable")
        assert page is self._page
        return _CdpSession()

    def storage_state(self) -> dict[str, object]:
        if self._storage_fail:
            raise RuntimeError("storage_state unavailable")
        return {"cookies": [], "origins": []}

    def clear_permissions(self) -> None:
        if self._permissions_fail:
            raise RuntimeError("clear_permissions unavailable")


class ProbeBrowser:
    def __init__(self, context: ProbeContext) -> None:
        self._context = context
        self.closed = False

    def new_context(self) -> ProbeContext:
        return self._context

    def close(self) -> None:
        self.closed = True


class ProbePlaywright:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class ProbeCdpConnector:
    def __init__(
        self,
        *,
        cdp_fail: bool = False,
        ax_fail: bool = False,
        storage_fail: bool = False,
        permissions_fail: bool = False,
    ) -> None:
        self.page = ProbePage(ax_fail=ax_fail)
        self.context = ProbeContext(
            self.page,
            cdp_fail=cdp_fail,
            storage_fail=storage_fail,
            permissions_fail=permissions_fail,
        )
        self.browser = ProbeBrowser(self.context)
        self.playwright = ProbePlaywright()
        self.connected_urls: list[str] = []

    def connect(self, cdp_url: str) -> ConnectedBrowser:
        self.connected_urls.append(cdp_url)
        return ConnectedBrowser(
            playwright=self.playwright,
            browser=self.browser,
            context=self.context,
            page=self.page,
        )


def test_runtime_probe_marks_supported_apis_true() -> None:
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=ProbeCdpConnector())
    browser.create_task_session(Task())

    caps = browser.capabilities()
    assert caps.can_create_context is True
    assert caps.can_close_created_context is True
    assert caps.can_create_cdp_session is True
    assert caps.can_capture_ax_tree is True
    assert caps.can_set_storage_state is True
    assert caps.can_clear_permissions is True
    assert caps.can_download is False
    assert caps.can_open_popup is False
    assert caps.supports_service_worker_cleanup is False


def test_runtime_probe_keeps_failed_apis_false() -> None:
    connector = ProbeCdpConnector(
        cdp_fail=True,
        ax_fail=True,
        storage_fail=True,
        permissions_fail=True,
    )
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=connector)
    browser.create_task_session(Task())

    caps = browser.capabilities()
    assert caps.can_create_context is True
    assert caps.can_close_created_context is True
    assert caps.can_create_cdp_session is False
    assert caps.can_capture_ax_tree is False
    assert caps.can_set_storage_state is False
    assert caps.can_clear_permissions is False


def test_perceive_report_matches_adapter_capabilities() -> None:
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=ProbeCdpConnector())
    browser.create_task_session(Task())

    report = BrowserCapabilityProbe().probe(browser)

    assert report.capabilities == browser.capabilities()
    assert len(report.items) == len(BROWSER_CAPABILITY_NAMES)
    for item in report.items:
        assert item.available is getattr(report.capabilities, item.name.value)


def test_perceive_report_all_false_without_session() -> None:
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=ProbeCdpConnector())

    report = BrowserCapabilityProbe().probe(browser)

    assert all(item.available is False for item in report.items)
    assert all(item.detail == "unavailable" for item in report.items)
