"""CLI utilities for logging and output formatting."""

import logging
import sys
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)


def log_error(message: str, exit_code: int = 1) -> None:
    """Log error and print to stderr, then exit."""
    logger.error(message)
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(exit_code)


def log_warning(message: str) -> None:
    """Log warning and print to stderr."""
    logger.warning(message)
    print(f"Warning: {message}", file=sys.stderr)


def log_info(message: str, verbose: bool = True) -> None:
    """Log info and optionally print to stdout."""
    logger.info(message)
    if verbose:
        print(message)


def format_processing_summary(processing_summary: Dict) -> None:
    """
    Format and display processing summary.
    
    Args:
        processing_summary: Dictionary with input_counts, output_counts, input_total, output_total
    """
    if not processing_summary:
        return
    
    input_counts = processing_summary.get("input_counts", {})
    output_counts = processing_summary.get("output_counts", {})
    input_total = processing_summary.get("input_total", 0)
    output_total = processing_summary.get("output_total", 0)
    
    if input_counts:
        log_info("Processing (Event type: count):")
        for event_type, count in sorted(input_counts.items()):
            output_count = output_counts.get(event_type, 0)
            if output_count != count:
                log_info(f"  - {event_type.value}: {count} (Collapsed to {output_count})")
            else:
                log_info(f"  - {event_type.value}: {count}")
        
        if output_total != input_total:
            log_info(f"  - Total: {input_total} (Collapsed to {output_total})")
        else:
            log_info(f"  - Total: {input_total}")


def format_relative_time(commit_date: datetime) -> str:
    """
    Format datetime as relative time for recent commits, full datetime for older.
    
    Args:
        commit_date: Datetime to format
        
    Returns:
        Formatted time string
    """
    if commit_date.tzinfo is None:
        # If no timezone, assume UTC
        commit_date = commit_date.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    time_diff = now - commit_date
    
    if time_diff.days == 0:
        if time_diff.seconds < 60:  # Less than 1 minute
            return "just now"
        elif time_diff.seconds < 3600:  # Less than 1 hour
            minutes = time_diff.seconds // 60
            return f"{minutes}m ago"
        else:  # Less than 24 hours
            hours = time_diff.seconds // 3600
            return f"{hours}h ago"
    elif time_diff.days < 7:
        return f"{time_diff.days}d ago"
    else:
        # Show full date and time for older commits
        return commit_date.strftime("%Y-%m-%d %H:%M")
