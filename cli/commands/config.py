"""Display configuration file path and settings."""

import os
from pathlib import Path

import typer

from app.config import CalendarConfig


def _find_env_file() -> Path | None:
    """Find .env file by searching current directory and parent directories."""
    current = Path.cwd()
    
    # Check current directory and all parent directories
    for path in [current] + list(current.parents):
        env_file = path / ".env"
        if env_file.exists():
            return env_file.resolve()
    
    return None


def config() -> None:
    """Display configuration file path and settings."""
    # Find .env file
    env_file = _find_env_file()
    
    # Get default config for comparison
    default_config = CalendarConfig()
    
    # Load config (from .env and environment)
    config_obj = CalendarConfig.from_env()
    
    # Display config file path
    typer.echo("Configuration File:")
    if env_file:
        typer.echo(f"  Path: {env_file}")
    else:
        typer.echo("  Path: Not found (using defaults and environment variables)")
    typer.echo()
    
    # Display config settings
    typer.echo("Configuration Settings:")
    label_width = 25
    
    # Determine source for each setting
    # Note: load_dotenv() loads .env into os.environ, so we can't distinguish
    # between .env and environment variables, but we can check if value differs from default
    def get_source(env_key: str, value, default_value) -> str:
        """Determine the source of a config value."""
        if env_key in os.environ:
            return "environment"
        elif value != default_value:
            # Value was set but not in current os.environ (shouldn't happen after load_dotenv)
            return "environment"
        else:
            return "default"
    
    # Default format
    source_format = get_source("CALENDAR_FORMAT", config_obj.default_format, default_config.default_format)
    typer.echo(f"{'default_format:':<{label_width}} {config_obj.default_format} ({source_format})")
    
    # Calendar directory
    source_dir = get_source("CALENDAR_DIR", str(config_obj.calendar_dir), str(default_config.calendar_dir))
    typer.echo(f"{'calendar_dir:':<{label_width}} {config_obj.calendar_dir} ({source_dir})")
    
    # LS default limit
    source_limit = get_source("LS_DEFAULT_LIMIT", config_obj.ls_default_limit, default_config.ls_default_limit)
    typer.echo(f"{'ls_default_limit:':<{label_width}} {config_obj.ls_default_limit} ({source_limit})")
    
    # Git remote URL
    source_git = get_source("CALENDAR_GIT_REMOTE_URL", config_obj.calendar_git_remote_url, default_config.calendar_git_remote_url)
    git_display = config_obj.calendar_git_remote_url if config_obj.calendar_git_remote_url else "None"
    typer.echo(f"{'calendar_git_remote_url:':<{label_width}} {git_display} ({source_git})")
