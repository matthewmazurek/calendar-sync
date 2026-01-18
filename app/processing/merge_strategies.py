"""Merge strategies for combining calendar events."""

from dataclasses import dataclass
from datetime import date

from app.models.event import Event


@dataclass
class ReplaceByRange:
    """Replace all events within date range with new events."""
    
    start_date: date
    end_date: date


@dataclass
class ReplaceByYear:
    """Convenience: replace all events for a specific year."""
    
    year: int
    
    def to_range(self) -> ReplaceByRange:
        """Convert to ReplaceByRange covering the entire year."""
        return ReplaceByRange(date(self.year, 1, 1), date(self.year, 12, 31))


@dataclass
class Add:
    """Add new events without removing any existing events."""
    
    pass


@dataclass
class UpsertById:
    """Match events by uid: update if exists, insert if new.
    
    Events without uid are preserved from existing calendar.
    New events without uid are added.
    """
    
    pass


# Type alias for all merge strategies
MergeStrategy = ReplaceByRange | ReplaceByYear | Add | UpsertById


def infer_year(events: list[Event]) -> int | None:
    """Return year if all events are from same year, else None.
    
    Args:
        events: List of events to check
        
    Returns:
        The year if all events are from the same year, None otherwise
    """
    if not events:
        return None
    years = {e.date.year for e in events}
    return years.pop() if len(years) == 1 else None


def merge_events(
    existing: list[Event],
    new: list[Event],
    strategy: MergeStrategy,
) -> list[Event]:
    """Merge new events into existing events using the specified strategy.
    
    Args:
        existing: Existing calendar events
        new: New events to merge in
        strategy: The merge strategy to use
        
    Returns:
        Merged list of events
    """
    match strategy:
        case ReplaceByYear() as s:
            # Convert to range and use range logic
            range_strategy = s.to_range()
            return _merge_by_range(existing, new, range_strategy)
        
        case ReplaceByRange() as range_strategy:
            return _merge_by_range(existing, new, range_strategy)
        
        case Add():
            return existing + new
        
        case UpsertById():
            return _merge_by_uid(existing, new)
    
    # Should never reach here, but satisfy type checker
    raise ValueError(f"Unknown merge strategy: {strategy}")


def _merge_by_range(
    existing: list[Event],
    new: list[Event],
    strategy: ReplaceByRange,
) -> list[Event]:
    """Replace all events within date range with new events."""
    # Remove events in range from existing
    filtered = [
        e for e in existing
        if not (strategy.start_date <= e.date <= strategy.end_date)
    ]
    # Add all new events
    return filtered + new


def _merge_by_uid(
    existing: list[Event],
    new: list[Event],
) -> list[Event]:
    """Merge events by uid: update if exists, insert if new.
    
    Logic:
    - Events without uid in existing are always kept
    - For events with uid in existing:
      - If uid is in new events, replace with new version
      - If uid is not in new events, keep existing
    - All new events are added (replacing any existing with same uid)
    """
    # Build uid -> event map from new events
    new_by_uid = {e.uid: e for e in new if e.uid}
    new_without_uid = [e for e in new if not e.uid]
    
    result = []
    
    # Process existing events
    for event in existing:
        if not event.uid:
            # No uid, always keep
            result.append(event)
        elif event.uid in new_by_uid:
            # Has uid that's in new - will be replaced by new version
            pass
        else:
            # Has uid that's not in new - keep existing
            result.append(event)
    
    # Add all new events with uid (these replace any existing with same uid)
    result.extend(new_by_uid.values())
    
    # Add all new events without uid
    result.extend(new_without_uid)
    
    return result
