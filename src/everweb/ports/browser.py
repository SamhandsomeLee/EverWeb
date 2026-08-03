"""Browser capability boundary."""

from typing import Protocol, runtime_checkable

from everweb.domain import (
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


@runtime_checkable
class BrowserPort(Protocol):
    """Infrastructure-neutral browser operations."""

    def capabilities(self) -> BrowserCapabilities: ...

    def create_task_session(self, task: Task) -> BrowserSession: ...

    def observe(self, req: ObservationRequest) -> ObservationReceipt: ...

    def execute(self, action: TypedAction) -> ActionReceipt: ...

    def capture(self, req: CaptureRequest) -> CaptureReceipt: ...

    def close_task_session(self) -> CloseReceipt: ...
