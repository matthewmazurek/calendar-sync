"""Flask application for calendar sync."""

import logging
import tempfile
from pathlib import Path

from app.utils import temp_file_path

try:
    from flask import Flask, Response, jsonify, request
except ImportError:
    Flask = None  # Fallback if flask not installed

from app.config import CalendarConfig
from app.exceptions import (
    CalendarError,
    CalendarNotFoundError,
    IngestionError,
    InvalidYearError,
    UnsupportedFormatError,
)
from app.ingestion.base import ReaderRegistry
from app.ingestion.ics_reader import ICSReader
from app.ingestion.json_reader import JSONReader
from app.ingestion.word_reader import WordReader
from app.models.template_loader import get_template
from app.output.ics_writer import ICSWriter
from app.processing.calendar_manager import CalendarManager
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService

logger = logging.getLogger(__name__)


def setup_reader_registry() -> ReaderRegistry:
    """Set up reader registry with all readers."""
    registry = ReaderRegistry()
    registry.register(WordReader(), [".doc", ".docx"])
    registry.register(ICSReader(), [".ics"])
    registry.register(JSONReader(), [".json"])
    return registry


def get_ics_writer():
    """Get ICS writer for calendar export."""
    return ICSWriter()


def setup_writer(format: str = "ics"):
    """Get writer for format. Deprecated - use get_ics_writer() instead.

    Kept for backwards compatibility. Always returns ICSWriter.
    """
    return ICSWriter()


def create_app():
    """Create and configure Flask application."""
    if Flask is None:
        raise ImportError("Flask is required for create_app()")

    app = Flask(__name__)

    # Initialize dependencies
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    reader_registry = setup_reader_registry()
    git_service = GitService(
        config.calendar_dir,
        remote_url=config.calendar_git_remote_url,
    )
    repository = CalendarRepository(
        config.calendar_dir, storage, git_service, reader_registry
    )
    manager = CalendarManager(repository)

    def handle_error(error: Exception, default_status: int = 500):
        """Handle errors and return appropriate JSON response."""
        error_type = type(error).__name__
        error_message = str(error)

        if isinstance(error, CalendarNotFoundError):
            status = 404
        elif isinstance(
            error,
            (UnsupportedFormatError, InvalidYearError, IngestionError, CalendarError),
        ):
            status = 400
        else:
            status = default_status

        logger.error(f"{error_type}: {error_message}")
        return jsonify({"error": error_message, "type": error_type}), status

    @app.route("/calendars/<calendar_name>", methods=["POST"])
    def create_or_update_calendar(calendar_name: str):
        """Create or update a calendar from uploaded file."""
        # Check for file upload
        if "file" not in request.files:
            return jsonify({"error": "No file provided", "type": "MissingFile"}), 400

        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"error": "No file provided", "type": "MissingFile"}), 400

        # Get query parameters
        year = request.args.get("year", type=int)
        publish = request.args.get("publish", "false").lower() == "true"

        # Save uploaded file to temp location
        filename = file.filename
        ext = Path(filename).suffix or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp:
            file.save(temp.name)
            temp_path = Path(temp.name)

        try:
            # Get appropriate reader for file format
            try:
                reader = reader_registry.get_reader(temp_path)
            except UnsupportedFormatError as e:
                return handle_error(e)

            # Read source calendar
            try:
                ingestion_result = reader.read(temp_path)
                source_calendar = ingestion_result.calendar
            except (IngestionError, InvalidYearError) as e:
                return handle_error(e)

            # Check if calendar exists
            existing = repository.load_calendar(calendar_name)

            if existing is None:
                # Create new calendar
                try:
                    result, processing_summary = manager.create_calendar_from_source(
                        source_calendar, calendar_name
                    )
                except InvalidYearError as e:
                    return handle_error(e)

                # Save calendar (stores as JSON, exports to ICS)
                filepath = repository.save_calendar(result.calendar, result.metadata)

                # Publish to git if requested
                published = False
                if publish:
                    git_service.publish_calendar(calendar_name, filepath)
                    published = True

                return (
                    jsonify(
                        {
                            "status": "success",
                            "calendar_name": calendar_name,
                            "action": "created",
                            "events_count": len(result.calendar.events),
                            "processing_summary": processing_summary,
                            "filepath": str(filepath),
                            "published": published,
                        }
                    ),
                    201,
                )
            else:
                # Compose with existing calendar - requires year
                if year is None:
                    # Try to determine year from source calendar
                    if source_calendar.year is None:
                        years = {event.date.year for event in source_calendar.events}
                        if len(years) != 1:
                            return (
                                jsonify(
                                    {
                                        "error": f"Source calendar contains events from multiple years: {years}. Please specify year parameter when updating an existing calendar.",
                                        "type": "InvalidYearError",
                                    }
                                ),
                                400,
                            )
                        year = years.pop()
                    else:
                        year = source_calendar.year

                try:
                    result, processing_summary = manager.compose_calendar_with_source(
                        calendar_name, source_calendar, year, repository
                    )
                except (CalendarNotFoundError, InvalidYearError) as e:
                    return handle_error(e)

                # Save updated calendar (stores as JSON, exports to ICS)
                filepath = repository.save_calendar(result.calendar, result.metadata)

                # Publish to git if requested
                published = False
                if publish:
                    git_service.publish_calendar(calendar_name, filepath)
                    published = True

                return (
                    jsonify(
                        {
                            "status": "success",
                            "calendar_name": calendar_name,
                            "action": "updated",
                            "year": year,
                            "events_count": len(result.calendar.events),
                            "processing_summary": processing_summary,
                            "filepath": str(filepath),
                            "published": published,
                        }
                    ),
                    200,
                )

        except Exception as e:
            return handle_error(e)
        finally:
            # Clean up temp file
            try:
                temp_path.unlink()
            except OSError:
                pass

    @app.route("/calendars/<calendar_name>", methods=["GET"])
    def get_calendar(calendar_name: str):
        """Get a calendar by name (always returns ICS format)."""
        try:
            calendar_with_metadata = repository.load_calendar(calendar_name)
            if calendar_with_metadata is None:
                return (
                    jsonify(
                        {
                            "error": f"Calendar '{calendar_name}' not found",
                            "type": "CalendarNotFoundError",
                        }
                    ),
                    404,
                )

            # Get template for resolving location_id references
            template = None
            metadata = calendar_with_metadata.metadata
            if metadata.template_name:
                try:
                    template = get_template(metadata.template_name, config.template_dir)
                except FileNotFoundError:
                    logger.warning(f"Template '{metadata.template_name}' not found")

            # Export to ICS format
            writer = get_ics_writer()

            # Write to temp file to get bytes
            with temp_file_path(suffix=".ics") as temp_path:
                writer.write(calendar_with_metadata, temp_path, template=template)
                content = temp_path.read_bytes()

                return Response(
                    content,
                    content_type="text/calendar; charset=utf-8",
                    headers={
                        "Content-Disposition": f'attachment; filename="{calendar_name}.ics"'
                    },
                )

        except Exception as e:
            return handle_error(e)

    @app.route("/calendars", methods=["GET"])
    def list_calendars():
        """List all calendars."""
        try:
            include_deleted = (
                request.args.get("include_deleted", "false").lower() == "true"
            )
            calendars = repository.list_calendars(include_deleted=include_deleted)

            # Get metadata for each calendar
            calendar_list = []
            for cal_name in calendars:
                # Try to load metadata
                metadata = repository.load_metadata(cal_name)
                if metadata:
                    calendar_list.append(
                        {
                            "name": cal_name,
                            "created": (
                                metadata.created.isoformat()
                                if metadata.created
                                else None
                            ),
                            "last_updated": (
                                metadata.last_updated.isoformat()
                                if metadata.last_updated
                                else None
                            ),
                        }
                    )
                else:
                    calendar_list.append({"name": cal_name})

            return jsonify({"calendars": calendar_list, "count": len(calendar_list)})
        except Exception as e:
            return handle_error(e)

    @app.route("/calendars/<calendar_name>", methods=["DELETE"])
    def delete_calendar(calendar_name: str):
        """Delete a calendar."""
        purge_history = request.args.get("purge_history", "false").lower() == "true"

        try:
            paths = repository.paths(calendar_name)
            calendar_exists = paths.directory.exists()

            if purge_history:
                # Hard delete: remove from git history entirely
                if git_service.purge_from_history(calendar_name):
                    # Remove from filesystem if it still exists
                    if calendar_exists:
                        repository.delete_calendar(calendar_name)
                    return (
                        jsonify(
                            {
                                "status": "success",
                                "message": f"Calendar '{calendar_name}' purged from git history",
                                "purged_from_history": True,
                            }
                        ),
                        200,
                    )
                else:
                    return (
                        jsonify(
                            {
                                "error": f"Failed to purge calendar '{calendar_name}' from git history",
                                "type": "GitError",
                            }
                        ),
                        500,
                    )
            else:
                # Regular delete: requires calendar to exist
                if not calendar_exists:
                    return (
                        jsonify(
                            {
                                "error": f"Calendar '{calendar_name}' not found",
                                "type": "CalendarNotFoundError",
                            }
                        ),
                        404,
                    )

                # Remove from filesystem and commit deletion to git
                repository.delete_calendar(calendar_name)
                git_service.commit_deletion(calendar_name)

                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": f"Calendar '{calendar_name}' deleted",
                            "purged_from_history": False,
                        }
                    ),
                    200,
                )

        except Exception as e:
            return handle_error(e)

    return app
