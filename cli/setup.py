"""CLI setup functions for readers and writers."""

from app.exceptions import UnsupportedFormatError
from app.ingestion.base import ReaderRegistry
from app.ingestion.ics_reader import ICSReader
from app.ingestion.json_reader import JSONReader
from app.ingestion.word_reader import WordReader
from app.output.ics_writer import ICSWriter
from app.output.json_writer import JSONWriter


def setup_reader_registry() -> ReaderRegistry:
    """Set up reader registry with all readers."""
    registry = ReaderRegistry()
    registry.register(WordReader(), [".doc", ".docx"])
    registry.register(ICSReader(), [".ics"])
    registry.register(JSONReader(), [".json"])
    return registry


def setup_writer(format: str):
    """Get writer for format."""
    if format == "ics":
        return ICSWriter()
    elif format == "json":
        return JSONWriter()
    else:
        raise UnsupportedFormatError(f"Unsupported output format: {format}")
