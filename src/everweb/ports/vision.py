"""Optional vision capability boundary."""

from typing import Protocol, runtime_checkable

from everweb.domain import VisionReceipt, VisionRequest


@runtime_checkable
class VisionPort(Protocol):
    """Provider-neutral optional vision operations."""

    def available(self) -> bool: ...

    def analyze(self, req: VisionRequest) -> VisionReceipt: ...
