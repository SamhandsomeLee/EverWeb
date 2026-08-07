"""Deterministic FakeBrowser implementing BrowserPort for harness runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

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
from everweb.harness.cassette import (
    CassetteEntry,
    CassetteValidationError,
    dump_cassette,
    load_cassette,
    model_to_json_object,
)
from everweb.harness.errors import FakeHarnessError, FakeScriptExhaustedError

FAKE_BROWSER_CAPABILITIES = BrowserCapabilities(
    can_create_context=True,
    can_close_created_context=True,
    can_create_cdp_session=True,
    can_capture_ax_tree=True,
    can_download=True,
    can_open_popup=True,
    can_set_storage_state=True,
    can_clear_permissions=True,
    supports_service_worker_cleanup=True,
)

_BROWSER_RESPONSE_TYPES: dict[str, type[BaseModel]] = {
    "capabilities": BrowserCapabilities,
    "create_task_session": BrowserSession,
    "observe": ObservationReceipt,
    "execute": ActionReceipt,
    "capture": CaptureReceipt,
    "close_task_session": CloseReceipt,
}


class FakeBrowser:
    """Recordable BrowserPort fake with empty placeholder receipts by default."""

    def __init__(
        self,
        *,
        script: Mapping[str, Sequence[BaseModel]] | None = None,
    ) -> None:
        self._script_queues: dict[str, list[BaseModel]] = {}
        self._script_indexes: dict[str, int] = {}
        if script is not None:
            for op, responses in script.items():
                if op not in _BROWSER_RESPONSE_TYPES:
                    raise FakeHarnessError(f"unknown FakeBrowser script op: {op}")
                expected = _BROWSER_RESPONSE_TYPES[op]
                queue: list[BaseModel] = []
                for index, response in enumerate(responses):
                    if not isinstance(response, expected):
                        raise TypeError(
                            f"script[{op!r}][{index}] must be {expected.__name__}"
                        )
                    queue.append(response)
                self._script_queues[op] = queue
                self._script_indexes[op] = 0
        self._calls: list[CassetteEntry] = []

    @property
    def calls(self) -> tuple[CassetteEntry, ...]:
        return tuple(self._calls)

    def dump_cassette(self, path: Path) -> None:
        dump_cassette(self._calls, path)

    @classmethod
    def from_cassette(cls, path: Path) -> FakeBrowser:
        entries = load_cassette(path)
        script: dict[str, list[BaseModel]] = {}
        for entry in entries:
            response_type = _BROWSER_RESPONSE_TYPES.get(entry.op)
            if response_type is None:
                raise CassetteValidationError(
                    f"cassette contains unknown FakeBrowser op: {entry.op}"
                )
            script.setdefault(entry.op, []).append(
                # Cassette JSON stores enum values as strings; coerce on replay.
                response_type.model_validate(entry.response, strict=False)
            )
        return cls(script=script)

    def capabilities(self) -> BrowserCapabilities:
        response = self._next_response(
            "capabilities",
            FAKE_BROWSER_CAPABILITIES,
        )
        assert isinstance(response, BrowserCapabilities)
        self._record("capabilities", {}, response)
        return response

    def create_task_session(self, task: Task) -> BrowserSession:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        response = self._next_response("create_task_session", BrowserSession())
        assert isinstance(response, BrowserSession)
        self._record("create_task_session", model_to_json_object(task), response)
        return response

    def observe(self, req: ObservationRequest) -> ObservationReceipt:
        if not isinstance(req, ObservationRequest):
            raise TypeError("req must be an ObservationRequest")
        response = self._next_response("observe", ObservationReceipt())
        assert isinstance(response, ObservationReceipt)
        self._record("observe", model_to_json_object(req), response)
        return response

    def execute(self, action: TypedAction) -> ActionReceipt:
        if not isinstance(action, TypedAction):
            raise TypeError("action must be a TypedAction")
        default = ActionReceipt(
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
        response = self._next_response("execute", default)
        assert isinstance(response, ActionReceipt)
        self._record("execute", model_to_json_object(action), response)
        return response

    def capture(self, req: CaptureRequest) -> CaptureReceipt:
        if not isinstance(req, CaptureRequest):
            raise TypeError("req must be a CaptureRequest")
        response = self._next_response("capture", CaptureReceipt())
        assert isinstance(response, CaptureReceipt)
        self._record("capture", model_to_json_object(req), response)
        return response

    def close_task_session(self) -> CloseReceipt:
        response = self._next_response("close_task_session", CloseReceipt())
        assert isinstance(response, CloseReceipt)
        self._record("close_task_session", {}, response)
        return response

    def _next_response(self, op: str, default: BaseModel) -> BaseModel:
        queue = self._script_queues.get(op)
        if queue is None:
            return default
        index = self._script_indexes[op]
        if index >= len(queue):
            raise FakeScriptExhaustedError(
                f"FakeBrowser script exhausted for op {op!r}"
            )
        self._script_indexes[op] = index + 1
        return queue[index]

    def _record(self, op: str, request: dict[str, object], response: BaseModel) -> None:
        self._calls.append(
            CassetteEntry(
                op=op,
                request=dict(request),
                response=model_to_json_object(response),
            )
        )
