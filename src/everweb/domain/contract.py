"""Base contract types shared by domain receipts."""

from pydantic import BaseModel, ConfigDict


class Receipt(BaseModel):
    """Immutable serialization base for concrete receipt types."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
