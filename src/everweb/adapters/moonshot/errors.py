"""Typed failures for the Moonshot/Kimi adapter."""

from __future__ import annotations


class MoonshotAdapterError(RuntimeError):
    """Base error for Moonshot adapter failures that must not leak secrets."""


class MoonshotTransportError(MoonshotAdapterError):
    """HTTP transport failed without exposing Authorization material."""


class MoonshotConfigError(MoonshotAdapterError):
    """Adapter configuration is invalid."""
