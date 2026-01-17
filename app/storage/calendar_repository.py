"""Calendar repository for managing named calendars."""

import json
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

    # Canonical storage format is JSON (calendar_data.json)
    CANONICAL_FILENAME = "calendar_data.json"
    # ICS is export-only format
    ICS_EXPORT_FILENAME = "calendar.ics"

    def __init__(
        self,
        calendar_dir: Path,
        storage: CalendarStorage,
        git_service: GitService,
        reader_registry: ReaderRegistry,
    ):
        """
        Initialize repository.

        Args:
            calendar_dir: Base directory for calendars
            storage: CalendarStorage instance (dependency injection)
            git_service: GitService instance (dependency injection)
            reader_registry: ReaderRegistry instance (for ingesting source files)
        """
        self.calendar_dir = calendar_dir
        self.storage = storage
        self.git_service = git_service
        self.reader_registry = reader_registry

    def _get_calendar_dir(self, name: str) -> Path:
        """Get directory for named calendar."""
        return self.calendar_dir / name

    def _get_canonical_path(self, name: str) -> Path:
        """Get path to canonical JSON storage file."""
        return self._get_calendar_dir(name) / self.CANONICAL_FILENAME

    def _get_ics_export_path(self, name: str) -> Path:
        """Get path to ICS export file."""
        return self._get_calendar_dir(name) / self.ICS_EXPORT_FILENAME

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

        # Fall back to legacy ICS format for migration
        legacy_ics_path = self._get_ics_export_path(name)
        if legacy_ics_path.exists():
            # Load from legacy ICS using reader
            reader = self.reader_registry.get_reader(legacy_ics_path)
            ingestion_result = reader.read(legacy_ics_path)
            calendar = ingestion_result.calendar

            # Load or create metadata
            metadata = self._load_legacy_metadata(name)
            if metadata is None:
                metadata = CalendarMetadata(
                    name=name,
                    created=datetime.now(),
                    last_updated=datetime.now(),
                )

            return CalendarWithMetadata(calendar=calendar, metadata=metadata)

        return None

    def _load_legacy_metadata(self, name: str) -> CalendarMetadata | None:
        """Load metadata from legacy metadata.json file, ignoring 'format' field."""
        metadata_path = self._get_calendar_dir(name) / "metadata.json"
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Remove 'format' field if present (legacy)
            data.pop("format", None)
            return CalendarMetadata(**data)
        except (OSError, ValueError, KeyError):
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
        # Try canonical JSON first
        canonical_path = self._get_canonical_path(name)
        content = self.git_service.get_file_at_commit(canonical_path, commit)

        if content is not None:
            # Load from canonical JSON
            return CalendarWithMetadata.model_validate_json(content.decode("utf-8"))

        # Fall back to legacy ICS format
        legacy_path = self._get_ics_export_path(name)
        content = self.git_service.get_file_at_commit(legacy_path, commit)
        if content is None:
            return None

        # Write to temp file for reading legacy ICS
        from app.utils import temp_file_path

        with temp_file_path(suffix=".ics") as tmp_path:
            tmp_path.write_bytes(content)

            # Load calendar using ICS reader
            reader = self.reader_registry.get_reader(tmp_path)
            ingestion_result = reader.read(tmp_path)
            calendar = ingestion_result.calendar

            # Load metadata (use current metadata)
            metadata = self._load_legacy_metadata(name)
            if metadata is None:
                metadata = CalendarMetadata(
                    name=name,
                    created=datetime.now(),
                    last_updated=datetime.now(),
                )

            return CalendarWithMetadata(calendar=calendar, metadata=metadata)

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
        if canonical_path.exists():
            try:
                calendar_with_metadata = CalendarWithMetadata.load(canonical_path)
                return calendar_with_metadata.metadata
            except (OSError, ValueError):
                pass

        # Fall back to legacy metadata.json
        return self._load_legacy_metadata(name)

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
        The format parameter is kept for backwards compatibility but we check canonical JSON first.

        Returns:
            List of (commit_hash, commit_date, commit_message) tuples
        """
        # Try canonical JSON first
        canonical_path = self._get_canonical_path(name)
        versions = self.git_service.get_file_versions(canonical_path)
        if versions:
            return versions

        # Fall back to legacy ICS
        legacy_path = self._get_ics_export_path(name)
        return self.git_service.get_file_versions(legacy_path)

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
