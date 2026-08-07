"""Contract tests for Moonshot/Kimi ModelPort with recorded transports."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any

import pytest

from everweb.adapters.moonshot import (
    FIXED_MODEL,
    FIXED_PROVIDER,
    MoonshotConfigError,
    MoonshotKimiModel,
)
from everweb.domain import Deadline, ModelMessage, ModelRequest
from everweb.domain.sensitive import contains_sensitive_content
from everweb.ports import ModelPort

ADAPTER_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "everweb"
    / "adapters"
    / "moonshot"
)
FORBIDDEN_IMPORT_ROOTS = (
    "openai",
    "playwright",
    "everweb.adapters.playwright_browser",
    "everweb.adapters.deepseek",
    "everweb.harness",
)


class RecordedChatCompletionsTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def post_chat_completions(
        self,
        *,
        api_key: str,
        body: dict[str, Any],
        timeout_s: float,
    ) -> dict[str, Any]:
        self.calls.append(
            {"api_key": api_key, "body": body, "timeout_s": timeout_s}
        )
        if not self._responses:
            raise RuntimeError("recorded transport exhausted")
        return self._responses.pop(0)


def _success_payload(
    *,
    model: str = FIXED_MODEL,
    content: str = '{"answer":"42"}',
    extra_message: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if extra_message:
        message.update(extra_message)
    return {
        "id": "chatcmpl-recorded",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
    }


def _request() -> ModelRequest:
    return ModelRequest(
        messages=(
            ModelMessage(role="user", content='Return JSON {"answer":"..."}'),
        ),
        response_format="json_object",
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


def test_moonshot_kimi_model_implements_model_port() -> None:
    model = MoonshotKimiModel(
        api_key="test-key",
        transport=RecordedChatCompletionsTransport([_success_payload()]),
    )
    assert isinstance(model, ModelPort)


def test_capabilities_pin_fixed_identity() -> None:
    model = MoonshotKimiModel(
        api_key="test-key",
        transport=RecordedChatCompletionsTransport([]),
    )
    caps = model.capabilities()
    assert caps.provider == FIXED_PROVIDER
    assert caps.configured_model == FIXED_MODEL
    assert caps.supports_structured_output is True


def test_rejects_non_fixed_configured_model() -> None:
    with pytest.raises(MoonshotConfigError):
        MoonshotKimiModel(
            api_key="test-key",
            model="latest",
            transport=RecordedChatCompletionsTransport([]),
        )


def test_recorded_complete_returns_structured_redacted_receipt() -> None:
    transport = RecordedChatCompletionsTransport(
        [
            _success_payload(
                extra_message={
                    "reasoning_content": "secret chain-of-thought",
                    "thinking": "do not leak",
                }
            )
        ]
    )
    model = MoonshotKimiModel(api_key="test-key", transport=transport)

    receipt = model.complete(_request(), Deadline(timeout_s=12.0))

    assert receipt.ok is True
    assert receipt.provider == FIXED_PROVIDER
    assert receipt.configured_model == FIXED_MODEL
    assert receipt.returned_model == FIXED_MODEL
    assert receipt.structured == {"answer": "42"}
    assert receipt.content_text == '{"answer":"42"}'
    assert receipt.input_tokens == 3
    assert receipt.output_tokens == 5
    assert receipt.error_code is None
    dumped = json.dumps(receipt.model_dump(mode="json"))
    assert "reasoning" not in dumped.casefold()
    assert "thinking" not in dumped.casefold()
    assert "test-key" not in dumped
    assert "Authorization" not in dumped
    assert not contains_sensitive_content(dumped)
    assert transport.calls[0]["body"]["model"] == FIXED_MODEL
    assert transport.calls[0]["timeout_s"] == 12.0
    assert transport.calls[0]["body"]["response_format"] == {"type": "json_object"}


def test_identity_mismatch_is_fail_closed() -> None:
    model = MoonshotKimiModel(
        api_key="test-key",
        transport=RecordedChatCompletionsTransport(
            [_success_payload(model="gpt-4o")]
        ),
    )
    receipt = model.complete(_request(), Deadline())
    assert receipt.ok is False
    assert receipt.error_code == "MODEL_IDENTITY_MISMATCH"
    assert receipt.structured is None


def test_malformed_json_is_fail_closed() -> None:
    model = MoonshotKimiModel(
        api_key="test-key",
        transport=RecordedChatCompletionsTransport(
            [_success_payload(content="{not-json")]
        ),
    )
    receipt = model.complete(_request(), Deadline())
    assert receipt.ok is False
    assert receipt.error_code == "MALFORMED_MODEL_OUTPUT"


def test_authorization_in_content_is_blocked_from_receipt() -> None:
    model = MoonshotKimiModel(
        api_key="test-key",
        transport=RecordedChatCompletionsTransport(
            [
                _success_payload(
                    content='{"Authorization":"Bearer leaked","answer":"1"}'
                )
            ]
        ),
    )
    receipt = model.complete(_request(), Deadline())
    assert receipt.ok is False
    assert receipt.error_code == "SENSITIVE_CONTENT_BLOCKED"
    dumped = json.dumps(receipt.model_dump(mode="json"))
    assert "Bearer leaked" not in dumped


def test_httpx_only_imported_in_transport_module() -> None:
    for path in ADAPTER_ROOT.rglob("*.py"):
        imported = _imported_modules(path)
        if path.name == "transport.py":
            continue
        assert "httpx" not in imported
        assert not any(name.startswith("httpx.") for name in imported)


def test_adapter_package_forbids_sdk_and_cross_adapter_imports() -> None:
    imported: set[str] = set()
    for path in ADAPTER_ROOT.rglob("*.py"):
        imported |= _imported_modules(path)
    for forbidden in FORBIDDEN_IMPORT_ROOTS:
        assert not any(
            module == forbidden or module.startswith(forbidden + ".")
            for module in imported
        ), imported


@pytest.mark.live
def test_live_moonshot_smoke_optional() -> None:
    if not os.environ.get("MOONSHOT_API_KEY"):
        pytest.skip("MOONSHOT_API_KEY not set")
    model = MoonshotKimiModel()
    receipt = model.complete(
        ModelRequest(
            messages=(ModelMessage(role="user", content='Reply with JSON {"ok":true}'),),
            response_format="json_object",
        ),
        Deadline(timeout_s=60.0),
    )
    assert receipt.configured_model == FIXED_MODEL
    assert receipt.returned_model is not None
