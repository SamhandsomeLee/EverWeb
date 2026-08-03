"""Worker heartbeat facts and Parent-side liveness assessment."""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from everweb.domain import RuntimePhase
from everweb.ports import ClockPort

NonEmptyString = Annotated[str, Field(min_length=1)]
PositiveInteger = Annotated[int, Field(gt=0)]
NonNegativeInteger = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]


class WorkerHeartbeat(BaseModel):
    """Operational Worker telemetry that never enters model context."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_id: NonEmptyString
    pid: PositiveInteger
    phase: RuntimePhase
    last_iteration: NonNegativeInteger
    last_official_step: NonNegativeInteger
    last_progress_at: AwareDatetime
    browser_connected: bool
    model_call_inflight: bool
    rss_bytes: NonNegativeInteger | None


class HeartbeatPolicy(BaseModel):
    """Frozen send interval and Parent expiry thresholds."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    interval_s: NonNegativeFloat = 3.0
    stale_after_s: NonNegativeFloat = 6.0
    startup_grace_s: NonNegativeFloat = 6.0

    @field_validator("interval_s", "stale_after_s", "startup_grace_s", mode="before")
    @classmethod
    def _require_exact_float(cls, value: object) -> object:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("heartbeat timing values must be finite floats")
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> HeartbeatPolicy:
        if not 2.0 <= self.interval_s <= 5.0:
            raise ValueError("heartbeat interval_s must be between 2 and 5 seconds")
        if self.stale_after_s < self.interval_s:
            raise ValueError("stale_after_s must not be shorter than interval_s")
        if self.startup_grace_s < self.interval_s:
            raise ValueError("startup_grace_s must not be shorter than interval_s")
        return self


class HeartbeatStatus(StrEnum):
    """Parent-observed Worker liveness state."""

    ALIVE = "alive"
    EXPIRED = "expired"
    EXITED = "exited"


class HeartbeatError(RuntimeError):
    """Base error for heartbeat protocol failures."""


class HeartbeatProtocolError(HeartbeatError):
    """A wire payload or Worker identity violates the protocol."""


class HeartbeatNotFoundError(HeartbeatError):
    """No heartbeat lifecycle is registered for an execution."""


@dataclass(slots=True)
class _HeartbeatRecord:
    pid: int
    started_at_monotonic: float
    last_received_at_monotonic: float | None = None
    latest: WorkerHeartbeat | None = None
    exited: bool = False


class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class HeartbeatMonitor:
    """Classify Worker liveness from process state and received messages."""

    def __init__(
        self,
        *,
        clock: ClockPort,
        policy: HeartbeatPolicy,
    ) -> None:
        self._clock = clock
        self._policy = policy
        self._records: dict[str, _HeartbeatRecord] = {}
        self._lock = threading.RLock()

    def register(self, execution_id: str, pid: int) -> None:
        if not execution_id:
            raise ValueError("execution_id must be non-empty")
        if type(pid) is not int or pid <= 0:
            raise ValueError("pid must be a positive int")
        now = self._monotonic()
        with self._lock:
            existing = self._records.get(execution_id)
            if existing is not None and not existing.exited:
                raise HeartbeatProtocolError(
                    f"heartbeat lifecycle already active for {execution_id!r}"
                )
            self._records[execution_id] = _HeartbeatRecord(
                pid=pid,
                started_at_monotonic=now,
            )

    def unregister(self, execution_id: str) -> None:
        with self._lock:
            self._records.pop(execution_id, None)

    def record_payload(
        self,
        payload: object,
        *,
        expected_execution_id: str,
        expected_pid: int,
    ) -> WorkerHeartbeat:
        try:
            encoded = json.dumps(
                payload,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            heartbeat = WorkerHeartbeat.model_validate_json(encoded)
        except (TypeError, ValueError, ValidationError) as exc:
            raise HeartbeatProtocolError("invalid heartbeat wire payload") from exc
        if heartbeat.execution_id != expected_execution_id:
            raise HeartbeatProtocolError("heartbeat execution_id mismatch")
        if heartbeat.pid != expected_pid:
            raise HeartbeatProtocolError("heartbeat pid mismatch")

        now = self._monotonic()
        with self._lock:
            record = self._record(expected_execution_id)
            if record.pid != expected_pid:
                raise HeartbeatProtocolError(
                    "registered Worker pid does not match heartbeat"
                )
            if record.exited:
                raise HeartbeatProtocolError(
                    "heartbeat arrived after Worker exit"
                )
            record.latest = heartbeat
            record.last_received_at_monotonic = now
        return heartbeat

    def mark_exited(self, execution_id: str) -> None:
        with self._lock:
            self._record(execution_id).exited = True

    def latest(self, execution_id: str) -> WorkerHeartbeat | None:
        with self._lock:
            return self._record(execution_id).latest

    def status(
        self,
        execution_id: str,
        *,
        process_exited: bool,
    ) -> HeartbeatStatus:
        if type(process_exited) is not bool:
            raise TypeError("process_exited must be a bool")
        now = self._monotonic()
        with self._lock:
            record = self._record(execution_id)
            if process_exited:
                record.exited = True
            if record.exited:
                return HeartbeatStatus.EXITED

            last_received = record.last_received_at_monotonic
            if last_received is None:
                age = self._elapsed(now, record.started_at_monotonic)
                return (
                    HeartbeatStatus.ALIVE
                    if age <= self._policy.startup_grace_s
                    else HeartbeatStatus.EXPIRED
                )

            age = self._elapsed(now, last_received)
            return (
                HeartbeatStatus.ALIVE
                if age <= self._policy.stale_after_s
                else HeartbeatStatus.EXPIRED
            )

    def _record(self, execution_id: str) -> _HeartbeatRecord:
        try:
            return self._records[execution_id]
        except KeyError as exc:
            raise HeartbeatNotFoundError(
                f"no heartbeat lifecycle for execution {execution_id!r}"
            ) from exc

    def _monotonic(self) -> float:
        value = self._clock.monotonic()
        if type(value) is not float or not math.isfinite(value):
            raise HeartbeatProtocolError(
                "ClockPort.monotonic() must return a finite float"
            )
        return value

    @staticmethod
    def _elapsed(now: float, then: float) -> float:
        if now < then:
            raise HeartbeatProtocolError("monotonic clock moved backwards")
        return now - then
