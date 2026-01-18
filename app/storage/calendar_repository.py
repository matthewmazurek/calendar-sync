"""Calendar repository for managing named calendars."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.exceptions import CalendarNotFoundError
from app.ingestion.base import ReaderRegistry
from app.models.calendar import Calendar
from app.models.settings import CalendarSettings
from app.output.ics_writer import ICSWriter
from app.storage.calendar_paths import CalendarPaths
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
        canonical_filename: str = "data.json",
        settings_filename: str = "config.json",
        export_pattern: str = "calendar.{format}",
    ):
        """
        Initialize repository.

        Args:
            calendar_dir: Base directory for calendars
            storage: CalendarStorage instance (dependency injection)
            git_service: GitService instance (dependency injection)
            reader_registry: ReaderRegistry instance (for ingesting source files)
            canonical_filename: Filename for canonical JSON storage
            settings_filename: Filename for calendar settings
            export_pattern: Pattern for export filenames (e.g., "calendar.{format}")
        """
        self.calendar_dir = calendar_dir
        self.storage = storage
        self.git_service = git_service
        self.reader_registry = reader_registry
        self.canonical_filename = canonical_filename
        self.settings_filename = settings_filename
        self.export_pattern = export_pattern

    def paths(self, name: str) -> CalendarPaths:
        """Get all paths for a calendar.

        Returns a CalendarPaths object with paths for all calendar files.
        Paths are always returned regardless of whether files exist.
        Use paths.exists or path.exists() to check existence.

        Args:
            name: Calendar name/ID

        Returns:
            CalendarPaths with directory, data, settings, and export() method
        """
        directory = self.calendar_dir / name
        return CalendarPaths(
            directory=directory,
            data=directory / self.canonical_filename,
            settings=directory / self.settings_filename,
            _export_pattern=self.export_pattern,
        )

    def load_calendar(self, name: str, format: str = "ics") -> Calendar | None:
        """
        Load calendar by name from canonical JSON storage.

        The format parameter is kept for backwards compatibility but ignored.
        Calendars are always loaded from the canonical JSON format.
        """
        paths = self.paths(name)
        if not paths.directory.exists():
            return None

        # Try loading from canonical JSON
        if paths.data.exists():
            return Calendar.load(paths.data)

        return None

    def load_calendar_by_commit(
        self, name: str, commit: str, format: str = "ics"
    ) -> Calendar | None:
        """
        Load calendar from specific git commit.

        Args:
            name: Calendar name
            commit: Git commit hash or tag
            format: Ignored (kept for backwards compatibility)

        Returns:
            Calendar or None if not found
        """
        paths = self.paths(name)
        content = self.git_service.get_file_at_commit(paths.data, commit)

        if content is None:
            return None

        # Parse the content - Calendar.load handles both old and new formats
        import json

        data = json.loads(content.decode("utf-8"))

        # Check if this is the legacy nested format
        if "calendar" in data and "metadata" in data:
            # Legacy format - flatten it
            calendar_data = data["calendar"]
            metadata = data["metadata"]

            flat_data = {
                "events": calendar_data.get("events", []),
                "name": metadata.get("name"),
                "created": metadata.get("created"),
                "last_updated": metadata.get("last_updated"),
                "source": metadata.get("source"),
                "source_revised_at": metadata.get("source_revised_at"),
                "composed_from": metadata.get("composed_from"),
                "template_name": metadata.get("template_name"),
                "template_version": metadata.get("template_version"),
            }
            return Calendar.model_validate(flat_data)

        # New flat format
        return Calendar.model_validate(data)

    def save(
        self, calendar: Calendar, template: "CalendarTemplate | None" = None
    ) -> Path:
        """
        Save calendar to canonical JSON format and export to ICS.

        This is the main save method that:
        1. Saves to canonical JSON format
        2. Exports to ICS for subscriptions (with template resolution)
        3. Commits locally for versioning

        Args:
            calendar: Calendar to save
            template: Optional template for resolving location_id references

        Returns:
            Path to ICS export file (for subscription URLs)
        """
        paths = self.paths(calendar.name)
        paths.directory.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        calendar.last_updated = datetime.now()

        # Save to canonical JSON format
        calendar.save(paths.data)

        # Export to ICS for calendar subscriptions
        ics_writer = ICSWriter()
        ics_writer.write_calendar(calendar, paths.export("ics"), template=template)

        # Commit locally for versioning (always commit, even without --publish)
        self.git_service.commit_calendar_locally(calendar.name)

        # Return ICS path (used for subscription URLs)
        return paths.export("ics")

    def save_json(self, calendar: Calendar) -> Path:
        """
        Save calendar to canonical JSON format only (no ICS export, no commit).

        This is used by the ingest command. For full save with export and commit,
        use save().

        Args:
            calendar: Calendar to save

        Returns:
            Path to canonical JSON file
        """
        paths = self.paths(calendar.name)
        paths.directory.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        calendar.last_updated = datetime.now()

        # Save to canonical JSON format
        calendar.save(paths.data)

        return paths.data

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
        calendar = self.load_calendar(name)
        if calendar is None:
            raise CalendarNotFoundError(f"Calendar '{name}' not found")

        paths = self.paths(name)
        ics_writer = ICSWriter()
        ics_writer.write_calendar(calendar, paths.export("ics"), template=template)

        return paths.export("ics")

    def load_settings(self, name: str) -> CalendarSettings | None:
        """Load calendar settings from config.json.

        Args:
            name: Calendar name

        Returns:
            CalendarSettings or None if not found
        """
        paths = self.paths(name)
        if not paths.settings.exists():
            return None

        try:
            return CalendarSettings.model_validate_json(paths.settings.read_text())
        except (OSError, ValueError):
            return None

    def save_settings(self, name: str, settings: CalendarSettings) -> Path:
        """Save calendar settings to config.json.

        Args:
            name: Calendar name
            settings: CalendarSettings to save

        Returns:
            Path to settings file
        """
        paths = self.paths(name)
        paths.directory.mkdir(parents=True, exist_ok=True)

        paths.settings.write_text(settings.model_dump_json(indent=2, exclude_none=True))

        return paths.settings

    def create_calendar(
        self,
        calendar_id: str,
        name: str | None = None,
        template: str | None = None,
        description: str | None = None,
    ) -> Path:
        """Create a new calendar with settings (no data required).

        A calendar is defined by its config.json file. This method creates
        the config.json file for a calendar. The directory may already exist
        (e.g., if data was ingested before), but config.json must not exist.

        Args:
            calendar_id: Calendar ID (directory name)
            name: Optional display name (falls back to calendar_id if not set)
            template: Default template for this calendar
            description: Human-readable description

        Returns:
            Path to created settings file

        Raises:
            ValueError: If calendar already exists (config.json exists)
        """
        paths = self.paths(calendar_id)
        if paths.settings.exists():
            raise ValueError(f"Calendar '{calendar_id}' already exists")

        settings = CalendarSettings(
            name=name,
            template=template,
            description=description,
            created=datetime.now(),
        )

        return self.save_settings(calendar_id, settings)

    def rename_calendar(self, old_name: str, new_name: str) -> None:
        """Rename a calendar.

        Renames the calendar directory. The data.json metadata is not updated
        as it reflects the ingestion context (what the calendar was called when
        that data was ingested). The next ingestion will use the new name.

        Args:
            old_name: Current calendar name
            new_name: New calendar name

        Raises:
            CalendarNotFoundError: If source calendar doesn't exist (no config.json)
            ValueError: If target calendar already exists
        """
        old_paths = self.paths(old_name)
        new_paths = self.paths(new_name)

        if not self.calendar_exists(old_name):
            raise CalendarNotFoundError(f"Calendar '{old_name}' not found")
        if self.calendar_exists(new_name):
            raise ValueError(f"Calendar '{new_name}' already exists")

        # Rename directory only — data.json metadata is ingestion context
        shutil.move(str(old_paths.directory), str(new_paths.directory))

    def calendar_exists(self, name: str) -> bool:
        """Check if a calendar exists (has config.json)."""
        return self.paths(name).exists

    def list_calendars(self, include_deleted: bool = False) -> list[str]:
        """
        List all available calendar names.

        A calendar is defined by having a config.json file in its directory.

        Args:
            include_deleted: If True, also include calendars that exist in git history
                           but have been deleted from the filesystem

        Returns:
            List of calendar names
        """
        calendars = set()

        # Get calendars from filesystem (directories with config.json)
        if self.calendar_dir.exists():
            for d in self.calendar_dir.iterdir():
                if d.is_dir() and not d.name.startswith("."):
                    # Only include if config.json exists
                    if self.paths(d.name).exists:
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
        paths = self.paths(name)
        return self.git_service.get_file_versions(paths.data)

    def delete_calendar(self, name: str) -> None:
        """Delete calendar directory and all contents."""
        paths = self.paths(name)
        if paths.directory.exists():
            shutil.rmtree(paths.directory)

    def get_calendar_path(self, name: str, format: str = "ics") -> Path | None:
        """
        Get path to calendar export file if it exists.

        Args:
            name: Calendar name
            format: Export format (e.g., 'ics', 'json')

        Returns:
            Path to export file or None if not exists
        """
        paths = self.paths(name)
        export_path = paths.export(format)
        if export_path.exists():
            return export_path
        return None

    def get_canonical_path(self, name: str) -> Path | None:
        """
        Get path to canonical JSON storage file if it exists.

        Returns:
            Path to data.json file or None if not exists
        """
        paths = self.paths(name)
        if paths.data.exists():
            return paths.data
        return None
