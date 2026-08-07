"""EverWeb act package boundary."""

from everweb.act.errors import (
    ActError,
    InvalidActionError,
    StaleRefError,
    TargetNotFoundError,
    UnsupportedActionKindError,
)
from everweb.act.executor import TypedActionExecutor
from everweb.act.locator import resolve_role_name_locator

__all__ = [
    "ActError",
    "InvalidActionError",
    "StaleRefError",
    "TargetNotFoundError",
    "TypedActionExecutor",
    "UnsupportedActionKindError",
    "resolve_role_name_locator",
]
