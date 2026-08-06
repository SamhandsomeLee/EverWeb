"""Unit tests for AX snapshot normalization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from everweb.perceive import MAX_INTERACTIVE_TARGETS, normalize_ax_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def test_normalize_collapses_wrappers_and_assigns_epoch_refs() -> None:
    result = normalize_ax_snapshot(
        _load("simple_form_ax.json"),
        snapshot_epoch=3,
        frame_id="frame-main",
    )

    assert [target.ref for target in result.targets] == ["3:1", "3:2", "3:3"]
    assert [target.role for target in result.targets] == ["textbox", "button", "link"]
    assert result.targets[0].name == "Email"
    assert result.targets[2].href == "https://example.com/docs"
    assert result.targets[2].source == "ax"
    assert result.headings == ("Contact",)
    assert result.truncated is False


def test_normalize_ignores_backend_dom_node_id_as_identity() -> None:
    result = normalize_ax_snapshot(
        _load("wrapped_controls_ax.json"),
        snapshot_epoch=1,
        frame_id="frame-main",
    )

    assert len(result.targets) == 1
    assert result.targets[0].ref == "1:1"
    assert result.targets[0].name == "Save"
    assert result.headings == ("Settings",)


def test_normalize_truncates_at_max_interactive_targets() -> None:
    children = [
        {"role": "button", "name": f"b{index}"} for index in range(MAX_INTERACTIVE_TARGETS + 5)
    ]
    result = normalize_ax_snapshot(
        {"role": "RootWebArea", "children": children},
        snapshot_epoch=0,
        frame_id="frame-main",
    )

    assert len(result.targets) == MAX_INTERACTIVE_TARGETS
    assert result.truncated is True


def test_normalize_empty_root() -> None:
    result = normalize_ax_snapshot(None, snapshot_epoch=0, frame_id="frame-main")
    assert result.targets == ()
    assert result.headings == ()
    assert result.truncated is False
