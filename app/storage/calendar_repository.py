"""Calendar repository for managing named calendars."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from app.exceptions import CalendarNotFoundError
from app.ingestion.base import ReaderRegistry
from app.ingestion.ics_reader import ICSReader
from app.ingestion.json_reader import JSONReader
from app.models.calendar import Calendar
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.output.base import CalendarWriter
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_version_service import GitVersionService
from app.publish import GitPublisher


class CalendarRepository:
    """Repository for managing named calendars with dependency injection."""

    def __init__(self, calendar_dir: Path, storage: CalendarStorage):
        """
        Initialize repository.

        Args:
            calendar_dir: Base directory for calendars
            storage: CalendarStorage instance (dependency injection)
        """
        self.calendar_dir = calendar_dir
        self.storage = storage

        # Initialize reader registry
        self.reader_registry = ReaderRegistry()
        self.reader_registry.register(ICSReader(), [".ics"])
        self.reader_registry.register(JSONReader(), [".json"])

        # Initialize git version service (use calendar_dir's parent as repo root)
        # Try to find git repo root by walking up from calendar_dir
        repo_root = calendar_dir
        while repo_root != repo_root.parent:
            if (repo_root / ".git").exists():
                break
            repo_root = repo_root.parent
        self.git_service = GitVersionService(repo_root)
        self.git_publisher = GitPublisher(calendar_dir)

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
    ) -> Optional[CalendarWithMetadata]:
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
        calendar = reader.read(calendar_path)

        # Load metadata
        metadata = self.load_metadata(name)
        if metadata is None:
            # Create default metadata if not found
            metadata = CalendarMetadata(
                name=name,
                created=datetime.now(),
                last_updated=datetime.now(),
                revision_count=0,
                format=format,
            )

        return CalendarWithMetadata(calendar=calendar, metadata=metadata)

    def load_calendar_by_commit(
        self, name: str, commit: str, format: str = "ics"
    ) -> Optional[CalendarWithMetadata]:
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
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=f".{format}", delete=False
        ) as tmp_file:
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)

        try:
            # Load calendar using appropriate reader
            reader = self.reader_registry.get_reader(tmp_path)
            calendar = reader.read(tmp_path)

            # Load metadata (use current metadata)
            metadata = self.load_metadata(name)
            if metadata is None:
                metadata = CalendarMetadata(
                    name=name,
                    created=datetime.now(),
                    last_updated=datetime.now(),
                    revision_count=0,
                    format=format,
                )

            return CalendarWithMetadata(calendar=calendar, metadata=metadata)
        finally:
            # Clean up temp file
            try:
                tmp_path.unlink()
            except Exception:
                pass

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
        filepath = self.storage.save_calendar(
            calendar, writer, calendar_dir, metadata.name
        )

        # Save metadata
        self.save_metadata(metadata)

        # Commit locally for versioning (always commit, even without --publish)
        self.git_publisher.commit_calendar_locally(metadata.name)

        return filepath

    def save_metadata(self, metadata: CalendarMetadata) -> None:
        """Save metadata.json."""
        metadata_path = self._get_metadata_path(metadata.name)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.model_dump(), f, indent=2, default=str)

    def load_metadata(self, name: str) -> Optional[CalendarMetadata]:
        """Load metadata.json."""
        metadata_path = self._get_metadata_path(name)
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CalendarMetadata(**data)
        except Exception:
            return None

    def list_calendars(self, include_deleted: bool = False) -> List[str]:
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
                result = subprocess.run(
                    ["git", "log", "--all", "--pretty=format:", "--name-only", "--", str(self.calendar_dir)],
                    cwd=self.git_service.repo_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                
                # Extract calendar names from paths like "data/calendars/name/calendar.ics"
                all_files = set(result.stdout.splitlines())
                for file_path in all_files:
                    if not file_path.strip():
                        continue
                    # Look for paths containing "calendars/" and "/calendar."
                    if "calendars/" in file_path and "/calendar." in file_path:
                        parts = file_path.split("calendars/")
                        if len(parts) > 1:
                            calendar_name = parts[1].split("/")[0]
                            if calendar_name and not calendar_name.startswith("."):
                                calendars.add(calendar_name)
            except Exception:
                # If git operations fail, just return filesystem calendars
                pass
        
        return sorted(calendars)

    def list_calendar_versions(
        self, name: str, format: str = "ics"
    ) -> List[Tuple[str, datetime, str]]:
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

    def get_latest_calendar_path(
        self, name: str, format: str = "ics"
    ) -> Optional[Path]:
        """
        Get path to calendar file.

        Returns path to calendar.{ext} file.
        """
        calendar_path = self._get_calendar_file_path(name, format)
        if calendar_path.exists():
            return calendar_path
        return None
