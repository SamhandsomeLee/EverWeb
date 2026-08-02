"""Contract tests for EverWeb's import-linter architecture gates."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from shutil import copytree
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
CONTRACT_TYPES = {
    "adapter-independence": "independence",
    "adapter-runtime-boundaries": "forbidden",
    "application-boundaries": "forbidden",
    "competition-public-entry": "forbidden",
    "domain-isolation": "forbidden",
    "layered-architecture": "layers",
    "production-harness-isolation": "forbidden",
    "provider-browser-isolation": "forbidden",
    "root-harness-isolation": "forbidden",
    "runtime-side-boundaries": "forbidden",
}
VIOLATION_CANARIES = (
    ("layered-architecture", "domain/violation.py", "import everweb.ports\n"),
    ("domain-isolation", "domain/violation.py", "import everweb.adapters\n"),
    (
        "adapter-independence",
        "adapters/moonshot/violation.py",
        "import everweb.adapters.deepseek\n",
    ),
    (
        "provider-browser-isolation",
        "adapters/moonshot/violation.py",
        "import everweb.adapters.playwright_browser\n",
    ),
    (
        "competition-public-entry",
        "competition/violation.py",
        "import everweb.supervisor.private\n",
    ),
    (
        "production-harness-isolation",
        "core/violation.py",
        "import everweb.harness\n",
    ),
    (
        "application-boundaries",
        "answer/violation.py",
        "import everweb.adapters\n",
    ),
    (
        "adapter-runtime-boundaries",
        "adapters/filesystem/violation.py",
        "import everweb.core\n",
    ),
    ("root-harness-isolation", "__init__.py", "import everweb.harness\n"),
    (
        "runtime-side-boundaries",
        "core/violation.py",
        "import everweb.adapters\n",
    ),
)


def load_import_contracts() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    configuration = project["tool"]["importlinter"]
    contracts = {contract["id"]: contract for contract in configuration["contracts"]}
    return configuration, contracts


def import_linter_command(*arguments: str) -> Sequence[str | Path]:
    executable = Path(sys.executable).with_name(
        "lint-imports.exe" if sys.platform == "win32" else "lint-imports"
    )
    return [executable, "--no-cache", *arguments]


def test_architecture_contracts_are_configured() -> None:
    configuration, contracts = load_import_contracts()

    assert configuration["root_package"] == "everweb"
    assert configuration["include_external_packages"] is True
    assert {contract_id: contract["type"] for contract_id, contract in contracts.items()} == (
        CONTRACT_TYPES
    )
    assert contracts["layered-architecture"]["layers"] == [
        "everweb.competition",
        "everweb.supervisor",
        "everweb.core",
        "everweb.ports",
        "everweb.domain",
    ]
    assert set(contracts["domain-isolation"]["source_modules"]) == {"everweb.domain"}
    assert {"everweb.adapters", "httpx", "playwright"} <= set(
        contracts["domain-isolation"]["forbidden_modules"]
    )
    assert set(contracts["adapter-independence"]["modules"]) == {
        "everweb.adapters.deepseek",
        "everweb.adapters.everos",
        "everweb.adapters.filesystem",
        "everweb.adapters.moonshot",
        "everweb.adapters.null_vision",
        "everweb.adapters.playwright_browser",
    }
    assert set(contracts["provider-browser-isolation"]["source_modules"]) == {
        "everweb.adapters.deepseek",
        "everweb.adapters.moonshot",
    }
    assert contracts["provider-browser-isolation"]["forbidden_modules"] == [
        "everweb.adapters.playwright_browser"
    ]
    assert contracts["competition-public-entry"]["allow_indirect_imports"] is True
    assert "everweb.supervisor.*" in contracts["competition-public-entry"][
        "forbidden_modules"
    ]
    assert contracts["production-harness-isolation"]["forbidden_modules"] == [
        "everweb.harness"
    ]
    assert set(contracts["application-boundaries"]["source_modules"]) == {
        "everweb.act",
        "everweb.answer",
        "everweb.perceive",
        "everweb.report",
    }
    assert {"httpx", "playwright"} <= set(
        contracts["application-boundaries"]["forbidden_modules"]
    )
    assert set(contracts["adapter-runtime-boundaries"]["source_modules"]) == {
        "everweb.adapters"
    }
    assert contracts["root-harness-isolation"]["as_packages"] is False
    assert {"everweb.adapters", "httpx", "playwright"} <= set(
        contracts["runtime-side-boundaries"]["forbidden_modules"]
    )


def test_current_package_satisfies_import_contracts() -> None:
    result = subprocess.run(
        import_linter_command(),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(("contract_id", "module_path", "source"), VIOLATION_CANARIES)
def test_contract_rejects_violation_canary(
    tmp_path: Path,
    contract_id: str,
    module_path: str,
    source: str,
) -> None:
    package = tmp_path / "everweb"
    copytree(ROOT / "src" / "everweb", package)
    (tmp_path / "pyproject.toml").write_bytes(PYPROJECT.read_bytes())
    (package / "supervisor" / "private.py").write_text(
        '"""Private supervisor implementation detail."""\n',
        encoding="utf-8",
    )
    violation = package / module_path
    violation.write_text(source, encoding="utf-8")

    result = subprocess.run(
        import_linter_command("--contract", contract_id),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1 broken" in result.stdout
