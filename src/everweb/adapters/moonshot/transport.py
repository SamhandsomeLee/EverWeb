"""Chat Completions transport boundary for MoonshotKimiModel."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from everweb.adapters.moonshot.errors import MoonshotTransportError

DEFAULT_MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"


@runtime_checkable
class ChatCompletionsTransport(Protocol):
    def post_chat_completions(
        self,
        *,
        api_key: str,
        body: dict[str, Any],
        timeout_s: float,
    ) -> dict[str, Any]: ...


class HttpxChatCompletionsTransport:
    """Production transport: httpx POST /chat/completions (lazy import)."""

    def __init__(self, *, base_url: str = DEFAULT_MOONSHOT_BASE_URL) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise MoonshotTransportError("base_url must be a non-empty str")
        self._base_url = base_url.rstrip("/")

    def post_chat_completions(
        self,
        *,
        api_key: str,
        body: dict[str, Any],
        timeout_s: float,
    ) -> dict[str, Any]:
        if not isinstance(api_key, str) or not api_key.strip():
            raise MoonshotTransportError("api_key must be a non-empty str")
        if type(timeout_s) is not float and type(timeout_s) is not int:
            raise MoonshotTransportError("timeout_s must be a number")
        if float(timeout_s) <= 0:
            raise MoonshotTransportError("timeout_s must be positive")
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - install contract covers this
            raise MoonshotTransportError(
                "httpx package is required for HttpxChatCompletionsTransport"
            ) from exc
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=body,
                timeout=float(timeout_s),
            )
            response.raise_for_status()
            payload = response.json()
        except MoonshotTransportError:
            raise
        except Exception as exc:
            raise MoonshotTransportError("moonshot chat completions request failed") from exc
        if not isinstance(payload, dict):
            raise MoonshotTransportError("moonshot response must be a JSON object")
        return payload


def default_chat_completions_transport() -> ChatCompletionsTransport:
    return HttpxChatCompletionsTransport()
