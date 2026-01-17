"""Template renderer for displaying compiled template configurations."""

from rich.table import Table

from app.models.template import (
    CalendarTemplate,
    ConsolidateConfig,
    EventTypeConfig,
    LocationConfig,
    OvernightConfig,
)
from cli.display.console import console


class TemplateRenderer:
    """Render compiled template configurations.

    Provides two view modes:
    - Tabular view: Compact tables for locations and event types
    - Detail view: Expanded blocks showing all fields for each item
    """

    def render_table(
        self, template: CalendarTemplate, extends: str | None = None
    ) -> None:
        """Render template in compact tabular format.

        Args:
            template: The compiled CalendarTemplate to display.
            extends: Original extends value (before compilation).
        """
        self._render_header(template, extends)
        self._render_settings(template)
        self._render_defaults(template)
        self._render_locations_table(template)
        self._render_types_table(template)
        self._render_footer(template)

    def render_detail(
        self, template: CalendarTemplate, extends: str | None = None
    ) -> None:
        """Render template in expanded detail format.

        Args:
            template: The compiled CalendarTemplate to display.
            extends: Original extends value (before compilation).
        """
        self._render_header(template, extends)
        self._render_settings(template)
        self._render_defaults(template)
        self._render_locations_detail(template)
        self._render_types_detail(template)
        self._render_footer(template)

    # ─────────────────────────────────────────────────────────────────────────
    # Common sections
    # ─────────────────────────────────────────────────────────────────────────

    def _render_header(self, template: CalendarTemplate, extends: str | None) -> None:
        """Render the template header."""
        console.print()
        console.print("━" * 50)
        console.print(f"[bold]  Template: {template.name} v{template.version}[/bold]")
        console.print("━" * 50)
        if extends:
            console.print(f"  Extends: {extends}")

    def _render_settings(self, template: CalendarTemplate) -> None:
        """Render the settings section."""
        console.print("\n[bold]Settings:[/bold]")
        console.print(f"  {'time_format':<18} {template.settings.time_format}")

    def _render_defaults(self, template: CalendarTemplate) -> None:
        """Render the defaults section."""
        defaults = template.defaults
        console.print("\n[bold]Event Defaults:[/bold]")

        # Location
        location = defaults.location or "-"
        console.print(f"  {'location':<18} {location}")

        # Consolidate
        consolidate_str = self._format_consolidate(defaults.consolidate)
        console.print(f"  {'consolidate':<18} {consolidate_str}")

        # Overnight
        overnight_str = self._format_overnight(defaults.overnight)
        console.print(f"  {'overnight':<18} {overnight_str}")

        # Time periods
        time_periods_str = self._format_time_periods(defaults.time_periods)
        console.print(f"  {'time_periods':<18} {time_periods_str}")

    def _render_footer(self, template: CalendarTemplate) -> None:
        """Render the footer with counts."""
        location_count = len(template.locations)
        type_count = len(template.types)

        console.print()
        console.print("─" * 50)
        console.print(
            f"[dim]{location_count} locations, {type_count} event types[/dim]"
        )
        console.print()

    # ─────────────────────────────────────────────────────────────────────────
    # Tabular view sections
    # ─────────────────────────────────────────────────────────────────────────

    def _render_locations_table(self, template: CalendarTemplate) -> None:
        """Render locations as a compact table."""
        if not template.locations:
            console.print("\n[bold]Locations:[/bold]")
            console.print("  [dim]None defined[/dim]")
            return

        console.print("\n[bold]Locations:[/bold]")
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("NAME", style="cyan")
        table.add_column("ADDRESS")
        table.add_column("GEO", style="dim")

        for name, loc in template.locations.items():
            address = self._truncate(loc.address, 35) if loc.address else "-"
            geo = self._format_geo(loc.geo) if loc.geo else "-"
            table.add_row(name, address, geo)

        console.print(table)

    def _render_types_table(self, template: CalendarTemplate) -> None:
        """Render event types as a compact table."""
        if not template.types:
            console.print("\n[bold]Event Types:[/bold]")
            console.print("  [dim]None defined[/dim]")
            return

        console.print("\n[bold]Event Types:[/bold]")
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("TYPE", style="cyan")
        table.add_column("MATCH")
        table.add_column("LOCATION")
        table.add_column("CONSOLIDATE")
        table.add_column("OVERNIGHT")
        table.add_column("BUSY")

        for name, type_config in template.types.items():
            match_str = (
                self._format_match_short(type_config.match)
                if type_config.match
                else "-"
            )
            location = type_config.location or "-"
            consolidate = self._format_consolidate_short(type_config.consolidate)
            overnight = self._format_overnight_short(type_config.overnight)
            busy = "yes" if type_config.busy else "no"

            table.add_row(name, match_str, location, consolidate, overnight, busy)

        console.print(table)

    # ─────────────────────────────────────────────────────────────────────────
    # Detail view sections
    # ─────────────────────────────────────────────────────────────────────────

    def _render_locations_detail(self, template: CalendarTemplate) -> None:
        """Render locations as expanded detail blocks."""
        console.print("\n[bold]Locations:[/bold]")

        if not template.locations:
            console.print("  [dim]None defined[/dim]")
            return

        for name, loc in template.locations.items():
            console.print(f"\n  [cyan]{name}[/cyan]")
            self._print_field("address", loc.address)
            self._print_field("geo", self._format_geo_full(loc.geo))
            self._print_field("apple_title", loc.apple_title)

    def _render_types_detail(self, template: CalendarTemplate) -> None:
        """Render event types as expanded detail blocks."""
        console.print("\n[bold]Event Types:[/bold]")

        if not template.types:
            console.print("  [dim]None defined[/dim]")
            return

        for name, type_config in template.types.items():
            console.print(f"\n  [cyan]{name}[/cyan]")
            self._render_type_fields(type_config, template)

    def _render_type_fields(
        self, type_config: EventTypeConfig, template: CalendarTemplate
    ) -> None:
        """Render all fields for an event type."""
        # Match
        if type_config.match:
            match_str = self._format_match_full(type_config.match)
            self._print_field("match", match_str)

        # Match mode (only show if non-default)
        self._print_field("match_mode", type_config.match_mode)

        # Label (regex pattern)
        if type_config.label:
            self._print_field("label", type_config.label)

        # Location
        self._print_field("location", type_config.location)

        # Consolidate
        consolidate_str = self._format_consolidate_detail(type_config.consolidate)
        self._print_field("consolidate", consolidate_str)

        # Overnight
        overnight_str = self._format_overnight_detail(type_config.overnight)
        self._print_field("overnight", overnight_str)

        # Time periods (only if defined on this type)
        if type_config.time_periods:
            time_periods_str = self._format_time_periods(type_config.time_periods)
            self._print_field("time_periods", time_periods_str)

        # Suppress
        self._print_field("suppress", "yes" if type_config.suppress else "no")

        # Busy
        self._print_field("busy", "yes" if type_config.busy else "no")

    def _print_field(self, label: str, value: str | None) -> None:
        """Print a field with consistent formatting."""
        display_value = value if value else "-"
        console.print(f"    {label:<18} {display_value}")

    # ─────────────────────────────────────────────────────────────────────────
    # Formatting helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis if too long."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    def _format_geo(self, geo: tuple[float, float] | None) -> str:
        """Format geo coordinates for table view."""
        if not geo:
            return "-"
        return f"{geo[0]:.2f}, {geo[1]:.2f}"

    def _format_geo_full(self, geo: tuple[float, float] | None) -> str | None:
        """Format geo coordinates for detail view."""
        if not geo:
            return None
        return f"{geo[0]}, {geo[1]}"

    def _format_match_short(self, match: str | list[str]) -> str:
        """Format match pattern(s) for table view."""
        if isinstance(match, str):
            return f'"{match}"'
        if len(match) == 1:
            return f'"{match[0]}"'
        # Show first item + indicator of more
        first = match[0]
        if len(first) > 12:
            first = first[:11] + "…"
        return f"{first}, …"

    def _format_match_full(self, match: str | list[str]) -> str:
        """Format match pattern(s) for detail view."""
        if isinstance(match, str):
            return f'"{match}"'
        if len(match) == 1:
            return f'"{match[0]}"'
        return ", ".join(match)

    def _format_consolidate(
        self, consolidate: str | ConsolidateConfig | bool | None
    ) -> str:
        """Format consolidate config for defaults section."""
        if consolidate is None:
            return "-"
        if consolidate is False:
            return "-"
        if isinstance(consolidate, str):
            return consolidate
        # ConsolidateConfig
        parts = [consolidate.group_by]
        extras = []
        if consolidate.pattern_aware:
            extras.append("pattern_aware: yes")
        else:
            extras.append("pattern_aware: no")
        if consolidate.only_all_day:
            extras.append("only_all_day: yes")
        if consolidate.require_same_times:
            extras.append("require_same_times: yes")
        if extras:
            parts.append(f"({', '.join(extras)})")
        return " ".join(parts)

    def _format_consolidate_short(
        self, consolidate: str | ConsolidateConfig | bool | None
    ) -> str:
        """Format consolidate config for table view (compact)."""
        if consolidate is None:
            return "-"
        if consolidate is False:
            return "-"
        if isinstance(consolidate, str):
            return consolidate
        # ConsolidateConfig - just show group_by
        return consolidate.group_by

    def _format_consolidate_detail(
        self, consolidate: str | ConsolidateConfig | bool | None
    ) -> str | None:
        """Format consolidate config for detail view."""
        if consolidate is None:
            return None
        if consolidate is False:
            return "-"
        if isinstance(consolidate, str):
            return consolidate
        # ConsolidateConfig - show all options
        parts = [f"group_by: {consolidate.group_by}"]
        if consolidate.pattern_aware:
            parts.append("pattern_aware: yes")
        if consolidate.only_all_day:
            parts.append("only_all_day: yes")
        if consolidate.require_same_times:
            parts.append("require_same_times: yes")
        return ", ".join(parts)

    def _format_overnight(self, overnight: str | OvernightConfig | None) -> str:
        """Format overnight config for defaults section."""
        if overnight is None:
            return "-"
        if isinstance(overnight, str):
            return overnight
        # OvernightConfig
        return overnight.as_

    def _format_overnight_short(self, overnight: str | OvernightConfig | None) -> str:
        """Format overnight config for table view (compact)."""
        if overnight is None:
            return "-"
        if isinstance(overnight, str):
            return overnight
        # OvernightConfig - just show the 'as' value
        return overnight.as_

    def _format_overnight_detail(
        self, overnight: str | OvernightConfig | None
    ) -> str | None:
        """Format overnight config for detail view."""
        if overnight is None:
            return None
        if isinstance(overnight, str):
            return overnight
        # OvernightConfig - show all options
        parts = [f"as: {overnight.as_}"]
        if overnight.format != "{title} {time_range}":
            parts.append(f'format: "{overnight.format}"')
        return ", ".join(parts)

    def _format_time_periods(
        self, time_periods: dict[str, tuple[str, str]] | None
    ) -> str:
        """Format time periods for display."""
        if not time_periods:
            return "-"
        parts = []
        for name, (start, end) in time_periods.items():
            start_fmt = self._format_time(start)
            end_fmt = self._format_time(end)
            parts.append(f"{name}: {start_fmt}-{end_fmt}")
        return ", ".join(parts)

    def _format_time(self, time_str: str) -> str:
        """Format HHMM time string to HH:MM."""
        if len(time_str) == 4:
            return f"{time_str[:2]}:{time_str[2:]}"
        return time_str
