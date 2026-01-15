"""Template models for configurable event processing."""

from typing import Literal

from pydantic import BaseModel, Field


class LocationConfig(BaseModel):
    """Location configuration with address and geo coordinates."""

    address: str | None = None
    geo: tuple[float, float] | None = None
    apple_title: str | None = None


class OvernightConfig(BaseModel):
    """Configuration for overnight event handling."""

    as_: Literal["split", "all_day", "keep"] = Field(alias="as")
    format: str = "{title} {time_range}"


class ConsolidateConfig(BaseModel):
    """Configuration for event consolidation."""

    group_by: Literal["title", "label"]
    pattern_aware: bool = False
    only_all_day: bool = False
    require_same_times: bool = False


class EventTypeConfig(BaseModel):
    """Configuration for an event type."""

    match: str | list[str]
    match_mode: Literal["contains", "regex"] = "contains"
    label: str | None = None
    location: str | None = None
    consolidate: str | ConsolidateConfig | Literal[False] | None = None
    overnight: str | OvernightConfig | None = None
    time_periods: dict[str, tuple[str, str]] | None = None


class TemplateSettings(BaseModel):
    """Global template settings."""

    time_format: Literal["12h", "24h"] = "12h"


class TemplateDefaults(BaseModel):
    """Default values inherited by event types."""

    location: str | None = None
    consolidate: str | ConsolidateConfig | Literal[False] = "title"
    overnight: str | OvernightConfig = "split"
    time_periods: dict[str, tuple[str, str]] = Field(
        default={"AM": ("0800", "1200"), "PM": ("1300", "1700")}
    )


class CalendarTemplate(BaseModel):
    """Complete calendar template configuration."""

    name: str
    version: str = "1.0"
    extends: str | None = None
    settings: TemplateSettings = TemplateSettings()
    locations: dict[str, LocationConfig] = {}
    defaults: TemplateDefaults = TemplateDefaults()
    types: dict[str, EventTypeConfig]
