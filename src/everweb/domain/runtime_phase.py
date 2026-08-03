"""Runtime phase facts shared across process boundaries."""

from enum import StrEnum


class RuntimePhase(StrEnum):
    """Canonical phases of one Worker task lifecycle."""

    ANALYZE = "analyze"
    NAVIGATE = "navigate"
    INTERACT = "interact"
    COLLECT = "collect"
    EXTRACT = "extract"
    VERIFY = "verify"
    RECOVER = "recover"
    PREPARE_FINAL_STATE = "prepare_final_state"
    TERMINAL_DECISION = "terminal_decision"
    SERIALIZE = "serialize"
    EMIT = "emit"
