"""Normalize Playwright-like accessibility snapshots into interactive targets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from everweb.domain import InteractiveTarget

MAX_INTERACTIVE_TARGETS = 60

_INTERACTIVE_ROLES = frozenset(
    {
        "button",
        "link",
        "textbox",
        "checkbox",
        "radio",
        "combobox",
        "listbox",
        "option",
        "menuitem",
        "menuitemcheckbox",
        "menuitemradio",
        "switch",
        "slider",
        "spinbutton",
        "tab",
        "searchbox",
        "treeitem",
    }
)

@dataclass(frozen=True, slots=True)
class AxNormalizeResult:
    """Intermediate AX facts for PageView assembly."""

    targets: tuple[InteractiveTarget, ...]
    headings: tuple[str, ...]
    truncated: bool


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _is_interactive(node: Mapping[str, Any]) -> bool:
    role = _str_or_none(node.get("role"))
    if role is None:
        return False
    return role.lower() in {item.lower() for item in _INTERACTIVE_ROLES}


def _is_heading(node: Mapping[str, Any]) -> bool:
    role = _str_or_none(node.get("role"))
    if role is None:
        return False
    return role.lower() == "heading"


def _children(node: Mapping[str, Any]) -> Sequence[Any]:
    children = node.get("children")
    if isinstance(children, Sequence) and not isinstance(children, (str, bytes)):
        return children
    return ()


def normalize_ax_snapshot(
    root: Mapping[str, Any] | None,
    *,
    snapshot_epoch: int,
    frame_id: str,
) -> AxNormalizeResult:
    """Collapse wrappers, assign epoch refs, keep semantic interactive nodes."""

    if snapshot_epoch < 0:
        raise ValueError("snapshot_epoch must be >= 0")
    if not isinstance(frame_id, str) or not frame_id:
        raise ValueError("frame_id must be a non-empty str")

    if root is None:
        return AxNormalizeResult(targets=(), headings=(), truncated=False)

    targets: list[InteractiveTarget] = []
    headings: list[str] = []
    next_local_id = 1
    truncated = False

    def visit(node_obj: object) -> None:
        nonlocal next_local_id, truncated
        node = _as_mapping(node_obj)
        if node is None:
            return

        # backendDOMNodeId is intentionally ignored as a stable identity.
        _ = node.get("backendDOMNodeId")

        if _is_heading(node):
            name = _str_or_none(node.get("name"))
            if name:
                headings.append(name)

        if _is_interactive(node) and not truncated:
            if len(targets) >= MAX_INTERACTIVE_TARGETS:
                truncated = True
            else:
                role = _str_or_none(node.get("role")) or "unknown"
                ref = f"{snapshot_epoch}:{next_local_id}"
                next_local_id += 1
                targets.append(
                    InteractiveTarget(
                        ref=ref,
                        role=role.lower(),
                        name=_str_or_none(node.get("name")),
                        href=(
                            (
                                _str_or_none(node.get("url"))
                                or _str_or_none(node.get("value"))
                            )
                            if role.lower() == "link"
                            else None
                        ),
                        selected=_bool_or_none(node.get("selected")),
                        checked=_bool_or_none(node.get("checked")),
                        expanded=_bool_or_none(node.get("expanded")),
                        disabled=_bool_or_none(node.get("disabled")),
                        frame_id=frame_id,
                        source="ax",
                        bbox=None,
                    )
                )

        # Wrappers are collapsed by not emitting targets; always walk children.
        for child in _children(node):
            visit(child)

    visit(root)
    return AxNormalizeResult(
        targets=tuple(targets),
        headings=tuple(headings),
        truncated=truncated,
    )
