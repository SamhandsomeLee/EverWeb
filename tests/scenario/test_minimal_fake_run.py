"""Scenario: FakeBrowser/FakeModel complete one no-key minimal run."""

from __future__ import annotations

import ast
import os
from datetime import UTC, datetime
from pathlib import Path

from everweb.core import MINIMAL_PHASES, Budget, MinimalRuntime
from everweb.domain import (
    InternalRunManifest,
    InternalTerminalState,
    OfficialOutputDraft,
    RuntimePhase,
    TaskIdentity,
)
from everweb.harness import FakeBrowser, FakeModel
from everweb.report import read_trace


class FixedClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
        self._monotonic = 100.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic


def test_minimal_fake_run_writes_internal_run_directory(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    runtime = MinimalRuntime(
        browser=FakeBrowser(),
        model=FakeModel(),
        clock=FixedClock(),
        run_root=run_root,
        budget=Budget(
            max_official_steps=100,
            max_model_calls=50,
            task_wall_clock_s=600,
        ),
    )

    # Prove the scenario does not depend on provider credentials.
    assert os.environ.get("OPENAI_API_KEY") in {None, ""}
    assert os.environ.get("MOONSHOT_API_KEY") in {None, ""}

    result = runtime.run(
        execution_id="execution-minimal-001",
        task_identity=TaskIdentity(task_id="task-minimal-001"),
    )

    run_directory = run_root / "execution-minimal-001"
    assert result.run_directory == run_directory
    assert result.manifest.phases == MINIMAL_PHASES
    assert (
        result.manifest.internal_terminal_state
        is InternalTerminalState.BEST_EFFORT
    )
    assert result.draft.mapped_status is None
    assert result.draft.urls == ()
    assert result.draft.actions == ()
    assert result.summary.browser_capabilities_called is True
    assert result.summary.model_capabilities_called is True
    assert result.summary.model_complete_called is True
    assert result.summary.mapped_status is None

    manifest_path = run_directory / "run_manifest.json"
    run_summary_path = run_directory / "run.json"
    draft_path = run_directory / "emit" / "official_output_draft.json"
    receipt_path = run_directory / "emit" / "output_receipt.json"
    trace_path = run_directory / "trace.jsonl"

    assert manifest_path.is_file()
    assert run_summary_path.is_file()
    assert draft_path.is_file()
    assert receipt_path.is_file()
    assert trace_path.is_file()

    manifest = InternalRunManifest.model_validate_json(manifest_path.read_bytes())
    draft = OfficialOutputDraft.model_validate_json(draft_path.read_bytes())
    assert manifest == result.manifest
    assert draft == result.draft
    assert draft.mapped_status is None
    assert draft.urls == ()
    assert draft.actions == ()

    trace = read_trace(trace_path, max_event_bytes=65_536)
    phase_events = [
        event
        for event in trace.events
        if event.event_type == "runtime.phase"
    ]
    assert [event.payload["phase"] for event in phase_events] == [
        phase.value for phase in MINIMAL_PHASES
    ]
    assert any(event.event_type == "runtime.budget" for event in trace.events)
    assert RuntimePhase.SERIALIZE in result.manifest.phases
    assert RuntimePhase.EMIT in result.manifest.phases


def test_core_runtime_module_does_not_import_harness_or_providers() -> None:
    runtime_path = Path(__file__).resolve().parents[2] / "src" / "everweb" / "core" / (
        "runtime.py"
    )
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)

    forbidden = (
        "everweb.harness",
        "everweb.adapters",
        "playwright",
        "httpx",
    )
    for module_name in imported:
        assert not any(
            module_name == root or module_name.startswith(f"{root}.")
            for root in forbidden
        ), module_name
