"""Export calendar JSON to ICS format."""

import logging
import sys

import typer
from typing_extensions import Annotated

from app.exceptions import CalendarNotFoundError, ExportError
from app.models.template_loader import get_template
from cli.context import get_context

logger = logging.getLogger(__name__)


def export_command(
    calendar_name: Annotated[
        str,
        typer.Argument(help="Calendar name to export"),
    ],
    template_name: Annotated[
        str | None,
        typer.Option(
            "--template", "-t", help="Template name for resolving location_id (overrides stored template)"
        ),
    ] = None,
) -> None:
    """
    Export calendar JSON to ICS format.
    
    Reads the calendar_data.json file and generates calendar.ics,
    resolving any location_id references using the template.
    
    If the calendar metadata contains a template_name, that template
    will be used by default. Use --template to override.
    """
    ctx = get_context()
    config = ctx.config
    repository = ctx.repository

    # Load calendar to check if it exists and get metadata
    calendar_with_metadata = repository.load_calendar(calendar_name)
    if calendar_with_metadata is None:
        logger.error(f"Calendar '{calendar_name}' not found")
        sys.exit(1)

    metadata = calendar_with_metadata.metadata

    # Determine template to use
    effective_template_name = template_name or metadata.template_name or config.default_template
    template = None
    
    if effective_template_name:
        try:
            template = get_template(effective_template_name, config.template_dir)
            logger.info(f"Using template: {template.name} (version {template.version})")
        except FileNotFoundError:
            logger.warning(f"Template '{effective_template_name}' not found, exporting without template")
            template = None

    # Export to ICS
    try:
        ics_path = repository.export_ics(calendar_name, template=template)
        
        print(f"{typer.style('✓', fg=typer.colors.GREEN, bold=True)} Exported ICS")
        print(f"  {ics_path.resolve()}")
        
        if template:
            print(f"  Template: {template.name} (v{template.version})")
        
        logger.info(f"Exported calendar '{calendar_name}' to {ics_path}")
        
    except CalendarNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except ExportError as e:
        logger.error(f"Export failed: {e}")
        print(
            f"\n{typer.style('Hint:', bold=True)} If location_id references are failing, "
            f"ensure the template defines all referenced locations."
        )
        sys.exit(1)


def export_all_command(
    template_name: Annotated[
        str | None,
        typer.Option(
            "--template", "-t", help="Template name for resolving location_id"
        ),
    ] = None,
) -> None:
    """
    Export all calendars to ICS format.
    
    Iterates through all calendars and exports each one to ICS.
    """
    ctx = get_context()
    repository = ctx.repository

    calendars = repository.list_calendars()
    if not calendars:
        print("No calendars found.")
        return

    print(f"Exporting {len(calendars)} calendars...")
    
    success = 0
    failed = 0
    
    for calendar_name in calendars:
        try:
            # Load calendar to get metadata
            calendar_with_metadata = repository.load_calendar(calendar_name)
            if calendar_with_metadata is None:
                logger.warning(f"Skipping '{calendar_name}': not found")
                failed += 1
                continue

            metadata = calendar_with_metadata.metadata
            
            # Determine template
            effective_template_name = template_name or metadata.template_name or ctx.config.default_template
            template = None
            
            if effective_template_name:
                try:
                    template = get_template(effective_template_name, ctx.config.template_dir)
                except FileNotFoundError:
                    pass

            # Export
            ics_path = repository.export_ics(calendar_name, template=template)
            print(f"  {typer.style('✓', fg=typer.colors.GREEN)} {calendar_name}")
            success += 1
            
        except Exception as e:
            print(f"  {typer.style('✗', fg=typer.colors.RED)} {calendar_name}: {e}")
            failed += 1

    print(f"\nExported: {success}, Failed: {failed}")


# Alias for CLI registration
export = export_command
