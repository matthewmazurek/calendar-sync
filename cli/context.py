"""Shared CLI context with lazy-initialized dependencies."""

from app import setup_reader_registry
from app.config import CalendarConfig
from app.ingestion.base import ReaderRegistry
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService


class CLIContext:
    """Shared context with lazy-initialized dependencies for CLI commands.

    This eliminates the need for each command to manually create config, storage,
    reader_registry, git_service, and repository objects.

    Usage:
        ctx = CLIContext()
        calendars = ctx.repository.list_calendars()
    """

    def __init__(self, verbose: bool = False, quiet: bool = False):
        """Initialize CLI context.

        Args:
            verbose: If True, enable debug logging
            quiet: If True, suppress non-error output
        """
        self.verbose = verbose
        self.quiet = quiet

        # Lazy-loaded dependencies
        self._config: CalendarConfig | None = None
        self._storage: CalendarStorage | None = None
        self._reader_registry: ReaderRegistry | None = None
        self._git_service: GitService | None = None
        self._repository: CalendarRepository | None = None

    @property
    def config(self) -> CalendarConfig:
        """Get configuration (lazy-loaded)."""
        if self._config is None:
            self._config = CalendarConfig.from_env()
        return self._config

    @property
    def storage(self) -> CalendarStorage:
        """Get calendar storage (lazy-loaded)."""
        if self._storage is None:
            self._storage = CalendarStorage(self.config)
        return self._storage

    @property
    def reader_registry(self) -> ReaderRegistry:
        """Get reader registry with all readers registered (lazy-loaded)."""
        if self._reader_registry is None:
            self._reader_registry = setup_reader_registry()
        return self._reader_registry

    @property
    def git_service(self) -> GitService:
        """Get git service (lazy-loaded)."""
        if self._git_service is None:
            self._git_service = GitService(
                self.config.calendar_dir,
                remote_url=self.config.calendar_git_remote_url,
                canonical_filename=self.config.canonical_filename,
                export_pattern=self.config.export_pattern,
                default_remote=self.config.git_default_remote,
                default_branch=self.config.git_default_branch,
            )
        return self._git_service

    @property
    def repository(self) -> CalendarRepository:
        """Get calendar repository (lazy-loaded)."""
        if self._repository is None:
            self._repository = CalendarRepository(
                self.config.calendar_dir,
                self.storage,
                self.git_service,
                self.reader_registry,
                canonical_filename=self.config.canonical_filename,
                export_pattern=self.config.export_pattern,
            )
        return self._repository


# Global context instance (set by Typer callback)
_ctx: CLIContext | None = None


def get_context() -> CLIContext:
    """Get the current CLI context.

    Returns:
        The global CLI context instance

    Raises:
        RuntimeError: If context not initialized
    """
    if _ctx is None:
        raise RuntimeError("CLI context not initialized. This should not happen.")
    return _ctx


def set_context(ctx: CLIContext) -> None:
    """Set the global CLI context.

    Args:
        ctx: The CLI context instance to set
    """
    global _ctx
    _ctx = ctx
