"""Ingestion result and summary models."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.models.event import Event

if TYPE_CHECKING:
    from app.models.calendar import Calendar


@dataclass
class RawIngestion:
    """Raw events parsed from a source file.

    This is the output of readers before any processing or metadata is added.
    Events may have uid populated (ICS) or not (Word).
    """

    events: list[Event] = field(default_factory=list)
    revised_at: date | None = None


class IngestionSummary(BaseModel):
    """Summary of ingestion stats derived from a source calendar."""

    events: int
    date_range: str | None = None
    year: int | None = None
    revised_date: date | None = None
    total_halfdays: int = 0
    weekly_coverage_year: float | None = None


class IngestionResult(BaseModel):
    """Result of ingesting a calendar file."""

    raw: RawIngestion
    summary: IngestionSummary

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


@dataclass
class IngestionContext:
    """Context containing all data from ingestion workflow.

    This is used by CLI commands to track state between ingestion and processing steps.
    """

    input_path: Path
    ingestion_result: IngestionResult
    existing_calendar: "Calendar | None"
    is_new: bool
