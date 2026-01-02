"""Tests for template models and loading."""

import json
import tempfile
from pathlib import Path

import pytest

from app.models.template import (
    CalendarTemplate,
    ConsolidateConfig,
    EventTypeConfig,
    OvernightConfig,
    TemplateDefaults,
    TemplateSettings,
)
from app.models.template_loader import clear_cache, load_template


def test_template_settings_defaults():
    """Test template settings with defaults."""
    settings = TemplateSettings()
    assert settings.time_format == "12h"


def test_template_defaults():
    """Test template defaults."""
    defaults = TemplateDefaults()
    assert defaults.location is None
    assert defaults.consolidate == "title"
    assert defaults.overnight == "split"
    assert "AM" in defaults.time_periods
    assert defaults.time_periods["AM"] == ("0800", "1200")


def test_event_type_config_shorthand():
    """Test event type config with string shorthands."""
    config = EventTypeConfig(match="on call")
    assert config.match == "on call"
    assert config.match_mode == "contains"
    assert config.consolidate is None
    assert config.overnight is None


def test_event_type_config_full():
    """Test event type config with full object configs."""
    consolidate = ConsolidateConfig(group_by="label", pattern_aware=True)
    overnight = OvernightConfig(**{"as": "all_day", "format": "{label} on call {time_range}"})
    config = EventTypeConfig(
        match="on call",
        label="^(.+?)\\s+on call",
        consolidate=consolidate,
        overnight=overnight,
    )
    assert config.match == "on call"
    assert isinstance(config.consolidate, ConsolidateConfig)
    assert config.consolidate.pattern_aware is True
    assert isinstance(config.overnight, OvernightConfig)
    assert config.overnight.as_ == "all_day"


def test_calendar_template_loading():
    """Test loading a complete calendar template."""
    template_data = {
        "name": "test_template",
        "version": "1.0",
        "settings": {"time_format": "12h"},
        "locations": {
            "work": {
                "address": "123 Main St",
                "geo": [51.0, -114.0],
                "apple_title": "Work",
            }
        },
        "defaults": {
            "location": None,
            "consolidate": "title",
            "overnight": "split",
            "time_periods": {"AM": ["0800", "1200"], "PM": ["1300", "1700"]},
        },
        "types": {
            "on_call": {
                "match": "on call",
                "label": "^(.+?)\\s+on call",
                "location": "work",
                "consolidate": {"group_by": "label", "pattern_aware": True},
                "overnight": {"as": "all_day", "format": "{label} on call {time_range}"},
            }
        },
    }

    template = CalendarTemplate(**template_data)
    assert template.name == "test_template"
    assert len(template.types) == 1
    assert "on_call" in template.types
    assert template.types["on_call"].location == "work"


def test_template_loader():
    """Test template loader."""
    clear_cache()

    template_data = {
        "name": "test_loader",
        "version": "1.0",
        "settings": {"time_format": "12h"},
        "locations": {},
        "defaults": {
            "location": None,
            "consolidate": "title",
            "overnight": "split",
            "time_periods": {},
        },
        "types": {"test": {"match": "test"}},
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        template_path = Path(temp_dir) / "test_loader.json"
        with open(template_path, "w") as f:
            json.dump(template_data, f)

        template = load_template("test_loader", Path(temp_dir))
        assert template.name == "test_loader"
        assert "test" in template.types

        # Test caching
        template2 = load_template("test_loader", Path(temp_dir))
        assert template is template2  # Should be same object from cache


def test_template_loader_not_found():
    """Test template loader with missing file."""
    clear_cache()

    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent", Path(temp_dir))


def test_template_loader_invalid_json():
    """Test template loader with invalid JSON."""
    clear_cache()

    with tempfile.TemporaryDirectory() as temp_dir:
        template_path = Path(temp_dir) / "invalid.json"
        with open(template_path, "w") as f:
            f.write("invalid json {")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_template("invalid", Path(temp_dir))
