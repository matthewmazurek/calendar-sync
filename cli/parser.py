"""CLI argument parsing and command routing."""

import argparse
import logging
import sys
import traceback

from app.exceptions import CalendarError
from cli.commands import (
    delete_command,
    info_command,
    ls_command,
    processes_command,
    publish_command,
    restore_command,
)

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Calendar sync tool with simplified processes command."
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Processes command
    processes_parser = subparsers.add_parser(
        "processes", help="Process calendar data file and create or update calendar"
    )
    processes_parser.add_argument(
        "calendar_data_file", type=str, help="Path to input calendar file"
    )
    processes_parser.add_argument(
        "calendar_name", type=str, help="Name of calendar to create or update"
    )
    processes_parser.add_argument(
        "--year", type=int, help="Year to replace (for composition)"
    )
    processes_parser.add_argument(
        "--format",
        choices=["ics", "json"],
        default="ics",
        help="Output format (default: ics)",
    )
    processes_parser.add_argument(
        "--publish",
        action="store_true",
        help="Commit and push calendar changes to git after saving",
    )

    # ls command (list calendars or versions)
    ls_parser = subparsers.add_parser("ls", help="List calendars or versions")
    ls_parser.add_argument(
        "name", nargs="?", help="Calendar name (optional, if provided lists versions)"
    )
    ls_parser.add_argument(
        "--all",
        action="store_true",
        help="Include deleted calendars (those that exist in git history but not in filesystem)",
    )

    # restore command
    restore_parser = subparsers.add_parser(
        "restore", help="Restore calendar from git commit"
    )
    restore_parser.add_argument("name", help="Calendar name")
    restore_parser.add_argument("commit", help="Git commit hash or tag")

    # Info command
    info_parser = subparsers.add_parser(
        "info", help="Display calendar info and event count"
    )
    info_parser.add_argument("name", type=str, help="Calendar name")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a calendar")
    delete_parser.add_argument("name", type=str, help="Calendar name")
    delete_parser.add_argument(
        "--purge-history",
        action="store_true",
        help="Remove calendar from git history entirely (hard delete, rewrites history)",
    )

    # Publish command
    publish_parser = subparsers.add_parser(
        "publish", help="Publish an existing calendar to git"
    )
    publish_parser.add_argument(
        "calendar_name", type=str, help="Name of calendar to publish"
    )
    publish_parser.add_argument(
        "--format",
        choices=["ics", "json"],
        default="ics",
        help="Calendar format (default: ics)",
    )

    return parser


def main() -> None:
    """Main CLI entry point with argument parsing and command routing."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "processes":
            processes_command(
                args.calendar_data_file,
                args.calendar_name,
                args.year,
                args.format,
                args.publish,
            )
        elif args.command == "ls":
            ls_command(args.name, include_deleted=args.all)
        elif args.command == "restore":
            restore_command(args.name, args.commit)
        elif args.command == "info":
            info_command(args.name)
        elif args.command == "delete":
            delete_command(args.name, purge_history=args.purge_history)
        elif args.command == "publish":
            publish_command(args.calendar_name, args.format)
    except CalendarError as e:
        logger.error(f"Calendar error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
