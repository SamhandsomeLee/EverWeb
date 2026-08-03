"""Fault tests for Parent heartbeat expiry under an injected clock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from everweb.domain import RuntimePhase
from everweb.supervisor import (
    HeartbeatMonitor,
    HeartbeatPolicy,
    HeartbeatStatus,
    WorkerHeartbeat,
)


@dataclass
class FakeClock:
    monotonic_value: float = 0.0

    def now(self) -> datetime:
        return datetime(2026, 8, 3, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.monotonic_value


def test_fake_clock_marks_worker_expired_without_waiting_real_time() -> None:
    clock = FakeClock()
    policy = HeartbeatPolicy(
        interval_s=2.0,
        stale_after_s=4.0,
        startup_grace_s=4.0,
    )
    monitor = HeartbeatMonitor(clock=clock, policy=policy)
    monitor.register("execution-fault", 4242)

    assert (
        monitor.status("execution-fault", process_exited=False)
        is HeartbeatStatus.ALIVE
    )

    clock.monotonic_value = 4.0
    assert (
        monitor.status("execution-fault", process_exited=False)
        is HeartbeatStatus.ALIVE
    )

    clock.monotonic_value = 4.001
    assert (
        monitor.status("execution-fault", process_exited=False)
        is HeartbeatStatus.EXPIRED
    )

    payload = WorkerHeartbeat(
        execution_id="execution-fault",
        pid=4242,
        phase=RuntimePhase.RECOVER,
        last_iteration=1,
        last_official_step=0,
        last_progress_at=datetime(2026, 8, 3, 1, 0, tzinfo=UTC),
        browser_connected=False,
        model_call_inflight=True,
        rss_bytes=None,
    ).model_dump(mode="json")
    monitor.record_payload(
        payload,
        expected_execution_id="execution-fault",
        expected_pid=4242,
    )

    assert (
        monitor.status("execution-fault", process_exited=False)
        is HeartbeatStatus.ALIVE
    )
    clock.monotonic_value = 8.002
    assert (
        monitor.status("execution-fault", process_exited=False)
        is HeartbeatStatus.EXPIRED
    )
