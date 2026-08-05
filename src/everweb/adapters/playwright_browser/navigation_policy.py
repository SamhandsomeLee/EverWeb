"""Scheme allowlist and search-engine denylist for adapter-controlled navigation."""

from __future__ import annotations

from urllib.parse import urlsplit

from everweb.adapters.playwright_browser.errors import NavigationDeniedError

ALLOWED_SCHEMES = frozenset({"http", "https"})

_SEARCH_ENGINE_BASE_HOSTS = frozenset(
    {
        "google.com",
        "bing.com",
        "duckduckgo.com",
        "baidu.com",
        "yahoo.com",
        "yandex.com",
        "sogou.com",
        "so.com",
    }
)


def _bare_hostname(hostname: str) -> str:
    host = hostname.strip().lower().rstrip(".")
    if host.startswith("www."):
        return host.removeprefix("www.")
    return host


def is_search_engine_host(hostname: str) -> bool:
    bare = _bare_hostname(hostname)
    if not bare:
        return False
    if bare in _SEARCH_ENGINE_BASE_HOSTS:
        return True
    # Regional search hosts: google.<ccTLD>, yandex.<ccTLD>
    if bare.startswith("google.") or bare.startswith("yandex."):
        return True
    for base in _SEARCH_ENGINE_BASE_HOSTS:
        if bare.endswith("." + base):
            return True
    return False


def assert_navigation_allowed(url: str) -> str:
    """Return a stripped URL if allowed; otherwise raise NavigationDeniedError."""

    if not isinstance(url, str):
        raise TypeError("url must be a str")
    candidate = url.strip()
    if not candidate:
        raise NavigationDeniedError("navigation url must be non-empty")

    parts = urlsplit(candidate)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise NavigationDeniedError(
            f"navigation scheme {scheme!r} is not allowed; only http/https"
        )
    hostname = parts.hostname
    if hostname is None or not hostname.strip():
        raise NavigationDeniedError("navigation url must include a hostname")
    if is_search_engine_host(hostname):
        raise NavigationDeniedError(
            f"search engine host {hostname!r} is denied by navigation policy"
        )
    return candidate
