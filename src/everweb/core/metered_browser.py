"""BrowserPort wrapper that couples execute results to StepMeter (INV-8)."""

from __future__ import annotations

from everweb.core.step_meter import StepMeter, StepReceipt
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
from everweb.ports import BrowserPort


class MeteredBrowser:
    """Delegate BrowserPort calls; record every execute via StepMeter."""

    def __init__(self, browser: BrowserPort, step_meter: StepMeter) -> None:
        if not isinstance(browser, BrowserPort):
            raise TypeError("browser must implement BrowserPort")
        if not isinstance(step_meter, StepMeter):
            raise TypeError("step_meter must be a StepMeter")
        self._browser = browser
        self._step_meter = step_meter
        self._last_step_receipt: StepReceipt | None = None

    @property
    def step_meter(self) -> StepMeter:
        return self._step_meter

    @property
    def last_step_receipt(self) -> StepReceipt | None:
        return self._last_step_receipt

    def capabilities(self) -> BrowserCapabilities:
        return self._browser.capabilities()

    def create_task_session(self, task: Task) -> BrowserSession:
        return self._browser.create_task_session(task)

    def observe(self, req: ObservationRequest) -> ObservationReceipt:
        return self._browser.observe(req)

    def execute(self, action: TypedAction) -> ActionReceipt:
        if not isinstance(action, TypedAction):
            raise TypeError("action must be a TypedAction")
        receipt = self._browser.execute(action)
        if not isinstance(receipt, ActionReceipt):
            raise TypeError("browser.execute must return ActionReceipt")
        self._last_step_receipt = self._step_meter.record(action, receipt)
        return receipt

    def capture(self, req: CaptureRequest) -> CaptureReceipt:
        return self._browser.capture(req)

    def close_task_session(self) -> CloseReceipt:
        return self._browser.close_task_session()
