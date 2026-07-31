#!/usr/bin/env python3
"""Block Git commits that do not advance exactly one execution-plan step."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLAN = Path("docs/execution/EverWeb_Execution_Plan_v1.0.md")
STEP_RE = re.compile(r"^### ((?:DOC|BL|W[0-4])-\d{3}) — .+$", re.MULTILINE)
STATUS_RE = re.compile(r"^- 状态：(.+)$", re.MULTILINE)
COMMIT_RE = re.compile(r"^- Commit：`(.+)`$", re.MULTILINE)


@dataclass(frozen=True)
class Step:
    step_id: str
    status: str
    commit_subject: str


def read_payload() -> dict[str, Any] | None:
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


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def plan_at(revision: str) -> str | None:
    result = git("show", f"{revision}:{PLAN.as_posix()}")
    return result.stdout if result.returncode == 0 else None


def parse_steps(text: str) -> list[Step]:
    matches = list(STEP_RE.finditer(text))
    steps: list[Step] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : end]
        status = STATUS_RE.search(block)
        commit_subject = COMMIT_RE.search(block)
        if status and commit_subject:
            steps.append(
                Step(
                    step_id=match.group(1),
                    status=status.group(1).strip(),
                    commit_subject=commit_subject.group(1).strip(),
                )
            )
    return steps


def deny(message: str) -> None:
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": message,
                "agent_message": message,
            }
        )
    )


def is_pending(status: str) -> bool:
    return status == "未开始" or status.startswith("⏸ PendingTemplate")


def is_completed(status: str) -> bool:
    return status.startswith("完成")


def main() -> None:
    payload = read_payload()
    if payload is None:
        deny("无法解析提交命令的 Hook 输入；为保护执行账本，已阻止 commit。")
        return

    command = str(payload.get("command", ""))
    if not re.search(r"\bgit\s+commit\b", command, flags=re.IGNORECASE):
        print(json.dumps({"permission": "allow"}))
        return

    staged_names = git("diff", "--cached", "--name-only")
    if staged_names.returncode != 0:
        deny("无法读取 Git 暂存区；已阻止 commit。")
        return

    staged = {line.strip().replace("\\", "/") for line in staged_names.stdout.splitlines()}
    if PLAN.as_posix() not in staged:
        deny(
            "执行计划未暂存。每个 commit 必须同时更新 "
            f"{PLAN.as_posix()} 中恰好一个步骤的状态。"
        )
        return

    before = plan_at("HEAD")
    after = plan_at("")
    if before is None or after is None:
        deny("无法比较 HEAD 与暂存区中的执行计划；已阻止 commit。")
        return

    old_steps = {step.step_id: step for step in parse_steps(before)}
    new_steps = parse_steps(after)
    transitioned = [
        step
        for step in new_steps
        if step.step_id in old_steps
        and is_pending(old_steps[step.step_id].status)
        and is_completed(step.status)
    ]
    newly_completed = [
        step
        for step in new_steps
        if step.step_id not in old_steps and is_completed(step.status)
    ]
    candidates = transitioned + newly_completed

    # One-time bootstrap: DOC-002 installs this guard while repairing the
    # already-created DOC-001 ledger status.
    if (
        {step.step_id for step in transitioned} == {"DOC-001"}
        and {step.step_id for step in newly_completed} == {"DOC-002"}
    ):
        candidates = newly_completed

    if len(candidates) != 1:
        deny(
            "每个 commit 必须恰好完成一个执行步骤；"
            f"当前检测到 {len(candidates)} 个有效状态转换。"
        )
        return

    target = candidates[0]
    for step in new_steps:
        if step.step_id == target.step_id:
            break
        if not (is_completed(step.status) or step.status.startswith("⏸ PendingTemplate")):
            deny(
                f"步骤 {target.step_id} 之前仍有未完成步骤 {step.step_id}；"
                "禁止跳步提交。"
            )
            return

    print(
        json.dumps(
            {
                "permission": "allow",
                "agent_message": (
                    f"Execution ledger permits {target.step_id}. "
                    f"Required commit subject: {target.commit_subject}"
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
