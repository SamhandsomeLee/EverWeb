"""EverWeb playwright browser package boundary."""

from everweb.adapters.playwright_browser.browser import PlaywrightCdpBrowser
from everweb.adapters.playwright_browser.connector import (
    CdpConnector,
    ConnectedBrowser,
    DefaultPlaywrightConnector,
    default_playwright_connector,
)
from everweb.adapters.playwright_browser.errors import (
    BrowserConnectionError,
    BrowserSessionError,
    NavigationDeniedError,
    PlaywrightBrowserError,
    UnsupportedNavigationError,
)
from everweb.adapters.playwright_browser.navigation_policy import (
    assert_navigation_allowed,
    is_search_engine_host,
)

__all__ = [
    "BrowserConnectionError",
    "BrowserSessionError",
    "CdpConnector",
    "ConnectedBrowser",
    "DefaultPlaywrightConnector",
    "NavigationDeniedError",
    "PlaywrightBrowserError",
    "PlaywrightCdpBrowser",
    "UnsupportedNavigationError",
    "assert_navigation_allowed",
    "default_playwright_connector",
    "is_search_engine_host",
]
