"""Ingestion result and summary models."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from app.models.calendar import Calendar


class IngestionSummary(BaseModel):
    """Summary of ingestion stats derived from a source calendar."""

    events: int
    date_range: str
    year: int | None = None
    revised_date: date | None = None
    total_halfdays: int
    weekly_coverage_year: float | None = None


class IngestionResult(BaseModel):
    """Result of ingesting a calendar file."""

    calendar: Calendar
    summary: IngestionSummary


@dataclass
class IngestionContext:
    """Context containing all data from ingestion workflow.

    This is used by CLI commands to track state between ingestion and processing steps.
    """

    input_path: Path
    ingestion_result: IngestionResult
    existing_calendar: Calendar | None
    is_new: bool
