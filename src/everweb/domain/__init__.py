"""EverWeb domain package boundary."""

from everweb.domain.action import (
    ActionKind,
    RoleNameLocator,
    ScrollMode,
    SideEffectRisk,
    TypedAction,
)
from everweb.domain.capability_probe import (
    BROWSER_CAPABILITY_NAMES,
    BrowserCapabilityName,
    BrowserCapabilityProbeReport,
    CapabilityAvailabilityReceipt,
)
from everweb.domain.contract import Receipt
from everweb.domain.emergency import EmergencySnapshot
from everweb.domain.errors import ErrorCode, FailureRecord
from everweb.domain.evidence import EvidenceAtom
from everweb.domain.gate import GateReceipt
from everweb.domain.output import OfficialOutputDraft
from everweb.domain.page_view import (
    FrameIdentity,
    InteractiveTarget,
    PageIdentity,
    PageView,
    ProtectedState,
)
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
    ModelMessage,
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
from everweb.domain.provider_manifest import (
    KIMI_PRIMARY_PROFILE,
    KIMI_PRIMARY_ROLES,
    ScoringPathProviderCall,
    ScoringPathProviderManifest,
)
from everweb.domain.run_manifest import InternalRunManifest
from everweb.domain.runtime_phase import RuntimePhase
from everweb.domain.task import TaskIdentity
from everweb.domain.terminal import InternalTerminalState
from everweb.domain.trace import TraceEnvelope
from everweb.domain.trace_projection import TraceProjection

__all__ = [
    "ActionReceipt",
    "ActionKind",
    "ArtifactRef",
    "ArtifactWrite",
    "BROWSER_CAPABILITY_NAMES",
    "BrowserCapabilities",
    "BrowserCapabilityName",
    "BrowserCapabilityProbeReport",
    "BrowserSession",
    "CapabilityAvailabilityReceipt",
    "CaptureReceipt",
    "CaptureRequest",
    "CloseReceipt",
    "Deadline",
    "EmergencySnapshot",
    "ErrorCode",
    "EvidenceAtom",
    "FailureRecord",
    "FrameIdentity",
    "GateReceipt",
    "InteractiveTarget",
    "InternalRunManifest",
    "InternalTerminalState",
    "KIMI_PRIMARY_PROFILE",
    "KIMI_PRIMARY_ROLES",
    "MemoryHealth",
    "ModelCapabilities",
    "ModelMessage",
    "ModelReceipt",
    "ModelRequest",
    "ObservationReceipt",
    "ObservationRequest",
    "OfficialOutputDraft",
    "PageIdentity",
    "PageView",
    "ProtectedState",
    "RecallReceipt",
    "RecallRequest",
    "Receipt",
    "RoleNameLocator",
    "RuntimePhase",
    "RunTrace",
    "ScoringPathProviderCall",
    "ScoringPathProviderManifest",
    "ScrollMode",
    "SideEffectRisk",
    "StoreReceipt",
    "Task",
    "TaskIdentity",
    "TraceEnvelope",
    "TraceProjection",
    "TypedAction",
    "VisionReceipt",
    "VisionRequest",
]
