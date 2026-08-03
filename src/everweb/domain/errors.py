"""Serializable internal failure types."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

ErrorCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^everweb(?:\.[a-z][a-z0-9_]*)+$",
    ),
]


class FailureRecord(BaseModel):
    """Minimal immutable failure fact without competition status semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: ErrorCode
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
