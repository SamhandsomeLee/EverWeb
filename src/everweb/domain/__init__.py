"""EverWeb domain package boundary."""

from everweb.domain.action import ActionKind, TypedAction
from everweb.domain.contract import Receipt
from everweb.domain.errors import ErrorCode, FailureRecord
from everweb.domain.evidence import EvidenceAtom
from everweb.domain.port_contracts import (
    ActionReceipt,
    ArtifactRef,
    ArtifactWrite,
    BrowserCapabilities,
    BrowserSession,
    CaptureReceipt,
    CaptureRequest,
    CloseReceipt,
    Deadline,
    MemoryHealth,
    ModelCapabilities,
    ModelReceipt,
    ModelRequest,
    ObservationReceipt,
    ObservationRequest,
    RecallReceipt,
    RecallRequest,
    RunTrace,
    StoreReceipt,
    Task,
    VisionReceipt,
    VisionRequest,
)
from everweb.domain.task import TaskIdentity
from everweb.domain.terminal import InternalTerminalState
from everweb.domain.trace import TraceEnvelope

__all__ = [
    "ActionReceipt",
    "ActionKind",
    "ArtifactRef",
    "ArtifactWrite",
    "BrowserCapabilities",
    "BrowserSession",
    "CaptureReceipt",
    "CaptureRequest",
    "CloseReceipt",
    "Deadline",
    "ErrorCode",
    "EvidenceAtom",
    "FailureRecord",
    "InternalTerminalState",
    "MemoryHealth",
    "ModelCapabilities",
    "ModelReceipt",
    "ModelRequest",
    "ObservationReceipt",
    "ObservationRequest",
    "RecallReceipt",
    "RecallRequest",
    "Receipt",
    "RunTrace",
    "StoreReceipt",
    "Task",
    "TaskIdentity",
    "TraceEnvelope",
    "TypedAction",
    "VisionReceipt",
    "VisionRequest",
]
