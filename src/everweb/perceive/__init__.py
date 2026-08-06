"""EverWeb perceive package boundary."""

from everweb.perceive.ax_snapshot import (
    MAX_INTERACTIVE_TARGETS,
    AxNormalizeResult,
    normalize_ax_snapshot,
)
from everweb.perceive.browser_capability_probe import BrowserCapabilityProbe
from everweb.perceive.dom_extract import DomExtractResult, extract_dom_targets
from everweb.perceive.page_view import (
    build_page_view,
    compute_page_signature,
    merge_targets,
)

__all__ = [
    "MAX_INTERACTIVE_TARGETS",
    "AxNormalizeResult",
    "BrowserCapabilityProbe",
    "DomExtractResult",
    "build_page_view",
    "compute_page_signature",
    "extract_dom_targets",
    "merge_targets",
    "normalize_ax_snapshot",
]
