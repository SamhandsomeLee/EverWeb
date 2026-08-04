"""Unit tests for TraceProjection."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from everweb.domain import ArtifactRef, TraceProjection


def artifact_ref(*, artifact_id: str = "artifact-001") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind="document",
        relative_path=f"documents/{artifact_id}.json",
        sha256="d" * 64,
        byte_size=4,
        mime_type="application/json",
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
        redacted=False,
    )


def test_trace_projection_preserves_order_and_allows_empty_sequences() -> None:
    projection = TraceProjection(
        urls=("https://z.example", "https://a.example"),
        actions=(),
        artifact_refs=(artifact_ref(),),
        capture_ref=artifact_ref(artifact_id="capture-001"),
        terminal_screenshot_ref=None,
    )

    assert projection.urls == ("https://z.example", "https://a.example")
    assert projection.actions == ()
    assert projection.terminal_screenshot_ref is None


def test_trace_projection_is_frozen() -> None:
    projection = TraceProjection()

    with pytest.raises(ValidationError):
        setattr(projection, "urls", ("https://forged.example",))
