"""Display available templates or show compiled template details."""

import json
from pathlib import Path

import typer
from typing_extensions import Annotated

from app.models.template_loader import load_template
from cli.context import get_context
from cli.display.template_renderer import TemplateRenderer


def template(
    name: Annotated[
        str | None,
        typer.Argument(help="Template name to view (omit to list all templates)"),
    ] = None,
    detail: Annotated[
        bool,
        typer.Option("--detail", "-d", help="Show expanded detail view"),
    ] = False,
) -> None:
    """Display available templates or show compiled template details.

    Without a name argument, lists all available templates.
    With a name, shows the compiled template configuration (with inherited values).

    Use --detail for an expanded view showing all fields for each event type.
    """
    if name:
        _show_template(name, detail)
    else:
        _list_templates()


def _show_template(name: str, detail: bool) -> None:
    """Show compiled template configuration.

    Args:
        name: Template name to display.
        detail: Whether to show expanded detail view.
    """
    ctx = get_context()
    template_dir = ctx.config.template_dir

    # Read raw template to get extends value before compilation
    template_path = template_dir / f"{name}.json"
    if not template_path.exists():
        typer.echo(f"\nTemplate '{name}' not found")
        typer.echo(f"  Searched in: {template_dir.resolve()}")
        raise typer.Exit(1)

    extends = None
    try:
        with open(template_path, "r") as f:
            raw_data = json.load(f)
            extends = raw_data.get("extends")
    except Exception:
        pass

    # Load compiled template (with inheritance applied)
    try:
        compiled_template = load_template(name, template_dir)
    except FileNotFoundError as e:
        typer.echo(f"\nError loading template '{name}': {e}")
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"\nError parsing template '{name}': {e}")
        raise typer.Exit(1)

    # Render the template
    renderer = TemplateRenderer()
    if detail:
        renderer.render_detail(compiled_template, extends)
    else:
        renderer.render_table(compiled_template, extends)


def _list_templates() -> None:
    """List all available templates."""
    ctx = get_context()
    config = ctx.config
    template_dir = config.template_dir

    # Display template directory
    typer.echo("Template Directory:")
    typer.echo(f"  Path: {template_dir.resolve()}")
    typer.echo()

    # Find all template files
    if not template_dir.exists():
        typer.echo("No templates found (directory does not exist)")
        return

    template_files = sorted(template_dir.glob("*.json"))

    if not template_files:
        typer.echo("No templates found")
        return

    # Display available templates header
    typer.echo(f"Available Templates ({len(template_files)}):")
    typer.echo()

    # Collect template data
    templates_data = []
    template_dir_resolved = template_dir.resolve()
    for template_file in template_files:
        template_name = template_file.stem  # filename without .json extension

        # Get relative path for display
        try:
            file_path = template_file.resolve().relative_to(template_dir_resolved)
        except ValueError:
            # Fallback to just the filename if relative path fails
            file_path = Path(template_file.name)

        # Read extends from JSON file first (before loading/merging)
        extends = None
        try:
            with open(template_file, "r") as f:
                raw_data = json.load(f)
                extends = raw_data.get("extends")
        except Exception:
            pass

        # Try to load template to get details
        try:
            template_obj = load_template(template_name, template_dir)
            version = template_obj.version
            event_type_count = len(template_obj.types) if template_obj.types else 0
            location_count = len(template_obj.locations) if template_obj.locations else 0

            templates_data.append(
                {
                    "name": template_name,
                    "version": version,
                    "event_types": event_type_count,
                    "locations": location_count,
                    "extends": extends,
                    "path": str(file_path),
                }
            )
        except Exception as e:
            # If we can't load it, still show it with error
            templates_data.append(
                {
                    "name": template_name,
                    "version": "error",
                    "event_types": "-",
                    "locations": "-",
                    "extends": extends or "-",
                    "path": str(file_path),
                    "error": str(e),
                }
            )

    # Print table header
    typer.echo(
        f"{'NAME':<20}  {'VERSION':<10}  {'TYPES':>6}  {'LOCATIONS':>9}  {'EXTENDS':<15}  {'PATH'}"
    )

    # Print table rows
    for template_data in templates_data:
        name = template_data["name"]
        version = template_data["version"]
        event_types = str(template_data["event_types"])
        locations = str(template_data["locations"])
        extends = template_data.get("extends") or ""
        path = template_data["path"]

        typer.echo(
            f"{name:<20}  {version:<10}  {event_types:>6}  {locations:>9}  {extends:<15}  {path}"
        )
