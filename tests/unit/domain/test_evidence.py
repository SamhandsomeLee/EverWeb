"""Unit tests for evidence facts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from everweb.domain import EvidenceAtom

EXPECTED_FIELDS = {
    "evidence_id",
    "execution_id",
    "iteration_id",
    "action_id",
    "claim_key",
    "raw_value",
    "normalized_value",
    "source_kind",
    "source_uri",
    "source_digest",
    "snapshot_ref",
    "locator_or_span",
    "page_id",
    "frame_id",
    "network_request_id",
    "document_page",
    "screenshot_ref",
    "observed_at",
    "extraction_method",
    "normalization_version",
    "trust_level",
    "parents",
    "deprecated_by",
}


def evidence_values() -> dict[str, Any]:
    return {
        "evidence_id": "evidence-001",
        "execution_id": "execution-001",
        "iteration_id": 1,
        "action_id": "action-001",
        "claim_key": "price",
        "raw_value": {"text": "$10.00"},
        "normalized_value": {"amount": 10, "currency": "USD"},
        "source_kind": "dom_text",
        "source_uri": "https://example.test/item",
        "source_digest": "sha256:example",
        "snapshot_ref": "snapshot-001",
        "locator_or_span": "#price",
        "page_id": "page-001",
        "frame_id": None,
        "network_request_id": None,
        "document_page": None,
        "screenshot_ref": "screenshot-001",
        "observed_at": datetime(2026, 8, 3, 2, 30, tzinfo=UTC),
        "extraction_method": "text_content",
        "normalization_version": "internal-v0",
        "trust_level": "direct",
    }


def test_evidence_atom_matches_canonical_fields_and_round_trips() -> None:
    evidence = EvidenceAtom.model_validate(evidence_values())

    assert set(EvidenceAtom.model_fields) == EXPECTED_FIELDS
    assert EvidenceAtom.model_validate_json(evidence.model_dump_json()) == evidence


def test_evidence_atom_requires_canonical_fields() -> None:
    required_fields = {
        field_name
        for field_name, field in EvidenceAtom.model_fields.items()
        if field.is_required()
    }

    assert required_fields == EXPECTED_FIELDS - {"parents", "deprecated_by"}


def test_evidence_parents_have_independent_empty_defaults() -> None:
    first = EvidenceAtom.model_validate(evidence_values())
    second = EvidenceAtom.model_validate(evidence_values())

    assert first.parents == []
    assert second.parents == []
    assert first.parents is not second.parents
    assert EvidenceAtom.model_fields["parents"].default_factory is list
    assert EvidenceAtom.model_fields["deprecated_by"].default is None


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("evidence_id", 1),
        ("iteration_id", "1"),
        ("action_id", 1),
        ("document_page", "2"),
        ("observed_at", "2026-08-03T02:30:00Z"),
        ("parents", [1]),
        ("deprecated_by", 1),
    ],
)
def test_evidence_atom_rejects_implicit_coercion(
    field_name: str,
    value: Any,
) -> None:
    values = evidence_values()
    values[field_name] = value

    with pytest.raises(ValidationError):
        EvidenceAtom.model_validate(values)


def test_evidence_atom_forbids_extra_fields_and_is_frozen() -> None:
    values = evidence_values()
    values["confidence"] = 0.9
    with pytest.raises(ValidationError):
        EvidenceAtom.model_validate(values)

    evidence = EvidenceAtom.model_validate(evidence_values())
    with pytest.raises(ValidationError):
        setattr(evidence, "deprecated_by", "evidence-002")
