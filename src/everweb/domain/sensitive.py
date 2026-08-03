"""Pure detection policy for content that must not reach persisted outputs."""

from __future__ import annotations

import re

SENSITIVE_TEXT = re.compile(
    r"(?i)(?:"
    r"\b(?:authorization|proxy-authorization|cookie|set-cookie|api[_-]?key|"
    r"session(?:[_-]?id)?|(?:access[_-]?|refresh[_-]?|id[_-]?)?token|"
    r"(?:auth[_-]?)?code|password|passwd|client[_-]?secret|private[_-]?key|"
    r"reasoning|provider[_-]?reasoning)\b[\"']?\s*[:=]"
    r"|\bbearer\s+[a-z0-9._~+/=-]+"
    r"|[?&](?:api[_-]?key|session(?:[_-]?id)?|"
    r"(?:access[_-]?|refresh[_-]?)?token|(?:auth[_-]?)?code)="
    r"[^&#\s]+"
    r")"
)


def contains_sensitive_content(content: bytes | str) -> bool:
    """Detect canonical secret fields and provider reasoning markers."""

    if isinstance(content, str):
        return SENSITIVE_TEXT.search(content) is not None

    candidates = [content.decode("latin-1")]
    for encoding, width in (
        ("utf-16-le", 2),
        ("utf-16-be", 2),
        ("utf-32-le", 4),
        ("utf-32-be", 4),
    ):
        for offset in range(width):
            usable_bytes = ((len(content) - offset) // width) * width
            if usable_bytes > 0:
                candidates.append(
                    content[offset : offset + usable_bytes].decode(
                        encoding,
                        errors="ignore",
                    )
                )
    return any(SENSITIVE_TEXT.search(text) is not None for text in candidates)
