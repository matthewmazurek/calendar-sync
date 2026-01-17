"""Calendar repository for managing named calendars."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.exceptions import CalendarNotFoundError
from app.ingestion.base import ReaderRegistry
from app.models.calendar import Calendar
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.output.ics_writer import ICSWriter
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService

if TYPE_CHECKING:
    from app.models.template import CalendarTemplate


class CalendarRepository:
    """Repository for managing named calendars with dependency injection."""

    def __init__(
        self,
        calendar_dir: Path,
        storage: CalendarStorage,
        git_service: GitService,
        reader_registry: ReaderRegistry,
        canonical_filename: str = "calendar_data.json",
        ics_export_filename: str = "calendar.ics",
    ):
        """
        Initialize repository.

        Args:
            calendar_dir: Base directory for calendars
            storage: CalendarStorage instance (dependency injection)
            git_service: GitService instance (dependency injection)
            reader_registry: ReaderRegistry instance (for ingesting source files)
            canonical_filename: Filename for canonical JSON storage
            ics_export_filename: Filename for ICS export
        """
        self.calendar_dir = calendar_dir
        self.storage = storage
        self.git_service = git_service
        self.reader_registry = reader_registry
        self.canonical_filename = canonical_filename
        self.ics_export_filename = ics_export_filename

    def _get_calendar_dir(self, name: str) -> Path:
        """Get directory for named calendar."""
        return self.calendar_dir / name

    def _get_canonical_path(self, name: str) -> Path:
        """Get path to canonical JSON storage file."""
        return self._get_calendar_dir(name) / self.canonical_filename

    def _get_ics_export_path(self, name: str) -> Path:
        """Get path to ICS export file."""
        return self._get_calendar_dir(name) / self.ics_export_filename

    def _get_calendar_file_path(self, name: str, format: str = "ics") -> Path:
        """Get path to calendar file (for backwards compatibility)."""
        calendar_dir = self._get_calendar_dir(name)
        return calendar_dir / f"calendar.{format}"

    def load_calendar(self, name: str, format: str = "ics") -> CalendarWithMetadata | None:
        """
        Load calendar by name from canonical JSON storage.

        The format parameter is kept for backwards compatibility but ignored.
        Calendars are always loaded from the canonical JSON format.
        """
        calendar_dir = self._get_calendar_dir(name)
        if not calendar_dir.exists():
            return None

        canonical_path = self._get_canonical_path(name)

        # Try loading from canonical JSON first
        if canonical_path.exists():
            return CalendarWithMetadata.load(canonical_path)

        return None

    def load_calendar_by_commit(
        self, name: str, commit: str, format: str = "ics"
    ) -> CalendarWithMetadata | None:
        """
        Load calendar from specific git commit.

        Args:
            name: Calendar name
            commit: Git commit hash or tag
            format: Ignored (kept for backwards compatibility)

        Returns:
            CalendarWithMetadata or None if not found
        """
        canonical_path = self._get_canonical_path(name)
        content = self.git_service.get_file_at_commit(canonical_path, commit)

        if content is None:
            return None

        return CalendarWithMetadata.model_validate_json(content.decode("utf-8"))

    def save_json(
        self, calendar: Calendar, metadata: CalendarMetadata
    ) -> Path:
        """
        Save calendar to canonical JSON format only (no ICS export, no commit).

        This is used by the ingest command. For full save with export and commit,
        use save_calendar().

        Args:
            calendar: Calendar to save
            metadata: Calendar metadata

        Returns:
            Path to canonical JSON file
        """
        calendar_dir = self._get_calendar_dir(metadata.name)
        calendar_dir.mkdir(parents=True, exist_ok=True)

        # Update metadata timestamp
        metadata.last_updated = datetime.now()

        # Create combined object
        calendar_with_metadata = CalendarWithMetadata(
            calendar=calendar, metadata=metadata
        )

        # Save to canonical JSON format
        canonical_path = self._get_canonical_path(metadata.name)
        calendar_with_metadata.save(canonical_path)

        return canonical_path

    def save_calendar(
        self,
        calendar: Calendar,
        metadata: CalendarMetadata,
        writer=None,
        template: "CalendarTemplate | None" = None,
    ) -> Path:
        """
        Save calendar to canonical JSON format and export to ICS.

        This is the main save method that:
        1. Saves to canonical JSON format
        2. Exports to ICS for subscriptions (with template resolution)
        3. Commits locally for versioning

        Args:
            calendar: Calendar to save
            metadata: Calendar metadata
            writer: Deprecated, ignored (kept for backwards compatibility)
            template: Optional template for resolving location_id references

        Returns:
            Path to ICS export file (for subscription URLs)
        """
        # Save JSON first
        self.save_json(calendar, metadata)

        # Export to ICS for calendar subscriptions
        calendar_with_metadata = CalendarWithMetadata(
            calendar=calendar, metadata=metadata
        )
        ics_path = self._get_ics_export_path(metadata.name)
        ics_writer = ICSWriter()
        ics_writer.write(calendar_with_metadata, ics_path, template=template)

        # Commit locally for versioning (always commit, even without --publish)
        self.git_service.commit_calendar_locally(metadata.name)

        # Return ICS path (used for subscription URLs)
        return ics_path

    def export_ics(
        self,
        name: str,
        template: "CalendarTemplate | None" = None,
    ) -> Path:
        """
        Export calendar to ICS format with template resolution.

        Loads the calendar from JSON and exports to ICS, resolving any
        location_id references using the provided template.

        Args:
            name: Calendar name
            template: Optional template for resolving location_id references

        Returns:
            Path to ICS export file

        Raises:
            CalendarNotFoundError: If calendar not found
            ExportError: If location_id references cannot be resolved
        """
        calendar_with_metadata = self.load_calendar(name)
        if calendar_with_metadata is None:
            raise CalendarNotFoundError(f"Calendar '{name}' not found")

        ics_path = self._get_ics_export_path(name)
        ics_writer = ICSWriter()
        ics_writer.write(calendar_with_metadata, ics_path, template=template)

        return ics_path

    def load_metadata(self, name: str) -> CalendarMetadata | None:
        """Load metadata from canonical JSON file."""
        canonical_path = self._get_canonical_path(name)
        if not canonical_path.exists():
            return None

        try:
            calendar_with_metadata = CalendarWithMetadata.load(canonical_path)
            return calendar_with_metadata.metadata
        except (OSError, ValueError):
            return None

    def list_calendars(self, include_deleted: bool = False) -> list[str]:
        """
        List all available calendar names.

        Args:
            include_deleted: If True, also include calendars that exist in git history
                           but have been deleted from the filesystem

        Returns:
            List of calendar names
        """
        calendars = set()

        # Get calendars from filesystem (existing directories)
        if self.calendar_dir.exists():
            for d in self.calendar_dir.iterdir():
                if d.is_dir() and not d.name.startswith("."):
                    calendars.add(d.name)

        # If including deleted, check git history for calendar files
        if include_deleted:
            try:
                # Get all calendar files that ever existed in git history
                # Use --all to check all branches, and --name-only to get file paths
                result = self.git_service.git_client.run_command(
                    [
                        "git",
                        "log",
                        "--all",
                        "--pretty=format:",
                        "--name-only",
                        "--",
                        ".",
                    ],
                    self.git_service.repo_root,
                )

                # Extract calendar names from paths like "name/calendar.ics" (relative to calendar_dir)
                all_files = set(result.stdout.splitlines())
                for file_path in all_files:
                    if not file_path.strip():
                        continue
                    # Look for paths containing "/calendar."
                    if "/calendar." in file_path:
                        # Path is relative to calendar_dir, so split on first /
                        parts = file_path.split("/", 1)
                        if len(parts) >= 1:
                            calendar_name = parts[0]
                            if calendar_name and not calendar_name.startswith("."):
                                calendars.add(calendar_name)
            except (OSError, ValueError):
                # If git operations fail, just return filesystem calendars
                pass

        return sorted(calendars)

    def list_calendar_versions(
        self, name: str, format: str = "ics"
    ) -> list[tuple[str, datetime, str]]:
        """
        List all versions from git log.

        Works even if the file doesn't exist in the working directory (checks git history).
        The format parameter is kept for backwards compatibility.

        Returns:
            List of (commit_hash, commit_date, commit_message) tuples
        """
        canonical_path = self._get_canonical_path(name)
        return self.git_service.get_file_versions(canonical_path)

    def delete_calendar(self, name: str) -> None:
        """Delete calendar directory and all contents."""
        calendar_dir = self._get_calendar_dir(name)
        if calendar_dir.exists():
            import shutil

            shutil.rmtree(calendar_dir)

    def get_calendar_path(self, name: str, format: str = "ics") -> Path | None:
        """
        Get path to calendar export file (ICS).

        The format parameter is kept for backwards compatibility but always returns ICS path.
        Returns path to calendar.ics file.
        """
        ics_path = self._get_ics_export_path(name)
        if ics_path.exists():
            return ics_path
        return None

    def get_canonical_path(self, name: str) -> Path | None:
        """
        Get path to canonical JSON storage file.

        Returns path to calendar_data.json file or None if not exists.
        """
        canonical_path = self._get_canonical_path(name)
        if canonical_path.exists():
            return canonical_path
        return None
