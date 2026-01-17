"""Template loader for loading and caching calendar templates."""

import json
import logging
from pathlib import Path

from app.models.template import CalendarTemplate

logger = logging.getLogger(__name__)

# Cache for loaded templates
_template_cache: dict[str, CalendarTemplate] = {}


def _merge_template_data(base_data: dict, extending_data: dict) -> dict:
    """
    Merge extending template data over base template data.

    Args:
        base_data: Base template data
        extending_data: Extending template data

    Returns:
        Merged template data
    """
    merged = base_data.copy()

    # Merge settings
    if "settings" in extending_data:
        merged["settings"] = {
            **base_data.get("settings", {}),
            **extending_data["settings"],
        }

    # Merge locations (extending locations override base locations)
    if "locations" in extending_data:
        merged["locations"] = {
            **base_data.get("locations", {}),
            **extending_data["locations"],
        }

    # Merge defaults
    if "defaults" in extending_data:
        base_defaults = base_data.get("defaults", {})
        extending_defaults = extending_data["defaults"]
        merged["defaults"] = {
            **base_defaults,
            **extending_defaults,
            # Deep merge time_periods
            "time_periods": {
                **base_defaults.get("time_periods", {}),
                **extending_defaults.get("time_periods", {}),
            },
        }

    # Merge types (deep merge - extending type configs merge with base type configs)
    if "types" in extending_data:
        base_types = base_data.get("types", {})
        extending_types = extending_data["types"]
        merged_types = {**base_types}
        for type_name, type_config in extending_types.items():
            if type_name in merged_types:
                # Deep merge: base config + extending config overrides
                merged_types[type_name] = {**merged_types[type_name], **type_config}
            else:
                # New type not in base
                merged_types[type_name] = type_config
        merged["types"] = merged_types

    # Override name and version from extending template
    if "name" in extending_data:
        merged["name"] = extending_data["name"]
    if "version" in extending_data:
        merged["version"] = extending_data["version"]

    # Remove extends field from merged result (it's only used during loading)
    merged.pop("extends", None)

    return merged


def load_template(template_name: str, template_dir: Path) -> CalendarTemplate:
    """
    Load a template from disk, using cache if available.
    Handles template extensions by loading base templates and merging.

    Args:
        template_name: Name of template (without .json extension)
        template_dir: Directory containing template files

    Returns:
        Loaded CalendarTemplate

    Raises:
        FileNotFoundError: If template file doesn't exist
        ValueError: If template JSON is invalid
    """
    # Check cache first
    cache_key = f"{template_dir}/{template_name}"
    if cache_key in _template_cache:
        return _template_cache[cache_key]

    # Load from file
    template_path = template_dir / f"{template_name}.json"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    try:
        with open(template_path, "r") as f:
            data = json.load(f)

        # Check if template extends another template
        extends_name = data.get("extends")
        if extends_name:
            # Load base template first (recursive, may also extend)
            base_template = load_template(extends_name, template_dir)
            # Merge extending template data over base template data
            # Use by_alias=True to get JSON-compatible format (with aliases like 'as' instead of 'as_')
            # Then serialize to JSON and parse back to ensure all nested models use aliases
            base_data = base_template.model_dump(by_alias=True)
            # Convert to JSON and back to ensure nested models also use aliases
            base_json = json.dumps(base_data)
            base_data = json.loads(base_json)
            merged_data = _merge_template_data(base_data, data)
            template = CalendarTemplate(**merged_data)
        else:
            template = CalendarTemplate(**data)

        _template_cache[cache_key] = template
        logger.info(f"Loaded template: {template_name} from {template_path}")
        return template
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in template {template_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Failed to load template {template_path}: {e}") from e


def build_default_template() -> CalendarTemplate:
    """Build a minimal fallback template with no intervention."""
    return CalendarTemplate(
        name="default_fallback",
        version="1.0",
        settings={"time_format": "12h"},
        locations={},
        defaults={
            "consolidate": False,
            "overnight": "keep",
            "time_periods": {},
        },
        types={},
    )


def get_template(template_name: str | None, template_dir: Path) -> CalendarTemplate:
    """
    Get a template by name, or return a minimal fallback if name is None.

    Args:
        template_name: Name of template (without .json extension), or None
        template_dir: Directory containing template files

    Returns:
        CalendarTemplate
    """
    if template_name is None:
        logger.warning(
            "No template configured - using minimal fallback (no consolidation or time inference)."
        )
        return build_default_template()
    return load_template(template_name, template_dir)


def clear_cache() -> None:
    """Clear the template cache (useful for testing)."""
    _template_cache.clear()
