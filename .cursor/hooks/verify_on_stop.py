#!/usr/bin/env python3
"""Run lightweight anti-drift checks when an Agent coding turn stops."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path.cwd()


def changed_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    paths: list[Path] = []
    for line in result.stdout.splitlines():
        raw_path = line[3:].strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        if raw_path:
            paths.append(Path(raw_path.strip('"')))
    return paths


def compile_changed_python(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for relative in paths:
        if relative.suffix != ".py":
            continue
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(relative), "exec")
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"{relative}: {exc}")
    return errors


def run_verifier() -> str | None:
    project_verifier = ROOT / "scripts" / "verify_agent_change.py"
    if project_verifier.is_file():
        command = [sys.executable, str(project_verifier), "--changed"]
    elif (ROOT / "pyproject.toml").is_file() and (ROOT / "tests").is_dir():
        if importlib.util.find_spec("pytest") is None:
            return "pytest is unavailable; install project development dependencies."
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--disable-warnings",
            "--maxfail=1",
        ]
    else:
        return None

    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=100,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "The changed-file verification timed out after 100 seconds."

    if result.returncode == 0:
        return None
    output = (result.stdout + "\n" + result.stderr).strip()
    return f"Changed-file verification failed:\n{output[-4000:]}"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        print("{}")
        return

    if payload.get("status") != "completed" or int(payload.get("loop_count", 0)) >= 2:
        print("{}")
        return

    changed = changed_paths()
    production = [
        path
        for path in changed
        if path.suffix == ".py" and path.as_posix().startswith("src/everweb/")
    ]
    tests = [
        path
        for path in changed
        if path.suffix == ".py" and path.as_posix().startswith("tests/")
    ]

    issues = compile_changed_python(changed)
    if production and not tests:
        issues.append(
            "Production Python changed without a corresponding test change. "
            "Add proportionate tests or explain why existing tests fully cover it."
        )

    verifier_failure = run_verifier() if production or tests else None
    if verifier_failure:
        issues.append(verifier_failure)

    if issues:
        message = (
            "EverWeb completion gate found unresolved issues:\n- "
            + "\n- ".join(issues)
            + "\nFix these issues, rerun the relevant checks, and report evidence."
        )
        print(json.dumps({"followup_message": message}))
        return

    print("{}")


if __name__ == "__main__":
    main()
