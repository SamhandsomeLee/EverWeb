"""CDP connection boundary for PlaywrightCdpBrowser."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from everweb.adapters.playwright_browser.errors import BrowserConnectionError


@runtime_checkable
class BrowserPage(Protocol):
    def goto(self, url: str) -> object: ...


@runtime_checkable
class BrowserContext(Protocol):
    def new_page(self) -> BrowserPage: ...

    def close(self) -> None: ...


@runtime_checkable
class BrowserHandle(Protocol):
    def new_context(self) -> BrowserContext: ...

    def close(self) -> None: ...


@runtime_checkable
class PlaywrightRuntime(Protocol):
    def stop(self) -> None: ...


@dataclass(slots=True)
class ConnectedBrowser:
    """Narrow handles produced by a CDP connector."""

    playwright: PlaywrightRuntime
    browser: BrowserHandle
    context: BrowserContext
    page: BrowserPage


@runtime_checkable
class CdpConnector(Protocol):
    def connect(self, cdp_url: str) -> ConnectedBrowser: ...


class DefaultPlaywrightConnector:
    """Production connector: sync Playwright over CDP with a new isolated context."""

    def connect(self, cdp_url: str) -> ConnectedBrowser:
        if not isinstance(cdp_url, str) or not cdp_url.strip():
            raise BrowserConnectionError("cdp_url must be a non-empty str")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - install contract covers this
            raise BrowserConnectionError(
                "playwright package is required for DefaultPlaywrightConnector"
            ) from exc

        playwright = sync_playwright().start()
        try:
            browser = playwright.chromium.connect_over_cdp(cdp_url.strip())
            context = browser.new_context()
            page = context.new_page()
        except Exception as exc:
            try:
                playwright.stop()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            raise BrowserConnectionError(
                f"failed to connect over CDP: {exc}"
            ) from exc
        return ConnectedBrowser(
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
        )


def default_playwright_connector() -> CdpConnector:
    return DefaultPlaywrightConnector()
