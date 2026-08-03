"""Emergency snapshot facts owned by the domain layer."""

from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from everweb.domain.errors import FailureRecord
from everweb.domain.gate import GateReceipt
from everweb.domain.port_contracts import ArtifactRef
from everweb.domain.task import TaskIdentity
from everweb.domain.terminal import InternalTerminalState

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
NonNegativeInteger = Annotated[int, Field(ge=0)]


class EmergencySnapshot(BaseModel):
    """Crash-recovery checkpoint for one Worker execution."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_id: NonEmptyString
    task_identity: TaskIdentity
    last_persisted_event_seq: NonNegativeInteger
    internal_terminal_state: InternalTerminalState | None
    best_candidate_ref: ArtifactRef | None
    last_url: str | None
    last_screenshot_ref: ArtifactRef | None
    navigation_gate: GateReceipt | None
    answer_gate: GateReceipt | None
    failure: FailureRecord | None
    updated_at: AwareDatetime
