"""Minimal gate receipt placeholder until Navigation/Answer gates land."""

from pydantic import BaseModel, ConfigDict


class GateReceipt(BaseModel):
    """Frozen placeholder for one gate evaluation outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    accepted: bool
