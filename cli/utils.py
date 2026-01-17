"""CLI utilities for user interaction.

Display-related functions have been moved to cli.display module.
This module now contains only user interaction utilities.
"""

import typer

# Re-export display functions for backwards compatibility
# These are deprecated - use cli.display directly instead
from cli.display.formatters import format_file_size, format_relative_time
from cli.display.summary_renderer import SummaryRenderer

# Create a default renderer instance for backwards compatibility
_summary_renderer = SummaryRenderer()


def confirm_or_exit(prompt: str = "Continue?", force: bool = False) -> None:
    """Prompt for confirmation unless force is True. Exits if declined.

    Args:
        prompt: The confirmation prompt to display.
        force: If True, skip the confirmation prompt.
    """
    if not force:
        typer.echo()
        if not typer.confirm(prompt):
            typer.echo("Operation cancelled.")
            raise typer.Exit(0)


# ─────────────────────────────────────────────────────────────────────────────
# Backwards compatibility wrappers (deprecated)
# Use SummaryRenderer from cli.display instead
# ─────────────────────────────────────────────────────────────────────────────


def print_header(title: str, calendar_name: str) -> None:
    """Print a styled header for a command.

    DEPRECATED: Use SummaryRenderer.render_header() instead.
    """
    _summary_renderer.render_header(title, calendar_name)


def print_source_info(input_path, ingestion_summary, template) -> None:
    """Print source file information.

    DEPRECATED: Use SummaryRenderer.render_source_info() instead.
    """
    _summary_renderer.render_source_info(input_path, ingestion_summary, template)


def print_processing_summary(processing_summary: dict) -> None:
    """Format processing summary with arrow notation.

    DEPRECATED: Use SummaryRenderer.render_processing_summary() instead.
    """
    _summary_renderer.render_processing_summary(processing_summary)


def print_stats(ingestion_summary: dict) -> None:
    """Format statistics in a compact single line.

    DEPRECATED: Use SummaryRenderer.render_stats() instead.
    """
    _summary_renderer.render_stats(ingestion_summary)


def print_success(message: str, path=None) -> None:
    """Print a success message with optional file path.

    DEPRECATED: Use SummaryRenderer.render_success() instead.
    """
    _summary_renderer.render_success(message, path)


def format_processing_summary(
    processing_summary: dict, ingestion_summary: dict | None = None
) -> None:
    """Format and display processing summary.

    DEPRECATED: Use SummaryRenderer methods instead.
    """
    _summary_renderer.render_processing_summary(processing_summary)
    if ingestion_summary:
        _summary_renderer.render_stats(ingestion_summary)
