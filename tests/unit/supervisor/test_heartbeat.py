"""Unit contracts for Worker heartbeat facts and monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from everweb.domain import ModelRequest, RuntimePhase
from everweb.supervisor import (
    HeartbeatMonitor,
    HeartbeatNotFoundError,
    HeartbeatPolicy,
    HeartbeatProtocolError,
    HeartbeatStatus,
    WorkerHeartbeat,
)
from everweb.supervisor import heartbeat as heartbeat_module

EXPECTED_HEARTBEAT_FIELDS = {
    "execution_id",
    "pid",
    "phase",
    "last_iteration",
    "last_official_step",
    "last_progress_at",
    "browser_connected",
    "model_call_inflight",
    "rss_bytes",
}


@dataclass
class FakeClock:
    monotonic_value: float = 100.0

    def now(self) -> datetime:
        return datetime(2026, 8, 3, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.monotonic_value

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds


def heartbeat(
    *,
    execution_id: str = "execution-001",
    pid: int = 123,
) -> WorkerHeartbeat:
    return WorkerHeartbeat(
        execution_id=execution_id,
        pid=pid,
        phase=RuntimePhase.INTERACT,
        last_iteration=7,
        last_official_step=4,
        last_progress_at=datetime(2026, 8, 3, 7, 0, tzinfo=UTC),
        browser_connected=True,
        model_call_inflight=False,
        rss_bytes=1024,
    )


def test_runtime_phase_and_heartbeat_contracts_are_exact() -> None:
    value = heartbeat()

    assert {phase.value for phase in RuntimePhase} == {
        "analyze",
        "navigate",
        "interact",
        "collect",
        "extract",
        "verify",
        "recover",
        "prepare_final_state",
        "terminal_decision",
        "serialize",
        "emit",
    }
    assert set(WorkerHeartbeat.model_fields) == EXPECTED_HEARTBEAT_FIELDS
    assert WorkerHeartbeat.model_validate_json(value.model_dump_json()) == value

    with pytest.raises(ValidationError):
        value.pid = 456
    with pytest.raises(ValidationError):
        WorkerHeartbeat.model_validate(
            {**value.model_dump(), "unexpected": "field"}
        )


def test_heartbeat_stays_out_of_model_request_context() -> None:
    assert "heartbeat" not in ModelRequest.model_fields
    assert set(ModelRequest.model_fields) == {"messages", "response_format"}
    assert heartbeat_module.__file__ is not None
    source = Path(heartbeat_module.__file__).read_text(encoding="utf-8")
    assert "ModelRequest" not in source
    assert "ModelPort" not in source
    assert "model_context" not in source


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("execution_id", ""),
        ("pid", True),
        ("phase", "interact"),
        ("last_iteration", -1),
        ("last_official_step", 1.0),
        ("last_progress_at", datetime(2026, 8, 3)),
        ("browser_connected", 1),
        ("model_call_inflight", 0),
        ("rss_bytes", -1),
    ],
)
def test_heartbeat_rejects_invalid_or_coerced_fields(
    field_name: str,
    value: Any,
) -> None:
    values = heartbeat().model_dump()
    values[field_name] = value

    with pytest.raises(ValidationError):
        WorkerHeartbeat.model_validate(values)


def test_heartbeat_policy_is_strict_frozen_and_bounded() -> None:
    policy = HeartbeatPolicy()

    assert policy == HeartbeatPolicy(
        interval_s=3.0,
        stale_after_s=6.0,
        startup_grace_s=6.0,
    )
    assert HeartbeatPolicy.model_validate_json(policy.model_dump_json()) == policy

    with pytest.raises(ValidationError):
        policy.interval_s = 4.0
    with pytest.raises(ValidationError):
        HeartbeatPolicy(interval_s=3)
    with pytest.raises(ValidationError):
        HeartbeatPolicy(interval_s=1.9)
    with pytest.raises(ValidationError):
        HeartbeatPolicy(interval_s=5.1)
    with pytest.raises(ValidationError):
        HeartbeatPolicy(stale_after_s=2.0)
    with pytest.raises(ValidationError):
        HeartbeatPolicy(startup_grace_s=2.0)
    with pytest.raises(ValidationError):
        HeartbeatPolicy(stale_after_s=float("inf"))


def test_monitor_expires_startup_and_received_heartbeat_with_fake_clock() -> None:
    clock = FakeClock()
    monitor = HeartbeatMonitor(clock=clock, policy=HeartbeatPolicy())
    monitor.register("execution-001", 123)

    assert (
        monitor.status("execution-001", process_exited=False)
        is HeartbeatStatus.ALIVE
    )
    clock.advance(6.0)
    assert (
        monitor.status("execution-001", process_exited=False)
        is HeartbeatStatus.ALIVE
    )
    clock.advance(0.001)
    assert (
        monitor.status("execution-001", process_exited=False)
        is HeartbeatStatus.EXPIRED
    )

    payload = heartbeat().model_dump(mode="json")
    monitor.record_payload(
        payload,
        expected_execution_id="execution-001",
        expected_pid=123,
    )
    assert monitor.latest("execution-001") == heartbeat()
    assert (
        monitor.status("execution-001", process_exited=False)
        is HeartbeatStatus.ALIVE
    )
    clock.advance(6.001)
    assert (
        monitor.status("execution-001", process_exited=False)
        is HeartbeatStatus.EXPIRED
    )


def test_monitor_process_exit_has_priority_over_heartbeat_age() -> None:
    clock = FakeClock()
    monitor = HeartbeatMonitor(clock=clock, policy=HeartbeatPolicy())
    monitor.register("execution-001", 123)

    assert (
        monitor.status("execution-001", process_exited=True)
        is HeartbeatStatus.EXITED
    )
    clock.advance(100.0)
    assert (
        monitor.status("execution-001", process_exited=False)
        is HeartbeatStatus.EXITED
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not-a-heartbeat",
        {},
        {"execution_id": "execution-001"},
        {**heartbeat().model_dump(mode="json"), "extra": True},
        {**heartbeat().model_dump(mode="json"), "last_iteration": True},
        {**heartbeat().model_dump(mode="json"), "rss_bytes": float("nan")},
    ],
)
def test_monitor_rejects_bad_wire_payloads(payload: object) -> None:
    monitor = HeartbeatMonitor(
        clock=FakeClock(),
        policy=HeartbeatPolicy(),
    )
    monitor.register("execution-001", 123)

    with pytest.raises(HeartbeatProtocolError):
        monitor.record_payload(
            payload,
            expected_execution_id="execution-001",
            expected_pid=123,
        )


def test_monitor_rejects_identity_mismatch_and_post_exit_message() -> None:
    monitor = HeartbeatMonitor(
        clock=FakeClock(),
        policy=HeartbeatPolicy(),
    )
    monitor.register("execution-001", 123)

    with pytest.raises(HeartbeatProtocolError, match="execution_id mismatch"):
        monitor.record_payload(
            heartbeat(execution_id="other").model_dump(mode="json"),
            expected_execution_id="execution-001",
            expected_pid=123,
        )
    with pytest.raises(HeartbeatProtocolError, match="pid mismatch"):
        monitor.record_payload(
            heartbeat(pid=456).model_dump(mode="json"),
            expected_execution_id="execution-001",
            expected_pid=123,
        )

    monitor.mark_exited("execution-001")
    with pytest.raises(HeartbeatProtocolError, match="after Worker exit"):
        monitor.record_payload(
            heartbeat().model_dump(mode="json"),
            expected_execution_id="execution-001",
            expected_pid=123,
        )


def test_monitor_rejects_unknown_execution_and_clock_regression() -> None:
    clock = FakeClock()
    monitor = HeartbeatMonitor(clock=clock, policy=HeartbeatPolicy())

    with pytest.raises(HeartbeatNotFoundError):
        monitor.latest("missing")

    monitor.register("execution-001", 123)
    clock.monotonic_value -= 1.0
    with pytest.raises(HeartbeatProtocolError, match="moved backwards"):
        monitor.status("execution-001", process_exited=False)
