"""Shared errors for harness Fake adapters."""


class FakeHarnessError(RuntimeError):
    """Base error for harness Fake adapters."""


class FakeScriptExhaustedError(FakeHarnessError):
    """A scripted Fake response queue was exhausted."""
