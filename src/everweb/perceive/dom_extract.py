"""Minimal DOM supplement for controls missing from AX."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from everweb.domain import InteractiveTarget

_FILTERED_TAGS = frozenset({"script", "style", "noscript"})

_INTERACTIVE_TAGS = frozenset(
    {
        "a",
        "button",
        "input",
        "select",
        "textarea",
        "option",
    }
)


@dataclass(frozen=True, slots=True)
class DomExtractResult:
    """DOM-derived interactive targets used to fill AX gaps."""

    targets: tuple[InteractiveTarget, ...]


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _bool_from_attr(attrs: Mapping[str, Any], key: str) -> bool | None:
    if key not in attrs:
        return None
    value = attrs[key]
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"", "true", key}:
            return True
        if lowered in {"false", "0", "off"}:
            return False
    return bool(value)


def _parse_bbox(value: object) -> tuple[float, float, float, float] | None:
    if (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and len(value) == 4
    ):
        try:
            x0, y0, x1, y1 = (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
        except (TypeError, ValueError):
            return None
        return (x0, y0, x1, y1)
    return None


def _role_for_tag(tag: str, attrs: Mapping[str, Any]) -> str:
    if tag == "a":
        return "link"
    if tag == "button":
        return "button"
    if tag == "textarea":
        return "textbox"
    if tag == "select":
        return "combobox"
    if tag == "option":
        return "option"
    if tag == "input":
        input_type = (_str_or_none(attrs.get("type")) or "text").lower()
        if input_type in {"checkbox"}:
            return "checkbox"
        if input_type in {"radio"}:
            return "radio"
        if input_type in {"submit", "button", "reset"}:
            return "button"
        if input_type in {"search"}:
            return "searchbox"
        return "textbox"
    return tag


def extract_dom_targets(
    nodes: Sequence[Mapping[str, Any]] | None,
    *,
    snapshot_epoch: int,
    frame_id: str,
    start_local_id: int = 1,
) -> DomExtractResult:
    """Filter noise tags and emit interactive DOM targets with bbox/state."""

    if snapshot_epoch < 0:
        raise ValueError("snapshot_epoch must be >= 0")
    if not isinstance(frame_id, str) or not frame_id:
        raise ValueError("frame_id must be a non-empty str")
    if start_local_id < 1:
        raise ValueError("start_local_id must be >= 1")

    if nodes is None:
        return DomExtractResult(targets=())

    targets: list[InteractiveTarget] = []
    local_id = start_local_id
    for node_obj in nodes:
        node = _as_mapping(node_obj)
        if node is None:
            continue
        tag = (_str_or_none(node.get("tag")) or "").lower()
        if not tag or tag in _FILTERED_TAGS:
            continue
        if tag not in _INTERACTIVE_TAGS:
            continue
        attrs_obj = node.get("attrs")
        attrs = _as_mapping(attrs_obj) or {}
        role = _role_for_tag(tag, attrs)
        name = _str_or_none(node.get("text")) or _str_or_none(attrs.get("aria-label"))
        href = _str_or_none(attrs.get("href")) if role == "link" else None
        ref = f"{snapshot_epoch}:{local_id}"
        local_id += 1
        targets.append(
            InteractiveTarget(
                ref=ref,
                role=role,
                name=name,
                href=href,
                selected=_bool_from_attr(attrs, "selected"),
                checked=_bool_from_attr(attrs, "checked"),
                expanded=None,
                disabled=_bool_from_attr(attrs, "disabled"),
                frame_id=_str_or_none(node.get("frame_id")) or frame_id,
                source="dom",
                bbox=_parse_bbox(node.get("bbox")),
            )
        )
    return DomExtractResult(targets=tuple(targets))
