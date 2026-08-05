"""Typed failures for the Playwright CDP browser adapter."""

from __future__ import annotations


class PlaywrightBrowserError(RuntimeError):
    """Base error for Playwright CDP browser adapter failures."""


class BrowserSessionError(PlaywrightBrowserError):
    """Browser session lifecycle is invalid for the requested operation."""


class BrowserConnectionError(PlaywrightBrowserError):
    """Connecting over CDP or creating an isolated context failed."""


class NavigationDeniedError(PlaywrightBrowserError):
    """Navigation was rejected by scheme or search-engine denylist policy."""


class UnsupportedNavigationError(PlaywrightBrowserError):
    """TypedAction NAVIGATE is unavailable until action payloads carry a URL."""
