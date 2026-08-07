"""Scoring-path provider manifest facts (INV-12)."""

from __future__ import annotations

from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]

KIMI_PRIMARY_PROFILE = "kimi_primary"

KIMI_PRIMARY_ROLES: tuple[str, ...] = (
    "task_analyzer",
    "navigator",
    "navigator_fast",
    "summarizer",
    "extractor",    
    "verifier",
    "vision",
)


class ScoringPathProviderCall(BaseModel):
    """One formal-context provider call recorded on the scoring path."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role: NonEmptyString
    provider: NonEmptyString
    configured_model: NonEmptyString
    returned_model: str | None
    endpoint_host: NonEmptyString
    request_id: str | None
    route_id: NonEmptyString
    route_generation: Annotated[int, Field(ge=0)]
    started_at: AwareDatetime
    finished_at: AwareDatetime
    config_digest: NonEmptyString


class ScoringPathProviderManifest(BaseModel):
    """Aggregate of scoring-path provider calls for one profile plan/run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    profile_name: NonEmptyString
    config_digest: NonEmptyString
    calls: tuple[ScoringPathProviderCall, ...] = Field(default_factory=tuple)
