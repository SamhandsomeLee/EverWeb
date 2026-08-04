"""Deterministic FakeModel implementing ModelPort for harness runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from everweb.domain import Deadline, ModelCapabilities, ModelReceipt, ModelRequest
from everweb.harness.cassette import (
    CassetteEntry,
    CassetteValidationError,
    dump_cassette,
    load_cassette,
    model_to_json_object,
)
from everweb.harness.errors import FakeHarnessError, FakeScriptExhaustedError

_MODEL_RESPONSE_TYPES: dict[str, type[BaseModel]] = {
    "capabilities": ModelCapabilities,
    "complete": ModelReceipt,
}


class FakeModel:
    """Recordable ModelPort fake with empty placeholder receipts by default."""

    def __init__(
        self,
        *,
        script: Mapping[str, Sequence[BaseModel]] | None = None,
    ) -> None:
        self._script_queues: dict[str, list[BaseModel]] = {}
        self._script_indexes: dict[str, int] = {}
        if script is not None:
            for op, responses in script.items():
                if op not in _MODEL_RESPONSE_TYPES:
                    raise FakeHarnessError(f"unknown FakeModel script op: {op}")
                expected = _MODEL_RESPONSE_TYPES[op]
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
    def from_cassette(cls, path: Path) -> FakeModel:
        entries = load_cassette(path)
        script: dict[str, list[BaseModel]] = {}
        for entry in entries:
            response_type = _MODEL_RESPONSE_TYPES.get(entry.op)
            if response_type is None:
                raise CassetteValidationError(
                    f"cassette contains unknown FakeModel op: {entry.op}"
                )
            script.setdefault(entry.op, []).append(
                response_type.model_validate(entry.response)
            )
        return cls(script=script)

    def capabilities(self) -> ModelCapabilities:
        response = self._next_response("capabilities", ModelCapabilities())
        assert isinstance(response, ModelCapabilities)
        self._record("capabilities", {}, response)
        return response

    def complete(self, req: ModelRequest, deadline: Deadline) -> ModelReceipt:
        if not isinstance(req, ModelRequest):
            raise TypeError("req must be a ModelRequest")
        if not isinstance(deadline, Deadline):
            raise TypeError("deadline must be a Deadline")
        response = self._next_response("complete", ModelReceipt())
        assert isinstance(response, ModelReceipt)
        self._record(
            "complete",
            {
                "req": model_to_json_object(req),
                "deadline": model_to_json_object(deadline),
            },
            response,
        )
        return response

    def _next_response(self, op: str, default: BaseModel) -> BaseModel:
        queue = self._script_queues.get(op)
        if queue is None:
            return default
        index = self._script_indexes[op]
        if index >= len(queue):
            raise FakeScriptExhaustedError(
                f"FakeModel script exhausted for op {op!r}"
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
