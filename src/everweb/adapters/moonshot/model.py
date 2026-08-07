"""Moonshot/Kimi ModelPort with fixed model identity and redacted receipts."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import JsonValue

from everweb.adapters.moonshot.errors import MoonshotConfigError, MoonshotTransportError
from everweb.adapters.moonshot.transport import (
    ChatCompletionsTransport,
    default_chat_completions_transport,
)
from everweb.domain import (
    Deadline,
    ModelCapabilities,
    ModelReceipt,
    ModelRequest,
)
from everweb.domain.sensitive import contains_sensitive_content

FIXED_PROVIDER = "moonshot"
FIXED_MODEL = "kimi-k2.6"
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def _normalize_model_id(value: str) -> str:
    return value.strip().casefold()


def _parse_structured_content(content: str) -> dict[str, JsonValue] | None:
    text = content.strip()
    if not text:
        return None
    candidates = [text]
    repaired = _TRAILING_COMMA.sub(r"\1", text)
    if repaired != text:
        candidates.append(repaired)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


class MoonshotKimiModel:
    """ModelPort backed by Moonshot Chat Completions for kimi-k2.6."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: ChatCompletionsTransport | None = None,
        model: str = FIXED_MODEL,
    ) -> None:
        if model != FIXED_MODEL:
            raise MoonshotConfigError(
                f"configured model must be {FIXED_MODEL!r}; got {model!r}"
            )
        key = api_key if api_key is not None else os.environ.get("MOONSHOT_API_KEY")
        if not isinstance(key, str) or not key.strip():
            raise MoonshotConfigError(
                "api_key or MOONSHOT_API_KEY environment variable is required"
            )
        self._api_key = key.strip()
        self._transport = (
            transport
            if transport is not None
            else default_chat_completions_transport()
        )
        self._configured_model = FIXED_MODEL

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider=FIXED_PROVIDER,
            configured_model=self._configured_model,
            supports_structured_output=True,
        )

    def complete(self, req: ModelRequest, deadline: Deadline) -> ModelReceipt:
        if not isinstance(req, ModelRequest):
            raise TypeError("req must be a ModelRequest")
        if not isinstance(deadline, Deadline):
            raise TypeError("deadline must be a Deadline")
        if not req.messages:
            return self._fail_receipt(
                returned_model=None,
                error_code="INVALID_MODEL_REQUEST",
                content_text=None,
            )

        body: dict[str, Any] = {
            "model": self._configured_model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in req.messages
            ],
        }
        if req.response_format == "json_object":
            body["response_format"] = {"type": "json_object"}

        try:
            payload = self._transport.post_chat_completions(
                api_key=self._api_key,
                body=body,
                timeout_s=deadline.timeout_s,
            )
        except MoonshotTransportError:
            return self._fail_receipt(
                returned_model=None,
                error_code="MODEL_TRANSPORT_ERROR",
                content_text=None,
            )

        returned_model = payload.get("model")
        returned_model_str = (
            returned_model if isinstance(returned_model, str) else None
        )
        if returned_model_str is None or _normalize_model_id(
            returned_model_str
        ) != _normalize_model_id(self._configured_model):
            return self._fail_receipt(
                returned_model=returned_model_str,
                error_code="MODEL_IDENTITY_MISMATCH",
                content_text=None,
            )

        content_text = self._extract_assistant_text(payload)
        usage = payload.get("usage")
        input_tokens: int | None = None
        output_tokens: int | None = None
        if isinstance(usage, dict):
            prompt = usage.get("prompt_tokens")
            completion = usage.get("completion_tokens")
            if type(prompt) is int:
                input_tokens = prompt
            if type(completion) is int:
                output_tokens = completion

        structured: dict[str, JsonValue] | None = None
        error_code: str | None = None
        ok = True
        if req.response_format == "json_object":
            if content_text is None:
                ok = False
                error_code = "MALFORMED_MODEL_OUTPUT"
            else:
                structured = _parse_structured_content(content_text)
                if structured is None:
                    ok = False
                    error_code = "MALFORMED_MODEL_OUTPUT"

        receipt = ModelReceipt(
            ok=ok,
            provider=FIXED_PROVIDER,
            configured_model=self._configured_model,
            returned_model=returned_model_str,
            content_text=content_text,
            structured=structured,
            error_code=error_code,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        dumped = json.dumps(receipt.model_dump(mode="json"), ensure_ascii=True)
        if contains_sensitive_content(dumped):
            return self._fail_receipt(
                returned_model=returned_model_str,
                error_code="SENSITIVE_CONTENT_BLOCKED",
                content_text=None,
            )
        return receipt

    def _extract_assistant_text(self, payload: dict[str, Any]) -> str | None:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first = choices[0]
        if not isinstance(first, dict):
            return None
        message = first.get("message")
        if not isinstance(message, dict):
            return None
        # Drop provider reasoning / thinking; only surface assistant content.
        content = message.get("content")
        if isinstance(content, str):
            return content
        return None

    def _fail_receipt(
        self,
        *,
        returned_model: str | None,
        error_code: str,
        content_text: str | None,
    ) -> ModelReceipt:
        return ModelReceipt(
            ok=False,
            provider=FIXED_PROVIDER,
            configured_model=self._configured_model,
            returned_model=returned_model,
            content_text=content_text,
            structured=None,
            error_code=error_code,
            input_tokens=None,
            output_tokens=None,
        )
