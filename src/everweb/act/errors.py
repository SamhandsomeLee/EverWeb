"""Typed failures for the act layer."""

from __future__ import annotations


class ActError(RuntimeError):
    """Base error for typed-action resolution/execution."""

    error_code: str = "ACT_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TargetNotFoundError(ActError):
    """No InteractiveTarget matches the requested ref."""

    error_code = "TARGET_NOT_FOUND"


class StaleRefError(ActError):
    """Target ref epoch does not match the current PageView snapshot epoch."""

    error_code = "STALE_REF"


class UnsupportedActionKindError(ActError):
    """Action kind is outside the W1-004 click/type/scroll surface."""

    error_code = "UNSUPPORTED_KIND"


class InvalidActionError(ActError):
    """Required per-kind parameters are missing or invalid."""

    error_code = "INVALID_ACTION"
