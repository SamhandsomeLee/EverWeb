"""Infrastructure-neutral value types used by core port contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, JsonValue

from everweb.domain.contract import Receipt


class _PortValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BrowserCapabilities(_PortValue):
    """Runtime capabilities exposed by a browser connection."""

    can_create_context: bool
    can_close_created_context: bool
    can_create_cdp_session: bool
    can_capture_ax_tree: bool
    can_download: bool
    can_open_popup: bool
    can_set_storage_state: bool
    can_clear_permissions: bool
    supports_service_worker_cleanup: bool


class Task(_PortValue):
    """Pending canonical task schema."""


class BrowserSession(_PortValue):
    """Pending browser session schema."""


class ObservationRequest(_PortValue):
    """Pending observation request schema."""


class ObservationReceipt(Receipt):
    """Pending observation receipt schema."""


class ActionReceipt(Receipt):
    """Pending action receipt schema."""


class CaptureRequest(_PortValue):
    """Pending capture request schema."""


class CaptureReceipt(Receipt):
    """Pending capture receipt schema."""


class CloseReceipt(Receipt):
    """Pending browser session close receipt schema."""


class ModelCapabilities(_PortValue):
    """Pending model capabilities schema."""


class ModelRequest(_PortValue):
    """Pending model request schema."""


class Deadline(_PortValue):
    """Pending deadline schema."""


class ModelReceipt(Receipt):
    """Pending model receipt schema."""


class VisionRequest(_PortValue):
    """Pending vision request schema."""


class VisionReceipt(Receipt):
    """Pending vision receipt schema."""


class RecallRequest(_PortValue):
    """Pending memory recall request schema."""


class RecallReceipt(Receipt):
    """Pending memory recall receipt schema."""


class RunTrace(_PortValue):
    """Pending memory run trace schema."""


class StoreReceipt(Receipt):
    """Pending memory store receipt schema."""


class MemoryHealth(_PortValue):
    """Pending memory health schema."""


class ArtifactWrite(_PortValue):
    """Content and metadata requested for one immutable artifact."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        ser_json_bytes="base64",
        val_json_bytes="base64",
    )

    artifact_id: str
    kind: str
    relative_path: str
    content: bytes | JsonValue
    mime_type: str | None


class ArtifactRef(_PortValue):
    """Verified reference to one immutable artifact."""

    artifact_id: str
    kind: str
    relative_path: str
    sha256: str
    byte_size: int
    mime_type: str | None
    created_at: datetime
    redacted: bool
