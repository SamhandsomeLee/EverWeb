"""Unit tests for TypedActionExecutor."""

from __future__ import annotations

from everweb.act import TypedActionExecutor
from everweb.domain import (
    ActionKind,
    ActionReceipt,
    BrowserCapabilities,
    BrowserSession,
    CaptureReceipt,
    CaptureRequest,
    CloseReceipt,
    FrameIdentity,
    InteractiveTarget,
    ObservationReceipt,
    ObservationRequest,
    PageIdentity,
    PageView,
    ProtectedState,
    ScrollMode,
    Task,
    TypedAction,
)
from everweb.ports import BrowserPort


class RecordingBrowser:
    def __init__(self) -> None:
        self.executed: list[TypedAction] = []

    def capabilities(self) -> BrowserCapabilities:
        return BrowserCapabilities(
            can_create_context=True,
            can_close_created_context=True,
            can_create_cdp_session=True,
            can_capture_ax_tree=True,
            can_download=False,
            can_open_popup=False,
            can_set_storage_state=False,
            can_clear_permissions=False,
            supports_service_worker_cleanup=False,
        )

    def create_task_session(self, task: Task) -> BrowserSession:
        return BrowserSession()

    def observe(self, req: ObservationRequest) -> ObservationReceipt:
        return ObservationReceipt()

    def execute(self, action: TypedAction) -> ActionReceipt:
        self.executed.append(action)
        return ActionReceipt(
            action_id=action.action_id,
            kind=action.kind,
            ok=True,
            target_ref=action.target_ref,
            locator_strategy=(
                None if action.locator is None else action.locator.strategy
            ),
            locator_role=None if action.locator is None else action.locator.role,
            locator_name=None if action.locator is None else action.locator.name,
        )

    def capture(self, req: CaptureRequest) -> CaptureReceipt:
        return CaptureReceipt()

    def close_task_session(self) -> CloseReceipt:
        return CloseReceipt()


def _page_view() -> PageView:
    page = PageIdentity(
        page_id="page-1",
        opener_page_id=None,
        current_url="https://example.com/form",
        is_active=True,
    )
    frame = FrameIdentity(
        frame_id="frame-main",
        page_id="page-1",
        parent_frame_id=None,
        origin="https://example.com",
    )
    return PageView(
        page_identity=page,
        frame_identity=frame,
        current_url=page.current_url,
        title="Form",
        page_signature="abc",
        snapshot_epoch=1,
        interactive_targets=(
            InteractiveTarget(
                ref="1:1",
                role="textbox",
                name="Email",
                frame_id="frame-main",
                source="ax",
            ),
            InteractiveTarget(
                ref="1:2",
                role="button",
                name="Submit",
                frame_id="frame-main",
                source="ax",
            ),
        ),
        open_pages=(page,),
        visible_headings=(),
        protected_state=ProtectedState(current_page=page, current_frame=frame),
        unknowns=(),
    )


def test_executor_fills_locator_before_port_call() -> None:
    browser: BrowserPort = RecordingBrowser()
    assert isinstance(browser, RecordingBrowser)
    receipt = TypedActionExecutor().execute(
        browser,
        _page_view(),
        TypedAction(action_id="a1", kind=ActionKind.CLICK, target_ref="1:2"),
    )
    assert receipt.ok is True
    assert len(browser.executed) == 1
    assert browser.executed[0].locator is not None
    assert browser.executed[0].locator.role == "button"
    assert browser.executed[0].locator.name == "Submit"


def test_executor_requires_text_for_type() -> None:
    browser = RecordingBrowser()
    receipt = TypedActionExecutor().execute(
        browser,
        _page_view(),
        TypedAction(action_id="a1", kind=ActionKind.TYPE, target_ref="1:1"),
    )
    assert receipt.ok is False
    assert receipt.error_code == "INVALID_ACTION"
    assert browser.executed == []


def test_executor_defaults_scroll_into_view() -> None:
    browser = RecordingBrowser()
    receipt = TypedActionExecutor().execute(
        browser,
        _page_view(),
        TypedAction(action_id="a1", kind=ActionKind.SCROLL, target_ref="1:2"),
    )
    assert receipt.ok is True
    assert browser.executed[0].scroll_mode is ScrollMode.INTO_VIEW


def test_executor_rejects_unsupported_kind() -> None:
    browser = RecordingBrowser()
    receipt = TypedActionExecutor().execute(
        browser,
        _page_view(),
        TypedAction(action_id="a1", kind=ActionKind.HOVER, target_ref="1:2"),
    )
    assert receipt.ok is False
    assert receipt.error_code == "UNSUPPORTED_KIND"
    assert browser.executed == []
