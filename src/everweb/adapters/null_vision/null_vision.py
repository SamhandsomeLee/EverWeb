"""NullVision adapter: vision capability explicitly unavailable."""

from __future__ import annotations

from typing import NoReturn

from everweb.domain import VisionRequest


class VisionUnavailableError(RuntimeError):
    """Raised when NullVision is asked to analyze while vision is off."""


class NullVision:
    """Production default for closed / unavailable optional vision."""

    def available(self) -> bool:
        return False

    def analyze(self, req: VisionRequest) -> NoReturn:
        if not isinstance(req, VisionRequest):
            raise TypeError("req must be a VisionRequest")
        raise VisionUnavailableError(
            "NullVision is unavailable; callers must handle vision off"
        )
