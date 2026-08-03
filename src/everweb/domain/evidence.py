"""Evidence facts owned by the domain layer."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceAtom(BaseModel):
    """Smallest provenance-bearing fact that may support an answer claim."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    evidence_id: str
    execution_id: str
    iteration_id: int
    action_id: str | None

    claim_key: str
    raw_value: Any
    normalized_value: Any

    source_kind: str
    source_uri: str | None
    source_digest: str
    snapshot_ref: str | None
    locator_or_span: str | None
    page_id: str | None
    frame_id: str | None
    network_request_id: str | None
    document_page: int | None
    screenshot_ref: str | None

    observed_at: datetime
    extraction_method: str
    normalization_version: str
    trust_level: str

    parents: list[str] = Field(default_factory=list)
    deprecated_by: str | None = None
