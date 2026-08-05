"""Materialize nine capability availability receipts from BrowserPort.capabilities()."""

from __future__ import annotations

from everweb.domain import (
    BROWSER_CAPABILITY_NAMES,
    BrowserCapabilityProbeReport,
    CapabilityAvailabilityReceipt,
)
from everweb.ports import BrowserPort

_UNAVAILABLE_DETAIL = "unavailable"


class BrowserCapabilityProbe:
    """Application probe that never invents capabilities the port did not report."""

    def probe(self, browser: BrowserPort) -> BrowserCapabilityProbeReport:
        if not isinstance(browser, BrowserPort):
            raise TypeError("browser must implement BrowserPort")
        capabilities = browser.capabilities()
        items: list[CapabilityAvailabilityReceipt] = []
        for name in BROWSER_CAPABILITY_NAMES:
            available = bool(getattr(capabilities, name.value))
            items.append(
                CapabilityAvailabilityReceipt(
                    name=name,
                    available=available,
                    detail=None if available else _UNAVAILABLE_DETAIL,
                )
            )
        return BrowserCapabilityProbeReport(
            capabilities=capabilities,
            items=tuple(items),
        )
