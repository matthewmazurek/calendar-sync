"""Word document reader for calendar files."""

import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import List

from docx import Document

from app.exceptions import IngestionError, InvalidYearError
from app.models.calendar import Calendar
from app.models.event import Event

logger = logging.getLogger(__name__)

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


def extract_year_from_header(header: str) -> int | None:
    """Extract the year from a month header (e.g., "JANUARY 2025")."""
    parts = header.split()
    if len(parts) < 2 or parts[0] not in MONTH_MAP:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def extract_revised_date(doc: Document) -> date | None:
    """Extract revised date from document header.
    
    Looks for pattern like "Revised December 16, 2025" in headers or paragraphs.
    """
    # Pattern: "Revised December 16, 2025" (matches format in header)
    pattern = r"Revised\s+([A-Za-z]+)\s+(\d+),?\s+(\d{4})"
    
    # Check headers first (most common location)
    for section in doc.sections:
        if section.header:
            for para in section.header.paragraphs:
                text = para.text
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    month_name = match.group(1).upper()
                    day = int(match.group(2))
                    year = int(match.group(3))
                    if month_name in MONTH_MAP:
                        try:
                            revised_date = datetime(year, MONTH_MAP[month_name], day).date()
                            logger.info(f"Extracted revised date from header: {revised_date}")
                            return revised_date
                        except ValueError:
                            pass
    
    # Fallback: check paragraphs
    for para in doc.paragraphs:
        text = para.text
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            month_name = match.group(1).upper()
            day = int(match.group(2))
            year = int(match.group(3))
            if month_name in MONTH_MAP:
                try:
                    revised_date = datetime(year, MONTH_MAP[month_name], day).date()
                    logger.info(f"Extracted revised date from paragraph: {revised_date}")
                    return revised_date
                except ValueError:
                    pass
    
    logger.debug("No revised date found in document")
    return None


def parse_cell_events(cell_text: str, month: int, year: int) -> List[dict]:
    """Parse events from a calendar cell."""
    events = []
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
            # If there's a time range like "Endo 1230-1630" or "Clinic 1230-1630 with Carmen"
            m_time = re.match(r"(.+?)\s+(\d{4})-(\d{4})(?:\s+(.+))?", ev)
            if m_time:
                title = m_time.group(1).strip()
                start = m_time.group(2)
                end = m_time.group(3)
                additional_text = m_time.group(4) if m_time.group(4) else ""

                full_title = title
                if additional_text:
                    full_title = f"{title} ({additional_text.strip()})"

                events.append(
                    {"title": full_title, "start": start, "end": end, "date": date_str}
                )
            else:
                # All-day or untimed event
                events.append({"title": ev, "date": date_str})

    return events


def normalize_to_docx(path: str | Path) -> str:
    """Convert .doc to .docx if needed."""
    path = str(path)
    root, ext = os.path.splitext(path)
    if ext.lower() == ".doc":
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_doc = os.path.join(temp_dir, os.path.basename(path))
            shutil.copy2(path, temp_doc)

            subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    "docx",
                    "--outdir",
                    temp_dir,
                    temp_doc,
                ],
                check=True,
            )

            temp_docx = os.path.splitext(temp_doc)[0] + ".docx"

            with tempfile.NamedTemporaryFile(
                suffix=".docx", delete=False
            ) as final_docx:
                shutil.copy2(temp_docx, final_docx.name)
                return final_docx.name
    elif ext.lower() == ".docx":
        return path
    else:
        raise ValueError(f"Unsupported extension: {ext}")


class WordReader:
    """Reader for Word document calendar files."""

    def read(self, path: Path) -> Calendar:
        """Read calendar from Word document."""
        try:
            docx_path = normalize_to_docx(path)
            try:
                return self._read_docx(docx_path)
            finally:
                # Clean up temporary docx file if it was created
                if docx_path != str(path):
                    try:
                        os.unlink(docx_path)
                    except OSError:
                        pass
        except Exception as e:
            raise IngestionError(f"Failed to read Word document: {e}") from e

    def _read_docx(self, docx_path: str) -> Calendar:
        """Read calendar from .docx file."""
        logger.info(f"Reading Word document: {docx_path}")
        doc = Document(str(docx_path))
        events = []

        # Extract revised date
        revised_date = extract_revised_date(doc)
        if revised_date:
            logger.info(f"Extracted revised date from Word document: {revised_date}")
        else:
            logger.debug("No revised date found in Word document")

        # Single big table: 12 months × 8 rows per month
        if not doc.tables:
            raise IngestionError("Document contains no tables")

        table = doc.tables[0]

        # Extract year from the first month's header
        first_header = table.rows[0].cells[0].text.strip().upper()
        year = extract_year_from_header(first_header)
        if year is None:
            raise IngestionError("Could not determine year from document")

        logger.info(f"Extracted year: {year}")

        cutoff_date = datetime(year, 12, 31)

        for month_idx in range(12):
            start_row = month_idx * 8
            if start_row >= len(table.rows):
                continue

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
            e
            for e in events
            if datetime.strptime(e["date"], "%Y-%m-%d") <= cutoff_date
        ]

        # Remove misattributed New Year's Day on Dec 1
        events = [
            e
            for e in events
            if not (
                e["title"].lower().startswith("new year")
                and e["date"] == f"{year}-12-01"
            )
        ]

        # Convert to Pydantic Event models
        event_models = []
        for event_dict in events:
            try:
                event_models.append(Event(**event_dict))
            except Exception as e:
                raise IngestionError(
                    f"Failed to create event from {event_dict}: {e}"
                ) from e
        
        logger.info(f"Created {len(event_models)} event models from Word document")

        # Validate single year
        years = {event.date.year for event in event_models}
        if len(years) > 1:
            raise InvalidYearError(
                f"Word document contains events from multiple years: {years}. "
                "Word documents must contain events from a single year."
            )

        return Calendar(events=event_models, revised_date=revised_date, year=year)
