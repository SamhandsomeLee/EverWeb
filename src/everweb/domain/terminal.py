"""Internal terminal states independent of competition status values."""

from enum import StrEnum


class InternalTerminalState(StrEnum):
    """Terminal outcomes produced by EverWeb core and domain logic."""

    VERIFIED_SUCCESS = "verified_success"
    BEST_EFFORT = "best_effort"
    BUDGET_EXHAUSTED = "budget_exhausted"
    WALL_CLOCK_EXHAUSTED = "wall_clock_exhausted"
    POLICY_BLOCKED = "policy_blocked"
    BROWSER_FAILURE = "browser_failure"
    MODEL_FAILURE = "model_failure"
    WORKER_CRASHED = "worker_crashed"
    OUTPUT_FAILURE = "output_failure"
