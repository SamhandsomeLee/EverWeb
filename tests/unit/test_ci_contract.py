"""Contract tests for the keyless continuous integration workflow."""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = ROOT / "pyproject.toml"


def test_ci_runs_required_quality_gates() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))
    quality = workflow["jobs"]["quality"]
    steps = {step["name"]: step for step in quality["steps"]}

    assert triggers == {"push": None, "pull_request": None}
    assert workflow["permissions"] == {"contents": "read"}
    assert quality["runs-on"] == "ubuntu-latest"
    assert quality["timeout-minutes"] == 10
    assert steps["Check out repository"] == {
        "name": "Check out repository",
        "uses": "actions/checkout@v7",
        "with": {"persist-credentials": False},
    }
    assert steps["Set up Python"] == {
        "name": "Set up Python",
        "uses": "actions/setup-python@v7",
        "with": {
            "python-version": "3.12",
            "cache": "pip",
            "cache-dependency-path": "pyproject.toml",
        },
    }
    assert (
        steps["Install development dependencies"]["run"]
        == 'python -m pip install -e ".[dev]"'
    )
    assert steps["Lint"]["run"] == "python -m ruff check ."
    assert steps["Type check"]["run"] == "python -m mypy src tests"
    assert steps["Architecture"]["run"] == "lint-imports --no-cache"
    assert steps["Test"]["run"] == "python -m pytest -q"


def test_ci_has_no_provider_browser_or_sealed_dependencies() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").casefold()
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    for forbidden in (
        "secrets.",
        "moonshot_api_key",
        "deepseek_api_key",
        "playwright",
        "cdp",
        "evalset/sealed",
    ):
        assert forbidden not in workflow

    assert project["project"]["dependencies"] == ["pydantic>=2,<3"]
    assert set(project["project"]["optional-dependencies"]["dev"]) == {
        "import-linter",
        "mypy",
        "pytest",
        "pyyaml",
        "ruff",
        "types-pyyaml",
    }
