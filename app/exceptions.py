"""Exception hierarchy for calendar operations."""


class CalendarError(Exception):
    """Base exception for calendar operations."""

    pass


class CalendarNotFoundError(CalendarError):
    """Calendar not found."""

    pass


class UnsupportedFormatError(CalendarError):
    """File format not supported."""

    pass


class ValidationError(CalendarError):
    """Pydantic validation error."""

    pass


class InvalidYearError(CalendarError):
    """Year validation error (e.g., multi-year calendar when single year required)."""

    pass


class IngestionError(CalendarError):
    """Error during calendar ingestion."""

    pass
