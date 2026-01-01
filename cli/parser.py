"""CLI argument parsing and command routing."""

import argparse
import logging
import sys
import traceback

from app.exceptions import CalendarError
from cli.commands import (
    delete_command,
    git_setup_command,
    info_command,
    ls_command,
    publish_command,
    restore_command,
    sync_command,
)

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Calendar sync tool with simplified sync command."
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync (or create new) calendar file from data file",
    )
    sync_parser.add_argument(
        "calendar_data_file", type=str, help="Path to input calendar file"
    )
    sync_parser.add_argument(
        "calendar_name", type=str, help="Name of calendar to create or update"
    )
    sync_parser.add_argument(
        "--year", type=int, help="Year to replace (for composition)"
    )
    sync_parser.add_argument(
        "--format",
        choices=["ics", "json"],
        default="ics",
        help="Output format (default: ics)",
    )
    sync_parser.add_argument(
        "--publish",
        action="store_true",
        help="Commit and push calendar changes to git after saving",
    )

    # ls command (list calendars or versions)
    ls_parser = subparsers.add_parser(
        "ls",
        help="List calendars or versions",
        description="List all calendars, or versions for a specific calendar.",
    )
    ls_parser.add_argument(
        "name",
        nargs="?",
        help="Calendar name. If provided, lists versions for that calendar.",
    )
    ls_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        dest="show_all",
        help="Show all versions (overrides --limit). Only applies when listing versions.",
    )
    ls_parser.add_argument(
        "--archived",
        action="store_true",
        dest="include_archived",
        help="Include archived calendars (removed from filesystem but preserved in git history). Only applies when listing calendars.",
    )
    ls_parser.add_argument(
        "-l",
        "--long",
        action="store_true",
        dest="show_info",
        help="Show detailed information (file path, size, event count)",
    )
    ls_parser.add_argument(
        "-n",
        "--limit",
        type=int,
        metavar="N",
        help="Limit number of versions to show (default: from LS_DEFAULT_LIMIT config). Ignored when --all is used.",
    )

    # restore command
    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore calendar from git commit, version number, or relative command",
    )
    restore_parser.add_argument("name", help="Calendar name")
    restore_parser.add_argument(
        "commit",
        help="Git commit hash, version number (#3 or 3), or relative command (latest, previous)",
    )
    restore_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompt",
    )

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
    delete_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompt",
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

    # Git setup command
    git_setup_parser = subparsers.add_parser(
        "git-setup", help="Initialize git repository in calendar directory"
    )
    git_setup_parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete local and remote git repository (with confirmation)",
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
        if args.command == "sync":
            sync_command(
                args.calendar_data_file,
                args.calendar_name,
                args.year,
                args.format,
                args.publish,
            )
        elif args.command == "ls":
            ls_command(
                args.name,
                include_archived=getattr(args, "include_archived", False),
                show_info=getattr(args, "show_info", False),
                limit=getattr(args, "limit", None),
                show_all=getattr(args, "show_all", False),
            )
        elif args.command == "restore":
            restore_command(args.name, args.commit, force=getattr(args, "force", False))
        elif args.command == "info":
            info_command(args.name)
        elif args.command == "delete":
            delete_command(
                args.name,
                purge_history=args.purge_history,
                force=getattr(args, "force", False),
            )
        elif args.command == "publish":
            publish_command(args.calendar_name, args.format)
        elif args.command == "git-setup":
            git_setup_command(delete=getattr(args, "delete", False))
    except CalendarError as e:
        logger.error(f"Calendar error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
