"""EverWeb harness package boundary."""

from everweb.harness.cassette import (
    CassetteEntry,
    CassetteError,
    CassetteValidationError,
    dump_cassette,
    load_cassette,
)
from everweb.harness.errors import FakeHarnessError, FakeScriptExhaustedError
from everweb.harness.fake_browser import FAKE_BROWSER_CAPABILITIES, FakeBrowser
from everweb.harness.fake_model import FakeModel

__all__ = [
    "CassetteEntry",
    "CassetteError",
    "CassetteValidationError",
    "FAKE_BROWSER_CAPABILITIES",
    "FakeBrowser",
    "FakeHarnessError",
    "FakeModel",
    "FakeScriptExhaustedError",
    "dump_cassette",
    "load_cassette",
]
