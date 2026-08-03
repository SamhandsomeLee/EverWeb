"""Unit and architecture tests for internal terminal states."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from everweb.domain import InternalTerminalState

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_MEMBERS = {
    "VERIFIED_SUCCESS": "verified_success",
    "BEST_EFFORT": "best_effort",
    "BUDGET_EXHAUSTED": "budget_exhausted",
    "WALL_CLOCK_EXHAUSTED": "wall_clock_exhausted",
    "POLICY_BLOCKED": "policy_blocked",
    "BROWSER_FAILURE": "browser_failure",
    "MODEL_FAILURE": "model_failure",
    "WORKER_CRASHED": "worker_crashed",
    "OUTPUT_FAILURE": "output_failure",
}
FORBIDDEN_OFFICIAL_STATUS_VALUES = {"", "FAIL", "SUCCESS"}
FORBIDDEN_OFFICIAL_STATUS_LITERALS = {"FAIL", "SUCCESS"}


def test_internal_terminal_state_matches_canonical_contract() -> None:
    assert {member.name: member.value for member in InternalTerminalState} == (
        EXPECTED_MEMBERS
    )
    assert FORBIDDEN_OFFICIAL_STATUS_VALUES.isdisjoint(
        member.value for member in InternalTerminalState
    )


def test_internal_terminal_state_is_string_serializable() -> None:
    state = InternalTerminalState("browser_failure")

    assert state is InternalTerminalState.BROWSER_FAILURE
    assert str(state) == "browser_failure"
    assert json.loads(json.dumps(state)) == "browser_failure"


def assignment_target_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Attribute):
        return {target.attr}
    if (
        isinstance(target, ast.Subscript)
        and isinstance(target.slice, ast.Constant)
        and target.slice.value == "status"
    ):
        return {"status"}
    if isinstance(target, ast.List | ast.Tuple):
        return {
            name
            for element in target.elts
            for name in assignment_target_names(element)
        }
    return set()


def assigned_status_value(node: ast.AST) -> tuple[set[str], ast.expr | None]:
    if isinstance(node, ast.Assign):
        return (
            {
                name
                for target in node.targets
                for name in assignment_target_names(target)
            },
            node.value,
        )
    if isinstance(node, ast.AnnAssign):
        return assignment_target_names(node.target), node.value
    if isinstance(node, ast.NamedExpr):
        return assignment_target_names(node.target), node.value
    if isinstance(node, ast.keyword):
        return {node.arg} if node.arg is not None else set(), node.value
    return set(), None


def official_status_violations(source_root: Path) -> list[str]:
    violations: list[str] = []

    for package_name in ("core", "domain"):
        for path in sorted((source_root / "everweb" / package_name).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value in FORBIDDEN_OFFICIAL_STATUS_LITERALS
                ):
                    violations.append(
                        f"{path.relative_to(source_root).as_posix()}:"
                        f"{getattr(node, 'lineno', 0)}"
                    )

                target_names, value = assigned_status_value(node)
                if (
                    "status" in target_names
                    and isinstance(value, ast.Constant)
                    and value.value == ""
                ):
                    violations.append(
                        f"{path.relative_to(source_root).as_posix()}:"
                        f"{getattr(node, 'lineno', 0)}"
                    )

                if isinstance(node, ast.Dict):
                    for key, item in zip(node.keys, node.values, strict=True):
                        if (
                            isinstance(key, ast.Constant)
                            and key.value == "status"
                            and isinstance(item, ast.Constant)
                            and item.value == ""
                        ):
                            violations.append(
                                f"{path.relative_to(source_root).as_posix()}:"
                                f"{node.lineno}"
                            )

    return violations


def test_core_and_domain_do_not_map_official_status_literals() -> None:
    assert official_status_violations(ROOT / "src") == []


def test_official_status_scanner_rejects_mapping_canaries(tmp_path: Path) -> None:
    core = tmp_path / "everweb" / "core"
    domain = tmp_path / "everweb" / "domain"
    core.mkdir(parents=True)
    domain.mkdir(parents=True)
    (domain / "__init__.py").write_text("", encoding="utf-8")
    (core / "status_canary.py").write_text(
        "\n".join(
            (
                'OFFICIAL_BY_STATE = {"verified_success": "SUCCESS"}',
                "",
                "def mapped_status() -> str:",
                '    return "FAIL"',
                "",
                'status = alias = ""',
                'result["status"] = ""',
                "",
            )
        ),
        encoding="utf-8",
    )

    assert set(official_status_violations(tmp_path)) == {
        "everweb/core/status_canary.py:1",
        "everweb/core/status_canary.py:4",
        "everweb/core/status_canary.py:6",
        "everweb/core/status_canary.py:7",
    }
