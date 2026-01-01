#!/usr/bin/env python3

import argparse
import json
from datetime import datetime

from app.calendar_parser import parse_cell_events


def test_event_parsing(event_text: str, day: int | None = None, month: int | None = None, year: int | None = None):
    """
    Test event parsing with a given event text string.
    
    Args:
        event_text: The event text to parse (e.g., "Clinic 0800-1200, Endo 1230-1630")
        month: Month number (1-12)
        year: Year (e.g., 2025)
    
    Returns:
        List of parsed event dictionaries
    """

    # If day, month, or year is not provided, use the current date
    current_date = datetime.now()
    if day is None:
        day = current_date.day
    if month is None:
        month = current_date.month
    if year is None:
        year = current_date.year

    # Format the cell text as if it came from a calendar cell
    # The first line should be the day number
    cell_text = f"{day}\n{event_text}"
    
    # Parse the events
    events = parse_cell_events(cell_text, month, year)
    
    return events

def main():
    parser = argparse.ArgumentParser(
        description="Test calendar event parsing with different event strings"
    )
    parser.add_argument(
        "event_text",
        type=str,
        help="Event text to parse (e.g., 'Clinic 0800-1200, Endo 1230-1630')"
    )
    parser.add_argument(
        "--month",
        type=int,
        default=1,
        help="Month number (1-12, default: 1)"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Year (default: 2025)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed parsing information"
    )

    args = parser.parse_args()

    try:
        # Test the event parsing
        events = test_event_parsing(args.event_text, args.month, args.year)
        
        if args.verbose:
            print(f"Input text: {args.event_text}")
            print(f"Month: {args.month}, Year: {args.year}")
            print(f"Parsed {len(events)} events:")
            print("-" * 50)
        
        if args.json:
            # Output in JSON format
            print(json.dumps(events, indent=2))
        else:
            # Output in human-readable format
            if not events:
                print("No events parsed from the input text.")
            else:
                for i, event in enumerate(events, 1):
                    print(f"Event {i}:")
                    print(f"  Title: {event.get('title', 'N/A')}")
                    print(f"  Date: {event.get('date', 'N/A')}")
                    if 'start' in event and 'end' in event:
                        print(f"  Time: {event['start']}-{event['end']}")
                        print(f"  Type: Timed event")
                    else:
                        print(f"  Type: All-day event")
                    if 'location' in event:
                        print(f"  Location: {event['location']}")
                    print()
        
        # Return exit code based on whether events were parsed
        return 0 if events else 1
        
    except Exception as e:
        print(f"Error parsing events: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main()) 