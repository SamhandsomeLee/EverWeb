#!/usr/bin/env python3
"""Deny Agent writes to sealed evaluation data and likely secret files."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def candidate_paths(value: Any, key: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            paths.extend(candidate_paths(child_value, child_key.lower()))
    elif isinstance(value, list):
        for item in value:
            paths.extend(candidate_paths(item, key))
    elif isinstance(value, str):
        if "path" in key or key in {"file", "target", "filename"}:
            paths.append(value)
        elif "patch" in key or "*** Begin Patch" in value:
            paths.extend(
                match.group(1).strip()
                for match in re.finditer(
                    r"^\*\*\* (?:Add|Update) File: (.+)$",
                    value,
                    flags=re.MULTILINE,
                )
            )
    return paths


def read_payload() -> dict[str, Any] | None:
    """Parse hook input without turning transport variance into a write lock."""
    raw = sys.stdin.buffer.read()
    if not raw.strip():
        return None

    for encoding in ("utf-8-sig", "utf-16"):
        try:
            value = json.loads(raw.decode(encoding))
        except (UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            return value
    return None


def relative_path(raw_path: str) -> str:
    project = Path(os.environ.get("CURSOR_PROJECT_DIR", os.getcwd())).resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = project / candidate
    try:
        relative = candidate.resolve().relative_to(project)
    except (OSError, ValueError):
        return candidate.as_posix().lower()
    return relative.as_posix().lower()


def blocked_reason(path: str) -> str | None:
    name = Path(path).name.lower()
    if path == "evalset/sealed" or path.startswith("evalset/sealed/"):
        return "sealed evaluation data is read-only"
    if name == ".env.example":
        return None
    if name == ".env" or name.startswith(".env."):
        return "environment secret files require manual editing"
    if name in {"credentials.json", "secrets.json"}:
        return "credential files require manual editing"
    if Path(name).suffix in {".key", ".pem", ".p12", ".pfx"}:
        return "private key material requires manual editing"
    return None


def main() -> None:
    payload = read_payload()
    if payload is None:
        print(json.dumps({"permission": "allow"}))
        return

    tool_input = payload.get("tool_input", payload)
    for raw_path in candidate_paths(tool_input):
        path = relative_path(raw_path)
        reason = blocked_reason(path)
        if reason:
            print(
                json.dumps(
                    {
                        "permission": "deny",
                        "user_message": f"Blocked write to {path}: {reason}.",
                        "agent_message": (
                            f"The project hook blocked {path}. Ask the user to make "
                            "this protected change manually or revise the approach."
                        ),
                    }
                )
            )
            return

    print(json.dumps({"permission": "allow"}))


if __name__ == "__main__":
    main()
