"""Architecture tests: StepMeter is the sole step-accounting boundary (INV-8)."""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "everweb"
STEP_METER = SRC_ROOT / "core" / "step_meter.py"
METERED_BROWSER = SRC_ROOT / "core" / "metered_browser.py"
ALLOWED_RECORD_CALL_FILES = frozenset({STEP_METER.resolve(), METERED_BROWSER.resolve()})
FORBIDDEN_COUNTER_NAMES = frozenset(
    {
        "_recorded_total",
        "recorded_total",
        "step_count",
        "official_step_count",
        "official_steps",
        "steps_used",
    }
)


def _iter_production_modules() -> list[Path]:
    return sorted(path for path in SRC_ROOT.rglob("*.py") if path.name != "__pycache__")


def _assignment_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Attribute):
        return {target.attr}
    if isinstance(target, ast.Tuple | ast.List):
        names: set[str] = set()
        for element in target.elts:
            names |= _assignment_names(element)
        return names
    return set()


def _rel(path: Path) -> str:
    return path.relative_to(SRC_ROOT.parent).as_posix()


def test_only_step_meter_mutates_recorded_total() -> None:
    offenders: list[str] = []
    for path in _iter_production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, ast.AnnAssign) and node.target is not None:
                targets.append(node.target)
            elif isinstance(node, ast.AugAssign):
                targets.append(node.target)
            for target in targets:
                names = _assignment_names(target)
                if "_recorded_total" in names and path.resolve() != STEP_METER.resolve():
                    offenders.append(f"{_rel(path)}:{getattr(node, 'lineno', '?')}")
    assert offenders == []


def test_production_step_meter_record_calls_only_from_metered_browser() -> None:
    """Sole execute→record coupling lives in MeteredBrowser (plus StepMeter def)."""

    offenders: list[str] = []
    for path in _iter_production_modules():
        if path.resolve() in ALLOWED_RECORD_CALL_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "record":
                offenders.append(f"{_rel(path)}:{node.lineno}")
    assert offenders == []


def test_single_step_meter_class_in_production() -> None:
    classes: list[str] = []
    for path in _iter_production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "StepMeter":
                classes.append(_rel(path))
    assert classes == ["everweb/core/step_meter.py"]


def test_no_parallel_step_counter_accumulators_outside_step_meter() -> None:
    offenders: list[str] = []
    for path in _iter_production_modules():
        if path.resolve() == STEP_METER.resolve():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AugAssign):
                names = _assignment_names(node.target)
                hit = names & FORBIDDEN_COUNTER_NAMES
                if hit:
                    offenders.append(
                        f"{_rel(path)}:{getattr(node, 'lineno', '?')}:{sorted(hit)}"
                    )
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    names = _assignment_names(target)
                    # Ban private parallel totals outside StepMeter.
                    if "_recorded_total" in names or "official_step_count" in names:
                        offenders.append(f"{_rel(path)}:{getattr(node, 'lineno', '?')}")
    assert offenders == []


def test_metered_browser_is_sole_browser_port_step_coupling_module() -> None:
    source = METERED_BROWSER.read_text(encoding="utf-8")
    assert "step_meter.record" in source or "_step_meter.record" in source
    assert "class MeteredBrowser" in source
