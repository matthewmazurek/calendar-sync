"""Template models for configurable event processing."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LocationConfig(BaseModel):
    """Location configuration with address and geo coordinates."""

    address: Optional[str] = None
    geo: Optional[tuple[float, float]] = None
    apple_title: Optional[str] = None


class OvernightConfig(BaseModel):
    """Configuration for overnight event handling."""

    as_: Literal["split", "all_day", "keep"] = Field(alias="as")
    format: str = "{title} {time_range}"


class ConsolidateConfig(BaseModel):
    """Configuration for event consolidation."""

    group_by: Literal["title", "label"]
    pattern_aware: bool = False


class EventTypeConfig(BaseModel):
    """Configuration for an event type."""

    match: str | list[str]
    match_mode: Literal["contains", "regex"] = "contains"
    label: Optional[str] = None
    location: Optional[str] = None
    consolidate: str | ConsolidateConfig | Literal[False] | None = None
    overnight: str | OvernightConfig | None = None
    time_periods: Optional[dict[str, tuple[str, str]]] = None


class TemplateSettings(BaseModel):
    """Global template settings."""

    time_format: Literal["12h", "24h"] = "12h"


class TemplateDefaults(BaseModel):
    """Default values inherited by event types."""

    location: Optional[str] = None
    consolidate: str | ConsolidateConfig | Literal[False] = "title"
    overnight: str | OvernightConfig = "split"
    time_periods: dict[str, tuple[str, str]] = Field(
        default={"AM": ("0800", "1200"), "PM": ("1300", "1700")}
    )


class CalendarTemplate(BaseModel):
    """Complete calendar template configuration."""

    name: str
    version: str = "1.0"
    extends: Optional[str] = None
    settings: TemplateSettings = TemplateSettings()
    locations: dict[str, LocationConfig] = {}
    defaults: TemplateDefaults = TemplateDefaults()
    types: dict[str, EventTypeConfig]
