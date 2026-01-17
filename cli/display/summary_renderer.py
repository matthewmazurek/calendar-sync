"""Summary renderer for ingestion and processing output."""

from pathlib import Path
from typing import TYPE_CHECKING

from cli.display.console import console

if TYPE_CHECKING:
    from app.models.ingestion import IngestionSummary
    from app.models.template import CalendarTemplate


class SummaryRenderer:
    """Render ingestion and processing summaries.

    Used by ingest and sync commands to display:
    - Command headers
    - Source file information
    - Processing summaries with event counts
    - Coverage statistics
    - Success messages
    """

    def render_header(self, title: str, calendar_name: str) -> None:
        """Render a styled header for a command.

        Args:
            title: Command title (e.g., "Creating", "Updating").
            calendar_name: Name of the calendar being processed.
        """
        console.print()
        console.print("━" * 40)
        console.print(f"[bold]  {title}: {calendar_name}[/bold]")
        console.print("━" * 40)

    def render_source_info(
        self,
        input_path: Path,
        ingestion_summary: "IngestionSummary",
        template: "CalendarTemplate",
    ) -> None:
        """Render source file information.

        Args:
            input_path: Path to the source file.
            ingestion_summary: Summary of ingested data.
            template: Template used for processing.
        """
        console.print(f"\nSource: {input_path}")
        source_details = [
            f"{ingestion_summary.events} events",
            ingestion_summary.date_range,
        ]
        if ingestion_summary.revised_date:
            source_details.append(f"revised {ingestion_summary.revised_date}")
        console.print(f"  {' · '.join(source_details)}")

        # Template info
        template_info = f"Template: {template.name}"
        if template.extends:
            template_info += f" (extends {template.extends})"
        console.print(f"  {template_info}")

    def render_processing_summary(self, processing_summary: dict) -> None:
        """Render processing summary with arrow notation for collapsed events.

        Args:
            processing_summary: Dictionary with input_counts, output_counts,
                input_total, output_total keys.
        """
        if not processing_summary:
            return

        input_counts = processing_summary.get("input_counts", {})
        output_counts = processing_summary.get("output_counts", {})
        input_total = processing_summary.get("input_total", 0)
        output_total = processing_summary.get("output_total", 0)

        if not input_counts:
            return

        console.print("\nProcessing:")

        # Format each event type
        for event_type, count in sorted(input_counts.items()):
            output_count = output_counts.get(event_type, 0)
            if output_count != count:
                console.print(f"  {event_type}: {count} → {output_count}")
            else:
                console.print(f"  {event_type}: {count}")

        # Total with separator
        console.print("  " + "─" * 30)
        if output_total != input_total:
            console.print(f"  Total: {input_total} → {output_total}")
        else:
            console.print(f"  Total: {input_total}")

    def render_stats(self, ingestion_summary: dict) -> None:
        """Render statistics in a compact single line.

        Args:
            ingestion_summary: Dictionary with total_halfdays and
                weekly_coverage_year keys.
        """
        parts = []

        total_halfdays = ingestion_summary.get("total_halfdays")
        weekly_coverage_year = ingestion_summary.get("weekly_coverage_year")

        if total_halfdays is not None:
            parts.append(f"{total_halfdays} half-days")
        if weekly_coverage_year is not None:
            parts.append(f"{weekly_coverage_year:.1f}/week coverage")

        if parts:
            console.print(f"\nStats: {' · '.join(parts)}")

    def render_success(self, message: str, path: Path | None = None) -> None:
        """Render a success message with optional file path.

        Args:
            message: Success message to display.
            path: Optional file path to display below the message.
        """
        console.print(f"\n[bold green]✓[/bold green] {message}")
        if path:
            console.print(f"  {path}")
