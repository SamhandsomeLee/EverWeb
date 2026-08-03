"""Trace event facts owned by the domain layer."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TraceEnvelope(BaseModel):
    """Versioned envelope for one append-only trace event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    seq: int
    schema_version: str
    execution_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime
    checksum: str
