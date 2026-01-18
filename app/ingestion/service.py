"""Ingestion service for reading calendar source files."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.exceptions import IngestionError, InvalidYearError, UnsupportedFormatError
from app.models.ingestion import IngestionResult

if TYPE_CHECKING:
    from app.ingestion.base import ReaderRegistry
    from app.models.template import CalendarTemplate

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting calendar source files."""

    def __init__(self, reader_registry: "ReaderRegistry"):
        """
        Initialize ingestion service.

        Args:
            reader_registry: Registry for getting appropriate reader by file type
        """
        self.registry = reader_registry

    def ingest(
        self,
        path: Path,
        template: "CalendarTemplate | None" = None,
    ) -> IngestionResult:
        """
        Read and parse a calendar source file.

        Args:
            path: Path to input file (DOCX, ICS, or JSON)
            template: Template to use for WordReader (required for Word files)

        Returns:
            IngestionResult with calendar and summary

        Raises:
            FileNotFoundError: If input file doesn't exist
            UnsupportedFormatError: If file format is not supported
            IngestionError: On file reading errors
            InvalidYearError: On year validation errors
        """
        input_path = Path(path).expanduser().resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        # Get appropriate reader
        reader = self.registry.get_reader(input_path)
        reader_name = reader.__class__.__name__
        logger.info(
            f"Reading calendar file: {input_path} (format: {input_path.suffix}, reader: {reader_name})"
        )

        # Read source file - WordReader requires template
        from app.ingestion.word_reader import WordReader

        if isinstance(reader, WordReader):
            ingestion_result = reader.read(input_path, template)
        else:
            ingestion_result = reader.read(input_path)

        logger.info(
            f"Ingested {len(ingestion_result.raw.events)} events from {input_path}"
        )

        return ingestion_result
