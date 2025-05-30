import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from docx import Document

# --- Configuration -----------------------------------------------------------

# Map month names (uppercase) to month numbers
MONTH_MAP = {
    "JANUARY": 1,
    "FEBRUARY": 2,
    "MARCH": 3,
    "APRIL": 4,
    "MAY": 5,
    "JUNE": 6,
    "JULY": 7,
    "AUGUST": 8,
    "SEPTEMBER": 9,
    "OCTOBER": 10,
    "NOVEMBER": 11,
    "DECEMBER": 12,
}

# --- Helper Functions --------------------------------------------------------


def extract_year_from_header(header: str) -> Optional[int]:
    """
    Extract the year from a month header (e.g., "JANUARY 2025").
    Returns None if the header is invalid.
    """
    parts = header.split()
    if len(parts) < 2 or parts[0] not in MONTH_MAP:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def parse_cell_events(cell_text: str, month: int, year: int) -> List[Dict]:
    """
    Given the raw text of a calendar cell and its month/year,
    return a list of event dicts from that cell.
    """
    events = []
    # Split lines, ignore blank
    lines = [ln.strip() for ln in cell_text.split("\n") if ln.strip()]
    if not lines:
        return events

    # First line may be "day [first event]" or just "day"
    m_day = re.match(r"^(\d+)\s*(.*)$", lines[0])
    if not m_day:
        return events
    day = int(m_day.group(1))
    first_ev = m_day.group(2).strip()

    # Special case: If we're in December and this is New Year's Day, it belongs to January
    if month == 12 and day == 1 and first_ev.lower().startswith("new year"):
        date_str = f"{year + 1}-01-01"
    else:
        date_str = f"{year}-{month:02d}-{day:02d}"

    # Collect all event lines
    ev_lines = []
    if first_ev:
        ev_lines.append(first_ev)
    ev_lines.extend(lines[1:])

    # For each event line, split on commas and parse times
    for ln in ev_lines:
        for part in ln.split(","):
            ev = part.strip()
            if not ev:
                continue
            # If there's a time range like "Endo 1230-1630"
            m_time = re.match(r"(.+?)\s+(\d{4})-(\d{4})$", ev)
            if m_time:
                title = m_time.group(1).strip()
                start = m_time.group(2)
                end = m_time.group(3)
                events.append(
                    {"title": title, "start": start, "end": end, "date": date_str}
                )
            else:
                # All-day or untimed event
                events.append({"title": ev, "date": date_str})

    return events


def normalize_to_docx(path: str | Path) -> str:
    """
    If path ends in .doc, run soffice --headless to convert to .docx
    Returns the path of the .docx file (or the original if already .docx).
    """
    path = str(path)
    root, ext = os.path.splitext(path)
    if ext.lower() == ".doc":
        # LibreOffice will produce root + '.docx' beside it
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                os.path.dirname(path),
                path,
            ],
            check=True,
        )
        return root + ".docx"
    elif ext.lower() == ".docx":
        return path
    else:
        raise ValueError(f"Unsupported extension: {ext}")


# --- Main Parsing Routine ----------------------------------------------------


def parse_word_events(word_path: str | Path) -> List[Dict]:
    """
    Parse a word file (.doc or .docx) containing a calendar into a list of events.
    """
    docx_path = normalize_to_docx(word_path)
    return parse_docx_events(docx_path)


def parse_docx_events(docx_path: str | Path) -> List[Dict]:
    """
    Parse a .docx file containing a calendar into a list of events.
    This is the main entry point that matches our existing interface.
    """
    doc = Document(str(docx_path))
    events = []

    # Single big table: 12 months × 8 rows per month
    table = doc.tables[0]

    # Extract year from the first month's header
    first_header = table.rows[0].cells[0].text.strip().upper()
    year = extract_year_from_header(first_header)
    if year is None:
        raise ValueError("Could not determine year from document")

    cutoff_date = datetime(year, 12, 31)

    for month_idx in range(12):
        # Each month block is 8 rows: header, weekdays, then 6 week rows
        start_row = month_idx * 8
        header = table.rows[start_row].cells[0].text.strip().upper()
        parts = header.split()
        if len(parts) < 2 or parts[0] not in MONTH_MAP or parts[1] != str(year):
            continue

        month = MONTH_MAP[parts[0]]

        # Iterate the 6 week rows
        for row in table.rows[start_row + 2 : start_row + 8]:
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    events.extend(parse_cell_events(cell_text, month, year))

    # Filter out any events after December 31 of the target year
    events = [
        e for e in events if datetime.strptime(e["date"], "%Y-%m-%d") <= cutoff_date
    ]

    # Remove misattributed New Year's Day on Dec 1
    events = [
        e
        for e in events
        if not (
            e["title"].lower().startswith("new year") and e["date"] == f"{year}-12-01"
        )
    ]

    return events
