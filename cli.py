#!/usr/bin/env python3

import argparse
from datetime import datetime
from pathlib import Path

from app.calendar_generator import generate_ical
from app.calendar_parser import parse_word_events
from app.event_processor import process_events


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Word document containing a calendar into an ICS file."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the input Word document (.doc or .docx)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="calendar.ics",
        help="Path for the output ICS file (default: calendar.ics)",
    )
    parser.add_argument(
        "--from-today",
        action="store_true",
        help="Filter out events before today",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        help="Filter out events before this date (YYYY-MM-DD format)",
    )

    args = parser.parse_args()

    # check if input file exists
    if not Path(args.input_file).exists():
        parser.error(f"Input file {args.input_file} does not exist")

    # Parse the input file
    events = parse_word_events(args.input_file)

    # Apply date filtering if requested
    if args.from_today:
        today = datetime.now().date()
        events = [
            e
            for e in events
            if datetime.strptime(e["date"], "%Y-%m-%d").date() >= today
        ]
    elif args.from_date:
        try:
            filter_date = datetime.strptime(args.from_date, "%Y-%m-%d").date()
            events = [
                e
                for e in events
                if datetime.strptime(e["date"], "%Y-%m-%d").date() >= filter_date
            ]
        except ValueError:
            parser.error("Invalid date format. Use YYYY-MM-DD")

    # Process events
    events = process_events(events)

    # Generate the calendar
    cal = generate_ical(events)

    # Write to file
    output_path = Path(args.output)
    output_path.write_bytes(cal.to_ical())
    print(f"Calendar written to {output_path}")


if __name__ == "__main__":
    main()
