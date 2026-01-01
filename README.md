# Calendar Sync

A Flask app to sync calendar data from Word documents.

## Installation

```bash
poetry install
```

## Usage

### CLI Tool

```bash
calendar-sync [command]
```

Available commands: `sync`, `ls`, `restore`, `info`, `delete`, `publish`, `git-setup`, `config`

### Flask App

Start the Flask development server:

```bash
poetry run flask --app app run --port 5001
```

Or with Python:

```bash
poetry run python -m flask --app app run --port 5001
```

**Note:** Port 5000 is often used by macOS AirPlay Receiver. Use port 5001 or another available port to avoid conflicts.

#### API Endpoints

**POST /calendars/<calendar_name>** - Create or update a calendar
- Upload a file (ICS, JSON, or Word document)
- Query parameters:
  - `format` - Output format: `ics` or `json` (default: `ics`)
  - `year` - Year to replace when updating existing calendar (required for updates)
  - `publish` - Set to `true` to commit and push to git

Example:
```bash
curl -X POST "http://localhost:5001/calendars/my-calendar?format=ics&publish=true" \
  -F "file=@calendar.docx"
```

**GET /calendars/<calendar_name>** - Get a calendar
- Query parameters:
  - `format` - Format to return: `ics` or `json` (default: `ics`)

Example:
```bash
curl "http://localhost:5001/calendars/my-calendar?format=ics" -o calendar.ics
```

**GET /calendars** - List all calendars
- Query parameters:
  - `include_deleted` - Set to `true` to include archived calendars

Example:
```bash
curl "http://localhost:5001/calendars"
```

**DELETE /calendars/<calendar_name>** - Delete a calendar
- Query parameters:
  - `purge_history` - Set to `true` to remove from git history entirely

Example:
```bash
curl -X DELETE "http://localhost:5001/calendars/my-calendar"
```

## License

See LICENSE file for details.
