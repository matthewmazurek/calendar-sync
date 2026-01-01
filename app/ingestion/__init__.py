"""Ingestion layer for calendar files."""

from app.ingestion.base import CalendarReader, ReaderRegistry
from app.ingestion.ics_reader import ICSReader
from app.ingestion.json_reader import JSONReader
from app.ingestion.word_reader import WordReader

__all__ = [
    "CalendarReader",
    "ReaderRegistry",
    "WordReader",
    "ICSReader",
    "JSONReader",
]
