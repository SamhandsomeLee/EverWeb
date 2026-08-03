"""Unit tests for competition capability facts and placeholders."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from everweb.competition import CompetitionCapabilities

PENDING_FIELDS = (
    "task_wall_clock_s",
    "official_status_values",
    "official_output_schema",
    "official_step_semantics",
    "downloads_parseable",
)


def test_known_capabilities_match_public_rules() -> None:
    capabilities = CompetitionCapabilities(schema_version="  internal-v0  ")

    assert capabilities.schema_version == "internal-v0"
    assert capabilities.max_concurrency == 8
    assert capabilities.max_official_steps == 100
    assert capabilities.model_request_timeout_s == 180
    assert capabilities.browser_transport == "cdp"
    assert capabilities.browser_interaction_must_use_playwright is True
    assert capabilities.search_engines_allowed is False
    assert capabilities.task_retry_allowed is False


def test_capabilities_round_trip_and_are_frozen() -> None:
    capabilities = CompetitionCapabilities(schema_version="internal-v0")

    assert (
        CompetitionCapabilities.model_validate_json(capabilities.model_dump_json())
        == capabilities
    )
    with pytest.raises(ValidationError):
        setattr(capabilities, "max_concurrency", 16)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("schema_version", ""),
        ("schema_version", "  "),
        ("schema_version", 1),
        ("max_concurrency", 0),
        ("max_official_steps", -1),
        ("model_request_timeout_s", 0),
        ("task_wall_clock_s", 0),
        ("browser_transport", "webdriver"),
        ("browser_interaction_must_use_playwright", "true"),
        ("search_engines_allowed", 0),
        ("task_retry_allowed", "false"),
    ],
)
def test_capabilities_reject_invalid_or_coerced_values(
    field_name: str,
    value: Any,
) -> None:
    values: dict[str, Any] = {"schema_version": "internal-v0", field_name: value}

    with pytest.raises(ValidationError):
        CompetitionCapabilities.model_validate(values)


def test_capabilities_require_schema_version_and_forbid_extra_fields() -> None:
    assert CompetitionCapabilities.model_fields["schema_version"].is_required()

    with pytest.raises(ValidationError):
        CompetitionCapabilities.model_validate({})

    with pytest.raises(ValidationError):
        CompetitionCapabilities.model_validate(
            {"schema_version": "internal-v0", "official_status": "SUCCESS"}
        )


def test_pending_template_fields_have_only_none_defaults() -> None:
    capabilities = CompetitionCapabilities(schema_version="internal-v0")

    assert all(getattr(capabilities, field_name) is None for field_name in PENDING_FIELDS)
    for field_name in PENDING_FIELDS:
        field = CompetitionCapabilities.model_fields[field_name]
        assert field.default is None
        assert field.default_factory is None


def test_pending_template_fields_accept_only_explicit_typed_values() -> None:
    capabilities = CompetitionCapabilities(
        schema_version="template-supplied",
        task_wall_clock_s=600,
        official_status_values=["template_status"],
        official_output_schema={"type": "object"},
        official_step_semantics="provided-by-template",
        downloads_parseable=False,
    )

    assert capabilities.model_dump(mode="json") == {
        "schema_version": "template-supplied",
        "max_concurrency": 8,
        "max_official_steps": 100,
        "model_request_timeout_s": 180,
        "task_wall_clock_s": 600,
        "browser_transport": "cdp",
        "browser_interaction_must_use_playwright": True,
        "search_engines_allowed": False,
        "task_retry_allowed": False,
        "official_status_values": ["template_status"],
        "official_output_schema": {"type": "object"},
        "official_step_semantics": "provided-by-template",
        "downloads_parseable": False,
    }


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("task_wall_clock_s", "600"),
        ("official_status_values", "template_status"),
        ("official_status_values", [1]),
        ("official_output_schema", []),
        ("official_step_semantics", 1),
        ("downloads_parseable", "false"),
    ],
)
def test_pending_template_fields_reject_implicit_coercion(
    field_name: str,
    value: Any,
) -> None:
    values: dict[str, Any] = {"schema_version": "internal-v0", field_name: value}

    with pytest.raises(ValidationError):
        CompetitionCapabilities.model_validate(values)
