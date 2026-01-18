"""Display module for rendering calendar output.

This module provides renderers for various display contexts:
- EventRenderer: Protocol for event rendering
- RichEventRenderer: Rich-based event display (agenda/list views)
- TableRenderer: Calendar and version list tables
- DiffRenderer: Calendar diff visualization
- StatsRenderer: Statistics display
- SummaryRenderer: Ingestion/processing summaries
- TemplateRenderer: Template configuration display

It also provides:
- console: Shared Rich console instance
- Formatting functions for dates, times, and file sizes
"""

from cli.display.console import console
from cli.display.diff_renderer import DiffRenderer
from cli.display.event_renderer import EventRenderer
from cli.display.formatters import (
    format_datetime,
    format_file_size,
    format_path,
    format_relative_time,
)
from cli.display.push_renderer import PushRenderer, push_calendar
from cli.display.rich_renderer import RichEventRenderer
from cli.display.stats_renderer import StatsRenderer
from cli.display.summary_renderer import SummaryRenderer
from cli.display.table_renderer import CalendarInfo, TableRenderer, VersionInfo
from cli.display.template_renderer import TemplateRenderer

__all__ = [
    # Console
    "console",
    # Protocols
    "EventRenderer",
    # Renderers
    "RichEventRenderer",
    "TableRenderer",
    "DiffRenderer",
    "StatsRenderer",
    "SummaryRenderer",
    "TemplateRenderer",
    "PushRenderer",
    # Functions
    "push_calendar",
    # Data classes
    "CalendarInfo",
    "VersionInfo",
    # Formatters
    "format_datetime",
    "format_file_size",
    "format_path",
    "format_relative_time",
]
