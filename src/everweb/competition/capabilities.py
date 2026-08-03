"""Competition capability facts and pending template placeholders."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SchemaVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
PositiveInteger = Annotated[int, Field(gt=0)]


class CompetitionCapabilities(BaseModel):
    """Versioned view of known and unresolved competition capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: SchemaVersion
    max_concurrency: PositiveInteger = 8
    max_official_steps: PositiveInteger = 100
    model_request_timeout_s: PositiveInteger = 180
    task_wall_clock_s: PositiveInteger | None = None

    browser_transport: Literal["cdp"] = "cdp"
    browser_interaction_must_use_playwright: bool = True
    search_engines_allowed: bool = False
    task_retry_allowed: bool = False

    official_status_values: list[str] | None = None
    official_output_schema: dict[str, Any] | None = None
    official_step_semantics: str | None = None
    downloads_parseable: bool | None = None
