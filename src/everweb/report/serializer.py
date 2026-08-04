"""Pure SERIALIZE projection from injected facts to OfficialOutputDraft."""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from everweb.domain import (
    ArtifactRef,
    InternalTerminalState,
    OfficialOutputDraft,
    TaskIdentity,
)


class SerializerError(RuntimeError):
    """Base error for pure serializer failures."""


class SerializerValidationError(SerializerError):
    """SerializeRequest or projected facts violate the contract."""


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ValueError("sequence fields must be a list or tuple")


def _require_str_items(values: tuple[Any, ...], *, field_name: str) -> tuple[str, ...]:
    for index, item in enumerate(values):
        if type(item) is not str:
            raise SerializerValidationError(
                f"{field_name}[{index}] must be a str"
            )
    return cast(tuple[str, ...], values)


class SerializeRequest(BaseModel):
    """Injected projected facts for one pure SERIALIZE call."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task_identity: TaskIdentity
    internal_terminal_state: InternalTerminalState
    agent_answer: str
    urls: tuple[str, ...] = Field(default_factory=tuple)
    actions: tuple[str, ...] = Field(default_factory=tuple)
    decision_summaries: tuple[str, ...] = Field(default_factory=tuple)
    artifact_refs: tuple[ArtifactRef, ...] = Field(default_factory=tuple)
    capture_ref: ArtifactRef | None = None
    terminal_screenshot_ref: ArtifactRef | None = None

    @field_validator(
        "urls",
        "actions",
        "decision_summaries",
        "artifact_refs",
        mode="before",
    )
    @classmethod
    def _coerce_sequences(cls, value: Any) -> tuple[Any, ...]:
        return _as_tuple(value)


def serialize(request: SerializeRequest) -> OfficialOutputDraft:
    """Assemble OfficialOutputDraft without I/O, ports, or discovery."""

    if not isinstance(request, SerializeRequest):
        raise TypeError("request must be a SerializeRequest")

    try:
        urls = _require_str_items(request.urls, field_name="urls")
        actions = _require_str_items(request.actions, field_name="actions")
        decision_summaries = _require_str_items(
            request.decision_summaries,
            field_name="decision_summaries",
        )
        artifact_refs = tuple(request.artifact_refs)
        for index, ref in enumerate(artifact_refs):
            if not isinstance(ref, ArtifactRef):
                raise SerializerValidationError(
                    f"artifact_refs[{index}] must be an ArtifactRef"
                )

        return OfficialOutputDraft(
            task_identity=request.task_identity,
            mapped_status=None,
            agent_answer=request.agent_answer,
            urls=urls,
            actions=actions,
            decision_summaries=decision_summaries,
            artifact_refs=artifact_refs,
            capture_ref=request.capture_ref,
            terminal_screenshot_ref=request.terminal_screenshot_ref,
        )
    except ValidationError as exc:
        raise SerializerValidationError(
            "failed to assemble OfficialOutputDraft"
        ) from exc
