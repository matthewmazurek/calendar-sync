"""Display configuration file path and settings."""

import os
from pathlib import Path

from rich.table import Table

from app.config import CalendarConfig
from cli.display import console


def _find_env_file() -> Path | None:
    """Find .env file by searching current directory and parent directories."""
    current = Path.cwd()

    # Check current directory and all parent directories
    for path in [current] + list(current.parents):
        env_file = path / ".env"
        if env_file.exists():
            return env_file.resolve()

    return None


def _get_source(env_key: str, value, default_value) -> str:
    """Determine the source of a config value."""
    if env_key in os.environ:
        return "env"
    elif value != default_value:
        return "env"
    else:
        return "default"


def _create_table(setting_width: int, source_width: int) -> Table:
    """Create a styled table for config sections with fixed column widths."""
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("SETTING", style="cyan", min_width=setting_width, no_wrap=True)
    table.add_column("SOURCE", style="dim", min_width=source_width, no_wrap=True)
    table.add_column("VALUE")
    return table


def config() -> None:
    """Display configuration file path and settings."""
    # Find .env file
    env_file = _find_env_file()

    # Get default config for comparison
    default_config = CalendarConfig()

    # Load config (from .env and environment)
    cfg = CalendarConfig.from_env()

    # Build all rows first to calculate column widths
    git_url_display = cfg.calendar_git_remote_url or "[dim]None[/dim]"

    sections: list[tuple[str, list[tuple[str, str, str]]]] = [
        (
            "Storage Paths",
            [
                (
                    "calendar_dir",
                    str(cfg.calendar_dir.resolve()),
                    _get_source(
                        "CALENDAR_DIR", str(cfg.calendar_dir), str(default_config.calendar_dir)
                    ),
                ),
                (
                    "template_dir",
                    str(cfg.template_dir.resolve()),
                    _get_source(
                        "TEMPLATE_DIR", str(cfg.template_dir), str(default_config.template_dir)
                    ),
                ),
                (
                    "log_dir",
                    str(cfg.log_dir.resolve()),
                    _get_source("LOG_DIR", str(cfg.log_dir), str(default_config.log_dir)),
                ),
            ],
        ),
        (
            "File Naming",
            [
                ("canonical_filename", cfg.canonical_filename, "default"),
                ("export_pattern", cfg.export_pattern, "default"),
                (
                    "log_filename",
                    cfg.log_filename,
                    _get_source("LOG_FILENAME", cfg.log_filename, default_config.log_filename),
                ),
            ],
        ),
        (
            "Templates",
            [
                (
                    "default_template",
                    cfg.default_template,
                    _get_source(
                        "DEFAULT_TEMPLATE", cfg.default_template, default_config.default_template
                    ),
                ),
            ],
        ),
        (
            "Git Settings",
            [
                (
                    "calendar_git_remote_url",
                    git_url_display,
                    _get_source(
                        "CALENDAR_GIT_REMOTE_URL",
                        cfg.calendar_git_remote_url,
                        default_config.calendar_git_remote_url,
                    ),
                ),
                (
                    "git_default_remote",
                    cfg.git_default_remote,
                    _get_source(
                        "GIT_DEFAULT_REMOTE",
                        cfg.git_default_remote,
                        default_config.git_default_remote,
                    ),
                ),
                (
                    "git_default_branch",
                    cfg.git_default_branch,
                    _get_source(
                        "GIT_DEFAULT_BRANCH",
                        cfg.git_default_branch,
                        default_config.git_default_branch,
                    ),
                ),
            ],
        ),
        (
            "CLI Defaults",
            [
                (
                    "ls_default_limit",
                    str(cfg.ls_default_limit),
                    _get_source(
                        "LS_DEFAULT_LIMIT", cfg.ls_default_limit, default_config.ls_default_limit
                    ),
                ),
            ],
        ),
    ]

    # Calculate max widths across all sections
    all_rows = [row for _, rows in sections for row in rows]
    setting_width = max(len(row[0]) for row in all_rows)
    source_width = max(len(row[2]) for row in all_rows)

    # Also consider header widths
    setting_width = max(setting_width, len("SETTING"))
    source_width = max(source_width, len("SOURCE"))

    # Header
    console.print()
    console.print("━" * 50)
    console.print("[bold]  Configuration[/bold]")
    console.print("━" * 50)

    # Config file section
    console.print("\n[bold]Config File:[/bold]")
    if env_file:
        console.print(f"  [cyan]{env_file}[/cyan]")
    else:
        console.print("  [dim]Not found (using defaults and environment variables)[/dim]")

    # Render each section
    for section_name, rows in sections:
        console.print(f"\n[bold]{section_name}:[/bold]")
        table = _create_table(setting_width, source_width)
        for setting, value, source in rows:
            table.add_row(setting, source, value)
        console.print(table)

    console.print()
