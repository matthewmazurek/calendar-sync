"""Tests for exception classes."""

import pytest

from app.exceptions import (
    CalendarError,
    CalendarGitRepoNotFoundError,
    CalendarNotFoundError,
    IngestionError,
    InvalidYearError,
    UnsupportedFormatError,
    ValidationError,
)


def test_calendar_error():
    """Test CalendarError base exception."""
    error = CalendarError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_calendar_not_found_error():
    """Test CalendarNotFoundError."""
    error = CalendarNotFoundError("Calendar not found")
    assert str(error) == "Calendar not found"
    assert isinstance(error, CalendarError)


def test_calendar_git_repo_not_found_error():
    """Test CalendarGitRepoNotFoundError."""
    error = CalendarGitRepoNotFoundError("Git repo not found")
    assert str(error) == "Git repo not found"
    assert isinstance(error, CalendarError)


def test_unsupported_format_error():
    """Test UnsupportedFormatError."""
    error = UnsupportedFormatError("Format not supported")
    assert str(error) == "Format not supported"
    assert isinstance(error, CalendarError)


def test_validation_error():
    """Test ValidationError."""
    error = ValidationError("Validation failed")
    assert str(error) == "Validation failed"
    assert isinstance(error, CalendarError)


def test_invalid_year_error():
    """Test InvalidYearError."""
    error = InvalidYearError("Invalid year")
    assert str(error) == "Invalid year"
    assert isinstance(error, CalendarError)


def test_ingestion_error():
    """Test IngestionError."""
    error = IngestionError("Ingestion failed")
    assert str(error) == "Ingestion failed"
    assert isinstance(error, CalendarError)
