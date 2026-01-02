#!/usr/bin/env python3
"""Test script to verify geo data is written to ICS files."""

from datetime import date, datetime, time
from pathlib import Path

from app.models.calendar import Calendar
from app.models.event import Event
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.output.ics_writer import ICSWriter


def test_geo_write():
    """Test that geo data is written to ICS file."""
    # Location data from mazurek.json template
    location_address = "1403 29 St NW, Calgary AB T2N 2T9, Canada"
    location_geo = (51.065389, -114.133306)
    location_apple_title = "Foothills Medical Centre"

    # Create an event with location and geo data
    event = Event(
        title="Test Endo Clinic",
        date=date(2026, 1, 15),
        start=time(9, 0),
        end=time(17, 0),
        location=location_address,
        location_geo=location_geo,
        location_apple_title=location_apple_title,
    )

    # Create calendar with metadata
    calendar = Calendar(events=[event])
    metadata = CalendarMetadata(
        name="geo_test",
        created=datetime.now(),
        last_updated=datetime.now(),
    )
    calendar_with_metadata = CalendarWithMetadata(calendar=calendar, metadata=metadata)

    # Write to temporary file
    test_output = Path("test_geo_output.ics")
    writer = ICSWriter()
    writer.write(calendar_with_metadata, test_output)

    # Read and check the output
    print(f"✅ ICS file written to: {test_output}")
    print("\n📄 File contents:")
    print("-" * 80)

    with open(test_output, "r", encoding="utf-8") as f:
        content = f.read()
        print(content)

    print("-" * 80)

    # Check for geo-related content
    has_location = "LOCATION:" in content
    has_geo = "X-APPLE-STRUCTURED-LOCATION" in content or "geo:" in content
    has_apple_title = "X-TITLE" in content or location_apple_title in content

    print("\n🔍 Verification:")
    print(f"  Location present: {has_location}")
    print(f"  Geo data present: {has_geo}")
    print(f"  Apple title present: {has_apple_title}")

    if has_location and has_geo and has_apple_title:
        print("\n✅ SUCCESS: All geo data appears to be written correctly!")
    else:
        print("\n❌ FAILURE: Some geo data is missing!")
        if not has_location:
            print("   - Missing LOCATION field")
        if not has_geo:
            print("   - Missing X-APPLE-STRUCTURED-LOCATION or geo: data")
        if not has_apple_title:
            print("   - Missing X-TITLE parameter")

    # Clean up
    if test_output.exists():
        print(f"\n🧹 Test file created at: {test_output.absolute()}")
        print("   (You can delete it manually or inspect it)")


if __name__ == "__main__":
    test_geo_write()
