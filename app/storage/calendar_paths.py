"""Calendar paths dataclass for consistent path access."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CalendarPaths:
    """Paths for a calendar's files.
    
    Always returns paths regardless of whether files exist.
    Use .exists property or path.exists() to check existence.
    """

    directory: Path
    data: Path  # data.json - canonical storage
    settings: Path  # config.json - settings
    _export_pattern: str = field(default="calendar.{format}", repr=False)

    def export(self, format: str = "ics") -> Path:
        """Get export file path for given format (ics, json, etc).
        
        Args:
            format: Export format extension (e.g., 'ics', 'json', 'csv')
            
        Returns:
            Path to export file (e.g., calendar.ics)
        """
        return self.directory / self._export_pattern.format(format=format)

    @property
    def exists(self) -> bool:
        """Check if calendar exists (has settings file)."""
        return self.settings.exists()
