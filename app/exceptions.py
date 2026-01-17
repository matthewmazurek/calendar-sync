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


class CalendarGitRepoNotFoundError(CalendarError):
    """Calendar git repository not found."""

    pass


class GitError(CalendarError):
    """Base exception for git operations."""

    pass


class GitRepositoryNotFoundError(GitError):
    """Git repository not found."""

    pass


class GitCommandError(GitError):
    """Git command execution error."""

    pass


class ExportError(CalendarError):
    """Error during calendar export."""

    pass
