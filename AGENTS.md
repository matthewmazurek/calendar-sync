# Agent Development Guide

This document provides coding agents with essential information about the calendar-sync codebase, including build commands, code style guidelines, and project conventions.

## Project Overview

Calendar-sync is a Python 3.10+ application for syncing calendar data from Word documents. It supports multiple input formats (Word/DOCX, ICS, JSON) and outputs calendars as ICS or JSON files. The project uses Flask for the web API and Poetry for dependency management.

## Build & Development Commands

### Installation
```bash
poetry install
```

### Running Tests
```bash
# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/test_processing.py

# Run a specific test function
poetry run pytest tests/test_processing.py::test_source_revised_at_extraction

# Run with verbose output
poetry run pytest -v

# Run with specific markers (if defined)
poetry run pytest -k "pattern"
```

### Running the Application

**CLI Tool:**
```bash
# Via poetry script
calsync [command]

# Via poetry run
poetry run calendar-sync [command]

# Direct invocation
poetry run python cli.py [command]
```

**Flask API:**
```bash
# Development server (use port 5001 to avoid macOS AirPlay conflict)
poetry run flask --app app run --port 5001

# Alternative
poetry run python -m flask --app app run --port 5001
```

### Linting & Formatting

No linters/formatters are currently configured in pyproject.toml. If adding linting:
- Consider: black (formatting), ruff (linting), mypy (type checking)
- Keep configuration in pyproject.toml for consistency

## Code Style Guidelines

### Import Organization

Follow this import order (separated by blank lines):

1. Standard library imports
2. Third-party library imports  
3. Local application imports (using absolute imports starting with `app.` or `cli.`)

**Example:**
```python
import logging
import os
from datetime import date, time
from pathlib import Path

from pydantic import BaseModel, Field
import typer

from app.exceptions import CalendarError, IngestionError
from app.models.calendar import Calendar
from app.models.event import Event
```

**Import conventions:**
- Use absolute imports: `from app.models.event import Event` (NOT relative imports like `from .event import Event` at module level)
- Import specific classes/functions rather than entire modules when practical
- Group related imports: `from app.exceptions import CalendarError, IngestionError`
- Keep imports alphabetically sorted within each group

### File Structure

**Module docstrings:**
- Every Python file should start with a docstring describing its purpose
- Use triple-quoted strings: `"""Description."""`

**Example:**
```python
"""Event model with Pydantic v2 validation."""

from datetime import date
# ... rest of file
```

### Type Hints

- Use type hints for all function parameters and return values
- Use `X | None` syntax for nullable values (Python 3.10+)
- Use modern syntax: `list[str]`, `dict[str, int]`, `tuple[float, float]`
- Avoid importing from `typing` unless needed for complex types like `Literal`

**Example:**
```python
def load_calendar(
    self, name: str, format: str = "ics"
) -> CalendarWithMetadata | None:
    """Load calendar by name."""
    pass
```

### Naming Conventions

- **Classes**: PascalCase (`CalendarProcessor`, `EventType`)
- **Functions/methods**: snake_case (`process_events`, `get_calendar`)
- **Variables**: snake_case (`calendar_name`, `event_type`)
- **Constants**: UPPER_SNAKE_CASE (`CALENDAR_EXTENSIONS`, `METADATA_FILENAME`)
- **Private methods**: prefix with underscore (`_get_calendar_dir`)
- **Enum members**: UPPER_SNAKE_CASE (`EventType.ON_CALL`)

### Docstrings

Use Google-style docstrings for functions and classes:

```python
def compose_calendar_with_source(
    self,
    calendar_name: str,
    source_calendar: Calendar,
    year: int,
    repository: CalendarRepository,
    template: CalendarTemplate | None = None,
) -> tuple[CalendarWithMetadata, dict]:
    """Compose existing calendar with new source data for a specific year.
    
    Args:
        calendar_name: Name of the calendar to update
        source_calendar: New calendar data to merge
        year: Year to replace in existing calendar
        repository: Calendar repository instance
        template: Optional template configuration
    
    Returns:
        Tuple of (processed_calendar_with_metadata, summary_dict)
    
    Raises:
        CalendarNotFoundError: If calendar doesn't exist
        InvalidYearError: If year validation fails
    """
```

### Error Handling

**Custom exceptions:**
- Use the exception hierarchy defined in `app/exceptions.py`
- All exceptions inherit from `CalendarError` base class
- Key exceptions: `CalendarNotFoundError`, `IngestionError`, `InvalidYearError`, `UnsupportedFormatError`, `GitError`

**Exception handling patterns:**
```python
from app.exceptions import CalendarNotFoundError, IngestionError

try:
    calendar = repository.load_calendar(name)
except CalendarNotFoundError as e:
    logger.error(f"Calendar not found: {e}")
    raise typer.Exit(1)
except IngestionError as e:
    logger.error(f"Failed to read calendar file: {e}")
    raise typer.Exit(1)
```

**Logging:**
- Use the `logging` module, not print statements
- Get logger: `logger = logging.getLogger(__name__)`
- Log levels: `logger.info()`, `logger.error()`, `logger.warning()`, `logger.debug()`

### Pydantic Models

Use Pydantic v2 for data validation:

```python
from pydantic import BaseModel, Field, field_validator, model_validator

class Event(BaseModel):
    """Event model with validation and computed fields."""
    
    title: str
    date: date
    start: time | None = None
    location: str | None = None
    
    @field_validator("start", mode="before")
    @classmethod
    def convert_time_string(cls, v):
        """Convert HHMM string to time object."""
        # validation logic
        
    @model_validator(mode="after")
    def validate_dates(self):
        """Validate date consistency."""
        # validation logic
        return self
```

**Key patterns:**
- Use `X | None` with `= None` for optional fields
- Use `Field()` for advanced configuration: `Field(default=..., alias="...")`
- Validators: `@field_validator` for individual fields, `@model_validator` for cross-field validation
- Config class for JSON encoders (if needed)

### Dependency Injection

The codebase uses dependency injection for major components:

```python
class CalendarRepository:
    """Repository for managing named calendars with dependency injection."""
    
    def __init__(
        self,
        calendar_dir: Path,
        storage: CalendarStorage,
        git_service: GitService,
        reader_registry: ReaderRegistry,
    ):
        self.calendar_dir = calendar_dir
        self.storage = storage
        self.git_service = git_service
        self.reader_registry = reader_registry
```

## Testing Guidelines

- Test files: `tests/test_*.py`
- Test functions: `test_*`
- Use pytest fixtures (see `tests/conftest.py`)
- Import test utilities: `import pytest`
- Use descriptive test names: `test_source_revised_at_extraction()`, `test_overnight_event_detection()`

## File Paths

- Use `pathlib.Path` for file paths, not string concatenation
- Expand user paths: `Path(path).expanduser()`
- Check existence: `path.exists()`
- Directory operations: `path.mkdir(parents=True, exist_ok=True)`

## Configuration

- Configuration class: `app.config.CalendarConfig`
- Load from environment: `CalendarConfig.from_env()`
- Uses Pydantic for validation
- Environment variables: `CALENDAR_FORMAT`, `CALENDAR_DIR`, `CALENDAR_GIT_REMOTE_URL`, `DEFAULT_TEMPLATE`
- `.env` file support via `python-dotenv`

## Git Ignore

Standard Python ignores plus:
- `__pycache__/`, `*.py[oc]`, `*.egg-info`
- `/data/calendars/` (has its own git repo)
- `logs/`, `*.log`
- `.venv`

## Key Architecture Patterns

1. **Reader Registry**: Factory pattern for file format readers (ICS, JSON, DOCX)
2. **Template System**: Configurable event processing via JSON templates in `app/processing/configurable_processor.py`
3. **Repository Pattern**: Abstraction over calendar storage with metadata
4. **Git Integration**: Versioned calendar storage with git operations
5. **CLIContext**: Lazy-loaded dependency injection for CLI commands via `cli/context.py`

## Common Tasks

**Adding a new calendar format:**
1. Create reader class in `app/ingestion/` implementing `CalendarReader` protocol
2. Register in `setup_reader_registry()` in `app/__init__.py`

**Modifying event processing:**
1. Update template rules in JSON template files (`data/templates/`)
2. For new processing logic, extend `ConfigurableEventProcessor` in `app/processing/configurable_processor.py`

**Adding CLI command:**
1. Create command function in `cli/commands/`
2. Use `get_context()` from `cli.context` for dependencies (repository, git_service, config)
3. Register in `cli/parser.py`

## Utilities

- **Temp file handling**: Use `temp_file_path()` context manager from `app/utils.py` for automatic cleanup
