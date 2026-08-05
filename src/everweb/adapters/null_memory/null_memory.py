"""NullMemory adapter: optional memory capability closed (off)."""

from __future__ import annotations

from everweb.domain import (
    MemoryHealth,
    RecallReceipt,
    RecallRequest,
    RunTrace,
    StoreReceipt,
)


class NullMemory:
    """Production default for closed optional memory (INV-11 off)."""

    def health(self) -> MemoryHealth:
        return MemoryHealth()

    def recall(self, req: RecallRequest) -> RecallReceipt:
        if not isinstance(req, RecallRequest):
            raise TypeError("req must be a RecallRequest")
        return RecallReceipt()

    def submit_run(self, trace: RunTrace) -> StoreReceipt:
        if not isinstance(trace, RunTrace):
            raise TypeError("trace must be a RunTrace")
        return StoreReceipt()
