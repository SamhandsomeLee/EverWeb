"""Unit tests for trace event facts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from everweb.domain import TraceEnvelope

EXPECTED_FIELDS = {
    "seq",
    "schema_version",
    "execution_id",
    "event_type",
    "payload",
    "timestamp",
    "checksum",
}


def trace_values() -> dict[str, Any]:
    return {
        "seq": 1,
        "schema_version": "internal-v0",
        "execution_id": "execution-001",
        "event_type": "page_observed",
        "payload": {"page_id": "page-001", "ready": True},
        "timestamp": datetime(2026, 8, 3, 2, 30, tzinfo=UTC),
        "checksum": "sha256:example",
    }


def test_trace_envelope_matches_canonical_fields_and_round_trips() -> None:
    envelope = TraceEnvelope.model_validate(trace_values())

    assert set(TraceEnvelope.model_fields) == EXPECTED_FIELDS
    assert all(field.is_required() for field in TraceEnvelope.model_fields.values())
    assert TraceEnvelope.model_validate_json(envelope.model_dump_json()) == envelope


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("seq", "1"),
        ("schema_version", 1),
        ("execution_id", 1),
        ("event_type", 1),
        ("payload", []),
        ("timestamp", "2026-08-03T02:30:00Z"),
        ("checksum", 1),
    ],
)
def test_trace_envelope_rejects_implicit_coercion(
    field_name: str,
    value: Any,
) -> None:
    values = trace_values()
    values[field_name] = value

    with pytest.raises(ValidationError):
        TraceEnvelope.model_validate(values)


def test_trace_envelope_requires_every_field() -> None:
    for field_name in EXPECTED_FIELDS:
        values = trace_values()
        del values[field_name]

        with pytest.raises(ValidationError):
            TraceEnvelope.model_validate(values)


def test_trace_envelope_forbids_extra_fields_and_is_frozen() -> None:
    values = trace_values()
    values["recovered"] = False
    with pytest.raises(ValidationError):
        TraceEnvelope.model_validate(values)

    envelope = TraceEnvelope.model_validate(trace_values())
    with pytest.raises(ValidationError):
        setattr(envelope, "checksum", "sha256:changed")
