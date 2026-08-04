"""Internal official output draft facts owned by the domain layer."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from everweb.domain.port_contracts import ArtifactRef
from everweb.domain.task import TaskIdentity


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ValueError("sequence fields must be a list or tuple")


def _parse_artifact_ref(value: Any) -> ArtifactRef:
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        return ArtifactRef.model_validate_json(json.dumps(value))
    raise ValueError("artifact ref must be an ArtifactRef or object")


class OfficialOutputDraft(BaseModel):
    """Frozen internal draft before competition OutputMapper mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task_identity: TaskIdentity
    mapped_status: str | None
    agent_answer: str
    urls: tuple[str, ...] = Field(default_factory=tuple)
    actions: tuple[str, ...] = Field(default_factory=tuple)
    decision_summaries: tuple[str, ...] = Field(default_factory=tuple)
    artifact_refs: tuple[ArtifactRef, ...] = Field(default_factory=tuple)
    capture_ref: ArtifactRef | None
    terminal_screenshot_ref: ArtifactRef | None

    @field_validator(
        "urls",
        "actions",
        "decision_summaries",
        mode="before",
    )
    @classmethod
    def _coerce_string_sequences(cls, value: Any) -> tuple[Any, ...]:
        return _as_tuple(value)

    @field_validator("artifact_refs", mode="before")
    @classmethod
    def _coerce_artifact_refs(cls, value: Any) -> tuple[ArtifactRef, ...]:
        return tuple(_parse_artifact_ref(item) for item in _as_tuple(value))

    @field_validator("capture_ref", "terminal_screenshot_ref", mode="before")
    @classmethod
    def _coerce_optional_artifact_ref(cls, value: Any) -> ArtifactRef | None:
        if value is None:
            return None
        return _parse_artifact_ref(value)
