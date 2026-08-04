"""Contract purity spies for SERIALIZE (INV-3 / INV-6)."""

from __future__ import annotations

import ast
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from everweb.domain import (
    ArtifactRef,
    InternalTerminalState,
    TaskIdentity,
)
from everweb.report import SerializeRequest, serialize
from everweb.report import serializer as serializer_module

SERIALIZER_PATH = Path(serializer_module.__file__).resolve()
FORBIDDEN_IMPORT_ROOTS = {
    "everweb.adapters",
    "everweb.competition",
    "everweb.supervisor",
    "everweb.ports",
    "httpx",
    "playwright",
}
FORBIDDEN_CALL_NAMES = {
    "listdir",
    "scandir",
    "glob",
    "iglob",
    "iterdir",
    "rglob",
    "walk",
}


def _module_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _module_name(node.value)
        if parent is None:
            return None
        return f"{parent}.{node.attr}"
    return None


def test_serializer_source_forbids_side_effect_imports_and_discovery() -> None:
    tree = ast.parse(SERIALIZER_PATH.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)

    for forbidden in FORBIDDEN_IMPORT_ROOTS:
        assert not any(
            name == forbidden or name.startswith(f"{forbidden}.")
            for name in imported
        ), forbidden

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _module_name(node.func)
        if name is None:
            continue
        leaf = name.rsplit(".", 1)[-1]
        assert leaf not in FORBIDDEN_CALL_NAMES, name


def test_serialize_runtime_does_not_touch_discovery_or_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hits: list[str] = []

    def spy_listdir(*args: object, **kwargs: object) -> list[str]:
        hits.append("listdir")
        return []

    def spy_iterdir(self: Path) -> list[Path]:
        hits.append("iterdir")
        return []

    class PortProbe:
        def capabilities(self) -> None:
            hits.append("port")

        def now(self) -> datetime:
            hits.append("clock")
            return datetime(2026, 8, 4, tzinfo=UTC)

        def monotonic(self) -> float:
            hits.append("clock")
            return 0.0

    monkeypatch.setattr(os, "listdir", spy_listdir)
    monkeypatch.setattr(Path, "iterdir", spy_iterdir)
    probe = PortProbe()

    request = SerializeRequest(
        task_identity=TaskIdentity(task_id="task-001"),
        internal_terminal_state=InternalTerminalState.BEST_EFFORT,
        agent_answer="answer",
        urls=("https://example.com",),
        actions=("click",),
        decision_summaries=("summary",),
        artifact_refs=(
            ArtifactRef(
                artifact_id="artifact-001",
                kind="document",
                relative_path="documents/a.json",
                sha256="e" * 64,
                byte_size=1,
                mime_type="application/json",
                created_at=datetime(2026, 8, 4, tzinfo=UTC),
                redacted=False,
            ),
        ),
        capture_ref=None,
        terminal_screenshot_ref=None,
    )
    draft = serialize(request)

    assert draft.mapped_status is None
    assert hits == []
    assert probe.capabilities is not None


def test_report_exports_serializer_surface() -> None:
    import everweb.report as report

    assert report.serialize is serialize
    assert report.SerializeRequest is SerializeRequest
