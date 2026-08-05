"""Browser capability probe receipts (nine §9.2 flags with explicit degrade)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from everweb.domain.contract import Receipt
from everweb.domain.port_contracts import BrowserCapabilities


class BrowserCapabilityName(StrEnum):
    """Closed set of BrowserCapabilities field names."""

    CAN_CREATE_CONTEXT = "can_create_context"
    CAN_CLOSE_CREATED_CONTEXT = "can_close_created_context"
    CAN_CREATE_CDP_SESSION = "can_create_cdp_session"
    CAN_CAPTURE_AX_TREE = "can_capture_ax_tree"
    CAN_DOWNLOAD = "can_download"
    CAN_OPEN_POPUP = "can_open_popup"
    CAN_SET_STORAGE_STATE = "can_set_storage_state"
    CAN_CLEAR_PERMISSIONS = "can_clear_permissions"
    SUPPORTS_SERVICE_WORKER_CLEANUP = "supports_service_worker_cleanup"


BROWSER_CAPABILITY_NAMES: tuple[BrowserCapabilityName, ...] = tuple(
    BrowserCapabilityName
)


class CapabilityAvailabilityReceipt(Receipt):
    """One probed capability availability fact."""

    name: BrowserCapabilityName
    available: bool
    detail: str | None = None


class BrowserCapabilityProbeReport(Receipt):
    """Aggregate of exactly nine capability availability receipts."""

    capabilities: BrowserCapabilities
    items: tuple[CapabilityAvailabilityReceipt, ...] = Field(min_length=9, max_length=9)

    @model_validator(mode="after")
    def _require_complete_unique_coverage(self) -> BrowserCapabilityProbeReport:
        names = tuple(item.name for item in self.items)
        if len(set(names)) != len(BROWSER_CAPABILITY_NAMES):
            raise ValueError("probe report must cover each BrowserCapabilityName once")
        if set(names) != set(BROWSER_CAPABILITY_NAMES):
            raise ValueError("probe report capability names must match the closed set")
        for item in self.items:
            expected = getattr(self.capabilities, item.name.value)
            if item.available is not expected:
                raise ValueError(
                    f"receipt {item.name.value} available={item.available} "
                    f"does not match capabilities.{item.name.value}={expected}"
                )
        return self
