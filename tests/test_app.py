import io
import os
import re
from pathlib import Path

import pytest
from flask import Flask

from app import create_app
from app.calendar_storage import DEFAULT_CALENDAR_DIR


def normalize_text(s):
    # Replace curly apostrophes and quotes with straight ones
    s = s.replace("'", "'").replace("'", "'")
    s = s.replace(""", '"').replace(""", '"')
    # Remove invisible/directional marks
    s = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def test_app_factory_exists():
    """Test that the app factory function exists."""
    assert callable(create_app)


def test_inbound_route_exists(app):
    """Test that the /inbound route exists and returns 400 or 404."""
    response = app.test_client().post("/inbound")
    assert response.status_code in (400, 404)


def test_inbound_no_form_data_returns_400(app):
    """POST /inbound with no form data returns 400."""
    response = app.test_client().post("/inbound")
    assert response.status_code == 400


def test_inbound_with_dummy_attachment_returns_400(app):
    """POST /inbound with dummy form-file attachment-1 returns 400 for invalid file."""
    data = {"attachment-1": (io.BytesIO(b"dummy"), "dummy.docx")}
    response = app.test_client().post("/inbound", data=data)
    assert response.status_code == 400
    assert response.data.decode() == "Invalid .docx file"


def test_save_attachment_to_temp_file(app):
    """Test that an uploaded file returns a success response."""
    # Read the example file
    example_path = Path("tests/fixtures/example-calendar.docx")
    with open(example_path, "rb") as f:
        file_content = f.read()

    # Upload the file
    data = {"attachment-1": (io.BytesIO(file_content), "example-calendar.docx")}
    response = app.test_client().post("/inbound", data=data)

    # Check response
    assert response.status_code == 200
    assert response.content_type == "application/json"
    data = response.get_json()
    assert data["status"] == "success"
    assert "filename" in data


def test_parse_complex_calendar_events():
    """Test parsing complex calendar events from the example document."""
    from app.calendar_parser import parse_docx_events

    fixture_path = Path("tests/fixtures/example-calendar.docx")
    events = parse_docx_events(fixture_path)

    # Test January 2025 events
    jan_1_events = [e for e in events if e.get("date") == "2025-01-01"]
    assert len(jan_1_events) == 1

    jan_7_events = [e for e in events if e.get("date") == "2025-01-07"]
    assert len(jan_7_events) == 2
    assert any(
        e["title"] == "Clinic" and e["start"] == "0800" and e["end"] == "1200"
        for e in jan_7_events
    )
    assert any(
        e["title"] == "TSE Clinic" and e["start"] == "1230" and e["end"] == "1630"
        for e in jan_7_events
    )

    # Test February 2025 events
    feb_6_events = [e for e in events if e.get("date") == "2025-02-06"]
    assert len(feb_6_events) == 2
    assert any(
        e["title"] == "CCSC" and e["start"] == "0730" and e["end"] == "1200"
        for e in feb_6_events
    )
    assert any(
        e["title"] == "Endo" and e["start"] == "1230" and e["end"] == "1630"
        for e in feb_6_events
    )

    # Test a special event (ADMIN DAY)
    feb_5_events = [e for e in events if e.get("date") == "2025-02-05"]
    assert len(feb_5_events) == 1
    assert feb_5_events[0]["title"] == "ADMIN DAY"

    # Verify we have events for the full year
    months_with_events = {e["date"][:7] for e in events}  # Get YYYY-MM from dates
    assert len(months_with_events) == 12  # All months should have events
    assert all(
        f"2025-{m:02d}" in months_with_events for m in range(1, 13)
    )  # January through December


def test_inbound_endpoint_full_integration(app):
    """Test full integration of /inbound endpoint with .docx processing and iCal generation."""
    # Read the example file
    fixture_path = Path("tests/fixtures/example-calendar.docx")
    with open(fixture_path, "rb") as f:
        file_content = f.read()

    # Upload the file
    data = {"attachment-1": (io.BytesIO(file_content), "example-calendar.docx")}
    response = app.test_client().post("/inbound", data=data)

    # Check response status and content type
    assert response.status_code == 200
    assert response.content_type == "application/json"
    data = response.get_json()
    assert data["status"] == "success"
    assert "filename" in data

    # Check that the calendar was saved
    assert DEFAULT_CALENDAR_DIR.exists()
    assert (DEFAULT_CALENDAR_DIR / "latest-calendar.ics").exists()

    # Get the calendar and verify its contents
    calendar_response = app.test_client().get("/calendar")
    assert calendar_response.status_code == 200
    assert calendar_response.content_type == "text/calendar; charset=utf-8"
    ical_content = calendar_response.data.decode("utf-8")

    # Basic iCal validation
    assert "BEGIN:VCALENDAR" in ical_content
    assert "END:VCALENDAR" in ical_content
    assert "VERSION:2.0" in ical_content

    # Verify specific events are present (skip New Year's Day)
    assert "Clinic" in ical_content
    assert "TSE Clinic" in ical_content
    assert "CCSC" in ical_content
    assert "Endo" in ical_content
    assert "ADMIN DAY" in ical_content

    # Verify dates and times
    assert "DTSTART:20250107T080000" in ical_content  # Clinic
    assert "DTSTART:20250107T123000" in ical_content  # TSE Clinic
    assert "DTSTART:20250206T073000" in ical_content  # CCSC
    assert "DTSTART:20250206T123000" in ical_content  # Endo
    assert (
        "DTSTART:20250205" in ical_content
        or "DTSTART;VALUE=DATE:20250205" in ical_content
    )  # ADMIN DAY


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    app = create_app()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


@pytest.fixture(autouse=True)
def cleanup_calendar_dir():
    """Clean up calendar directory before and after each test."""
    if DEFAULT_CALENDAR_DIR.exists():
        for file in DEFAULT_CALENDAR_DIR.glob("*"):
            if file.is_file():
                file.unlink()
        DEFAULT_CALENDAR_DIR.rmdir()
    yield
    if DEFAULT_CALENDAR_DIR.exists():
        for file in DEFAULT_CALENDAR_DIR.glob("*"):
            if file.is_file():
                file.unlink()
        DEFAULT_CALENDAR_DIR.rmdir()


def test_inbound_no_attachment(client):
    """Test inbound endpoint with no attachment."""
    response = client.post("/inbound")
    assert response.status_code == 400


def test_inbound_with_docx(client):
    """Test inbound endpoint with a valid .docx attachment."""
    # Create a test .docx file
    test_docx = Path("data/test_documents/example-calendar.docx")
    assert test_docx.exists(), "Test .docx file not found"

    with open(test_docx, "rb") as f:
        response = client.post(
            "/inbound",
            data={"attachment-1": (f, "test.docx")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "filename" in data

    # Check that the calendar was saved
    assert DEFAULT_CALENDAR_DIR.exists()
    assert (DEFAULT_CALENDAR_DIR / "latest-calendar.ics").exists()


def test_get_calendar_no_calendar(client):
    """Test getting calendar when none exists."""
    response = client.get("/calendar")
    assert response.status_code == 404


def test_get_calendar_with_calendar(client):
    """Test getting calendar when one exists."""
    # First create a calendar via inbound
    test_docx = Path("data/test_documents/example-calendar.docx")
    with open(test_docx, "rb") as f:
        client.post(
            "/inbound",
            data={"attachment-1": (f, "test.docx")},
            content_type="multipart/form-data",
        )

    # Then try to get it
    response = client.get("/calendar")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/calendar; charset=utf-8"
    assert (
        response.headers["Content-Disposition"]
        == "attachment; filename=latest-calendar.ics"
    )
    assert response.data.startswith(b"BEGIN:VCALENDAR")
