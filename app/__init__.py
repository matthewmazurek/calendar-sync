import os
import tempfile

from docx.opc.exceptions import PackageNotFoundError
from flask import Flask, Response, jsonify, request

from .calendar_generator import generate_ical
from .calendar_parser import parse_word_events
from .calendar_storage import save_calendar
from .event_processor import process_events


def create_app():
    app = Flask(__name__)

    @app.route("/inbound", methods=["POST"])
    def inbound():
        if "attachment-1" not in request.files:
            return "", 400

        attachment = request.files.get("attachment-1")
        if not attachment:
            return ("No attachment", 400)

        # Save to temp file with original extension
        filename = attachment.filename or "tempfile"
        _, ext = os.path.splitext(filename)
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp:
            attachment.save(temp.name)
            try:
                try:
                    # Parse events from docx
                    events = parse_word_events(temp.name)

                    # Process events (consolidate on-call, add locations, etc.)
                    processed_events = process_events(events)
                except PackageNotFoundError:
                    return ("Invalid .docx file", 400)

                # Generate iCal content
                cal = generate_ical(processed_events)
                ical_content = cal.to_ical()

                # Save the calendar
                filename = save_calendar(ical_content)

                # Return success response
                return jsonify(
                    {
                        "status": "success",
                        "message": "Calendar processed and saved",
                        "events": processed_events,
                        "filename": filename,
                    }
                )
            finally:
                # Clean up temp file
                os.unlink(temp.name)

    @app.route("/calendar", methods=["GET"])
    def get_calendar():
        """Serve the latest calendar file."""
        from .calendar_storage import get_latest_calendar

        ical_content = get_latest_calendar()
        if not ical_content:
            return ("No calendar available", 404)

        return Response(
            ical_content,
            content_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=latest-calendar.ics"},
        )

    return app
