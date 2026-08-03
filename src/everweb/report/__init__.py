"""EverWeb report package boundary."""

from everweb.report.trace_writer import (
    TraceCorruptionError,
    TraceDurability,
    TraceError,
    TraceEventTooLargeError,
    TraceReadResult,
    TraceRecoveryWarning,
    TraceSerializationError,
    TraceWriter,
    TraceWriterClosedError,
    compute_trace_checksum,
    read_trace,
)

__all__ = [
    "TraceCorruptionError",
    "TraceDurability",
    "TraceError",
    "TraceEventTooLargeError",
    "TraceReadResult",
    "TraceRecoveryWarning",
    "TraceSerializationError",
    "TraceWriter",
    "TraceWriterClosedError",
    "compute_trace_checksum",
    "read_trace",
]
