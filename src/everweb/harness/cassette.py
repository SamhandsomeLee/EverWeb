"""Canonical cassette records for harness Fake adapters."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CassetteError(RuntimeError):
    """Base error for cassette persistence failures."""


class CassetteValidationError(CassetteError):
    """Cassette payload or path violates the harness contract."""


class CassetteEntry(BaseModel):
    """One recorded Fake Port call using only already-defined fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    op: str = Field(min_length=1)
    request: dict[str, Any]
    response: dict[str, Any]


def model_to_json_object(value: BaseModel | None) -> dict[str, Any]:
    """Serialize a domain model to a JSON object of existing fields only."""

    if value is None:
        return {}
    if not isinstance(value, BaseModel):
        raise TypeError("value must be a pydantic BaseModel or None")
    dumped = value.model_dump(mode="json")
    if not isinstance(dumped, dict):
        raise CassetteValidationError("cassette models must serialize to objects")
    return dumped


def dump_cassette(entries: Sequence[CassetteEntry], path: Path) -> None:
    """Write cassette entries as deterministic canonical JSON."""

    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    payload = [entry.model_dump(mode="json") for entry in entries]
    try:
        encoded = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CassetteValidationError("cassette is not canonical JSON") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)


def load_cassette(path: Path) -> tuple[CassetteEntry, ...]:
    """Load cassette entries from a canonical JSON file."""

    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if not path.is_file():
        raise CassetteValidationError("cassette path must be an existing file")
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CassetteValidationError("failed to read cassette JSON") from exc
    if not isinstance(payload, list):
        raise CassetteValidationError("cassette root must be a JSON array")
    try:
        return tuple(CassetteEntry.model_validate(item) for item in payload)
    except ValidationError as exc:
        raise CassetteValidationError("cassette entries are malformed") from exc
