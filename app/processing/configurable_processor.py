"""Configurable event processor driven by template rules."""

import logging
from collections import defaultdict
from datetime import date, time, timedelta
from typing import Literal

from app.models.event import Event
from app.models.template import (
    CalendarTemplate,
    ConsolidateConfig,
    EventTypeConfig,
    OvernightConfig,
)
from app.processing.template_utils import (
    detect_shift_pattern,
    format_title,
    is_overnight,
)

logger = logging.getLogger(__name__)


def are_consecutive_dates(date1: date, date2: date) -> bool:
    """Check if two dates are consecutive."""
    return (date2 - date1).days == 1


def resolve_consolidate_config(
    config: str | ConsolidateConfig | Literal[False] | None,
    defaults,
) -> ConsolidateConfig | Literal[False] | None:
    """Resolve consolidate config from shorthand or object."""
    if config is False:
        return False
    if config is None:
        # Use default
        default_consolidate = defaults.consolidate
        if isinstance(default_consolidate, str):
            return ConsolidateConfig(group_by=default_consolidate, pattern_aware=False)
        return default_consolidate
    if isinstance(config, str):
        return ConsolidateConfig(group_by=config, pattern_aware=False)
    return config


def resolve_overnight_config(
    config: str | OvernightConfig | None, defaults
) -> OvernightConfig:
    """Resolve overnight config from shorthand or object."""
    if config is None:
        default_overnight = defaults.overnight
        if isinstance(default_overnight, str):
            return OvernightConfig(
                **{"as": default_overnight, "format": "{title} {time_range}"}
            )
        return default_overnight
    if isinstance(config, str):
        return OvernightConfig(**{"as": config, "format": "{title} {time_range}"})
    return config


class ConfigurableEventProcessor:
    """Event processor driven by template configuration."""

    def __init__(self, template: CalendarTemplate):
        """Initialize processor with template."""
        self.template = template

    def process(self, events: list[Event]) -> list[Event]:
        """Process events using template rules."""
        if not events:
            return []

        # Group events by type
        by_type: dict[str | None, list[Event]] = defaultdict(list)
        for event in events:
            type_name = event.type
            by_type[type_name].append(event)

        processed_events = []
        for type_name, type_events in by_type.items():
            if type_name is None:
                # No type assigned - use defaults
                processed_events.extend(self._process_with_defaults(type_events))
            else:
                # Template types are keyed by their template name (user-defined)
                # Try exact match first, then lowercase (for backward compatibility)
                type_config = self.template.types.get(
                    type_name
                ) or self.template.types.get(type_name.lower())
                if type_config:
                    processed_events.extend(
                        self._process_type(type_events, type_config)
                    )
                else:
                    # Type not in template - use defaults
                    processed_events.extend(self._process_with_defaults(type_events))

        # Sort by date
        processed_events.sort(key=lambda e: e.date)

        return processed_events

    def _process_with_defaults(self, events: list[Event]) -> list[Event]:
        """Process events using default template settings."""
        defaults = self.template.defaults
        consolidate_config = resolve_consolidate_config(None, defaults)
        overnight_config = resolve_overnight_config(None, defaults)

        # Apply overnight transforms
        transformed = self._apply_overnight_transforms(events, overnight_config)

        # Apply consolidation (pass overnight_config for pattern-aware)
        if consolidate_config and consolidate_config.pattern_aware:
            consolidated, _ = self._apply_consolidation_with_overnight(
                transformed, consolidate_config, overnight_config
            )
        else:
            consolidated = self._apply_consolidation(transformed, consolidate_config)

        # Assign locations
        return self._assign_locations(consolidated, defaults.location)

    def _process_type(
        self, events: list[Event], type_config: EventTypeConfig
    ) -> list[Event]:
        """Process events of a specific type."""
        # Resolve configs
        consolidate_config = resolve_consolidate_config(
            type_config.consolidate, self.template.defaults
        )
        overnight_config = resolve_overnight_config(
            type_config.overnight, self.template.defaults
        )

        # For pattern-aware consolidation, we need to track overnight dates BEFORE transforming
        # Apply consolidation (returns consolidated events and overnight dates for mixed stretches)
        consolidated, overnight_dates = self._apply_consolidation_with_overnight(
            events, consolidate_config, overnight_config
        )

        # Generate overnight events if needed (for pattern-aware consolidation)
        if consolidate_config and consolidate_config.pattern_aware:
            if overnight_dates:
                # Generate separate overnight events for mixed stretches
                overnight_events = self._generate_overnight_events(
                    overnight_dates, events, type_config, overnight_config
                )
                consolidated.extend(overnight_events)
            # For pattern-aware, don't apply overnight transforms to consolidated events
            # (uniform_24h stays as 24h, uniform_day stays as day, mixed gets day + overnight)
        else:
            # Apply overnight transforms for non-pattern-aware consolidation
            consolidated = self._apply_overnight_transforms(
                consolidated, overnight_config
            )

        # Assign locations
        location = type_config.location or self.template.defaults.location
        return self._assign_locations(consolidated, location)

    def _apply_overnight_transforms(
        self, events: list[Event], overnight_config: OvernightConfig
    ) -> list[Event]:
        """Apply overnight transform to events."""
        if overnight_config.as_ == "keep":
            # For keep mode, ensure end_date is set for overnight events
            result = []
            for event in events:
                if is_overnight(event) and event.end_date is None:
                    # Set end_date to next day
                    updated_event = event.model_copy(
                        update={"end_date": event.date + timedelta(days=1)}
                    )
                    result.append(updated_event)
                else:
                    result.append(event)
            return result

        result = []
        for event in events:
            if not is_overnight(event):
                result.append(event)
                continue

            if overnight_config.as_ == "split":
                # Split at midnight
                first_event = Event(
                    title=event.title,
                    date=event.date,
                    start=event.start,
                    end=None,  # End at midnight
                    location=event.location,
                    location_geo=event.location_geo,
                    location_apple_title=event.location_apple_title,
                    type=event.type,
                    label=event.label,
                )
                second_event = Event(
                    title=event.title,
                    date=(
                        event.end_date
                        if event.end_date
                        else event.date + timedelta(days=1)
                    ),
                    start=None,  # Start at midnight
                    end=event.end,
                    location=event.location,
                    location_geo=event.location_geo,
                    location_apple_title=event.location_apple_title,
                    type=event.type,
                    label=event.label,
                )
                result.extend([first_event, second_event])
            elif overnight_config.as_ == "all_day":
                # Convert to all-day with formatted title
                label = event.label or ""
                formatted_title = format_title(
                    overnight_config.format, event, label, self.template.settings
                )
                all_day_event = Event(
                    title=formatted_title,
                    date=event.date,
                    location=event.location,
                    location_geo=event.location_geo,
                    location_apple_title=event.location_apple_title,
                    type=event.type,
                    label=event.label,
                )
                result.append(all_day_event)
            else:
                result.append(event)

        return result

    def _apply_consolidation(
        self,
        events: list[Event],
        consolidate_config: ConsolidateConfig | Literal[False] | None,
    ) -> list[Event]:
        """Apply consolidation rules to events."""
        consolidated, _ = self._apply_consolidation_with_overnight(
            events, consolidate_config
        )
        return consolidated

    def _apply_consolidation_with_overnight(
        self,
        events: list[Event],
        consolidate_config: ConsolidateConfig | Literal[False] | None,
        overnight_config: OvernightConfig | None = None,
    ) -> tuple[list[Event], list[date]]:
        """Apply consolidation rules to events, returning overnight dates for mixed stretches."""
        if consolidate_config is False or consolidate_config is None:
            return events, []

        # Group events by group_by key
        if consolidate_config.group_by == "label":
            key_func = lambda e: e.label or ""
        else:  # title
            key_func = lambda e: e.title

        by_key = defaultdict(list)
        for event in events:
            key = key_func(event)
            by_key[key].append(event)

        consolidated = []
        all_overnight_dates = []
        for key, key_events in by_key.items():
            if consolidate_config.pattern_aware:
                # Pattern-aware consolidation
                consolidated_events, overnight_dates = self._consolidate_pattern_aware(
                    key_events, consolidate_config, overnight_config
                )
                consolidated.extend(consolidated_events)
                all_overnight_dates.extend(overnight_dates)
            else:
                # Simple consolidation
                consolidated.extend(
                    self._consolidate_simple(key_events, consolidate_config)
                )

        return consolidated, all_overnight_dates

    def _consolidate_simple(
        self, events: list[Event], consolidate_config: ConsolidateConfig | None = None
    ) -> list[Event]:
        """Simple consolidation by consecutive dates."""
        if not events:
            return []

        # Sort by date
        events.sort(key=lambda e: e.date)
        events_by_date = {e.date: e for e in events}
        all_dates = sorted(events_by_date.keys())

        consolidated = []
        start_idx = 0
        while start_idx < len(all_dates):
            end_idx = start_idx
            while end_idx + 1 < len(all_dates) and are_consecutive_dates(
                all_dates[end_idx], all_dates[end_idx + 1]
            ):
                end_idx += 1

            first_date = all_dates[start_idx]
            last_date = all_dates[end_idx]
            first_event = events_by_date[first_date]

            stretch_events = [
                events_by_date[d] for d in all_dates[start_idx : end_idx + 1]
            ]
            if consolidate_config and consolidate_config.only_all_day:
                if any(
                    e.start is not None or e.end is not None for e in stretch_events
                ):
                    consolidated.extend(stretch_events)
                    start_idx = end_idx + 1
                    continue
            if consolidate_config and consolidate_config.require_same_times:
                time_pairs = {(e.start, e.end) for e in stretch_events}
                if len(time_pairs) > 1:
                    consolidated.extend(stretch_events)
                    start_idx = end_idx + 1
                    continue

            if start_idx == end_idx:
                consolidated.append(first_event)
            else:
                consolidated_event = Event(
                    title=first_event.title,
                    date=first_date,
                    end_date=last_date,
                    location=first_event.location,
                    location_geo=first_event.location_geo,
                    location_apple_title=first_event.location_apple_title,
                    start=first_event.start,
                    end=first_event.end,
                    type=first_event.type,
                    label=first_event.label,
                )
                consolidated.append(consolidated_event)

            start_idx = end_idx + 1

        return consolidated

    def _consolidate_pattern_aware(
        self,
        events: list[Event],
        consolidate_config: ConsolidateConfig,
        overnight_config: OvernightConfig | None = None,
    ) -> tuple[list[Event], list[date]]:
        """Pattern-aware consolidation that detects uniform vs mixed stretches."""
        if not events:
            return [], []

        # Sort by date
        events.sort(key=lambda e: e.date)
        events_by_date = {e.date: e for e in events}
        all_dates = sorted(events_by_date.keys())

        # Find consecutive stretches (don't break on pattern changes)
        stretches = self._detect_consecutive_stretches(all_dates)

        consolidated = []
        overnight_dates = []
        for stretch_dates in stretches:
            stretch_events = [events_by_date[d] for d in stretch_dates]
            pattern = detect_shift_pattern(stretch_events)

            if pattern == "uniform_24h":
                # All 24h - consolidate as all-day if overnight config says so, otherwise as 24h
                first_event = stretch_events[0]
                # If overnight config is "all_day", create all-day event
                if overnight_config and overnight_config.as_ == "all_day":
                    consolidated_event = Event(
                        title=first_event.title,
                        date=stretch_dates[0],
                        end_date=stretch_dates[-1],
                        start=None,  # All-day event
                        end=None,  # All-day event
                        location=first_event.location,
                        location_geo=first_event.location_geo,
                        location_apple_title=first_event.location_apple_title,
                        type=first_event.type,
                        label=first_event.label,
                    )
                else:
                    # Keep as 24h timed event
                    consolidated_event = Event(
                        title=first_event.title,
                        date=stretch_dates[0],
                        end_date=stretch_dates[-1],
                        start=first_event.start,
                        end=first_event.end,
                        location=first_event.location,
                        location_geo=first_event.location_geo,
                        location_apple_title=first_event.location_apple_title,
                        type=first_event.type,
                        label=first_event.label,
                    )
                consolidated.append(consolidated_event)
            elif pattern == "uniform_day":
                # All day-only - consolidate as all-day if overnight config says so
                if overnight_config and overnight_config.as_ == "all_day":
                    # Convert to all-day events before consolidating
                    all_day_events = [
                        Event(
                            title=e.title,
                            date=e.date,
                            start=None,
                            end=None,
                            location=e.location,
                            location_geo=e.location_geo,
                            location_apple_title=e.location_apple_title,
                            type=e.type,
                            label=e.label,
                        )
                        for e in stretch_events
                    ]
                    consolidated.extend(
                        self._consolidate_simple(all_day_events, consolidate_config)
                    )
                else:
                    consolidated.extend(
                        self._consolidate_simple(stretch_events, consolidate_config)
                    )
            else:  # mixed
                # Mixed - consolidate day portion as all-day event, track overnight dates
                day_events = []
                for event in stretch_events:
                    if is_overnight(event):
                        overnight_dates.append(event.date)
                        # Create day-only version for consolidation (all-day, no times)
                        day_event = Event(
                            title=event.title,
                            date=event.date,
                            start=None,  # All-day event, no start time
                            end=None,  # All-day event, no end time
                            location=event.location,
                            location_geo=event.location_geo,
                            location_apple_title=event.location_apple_title,
                            type=event.type,
                            label=event.label,
                        )
                        day_events.append(day_event)
                    else:
                        # Convert day-only events to all-day for consolidation
                        day_event = Event(
                            title=event.title,
                            date=event.date,
                            start=None,  # All-day event, no start time
                            end=None,  # All-day event, no end time
                            location=event.location,
                            location_geo=event.location_geo,
                            location_apple_title=event.location_apple_title,
                            type=event.type,
                            label=event.label,
                        )
                        day_events.append(day_event)

                # Consolidate day portion as all-day events
                if day_events:
                    consolidated.extend(
                        self._consolidate_simple(day_events, consolidate_config)
                    )

        return consolidated, overnight_dates

    def _detect_consecutive_stretches(self, all_dates: list[date]) -> list[list[date]]:
        """Detect stretches of consecutive dates (don't break on pattern changes)."""
        if not all_dates:
            return []

        stretches = []
        current_stretch = [all_dates[0]]

        for i in range(1, len(all_dates)):
            if are_consecutive_dates(all_dates[i - 1], all_dates[i]):
                # Consecutive - continue stretch
                current_stretch.append(all_dates[i])
            else:
                # Gap - start new stretch
                stretches.append(current_stretch)
                current_stretch = [all_dates[i]]

        if current_stretch:
            stretches.append(current_stretch)

        return stretches

    def _generate_overnight_events(
        self,
        overnight_dates: list[date],
        original_events: list[Event],
        type_config: EventTypeConfig,
        overnight_config: OvernightConfig,
    ) -> list[Event]:
        """Generate separate overnight events for dates that had overnight in mixed stretches."""
        if overnight_config.as_ != "all_day":
            # Only generate overnight events when using all_day mode
            return []

        # Create a map of date -> original event for overnight dates
        original_by_date = {e.date: e for e in original_events if is_overnight(e)}

        overnight_events = []
        for overnight_date in overnight_dates:
            original_event = original_by_date.get(overnight_date)
            if not original_event:
                continue

            # Create a temporary event with overnight time range for formatting
            # Overnight portion starts at 1700 (day ends) and goes to the original end time
            overnight_start = time(17, 0)  # Day portion ends at 1700
            overnight_end = original_event.end  # Original end time (e.g., 0800)

            # Create temporary event with overnight times for title formatting
            temp_event = Event(
                title=original_event.title,
                date=original_event.date,
                start=overnight_start,
                end=overnight_end,
                location=original_event.location,
                location_geo=original_event.location_geo,
                location_apple_title=original_event.location_apple_title,
                type=original_event.type,
                label=original_event.label,
            )

            # Format title using template with overnight time range
            label = original_event.label or ""
            formatted_title = format_title(
                overnight_config.format, temp_event, label, self.template.settings
            )

            # Create all-day overnight event
            overnight_event = Event(
                title=formatted_title,
                date=overnight_date,
                location=original_event.location,
                location_geo=original_event.location_geo,
                location_apple_title=original_event.location_apple_title,
                type=original_event.type,
                label=original_event.label,
            )
            overnight_events.append(overnight_event)

        return overnight_events

    def _assign_locations(
        self, events: list[Event], location_ref: str | None
    ) -> list[Event]:
        """Assign location references to events.
        
        Sets location_id instead of expanding location details.
        Location resolution happens at export time.
        """
        if location_ref is None:
            return events

        # Validate that location exists in template
        location_config = self.template.locations.get(location_ref)
        if not location_config:
            logger.warning(f"Location '{location_ref}' not found in template")
            return events

        result = []
        for event in events:
            # Only set location_id if event doesn't already have a location
            if not event.location and not event.location_id:
                # Set location_id reference (will be resolved at export time)
                updated_event = event.model_copy(update={"location_id": location_ref})
                result.append(updated_event)
            else:
                # Event already has location or location_id - keep as-is
                result.append(event)

        return result
