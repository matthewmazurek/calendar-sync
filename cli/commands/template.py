"""Display available templates and template directory."""

from pathlib import Path

from app.config import CalendarConfig
from app.models.template_loader import load_template


def template_command() -> None:
    """Display available templates and template directory."""
    config = CalendarConfig.from_env()
    template_dir = config.template_dir

    # Display template directory
    print("Template Directory:")
    print(f"  Path: {template_dir.resolve()}")
    print()

    # Find all template files
    if not template_dir.exists():
        print("No templates found (directory does not exist)")
        return

    template_files = sorted(template_dir.glob("*.json"))

    if not template_files:
        print("No templates found")
        return

    # Display available templates header
    print(f"Available Templates ({len(template_files)}):")
    print()

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
            import json

            with open(template_file, "r") as f:
                raw_data = json.load(f)
                extends = raw_data.get("extends")
        except Exception:
            pass

        # Try to load template to get details
        try:
            template = load_template(template_name, template_dir)
            version = template.version
            event_type_count = len(template.types) if template.types else 0
            location_count = len(template.locations) if template.locations else 0

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
    print(
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

        print(
            f"{name:<20}  {version:<10}  {event_types:>6}  {locations:>9}  {extends:<15}  {path}"
        )
