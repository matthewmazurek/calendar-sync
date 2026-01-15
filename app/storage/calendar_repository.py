"""Calendar repository for managing named calendars."""

import json
from datetime import datetime
from pathlib import Path

from app.exceptions import CalendarNotFoundError
from app.ingestion.base import ReaderRegistry
from app.models.calendar import Calendar
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.output.base import CalendarWriter
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService


class CalendarRepository:
    """Repository for managing named calendars with dependency injection."""

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
            reader_registry: ReaderRegistry instance (dependency injection)
        """
        self.calendar_dir = calendar_dir
        self.storage = storage
        self.git_service = git_service
        self.reader_registry = reader_registry

    def _get_calendar_dir(self, name: str) -> Path:
        """Get directory for named calendar."""
        return self.calendar_dir / name

    def _get_metadata_path(self, name: str) -> Path:
        """Get path to metadata file."""
        return self._get_calendar_dir(name) / "metadata.json"

    def _get_calendar_file_path(self, name: str, format: str = "ics") -> Path:
        """Get path to calendar file."""
        calendar_dir = self._get_calendar_dir(name)
        return calendar_dir / f"calendar.{format}"

    def load_calendar(
        self, name: str, format: str = "ics"
    ) -> CalendarWithMetadata | None:
        """
        Load calendar by name.

        Loads calendar.{ext} file directly.
        """
        calendar_dir = self._get_calendar_dir(name)
        if not calendar_dir.exists():
            return None

        calendar_path = self._get_calendar_file_path(name, format)
        if not calendar_path.exists():
            return None

        # Load calendar using appropriate reader
        reader = self.reader_registry.get_reader(calendar_path)
        ingestion_result = reader.read(calendar_path)
        calendar = ingestion_result.calendar

        # Load metadata
        metadata = self.load_metadata(name)
        if metadata is None:
            # Create default metadata if not found
            metadata = CalendarMetadata(
                name=name,
                created=datetime.now(),
                last_updated=datetime.now(),
                format=format,
            )

        return CalendarWithMetadata(calendar=calendar, metadata=metadata)

    def load_calendar_by_commit(
        self, name: str, commit: str, format: str = "ics"
    ) -> CalendarWithMetadata | None:
        """
        Load calendar from specific git commit.

        Args:
            name: Calendar name
            commit: Git commit hash or tag
            format: Calendar format

        Returns:
            CalendarWithMetadata or None if not found
        """
        calendar_path = self._get_calendar_file_path(name, format)

        # Get file content at specific commit
        content = self.git_service.get_file_at_commit(calendar_path, commit)
        if content is None:
            return None

        # Write to temp file for reading
        from app.utils import temp_file_path

        with temp_file_path(suffix=f".{format}") as tmp_path:
            tmp_path.write_bytes(content)

            # Load calendar using appropriate reader
            reader = self.reader_registry.get_reader(tmp_path)
            ingestion_result = reader.read(tmp_path)
            calendar = ingestion_result.calendar

            # Load metadata (use current metadata)
            metadata = self.load_metadata(name)
            if metadata is None:
                metadata = CalendarMetadata(
                    name=name,
                    created=datetime.now(),
                    last_updated=datetime.now(),
                    format=format,
                )

            return CalendarWithMetadata(calendar=calendar, metadata=metadata)

    def save_calendar(
        self, calendar: Calendar, metadata: CalendarMetadata, writer: CalendarWriter
    ) -> Path:
        """
        Save calendar with timestamp, updates metadata.

        Args:
            calendar: Calendar to save
            metadata: Calendar metadata
            writer: CalendarWriter implementation

        Returns:
            Path to saved file
        """
        calendar_dir = self._get_calendar_dir(metadata.name)
        calendar_dir.mkdir(parents=True, exist_ok=True)

        # Update metadata format
        metadata.format = writer.get_extension()
        metadata.last_updated = datetime.now()

        # Save calendar file
        calendar_with_metadata = CalendarWithMetadata(
            calendar=calendar, metadata=metadata
        )
        filepath = self.storage.save_calendar(
            calendar_with_metadata, writer, calendar_dir
        )

        # Save metadata
        self.save_metadata(metadata)

        # Commit locally for versioning (always commit, even without --publish)
        self.git_service.commit_calendar_locally(metadata.name)

        return filepath

    def save_metadata(self, metadata: CalendarMetadata) -> None:
        """Save metadata.json."""
        metadata_path = self._get_metadata_path(metadata.name)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.model_dump(), f, indent=2, default=str)

    def load_metadata(self, name: str) -> CalendarMetadata | None:
        """Load metadata.json."""
        metadata_path = self._get_metadata_path(name)
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CalendarMetadata(**data)
        except (OSError, ValueError, KeyError):
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

        Returns:
            List of (commit_hash, commit_date, commit_message) tuples
        """
        calendar_path = self._get_calendar_file_path(name, format)
        # Don't check if file exists - git log works for deleted files too
        return self.git_service.get_file_versions(calendar_path)

    def delete_calendar(self, name: str) -> None:
        """Delete calendar directory and all contents."""
        calendar_dir = self._get_calendar_dir(name)
        if calendar_dir.exists():
            import shutil

            shutil.rmtree(calendar_dir)

    def get_calendar_path(self, name: str, format: str = "ics") -> Path | None:
        """
        Get path to calendar file.

        Returns path to calendar.{ext} file.
        """
        calendar_path = self._get_calendar_file_path(name, format)
        if calendar_path.exists():
            return calendar_path
        return None
