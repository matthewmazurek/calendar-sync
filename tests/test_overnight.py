"""Tests for overnight event transformations."""

from datetime import date, time

import pytest

from app.models.event import Event
from app.models.template import CalendarTemplate, EventTypeConfig, OvernightConfig
from app.processing.configurable_processor import ConfigurableEventProcessor


@pytest.fixture
def split_template():
    """Template with split overnight handling."""
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
        types={"test": EventTypeConfig(match="test")},
    )


@pytest.fixture
def all_day_template():
    """Template with all_day overnight handling."""
    return CalendarTemplate(
        name="test",
        version="1.0",
        settings={"time_format": "12h"},
        locations={},
        defaults={
            "location": None,
            "consolidate": "title",
            "overnight": {"as": "all_day", "format": "{title} {time_range}"},
            "time_periods": {},
        },
        types={"test": EventTypeConfig(match="test")},
    )


@pytest.fixture
def keep_template():
    """Template with keep overnight handling."""
    return CalendarTemplate(
        name="test",
        version="1.0",
        settings={"time_format": "12h"},
        locations={},
        defaults={
            "location": None,
            "consolidate": "title",
            "overnight": "keep",
            "time_periods": {},
        },
        types={"test": EventTypeConfig(match="test")},
    )


def test_overnight_split(split_template):
    """Overnight event split at midnight into two events."""
    event = Event(
        title="Test Event",
        date=date(2025, 1, 1),
        start=time(17, 0),  # 5 PM
        end=time(8, 0),  # 8 AM next day
        type="test",
    )

    processor = ConfigurableEventProcessor(split_template)
    result = processor.process([event])

    assert len(result) == 2
    # First event: 5 PM to midnight
    assert result[0].date == date(2025, 1, 1)
    assert result[0].start == time(17, 0)
    assert result[0].end is None
    # Second event: midnight to 8 AM
    assert result[1].date == date(2025, 1, 2)
    assert result[1].start is None
    assert result[1].end == time(8, 0)


def test_overnight_as_all_day(all_day_template):
    """Overnight event converted to all-day with times in title."""
    event = Event(
        title="Test Event",
        date=date(2025, 1, 1),
        start=time(17, 0),  # 5 PM
        end=time(8, 0),  # 8 AM next day
        type="test",
    )

    processor = ConfigurableEventProcessor(all_day_template)
    result = processor.process([event])

    assert len(result) == 1
    assert result[0].is_all_day is True
    assert "5:00 PM" in result[0].title
    assert "8:00 AM" in result[0].title


def test_overnight_keep(keep_template):
    """Overnight event kept as multi-day timed event."""
    event = Event(
        title="Test Event",
        date=date(2025, 1, 1),
        start=time(17, 0),  # 5 PM
        end=time(8, 0),  # 8 AM next day
        type="test",
    )

    processor = ConfigurableEventProcessor(keep_template)
    result = processor.process([event])

    assert len(result) == 1
    assert result[0].start == time(17, 0)
    assert result[0].end == time(8, 0)
    assert result[0].end_date == date(2025, 1, 2)


def test_non_overnight_not_affected(split_template):
    """Non-overnight events are not affected by overnight transforms."""
    event = Event(
        title="Test Event",
        date=date(2025, 1, 1),
        start=time(9, 0),  # 9 AM
        end=time(17, 0),  # 5 PM
        type="test",
    )

    processor = ConfigurableEventProcessor(split_template)
    result = processor.process([event])

    assert len(result) == 1
    assert result[0].start == time(9, 0)
    assert result[0].end == time(17, 0)
