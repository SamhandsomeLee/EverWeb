"""Typed failures for EverWeb config loading."""

from __future__ import annotations


class ConfigError(ValueError):
    """Base error for invalid model-route configuration."""


class ManifestCompletenessError(ConfigError):
    """Scoring-path manifest is missing required formal-context roles."""
