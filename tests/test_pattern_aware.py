"""Tests for pattern-aware consolidation."""

from datetime import date, time

import pytest

from app.models.event import Event
from app.models.template import CalendarTemplate, ConsolidateConfig, EventTypeConfig
from app.processing.configurable_processor import ConfigurableEventProcessor


@pytest.fixture
def on_call_template():
    """Create a template with pattern-aware on-call configuration."""
    return CalendarTemplate(
        name="test",
        version="1.0",
        settings={"time_format": "12h"},
        locations={},
        defaults={
            "location": None,
            "consolidate": "title",
            "overnight": "split",
            "time_periods": {},
        },
        types={
            "on_call": EventTypeConfig(
                match="on call",
                label="^(.+?)\\s+on call",
                consolidate=ConsolidateConfig(group_by="label", pattern_aware=True),
                overnight={"as": "all_day", "format": "{label} on call {time_range}"},
            )
        },
    )


def test_uniform_24h_stretch(on_call_template):
    """Fri-Sun all 0800-0800 -> single consolidated 24h event, no overnight."""
    events = [
        Event(
            title="Primary on call",
            date=date(2025, 1, 3),  # Friday
            start=time(8, 0),
            end=time(8, 0),
            type="on_call",
            label="Primary",
        ),
        Event(
            title="Primary on call",
            date=date(2025, 1, 4),  # Saturday
            start=time(8, 0),
            end=time(8, 0),
            type="on_call",
            label="Primary",
        ),
        Event(
            title="Primary on call",
            date=date(2025, 1, 5),  # Sunday
            start=time(8, 0),
            end=time(8, 0),
            type="on_call",
            label="Primary",
        ),
    ]

    processor = ConfigurableEventProcessor(on_call_template)
    result = processor.process(events)

    # Should have one consolidated all-day event (since overnight is "all_day"), no separate overnight events
    assert len(result) == 1
    assert result[0].date == date(2025, 1, 3)
    assert result[0].end_date == date(2025, 1, 5)
    assert result[0].is_all_day is True, "Consolidated event should be all-day when overnight is 'all_day'"
    assert result[0].start is None, "Consolidated event should have no start time"
    assert result[0].end is None, "Consolidated event should have no end time"


def test_mixed_stretch(on_call_template):
    """Mon-Thu with mixed day/overnight -> day consolidated + overnight events."""
    events = [
        Event(
            title="Primary on call",
            date=date(2025, 1, 6),  # Monday
            start=time(8, 0),
            end=time(8, 0),  # 24h (overnight)
            type="on_call",
            label="Primary",
        ),
        Event(
            title="Primary on call",
            date=date(2025, 1, 7),  # Tuesday
            start=time(8, 0),
            end=time(17, 0),  # Day only
            type="on_call",
            label="Primary",
        ),
        Event(
            title="Primary on call",
            date=date(2025, 1, 8),  # Wednesday
            start=time(8, 0),
            end=time(8, 0),  # 24h (overnight)
            type="on_call",
            label="Primary",
        ),
        Event(
            title="Primary on call",
            date=date(2025, 1, 9),  # Thursday
            start=time(8, 0),
            end=time(17, 0),  # Day only
            type="on_call",
            label="Primary",
        ),
    ]

    processor = ConfigurableEventProcessor(on_call_template)
    result = processor.process(events)

    # Expected output for mixed stretch:
    # 1. One consolidated all-day event for day portion (Mon-Thu)
    # 2. Two overnight all-day events for Mon and Wed (the isolated overnight days)
    
    # Find consolidated day event
    consolidated = [e for e in result if e.end_date and e.end_date > e.date]
    assert len(consolidated) == 1, f"Expected 1 consolidated event, got {len(consolidated)}"
    consolidated_event = consolidated[0]
    assert consolidated_event.date == date(2025, 1, 6)
    assert consolidated_event.end_date == date(2025, 1, 9)
    assert consolidated_event.is_all_day is True, "Consolidated day portion should be all-day"
    assert consolidated_event.start is None, "Consolidated day portion should have no start time"
    assert consolidated_event.end is None, "Consolidated day portion should have no end time"
    
    # Find overnight all-day events
    overnight_events = [e for e in result if not e.start and not e.end and "5:00 PM" in e.title]
    assert len(overnight_events) == 2, f"Expected 2 overnight events, got {len(overnight_events)}"
    overnight_dates = {e.date for e in overnight_events}
    assert overnight_dates == {date(2025, 1, 6), date(2025, 1, 8)}, f"Overnight events on wrong dates: {overnight_dates}"
    
    # Verify overnight event titles
    for e in overnight_events:
        assert "Primary on call" in e.title
        assert "5:00 PM" in e.title
        assert "8:00 AM" in e.title
    
    # Total should be 3 events: 1 consolidated + 2 overnight
    assert len(result) == 3, f"Expected 3 total events, got {len(result)}"


def test_pattern_break(on_call_template):
    """Mon-Thu mixed, Fri-Sun uniform -> two separate consolidations."""
    events = [
        # Mon-Thu mixed
        Event(
            title="Primary on call",
            date=date(2025, 1, 6),  # Monday
            start=time(8, 0),
            end=time(8, 0),
            type="on_call",
            label="Primary",
        ),
        Event(
            title="Primary on call",
            date=date(2025, 1, 7),  # Tuesday
            start=time(8, 0),
            end=time(17, 0),
            type="on_call",
            label="Primary",
        ),
        # Fri-Sun uniform
        Event(
            title="Primary on call",
            date=date(2025, 1, 10),  # Friday
            start=time(8, 0),
            end=time(8, 0),
            type="on_call",
            label="Primary",
        ),
        Event(
            title="Primary on call",
            date=date(2025, 1, 11),  # Saturday
            start=time(8, 0),
            end=time(8, 0),
            type="on_call",
            label="Primary",
        ),
        Event(
            title="Primary on call",
            date=date(2025, 1, 12),  # Sunday
            start=time(8, 0),
            end=time(8, 0),
            type="on_call",
            label="Primary",
        ),
    ]

    processor = ConfigurableEventProcessor(on_call_template)
    result = processor.process(events)

    # Should have separate consolidations for Mon-Thu and Fri-Sun
    # (There's a gap between Thu and Fri, so they're separate stretches)
    assert len(result) >= 2
