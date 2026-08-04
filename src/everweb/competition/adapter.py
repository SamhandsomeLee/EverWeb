"""CompetitionAdapter protocol and pending-template null implementation."""

from __future__ import annotations

from typing import Never, Protocol, runtime_checkable

from everweb.competition.capabilities import CompetitionCapabilities
from everweb.competition.errors import PendingTemplateError
from everweb.domain import (
    ActionReceipt,
    InternalTerminalState,
    OfficialOutputDraft,
    Task,
    TypedAction,
)


@runtime_checkable
class CompetitionAdapter(Protocol):
    """Official template boundary. Unresolved methods stay PendingTemplate."""

    def capabilities(self) -> CompetitionCapabilities: ...

    def load_tasks(self, source: str) -> list[Task]: ...

    def map_status(self, state: InternalTerminalState) -> str | None: ...

    def map_output(self, draft: OfficialOutputDraft) -> Never: ...

    def count_step(self, action: TypedAction, receipt: ActionReceipt) -> int: ...


class NullCompetitionAdapter:
    """Pending-template adapter that never invents official schema or status."""

    def __init__(self, capabilities: CompetitionCapabilities) -> None:
        self._capabilities = capabilities

    def capabilities(self) -> CompetitionCapabilities:
        return self._capabilities

    def load_tasks(self, source: str) -> list[Task]:
        raise PendingTemplateError(
            "CompetitionAdapter.load_tasks is PendingTemplate until the "
            "official task source contract is published"
        )

    def map_status(self, state: InternalTerminalState) -> str | None:
        if not isinstance(state, InternalTerminalState):
            raise TypeError("state must be an InternalTerminalState")
        return None

    def map_output(self, draft: OfficialOutputDraft) -> Never:
        if not isinstance(draft, OfficialOutputDraft):
            raise TypeError("draft must be an OfficialOutputDraft")
        raise PendingTemplateError(
            "CompetitionAdapter.map_output is PendingTemplate until the "
            "official output schema is published (P2)"
        )

    def count_step(self, action: TypedAction, receipt: ActionReceipt) -> int:
        raise PendingTemplateError(
            "CompetitionAdapter.count_step is PendingTemplate until official "
            "step semantics are published"
        )
