"""Unit tests for minimal DOM extract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from everweb.perceive import extract_dom_targets

FIXTURES = Path(__file__).parent / "fixtures"


def _load_list(name: str) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        json.loads((FIXTURES / name).read_text(encoding="utf-8")),
    )


def test_extract_filters_script_style_and_keeps_controls() -> None:
    result = extract_dom_targets(
        _load_list("simple_form_dom.json"),
        snapshot_epoch=3,
        frame_id="frame-main",
        start_local_id=10,
    )

    assert len(result.targets) == 1
    target = result.targets[0]
    assert target.ref == "3:10"
    assert target.role == "checkbox"
    assert target.name == "Subscribe"
    assert target.checked is True
    assert target.source == "dom"
    assert target.bbox == (10.0, 20.0, 30.0, 40.0)


def test_extract_reads_disabled_textbox() -> None:
    result = extract_dom_targets(
        _load_list("wrapped_controls_dom.json"),
        snapshot_epoch=1,
        frame_id="frame-main",
    )

    roles = [target.role for target in result.targets]
    assert roles == ["button", "textbox"]
    assert result.targets[1].name == "Token"
    assert result.targets[1].disabled is True
