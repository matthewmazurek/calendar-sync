"""JSON file reader for calendar files."""

from pathlib import Path

from app.exceptions import IngestionError
from app.ingestion.summary import build_ingestion_summary
from app.models.calendar import Calendar
from app.models.ingestion import IngestionResult


class JSONReader:
    """Reader for JSON calendar files."""

    def read(self, path: Path) -> IngestionResult:
        """Read calendar from JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                import json

                data = json.load(f)
        except Exception as e:
            raise IngestionError(f"Failed to read JSON file: {e}") from e

        try:
            # Use Pydantic's JSON deserialization
            calendar = Calendar.model_validate(data)
            return IngestionResult(
                calendar=calendar, summary=build_ingestion_summary(calendar)
            )
        except Exception as e:
            raise IngestionError(f"Failed to parse JSON calendar: {e}") from e
