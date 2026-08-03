"""Task identity types owned by the domain layer."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class TaskIdentity(BaseModel):
    """Stable identity for one task, independent of competition input details."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
