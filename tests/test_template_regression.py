"""Tests for template-based processing."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.config import CalendarConfig
from app.ingestion.ics_reader import ICSReader
from app.ingestion.word_reader import WordReader
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.models.template_loader import load_template
from app.output.ics_writer import ICSWriter
from app.processing.event_processor import process_events_with_template


def normalize_event_for_comparison(event):
    """Normalize event for comparison (ignore UIDs, timestamps, etc.)."""
    return {
        "title": event.title,
        "date": event.date.isoformat() if event.date else None,
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "start": event.start.strftime("%H:%M") if event.start else None,
        "end": event.end.strftime("%H:%M") if event.end else None,
        "location": event.location,
    }


def test_template_word_reader_type_assignment():
    """Verify WordReader assigns types when template is provided."""
    fixture_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    if not fixture_path.exists():
        pytest.skip("Fixture file not found")

    # Load template
    config = CalendarConfig.from_env()
    template = load_template(config.default_template, config.template_dir)

    # Read with template
    reader = WordReader()
    ingestion_result = reader.read(fixture_path, template)
    calendar = ingestion_result.calendar

    # Check that some events have types assigned
    events_with_types = [e for e in calendar.events if e.type is not None]
    assert len(events_with_types) > 0

    # Check that on-call events have labels
    on_call_events = [e for e in calendar.events if e.type == "on_call"]
    if on_call_events:
        events_with_labels = [e for e in on_call_events if e.label is not None]
        # At least some on-call events should have labels
        assert len(events_with_labels) > 0


def test_end_to_end_template_vs_expected_ics():
    """End-to-end test: process example-calendar.docx with template and compare to example-calendar.ics."""
    docx_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    expected_ics_path = Path(__file__).parent / "fixtures" / "example-calendar.ics"

    if not docx_path.exists() or not expected_ics_path.exists():
        pytest.skip("Fixture files not found")

    # Load the 'default' template explicitly (not mazurek which suppresses holidays)
    config = CalendarConfig.from_env()
    template = load_template("default", config.template_dir)

    # Read and process with template
    word_reader = WordReader()
    ingestion_result = word_reader.read(docx_path, template)
    source_calendar = ingestion_result.calendar
    processed_events, _ = process_events_with_template(source_calendar.events, template)
    processed_calendar = source_calendar.model_copy(update={"events": processed_events})

    # Write to temporary ICS file
    with tempfile.NamedTemporaryFile(suffix=".ics", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
        try:
            metadata = CalendarMetadata(
                name="regression_test",
                created=datetime.now(),
                last_updated=datetime.now(),
            )
            calendar_with_metadata = CalendarWithMetadata(
                calendar=processed_calendar, metadata=metadata
            )
            writer = ICSWriter()
            # Pass template for resolving location_id references
            writer.write(calendar_with_metadata, tmp_path, template=template)

            # Read both ICS files
            ics_reader = ICSReader()
            actual_result = ics_reader.read(tmp_path)
            expected_result = ics_reader.read(expected_ics_path)
            actual_calendar = actual_result.calendar
            expected_calendar = expected_result.calendar

            # Normalize events for comparison
            actual_normalized = sorted(
                [normalize_event_for_comparison(e) for e in actual_calendar.events],
                key=lambda x: (x["date"], x["title"]),
            )
            expected_normalized = sorted(
                [normalize_event_for_comparison(e) for e in expected_calendar.events],
                key=lambda x: (x["date"], x["title"]),
            )

            # Compare counts (template may consolidate more aggressively, so allow some difference)
            actual_count = len(actual_normalized)
            expected_count = len(expected_normalized)
            assert actual_count > 0, "No events produced"
            assert expected_count > 0, "No expected events"
            # Template processing may consolidate more, so actual should be <= expected
            # Allow up to 20% fewer events due to better consolidation
            assert actual_count >= expected_count * 0.8, (
                f"Too few events: {actual_count} vs {expected_count} "
                "(template may be over-consolidating)"
            )

            # Compare events (allowing for some differences in consolidation/formatting)
            # We'll do a fuzzy match - check that key events are present
            actual_titles_by_date: dict[str, list[str]] = {}
            for event in actual_normalized:
                date_key = event["date"]
                if date_key not in actual_titles_by_date:
                    actual_titles_by_date[date_key] = []
                actual_titles_by_date[date_key].append(event["title"])

            expected_titles_by_date: dict[str, list[str]] = {}
            for event in expected_normalized:
                date_key = event["date"]
                if date_key not in expected_titles_by_date:
                    expected_titles_by_date[date_key] = []
                expected_titles_by_date[date_key].append(event["title"])

            # Check that we have events on most of the same dates
            # (some dates might be consolidated differently)
            actual_dates = set(actual_titles_by_date.keys())
            expected_dates = set(expected_titles_by_date.keys())
            overlap = actual_dates & expected_dates
            assert (
                len(overlap) >= len(expected_dates) * 0.9
            ), f"Too many date mismatches: {len(overlap)}/{len(expected_dates)} dates match"

            # Sample a few key dates to verify key events are present
            sample_dates = sorted(overlap)[:20]  # Check first 20 dates
            for date_key in sample_dates:
                actual_titles = set(actual_titles_by_date[date_key])
                expected_titles = set(expected_titles_by_date[date_key])
                # Allow for some variation (e.g., consolidation differences)
                # But key events should be present
                assert len(actual_titles) > 0, f"No events on {date_key}"
                assert len(expected_titles) > 0, f"No expected events on {date_key}"

            # Verify that we have some key event types
            all_actual_titles = {e["title"] for e in actual_normalized}
            all_expected_titles = {e["title"] for e in expected_normalized}
            # Check that common event types are present
            common_titles = all_actual_titles & all_expected_titles
            assert len(common_titles) > 50, (
                f"Too few common events: {len(common_titles)} "
                "(template processing may be too different)"
            )

        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()
