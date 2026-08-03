"""Artifact storage capability boundary."""

from typing import Protocol, runtime_checkable

from everweb.domain import ArtifactRef, ArtifactWrite


@runtime_checkable
class ArtifactPort(Protocol):
    """Infrastructure-neutral artifact operations."""

    def put_bytes(self, req: ArtifactWrite) -> ArtifactRef: ...

    def put_json(self, req: ArtifactWrite) -> ArtifactRef: ...

    def read(self, ref: ArtifactRef) -> bytes: ...
