"""Contract tests for infrastructure-neutral core ports."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from everweb.domain import (
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
    Receipt,
    RunTrace,
    StoreReceipt,
    Task,
    TypedAction,
    VisionReceipt,
    VisionRequest,
)
from everweb.ports import (
    ArtifactPort,
    BrowserPort,
    ClockPort,
    MemoryPort,
    ModelPort,
    VisionPort,
)

EXPECTED_BROWSER_CAPABILITY_FIELDS = {
    "can_create_context",
    "can_close_created_context",
    "can_create_cdp_session",
    "can_capture_ax_tree",
    "can_download",
    "can_open_popup",
    "can_set_storage_state",
    "can_clear_permissions",
    "supports_service_worker_cleanup",
}
EXPECTED_ARTIFACT_WRITE_FIELDS = {
    "artifact_id",
    "kind",
    "relative_path",
    "content",
    "mime_type",
}
EXPECTED_ARTIFACT_REF_FIELDS = {
    "artifact_id",
    "kind",
    "relative_path",
    "sha256",
    "byte_size",
    "mime_type",
    "created_at",
    "redacted",
}

PLACEHOLDER_TYPES: tuple[type[BaseModel], ...] = (
    Task,
    BrowserSession,
    ObservationRequest,
    ObservationReceipt,
    ActionReceipt,
    CaptureRequest,
    CaptureReceipt,
    CloseReceipt,
    ModelCapabilities,
    ModelRequest,
    Deadline,
    ModelReceipt,
    VisionRequest,
    VisionReceipt,
    RecallRequest,
    RecallReceipt,
    RunTrace,
    StoreReceipt,
    MemoryHealth,
)


def browser_capabilities() -> BrowserCapabilities:
    return BrowserCapabilities(
        can_create_context=True,
        can_close_created_context=True,
        can_create_cdp_session=True,
        can_capture_ax_tree=True,
        can_download=True,
        can_open_popup=True,
        can_set_storage_state=True,
        can_clear_permissions=True,
        supports_service_worker_cleanup=True,
    )


def artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="artifact-001",
        kind="document",
        relative_path="documents/artifact-001.json",
        sha256="0" * 64,
        byte_size=2,
        mime_type="application/json",
        created_at=datetime(2026, 8, 3, tzinfo=UTC),
        redacted=False,
    )


class BrowserStub:
    def capabilities(self) -> BrowserCapabilities:
        return browser_capabilities()

    def create_task_session(self, task: Task) -> BrowserSession:
        return BrowserSession()

    def observe(self, req: ObservationRequest) -> ObservationReceipt:
        return ObservationReceipt()

    def execute(self, action: TypedAction) -> ActionReceipt:
        return ActionReceipt()

    def capture(self, req: CaptureRequest) -> CaptureReceipt:
        return CaptureReceipt()

    def close_task_session(self) -> CloseReceipt:
        return CloseReceipt()


class ModelStub:
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities()

    def complete(self, req: ModelRequest, deadline: Deadline) -> ModelReceipt:
        return ModelReceipt()


class VisionStub:
    def available(self) -> bool:
        return False

    def analyze(self, req: VisionRequest) -> VisionReceipt:
        return VisionReceipt()


class MemoryStub:
    def recall(self, req: RecallRequest) -> RecallReceipt:
        return RecallReceipt()

    def submit_run(self, trace: RunTrace) -> StoreReceipt:
        return StoreReceipt()

    def health(self) -> MemoryHealth:
        return MemoryHealth()


class ArtifactStub:
    def put_bytes(self, req: ArtifactWrite) -> ArtifactRef:
        return artifact_ref()

    def put_json(self, req: ArtifactWrite) -> ArtifactRef:
        return artifact_ref()

    def read(self, ref: ArtifactRef) -> bytes:
        return b""


class ClockStub:
    def now(self) -> datetime:
        return datetime(2026, 8, 3, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1.0


def conforming_stubs() -> tuple[
    BrowserPort,
    ModelPort,
    VisionPort,
    MemoryPort,
    ArtifactPort,
    ClockPort,
]:
    browser: BrowserPort = BrowserStub()
    model: ModelPort = ModelStub()
    vision: VisionPort = VisionStub()
    memory: MemoryPort = MemoryStub()
    artifact: ArtifactPort = ArtifactStub()
    clock: ClockPort = ClockStub()
    return browser, model, vision, memory, artifact, clock


def declared_methods(protocol: type[object]) -> set[str]:
    return {
        name
        for name, value in vars(protocol).items()
        if not name.startswith("_") and callable(value)
    }


def test_stubs_conform_to_runtime_and_static_protocols() -> None:
    browser, model, vision, memory, artifact, clock = conforming_stubs()

    assert isinstance(browser, BrowserPort)
    assert isinstance(model, ModelPort)
    assert isinstance(vision, VisionPort)
    assert isinstance(memory, MemoryPort)
    assert isinstance(artifact, ArtifactPort)
    assert isinstance(clock, ClockPort)


def test_ports_expose_only_canonical_or_approved_methods() -> None:
    assert declared_methods(BrowserPort) == {
        "capabilities",
        "capture",
        "close_task_session",
        "create_task_session",
        "execute",
        "observe",
    }
    assert declared_methods(ModelPort) == {"capabilities", "complete"}
    assert declared_methods(VisionPort) == {"analyze", "available"}
    assert declared_methods(MemoryPort) == {"health", "recall", "submit_run"}
    assert declared_methods(ArtifactPort) == {"put_bytes", "put_json", "read"}
    assert declared_methods(ClockPort) == {"monotonic", "now"}


def test_browser_capabilities_are_strict_frozen_and_round_trip() -> None:
    capabilities = browser_capabilities()

    assert set(BrowserCapabilities.model_fields) == EXPECTED_BROWSER_CAPABILITY_FIELDS
    assert (
        BrowserCapabilities.model_validate_json(capabilities.model_dump_json())
        == capabilities
    )

    values = capabilities.model_dump()
    values["can_download"] = "true"
    with pytest.raises(ValidationError):
        BrowserCapabilities.model_validate(values)

    with pytest.raises(ValidationError):
        setattr(capabilities, "can_download", False)

    values = capabilities.model_dump()
    values["browser_name"] = "chromium"
    with pytest.raises(ValidationError):
        BrowserCapabilities.model_validate(values)


def test_artifact_contracts_are_strict_frozen_and_round_trip() -> None:
    write = ArtifactWrite(
        artifact_id="artifact-001",
        kind="document",
        relative_path="documents/artifact-001.json",
        content={"value": 1},
        mime_type="application/json",
    )
    reference = artifact_ref()
    binary_write = ArtifactWrite(
        artifact_id="artifact-002",
        kind="screenshot",
        relative_path="screenshots/artifact-002.png",
        content=b"\x89PNG\xff",
        mime_type="image/png",
    )

    assert set(ArtifactWrite.model_fields) == EXPECTED_ARTIFACT_WRITE_FIELDS
    assert set(ArtifactRef.model_fields) == EXPECTED_ARTIFACT_REF_FIELDS
    assert ArtifactWrite.model_validate_json(write.model_dump_json()) == write
    assert (
        ArtifactWrite.model_validate_json(binary_write.model_dump_json())
        == binary_write
    )
    assert ArtifactRef.model_validate_json(reference.model_dump_json()) == reference

    with pytest.raises(ValidationError):
        setattr(reference, "byte_size", 3)

    with pytest.raises(ValidationError):
        ArtifactWrite.model_validate(
            {
                **write.model_dump(),
                "relative_path": 1,
            }
        )

    with pytest.raises(ValidationError):
        ArtifactRef.model_validate(
            {
                **reference.model_dump(),
                "provider_id": "sdk-leak",
            }
        )


def test_pending_port_types_have_no_guessed_fields() -> None:
    for placeholder_type in PLACEHOLDER_TYPES:
        assert placeholder_type.model_fields == {}
        assert placeholder_type.model_config["extra"] == "forbid"
        assert placeholder_type.model_config["frozen"] is True
        assert placeholder_type.model_config["strict"] is True
        assert placeholder_type.model_validate_json("{}") == placeholder_type()

        with pytest.raises(ValidationError):
            placeholder_type.model_validate({"guessed_field": "value"})


def test_receipt_placeholders_preserve_receipt_contract() -> None:
    receipt_types = (
        ObservationReceipt,
        ActionReceipt,
        CaptureReceipt,
        CloseReceipt,
        ModelReceipt,
        VisionReceipt,
        RecallReceipt,
        StoreReceipt,
    )

    assert all(issubclass(receipt_type, Receipt) for receipt_type in receipt_types)
