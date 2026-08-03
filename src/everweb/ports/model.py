"""Model provider capability boundary."""

from typing import Protocol, runtime_checkable

from everweb.domain import Deadline, ModelCapabilities, ModelReceipt, ModelRequest


@runtime_checkable
class ModelPort(Protocol):
    """Provider-neutral model operations."""

    def capabilities(self) -> ModelCapabilities: ...

    def complete(self, req: ModelRequest, deadline: Deadline) -> ModelReceipt: ...
