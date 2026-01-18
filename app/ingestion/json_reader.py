"""JSON file reader for calendar files."""

import json
from pathlib import Path

from app.exceptions import IngestionError
from app.ingestion.summary import build_ingestion_summary
from app.models.event import Event
from app.models.ingestion import IngestionResult, RawIngestion


class JSONReader:
    """Reader for JSON calendar files."""

    def read(self, path: Path) -> IngestionResult:
        """Read calendar from JSON file.
        
        Supports multiple formats:
        - Array of events: [{event1}, {event2}, ...]
        - Object with events key: {events: [...]}
        - Legacy nested format: {calendar: {events: [...]}, metadata: {...}}
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise IngestionError(f"Failed to read JSON file: {e}") from e

        try:
            events = self._extract_events(data)
            raw = RawIngestion(events=events)
            return IngestionResult(raw=raw, summary=build_ingestion_summary(raw))
        except Exception as e:
            raise IngestionError(f"Failed to parse JSON calendar: {e}") from e

    def _extract_events(self, data: dict | list) -> list[Event]:
        """Extract events from various JSON formats."""
        if isinstance(data, list):
            # Array of events
            return [Event.model_validate(e) for e in data]
        
        if isinstance(data, dict):
            # Check for legacy nested format
            if "calendar" in data and "metadata" in data:
                calendar_data = data["calendar"]
                events_data = calendar_data.get("events", [])
                return [Event.model_validate(e) for e in events_data]
            
            # Check for events key
            if "events" in data:
                events_data = data["events"]
                return [Event.model_validate(e) for e in events_data]
        
        raise IngestionError(
            "JSON format not recognized. Expected array of events, "
            "object with 'events' key, or legacy nested format."
        )
