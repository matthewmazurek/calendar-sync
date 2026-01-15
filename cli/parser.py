"""CLI argument parsing and command routing using Typer."""

import typer
from typing_extensions import Annotated

from cli import setup_logging
from cli.context import CLIContext, set_context

# Create the main Typer app
app = typer.Typer(
    name="calendar-sync",
    help="Calendar sync tool for managing calendars from various data sources.",
    add_completion=True,
    rich_markup_mode="rich",
)

# Version from pyproject.toml
__version__ = "0.1.0"


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"calendar-sync version {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show debug output"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Only show errors"),
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = None,
) -> None:
    """Calendar sync tool with simplified sync command."""
    # Set up logging based on flags
    setup_logging(verbose=verbose, quiet=quiet)

    # Create and set global context
    ctx = CLIContext(verbose=verbose, quiet=quiet)
    set_context(ctx)


from cli.commands.config import config
from cli.commands.delete import delete
from cli.commands.diff import diff
from cli.commands.git_setup import git_setup
from cli.commands.info import info
from cli.commands.ls import ls
from cli.commands.publish import publish
from cli.commands.restore import restore

# Import and register commands
from cli.commands.sync import sync
from cli.commands.template import template

app.command(name="sync")(sync)
app.command(name="ls")(ls)
app.command(name="restore")(restore)
app.command(name="info")(info)
app.command(name="delete")(delete)
app.command(name="diff")(diff)
app.command(name="publish")(publish)
app.command(name="git-setup")(git_setup)
app.command(name="config")(config)
app.command(name="template")(template)


if __name__ == "__main__":
    app()
