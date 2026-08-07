"""Contract tests for Playwright CDP BrowserPort with recorded connectors."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from everweb.adapters.playwright_browser import (
    ConnectedBrowser,
    NavigationDeniedError,
    PlaywrightCdpBrowser,
    UnsupportedNavigationError,
    assert_navigation_allowed,
    is_search_engine_host,
)
from everweb.domain import (
    ActionKind,
    ActionReceipt,
    BrowserSession,
    CaptureReceipt,
    CaptureRequest,
    CloseReceipt,
    ObservationReceipt,
    ObservationRequest,
    RoleNameLocator,
    Task,
    TypedAction,
)
from everweb.ports import BrowserPort

ADAPTER_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "everweb"
    / "adapters"
    / "playwright_browser"
)
FORBIDDEN_IMPORT_ROOTS = ("httpx", "requests", "urllib.request")
PLACEHOLDER_TYPES = (
    Task,
    BrowserSession,
    ObservationRequest,
    ObservationReceipt,
    CaptureRequest,
    CaptureReceipt,
    CloseReceipt,
)
CDP_URL = "http://127.0.0.1:9222"


class RecordedLocator:
    def __init__(self, *, role: str, name: str | None) -> None:
        self.role = role
        self.name = name
        self.clicks = 0
        self.fills: list[str] = []
        self.scrolls = 0

    def click(self) -> None:
        self.clicks += 1

    def fill(self, text: str) -> None:
        self.fills.append(text)

    def scroll_into_view_if_needed(self) -> None:
        self.scrolls += 1


class RecordedPage:
    def __init__(self) -> None:
        self.goto_urls: list[str] = []
        self.role_lookups: list[tuple[str, str | None]] = []
        self.locators: list[RecordedLocator] = []

    def goto(self, url: str) -> None:
        self.goto_urls.append(url)

    def get_by_role(self, role: str, *, name: str | None = None) -> RecordedLocator:
        self.role_lookups.append((role, name))
        locator = RecordedLocator(role=role, name=name)
        self.locators.append(locator)
        return locator


class RecordedContext:
    def __init__(self, page: RecordedPage) -> None:
        self._page = page
        self.closed = False

    def new_page(self) -> RecordedPage:
        return self._page

    def close(self) -> None:
        self.closed = True


class RecordedBrowser:
    def __init__(self, context: RecordedContext) -> None:
        self._context = context
        self.closed = False

    def new_context(self) -> RecordedContext:
        return self._context

    def close(self) -> None:
        self.closed = True


class RecordedPlaywright:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class RecordedCdpConnector:
    def __init__(self) -> None:
        self.page = RecordedPage()
        self.context = RecordedContext(self.page)
        self.browser = RecordedBrowser(self.context)
        self.playwright = RecordedPlaywright()
        self.connected_urls: list[str] = []

    def connect(self, cdp_url: str) -> ConnectedBrowser:
        self.connected_urls.append(cdp_url)
        return ConnectedBrowser(
            playwright=self.playwright,
            browser=self.browser,
            context=self.context,
            page=self.page,
        )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_playwright_cdp_browser_implements_browser_port() -> None:
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=RecordedCdpConnector())
    assert isinstance(browser, BrowserPort)


def test_recorded_cdp_session_lifecycle() -> None:
    connector = RecordedCdpConnector()
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=connector)

    assert browser.capabilities().can_create_cdp_session is False
    session = browser.create_task_session(Task())
    assert isinstance(session, BrowserSession)
    assert connector.connected_urls == [CDP_URL]
    # Minimal recorded stubs lack CDP/AX/storage APIs → honest False after probe.
    assert browser.capabilities().model_dump(mode="json") == {
        "can_create_context": True,
        "can_close_created_context": True,
        "can_create_cdp_session": False,
        "can_capture_ax_tree": False,
        "can_download": False,
        "can_open_popup": False,
        "can_set_storage_state": False,
        "can_clear_permissions": False,
        "supports_service_worker_cleanup": False,
    }
    assert isinstance(browser.observe(ObservationRequest()), ObservationReceipt)
    missing = browser.execute(TypedAction(action_id="a1", kind=ActionKind.CLICK))
    assert isinstance(missing, ActionReceipt)
    assert missing.ok is False
    assert missing.error_code == "MISSING_LOCATOR"
    assert isinstance(browser.capture(CaptureRequest()), CaptureReceipt)

    receipt = browser.close_task_session()
    assert isinstance(receipt, CloseReceipt)
    assert connector.context.closed is True
    assert connector.browser.closed is True
    assert connector.playwright.stopped is True
    assert browser.capabilities().can_create_cdp_session is False


def test_goto_allows_non_search_https_target() -> None:
    connector = RecordedCdpConnector()
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=connector)
    browser.create_task_session(Task())

    browser.goto("https://example.com/docs/value")

    assert connector.page.goto_urls == ["https://example.com/docs/value"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.google.com/search?q=everweb",
        "https://bing.com/",
        "https://duckduckgo.com/?q=x",
        "https://www.baidu.com/s?wd=x",
        "https://google.co.uk/search?q=x",
        "javascript:alert(1)",
        "data:text/html,hi",
        "file:///tmp/x",
    ],
)
def test_goto_denies_search_engines_and_bad_schemes(url: str) -> None:
    connector = RecordedCdpConnector()
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=connector)
    browser.create_task_session(Task())

    with pytest.raises(NavigationDeniedError):
        browser.goto(url)

    assert connector.page.goto_urls == []


def test_execute_navigate_is_fail_closed() -> None:
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=RecordedCdpConnector())
    browser.create_task_session(Task())

    with pytest.raises(UnsupportedNavigationError):
        browser.execute(TypedAction(action_id="nav-1", kind=ActionKind.NAVIGATE))


def _role_name_action(
    *,
    action_id: str,
    kind: ActionKind,
    role: str,
    name: str,
    text: str | None = None,
) -> TypedAction:
    return TypedAction(
        action_id=action_id,
        kind=kind,
        target_ref="1:1",
        text=text,
        locator=RoleNameLocator(
            role=role,
            name=name,
            frame_id="frame-main",
            ref="1:1",
        ),
    )


def test_execute_click_type_scroll_uses_locator_api() -> None:
    connector = RecordedCdpConnector()
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=connector)
    browser.create_task_session(Task())

    click_receipt = browser.execute(
        _role_name_action(
            action_id="click-1",
            kind=ActionKind.CLICK,
            role="button",
            name="Submit",
        )
    )
    type_receipt = browser.execute(
        _role_name_action(
            action_id="type-1",
            kind=ActionKind.TYPE,
            role="textbox",
            name="Email",
            text="a@example.com",
        )
    )
    scroll_receipt = browser.execute(
        _role_name_action(
            action_id="scroll-1",
            kind=ActionKind.SCROLL,
            role="link",
            name="Docs",
        )
    )

    assert click_receipt.ok and type_receipt.ok and scroll_receipt.ok
    assert click_receipt.locator_strategy == "role_name"
    assert connector.page.role_lookups == [
        ("button", "Submit"),
        ("textbox", "Email"),
        ("link", "Docs"),
    ]
    assert len(connector.page.locators) == 3
    assert connector.page.locators[0].clicks == 1
    assert connector.page.locators[1].fills == ["a@example.com"]
    assert connector.page.locators[2].scrolls == 1


def test_execute_without_locator_returns_fail_receipt() -> None:
    browser = PlaywrightCdpBrowser(cdp_url=CDP_URL, connector=RecordedCdpConnector())
    browser.create_task_session(Task())

    receipt = browser.execute(
        TypedAction(action_id="click-1", kind=ActionKind.CLICK, target_ref="1:1")
    )
    assert receipt.ok is False
    assert receipt.error_code == "MISSING_LOCATOR"


def test_adapter_sources_forbid_evaluate() -> None:
    for path in ADAPTER_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert "evaluate" not in ast.dump(node.func).lower()


def test_adapter_package_forbids_http_client_bypass_imports() -> None:
    imported: set[str] = set()
    for path in ADAPTER_ROOT.rglob("*.py"):
        imported |= _imported_modules(path)

    for forbidden in FORBIDDEN_IMPORT_ROOTS:
        assert not any(
            module == forbidden or module.startswith(forbidden + ".")
            for module in imported
        ), imported


def test_placeholder_port_dtos_remain_fieldless() -> None:
    for model_type in PLACEHOLDER_TYPES:
        assert model_type.model_json_schema()["properties"] == {}
        assert model_type().model_dump(mode="json") == {}


def test_search_engine_host_helpers() -> None:
    assert is_search_engine_host("www.Google.com")
    assert is_search_engine_host("maps.google.com")
    assert not is_search_engine_host("example.com")
    assert assert_navigation_allowed("http://example.com/") == "http://example.com/"
