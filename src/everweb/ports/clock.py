"""Injectable clock capability boundary."""

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class ClockPort(Protocol):
    """Wall and monotonic time reads without scheduling behavior."""

    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...
