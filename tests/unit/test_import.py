"""Import smoke tests for the EverWeb package skeleton."""

from __future__ import annotations

from importlib import import_module

EXPECTED_PACKAGES = (
    "act",
    "adapters",
    "adapters.deepseek",
    "adapters.everos",
    "adapters.filesystem",
    "adapters.moonshot",
    "adapters.null_memory",
    "adapters.null_vision",
    "adapters.playwright_browser",
    "answer",
    "competition",
    "core",
    "domain",
    "harness",
    "perceive",
    "ports",
    "report",
    "supervisor",
)


def test_import_everweb_package() -> None:
    package = import_module("everweb")

    assert package.__name__ == "everweb"


def test_import_architecture_package_boundaries() -> None:
    for package_name in EXPECTED_PACKAGES:
        package = import_module(f"everweb.{package_name}")

        assert package.__name__ == f"everweb.{package_name}"
