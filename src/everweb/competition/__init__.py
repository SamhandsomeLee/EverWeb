"""EverWeb competition package boundary."""

from everweb.competition.adapter import CompetitionAdapter, NullCompetitionAdapter
from everweb.competition.capabilities import CompetitionCapabilities
from everweb.competition.errors import PendingTemplateError
from everweb.competition.output_contract import (
    OutputContractDraftError,
    OutputContractDraftMapper,
    OutputContractDraftValidationError,
)

__all__ = [
    "CompetitionAdapter",
    "CompetitionCapabilities",
    "NullCompetitionAdapter",
    "OutputContractDraftError",
    "OutputContractDraftMapper",
    "OutputContractDraftValidationError",
    "PendingTemplateError",
]
