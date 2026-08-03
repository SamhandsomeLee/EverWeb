"""Optional memory capability boundary."""

from typing import Protocol, runtime_checkable

from everweb.domain import (
    MemoryHealth,
    RecallReceipt,
    RecallRequest,
    RunTrace,
    StoreReceipt,
)


@runtime_checkable
class MemoryPort(Protocol):
    """Infrastructure-neutral optional memory operations."""

    def recall(self, req: RecallRequest) -> RecallReceipt: ...

    def submit_run(self, trace: RunTrace) -> StoreReceipt: ...

    def health(self) -> MemoryHealth: ...
