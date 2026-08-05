"""Unit tests for perceive BrowserCapabilityProbe receipt materialization."""

from __future__ import annotations

from everweb.domain import (
    BROWSER_CAPABILITY_NAMES,
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
from everweb.perceive import BrowserCapabilityProbe
from everweb.ports import BrowserPort


class StubBrowser:
    def __init__(self, capabilities: BrowserCapabilities) -> None:
        self._capabilities = capabilities

    def capabilities(self) -> BrowserCapabilities:
        return self._capabilities

    def create_task_session(self, task: Task) -> BrowserSession:
        return BrowserSession()

    def observe(self, req: ObservationRequest) -> ObservationReceipt:
        return ObservationReceipt()

    def execute(self, action: TypedAction) -> ActionReceipt:
        return ActionReceipt()

    def capture(self, req: CaptureRequest) -> CaptureReceipt:
        return CaptureReceipt()

    def close_task_session(self) -> CloseReceipt:
        return CloseReceipt()


def test_probe_emits_exactly_nine_receipts_matching_capabilities() -> None:
    capabilities = BrowserCapabilities(
        can_create_context=True,
        can_close_created_context=True,
        can_create_cdp_session=False,
        can_capture_ax_tree=True,
        can_download=False,
        can_open_popup=False,
        can_set_storage_state=True,
        can_clear_permissions=False,
        supports_service_worker_cleanup=False,
    )
    browser: BrowserPort = StubBrowser(capabilities)

    report = BrowserCapabilityProbe().probe(browser)

    assert report.capabilities == capabilities
    assert len(report.items) == 9
    assert tuple(item.name for item in report.items) == BROWSER_CAPABILITY_NAMES
    for item in report.items:
        expected = getattr(capabilities, item.name.value)
        assert item.available is expected
        if expected:
            assert item.detail is None
        else:
            assert item.detail == "unavailable"


def test_probe_never_upgrades_false_capabilities() -> None:
    capabilities = BrowserCapabilities(
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

    report = BrowserCapabilityProbe().probe(StubBrowser(capabilities))

    assert all(item.available is False for item in report.items)
    assert all(item.detail == "unavailable" for item in report.items)
