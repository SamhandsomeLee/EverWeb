"""Competition-side OutputContract draft mapper from TraceProjection facts."""

from __future__ import annotations

from typing import Any, cast

from pydantic import ValidationError

from everweb.domain import (
    ArtifactRef,
    OfficialOutputDraft,
    TaskIdentity,
    TraceProjection,
)


class OutputContractDraftError(RuntimeError):
    """Base error for OutputContract draft mapping failures."""


class OutputContractDraftValidationError(OutputContractDraftError):
    """Draft inputs violate the OutputContract draft mapping contract."""


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ValueError("sequence fields must be a list or tuple")


def _require_str_items(values: tuple[Any, ...], *, field_name: str) -> tuple[str, ...]:
    for index, item in enumerate(values):
        if type(item) is not str:
            raise OutputContractDraftValidationError(
                f"{field_name}[{index}] must be a str"
            )
    return cast(tuple[str, ...], values)


class OutputContractDraftMapper:
    """Assemble OfficialOutputDraft from TraceProjection without guessing status."""

    def map_draft(
        self,
        *,
        task_identity: TaskIdentity,
        trace_projection: TraceProjection,
        agent_answer: str,
        decision_summaries: tuple[str, ...] | list[str] = (),
        artifact_refs: tuple[ArtifactRef, ...] | list[ArtifactRef] | None = None,
    ) -> OfficialOutputDraft:
        if not isinstance(task_identity, TaskIdentity):
            raise TypeError("task_identity must be a TaskIdentity")
        if not isinstance(trace_projection, TraceProjection):
            raise TypeError("trace_projection must be a TraceProjection")
        if type(agent_answer) is not str:
            raise TypeError("agent_answer must be a str")

        try:
            summaries = _require_str_items(
                _as_tuple(decision_summaries),
                field_name="decision_summaries",
            )
            if artifact_refs is None:
                merged_refs = trace_projection.artifact_refs
            else:
                merged_refs = tuple(artifact_refs)
            for index, ref in enumerate(merged_refs):
                if not isinstance(ref, ArtifactRef):
                    raise OutputContractDraftValidationError(
                        f"artifact_refs[{index}] must be an ArtifactRef"
                    )

            return OfficialOutputDraft(
                task_identity=task_identity,
                mapped_status=None,
                agent_answer=agent_answer,
                urls=trace_projection.urls,
                actions=trace_projection.actions,
                decision_summaries=summaries,
                artifact_refs=merged_refs,
                capture_ref=trace_projection.capture_ref,
                terminal_screenshot_ref=trace_projection.terminal_screenshot_ref,
            )
        except ValidationError as exc:
            raise OutputContractDraftValidationError(
                "failed to assemble OfficialOutputDraft"
            ) from exc
