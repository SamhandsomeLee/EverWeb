"""Contract suite: NullVision/NullMemory off + OutputContract internal emit."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from everweb.adapters.null_memory import NullMemory
from everweb.adapters.null_vision import NullVision, VisionUnavailableError
from everweb.competition import OutputContractDraftMapper
from everweb.core import MinimalRuntime
from everweb.domain import (
    MemoryHealth,
    OfficialOutputDraft,
    RecallReceipt,
    RecallRequest,
    RunTrace,
    StoreReceipt,
    TaskIdentity,
    TraceProjection,
    VisionRequest,
)
from everweb.harness import FakeBrowser, FakeModel
from everweb.ports import MemoryPort, VisionPort

NULL_VISION_PATH = Path(__file__).resolve().parents[2] / (
    "src/everweb/adapters/null_vision/null_vision.py"
)
NULL_MEMORY_PATH = Path(__file__).resolve().parents[2] / (
    "src/everweb/adapters/null_memory/null_memory.py"
)
FORBIDDEN_IMPORT_ROOTS = (
    "everweb.core",
    "everweb.harness",
    "everweb.report",
    "everweb.competition",
    "playwright",
    "httpx",
)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 5, 10, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1.0


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_null_adapters_implement_optional_ports() -> None:
    assert isinstance(NullVision(), VisionPort)
    assert isinstance(NullMemory(), MemoryPort)


def test_null_vision_is_unavailable() -> None:
    vision = NullVision()
    assert vision.available() is False
    with pytest.raises(VisionUnavailableError, match="unavailable"):
        vision.analyze(VisionRequest())


def test_null_memory_off_returns_empty_placeholders() -> None:
    memory = NullMemory()
    assert memory.health() == MemoryHealth()
    assert memory.recall(RecallRequest()) == RecallReceipt()
    assert memory.submit_run(RunTrace()) == StoreReceipt()


def test_output_contract_draft_mapper_works_with_optional_capabilities_off() -> None:
    # Null adapters are constructed to represent closed Vision/Memory.
    vision = NullVision()
    memory = NullMemory()
    assert vision.available() is False
    assert memory.health() == MemoryHealth()

    draft = OutputContractDraftMapper().map_draft(
        task_identity=TaskIdentity(task_id="task-null-001"),
        trace_projection=TraceProjection(),
        agent_answer="",
        decision_summaries=("optional_off",),
    )
    assert isinstance(draft, OfficialOutputDraft)
    assert draft.mapped_status is None
    assert draft.urls == ()
    assert draft.actions == ()


def test_internal_output_still_emitted_when_vision_and_memory_closed(
    tmp_path: Path,
) -> None:
    vision = NullVision()
    memory = NullMemory()
    assert vision.available() is False
    assert memory.health() == MemoryHealth()

    run_root = tmp_path / "run"
    run_root.mkdir()
    runtime = MinimalRuntime(
        browser=FakeBrowser(),
        model=FakeModel(),
        clock=FixedClock(),
        run_root=run_root,
    )
    result = runtime.run(
        execution_id="execution-null-off-001",
        task_identity=TaskIdentity(task_id="task-null-off-001"),
    )

    assert result.draft.mapped_status is None
    assert (result.run_directory / "emit" / "official_output_draft.json").is_file()
    assert (result.run_directory / "run_manifest.json").is_file()
    # Closed optional adapters must not be required by the main emit path.
    with pytest.raises(VisionUnavailableError):
        vision.analyze(VisionRequest())


def test_null_adapter_modules_forbid_runtime_and_provider_imports() -> None:
    for path in (NULL_VISION_PATH, NULL_MEMORY_PATH):
        imported = _imported_modules(path)
        for module_name in imported:
            assert not any(
                module_name == root or module_name.startswith(f"{root}.")
                for root in FORBIDDEN_IMPORT_ROOTS
            ), f"{path.name}: {module_name}"
