"""Shared pure helpers for strict JSONL persistence."""

from __future__ import annotations

import json
import math
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


class CanonicalJsonError(ValueError):
    """A value cannot be represented as strict canonical JSON."""


def canonical_json_bytes(value: Any) -> bytes:
    """Encode deterministic UTF-8 JSON without non-finite numbers."""

    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalJsonError("value is not canonical JSON") from exc


def normalize_json_value(
    value: Any,
    *,
    seen: set[int] | None = None,
) -> Any:
    """Validate JSON-native values and return a detached deep copy."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalJsonError("JSON numbers must be finite")
        return value

    active = set() if seen is None else seen
    if isinstance(value, list):
        identity = id(value)
        if identity in active:
            raise CanonicalJsonError("JSON must not contain cycles")
        active.add(identity)
        try:
            return [normalize_json_value(item, seen=active) for item in value]
        finally:
            active.remove(identity)

    if isinstance(value, dict):
        identity = id(value)
        if identity in active:
            raise CanonicalJsonError("JSON must not contain cycles")
        active.add(identity)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise CanonicalJsonError("JSON object keys must be strings")
                normalized[key] = normalize_json_value(item, seen=active)
            return normalized
        finally:
            active.remove(identity)

    raise CanonicalJsonError(
        f"JSON value has unsupported type {type(value).__name__}"
    )


def validate_single_path_segment(value: str, *, field_name: str) -> None:
    """Reject path separators and names invalid on POSIX or Windows."""

    posix_value = PurePosixPath(value)
    windows_value = PureWindowsPath(value)
    has_windows_invalid_character = any(
        character in '<>:"/\\|?*' or ord(character) < 32 for character in value
    )
    invalid = (
        not value
        or "\x00" in value
        or has_windows_invalid_character
        or value.endswith((".", " "))
        or posix_value.is_absolute()
        or windows_value.is_absolute()
        or bool(windows_value.drive)
        or len(posix_value.parts) != 1
        or len(windows_value.parts) != 1
        or windows_value.is_reserved()
        or value in {".", ".."}
    )
    if invalid:
        raise ValueError(f"{field_name} must be one portable path segment")
