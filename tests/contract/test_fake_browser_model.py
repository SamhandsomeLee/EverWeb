"""Contract tests for harness FakeBrowser and FakeModel."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from everweb.domain import (
    ActionKind,
    ActionReceipt,
    BrowserSession,
    CaptureReceipt,
    CaptureRequest,
    CloseReceipt,
    Deadline,
    ModelCapabilities,
    ModelReceipt,
    ModelRequest,
    ObservationReceipt,
    ObservationRequest,
    Task,
    TypedAction,
)
from everweb.harness import (
    FAKE_BROWSER_CAPABILITIES,
    FakeBrowser,
    FakeModel,
    FakeScriptExhaustedError,
    load_cassette,
)
from everweb.harness import fake_browser as fake_browser_module
from everweb.harness import fake_model as fake_model_module
from everweb.ports import BrowserPort, ModelPort

PLACEHOLDER_TYPES = (
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
)

FORBIDDEN_IMPORT_ROOTS = (
    "everweb.adapters",
    "httpx",
    "playwright",
    "everweb.adapters.moonshot",
    "everweb.adapters.deepseek",
    "everweb.adapters.playwright_browser",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_fakes_implement_public_ports() -> None:
    assert isinstance(FakeBrowser(), BrowserPort)
    assert isinstance(FakeModel(), ModelPort)


def test_default_fake_responses_are_deterministic() -> None:
    browser_a = FakeBrowser()
    browser_b = FakeBrowser()
    action = TypedAction(action_id="a1", kind=ActionKind.CLICK)

    first = [
        browser_a.capabilities().model_dump(mode="json"),
        browser_a.create_task_session(Task()).model_dump(mode="json"),
        browser_a.observe(ObservationRequest()).model_dump(mode="json"),
        browser_a.execute(action).model_dump(mode="json"),
        browser_a.capture(CaptureRequest()).model_dump(mode="json"),
        browser_a.close_task_session().model_dump(mode="json"),
    ]
    second = [
        browser_b.capabilities().model_dump(mode="json"),
        browser_b.create_task_session(Task()).model_dump(mode="json"),
        browser_b.observe(ObservationRequest()).model_dump(mode="json"),
        browser_b.execute(action).model_dump(mode="json"),
        browser_b.capture(CaptureRequest()).model_dump(mode="json"),
        browser_b.close_task_session().model_dump(mode="json"),
    ]
    assert first == second
    assert browser_a.capabilities() == FAKE_BROWSER_CAPABILITIES

    model_a = FakeModel()
    model_b = FakeModel()
    assert model_a.capabilities().model_dump(mode="json") == (
        model_b.capabilities().model_dump(mode="json")
    )
    assert model_a.complete(ModelRequest(), Deadline()).model_dump(mode="json") == (
        model_b.complete(ModelRequest(), Deadline()).model_dump(mode="json")
    )


def test_cassette_round_trip_replays_identical_responses(tmp_path: Path) -> None:
    browser = FakeBrowser()
    browser.capabilities()
    browser.create_task_session(Task())
    browser.observe(ObservationRequest())
    browser.execute(TypedAction(action_id="nav-1", kind=ActionKind.NAVIGATE))
    browser.capture(CaptureRequest())
    browser.close_task_session()
    cassette_path = tmp_path / "browser.json"
    browser.dump_cassette(cassette_path)

    replay = FakeBrowser.from_cassette(cassette_path)
    replay.capabilities()
    replay.create_task_session(Task())
    replay.observe(ObservationRequest())
    replay.execute(TypedAction(action_id="nav-1", kind=ActionKind.NAVIGATE))
    replay.capture(CaptureRequest())
    replay.close_task_session()

    assert [entry.response for entry in replay.calls] == [
        entry.response for entry in browser.calls
    ]
    assert [entry.op for entry in load_cassette(cassette_path)] == [
        "capabilities",
        "create_task_session",
        "observe",
        "execute",
        "capture",
        "close_task_session",
    ]

    model = FakeModel()
    model.capabilities()
    model.complete(ModelRequest(), Deadline())
    model_path = tmp_path / "model.json"
    model.dump_cassette(model_path)
    model_replay = FakeModel.from_cassette(model_path)
    model_replay.capabilities()
    model_replay.complete(ModelRequest(), Deadline())
    assert [entry.response for entry in model_replay.calls] == [
        entry.response for entry in model.calls
    ]


def test_script_exhaustion_is_fail_closed() -> None:
    browser = FakeBrowser(
        script={
            "observe": (ObservationReceipt(),),
            "execute": (ActionReceipt(),),
        }
    )
    browser.observe(ObservationRequest())
    with pytest.raises(FakeScriptExhaustedError, match="observe"):
        browser.observe(ObservationRequest())

    model = FakeModel(script={"complete": (ModelReceipt(),)})
    model.complete(ModelRequest(), Deadline())
    with pytest.raises(FakeScriptExhaustedError, match="complete"):
        model.complete(ModelRequest(), Deadline())


def test_fake_modules_forbid_provider_and_browser_imports() -> None:
    for module in (fake_browser_module, fake_model_module):
        module_file = module.__file__
        assert module_file is not None
        path = Path(module_file).resolve()
        imported = _imported_modules(path)
        for module_name in imported:
            assert not any(
                module_name == root or module_name.startswith(f"{root}.")
                for root in FORBIDDEN_IMPORT_ROOTS
            ), module_name


def test_placeholder_port_dtos_remain_fieldless() -> None:
    for placeholder_type in PLACEHOLDER_TYPES:
        assert placeholder_type.model_fields == {}


def test_scripted_browser_uses_injected_receipts() -> None:
    browser = FakeBrowser(
        script={
            "create_task_session": (BrowserSession(),),
            "close_task_session": (CloseReceipt(),),
            "capture": (CaptureReceipt(),),
        }
    )
    assert browser.create_task_session(Task()) == BrowserSession()
    assert browser.close_task_session() == CloseReceipt()
    assert browser.capture(CaptureRequest()) == CaptureReceipt()
    assert browser.capabilities() == FAKE_BROWSER_CAPABILITIES


def test_model_capabilities_remain_empty_placeholder() -> None:
    assert FakeModel().capabilities() == ModelCapabilities()
    assert set(ModelCapabilities.model_fields) == set()
