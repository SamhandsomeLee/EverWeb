"""Internal run manifest facts (not the full §27.1 competition RunManifest)."""

from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from everweb.domain.runtime_phase import RuntimePhase
from everweb.domain.task import TaskIdentity
from everweb.domain.terminal import InternalTerminalState

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class InternalRunManifest(BaseModel):
    """Minimal durable identity for one completed internal run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: NonEmptyString
    execution_id: NonEmptyString
    task_identity: TaskIdentity
    started_at: AwareDatetime
    ended_at: AwareDatetime
    internal_terminal_state: InternalTerminalState
    phases: tuple[RuntimePhase, ...] = Field(default_factory=tuple)
