# Calendar Sync

A Python CLI tool for syncing and managing calendar data from various sources including Word documents, ICS files, and JSON.

## Features

- **Multiple input formats**: Import calendars from Word/DOCX, ICS, or JSON files
- **Flexible output**: Export calendars as ICS or JSON
- **Git integration**: Version control for calendar data with automatic commit and push
- **Template system**: Configurable event processing rules
- **Calendar merging**: Intelligently merge and update calendar data by year

## Installation

```bash
poetry install
```

## Usage

```bash
calendar-sync [command] [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `sync` | Sync calendar from a source file (ingest + export + commit) |
| `ingest` | Import calendar data from a file |
| `export` | Export calendar to ICS or JSON format |
| `commit` | Commit calendar changes to git |
| `push` | Push committed changes to remote |
| `ls` | List all calendars |
| `show` | Display calendar events |
| `search` | Search for events |
| `info` | Show calendar information and metadata |
| `stats` | Display calendar statistics |
| `diff` | Show differences between calendar versions |
| `restore` | Restore a deleted calendar |
| `delete` | Delete a calendar |
| `git-setup` | Configure git repository for calendar storage |
| `config` | View or set configuration options |
| `template` | Manage calendar templates |

### Examples

Sync a calendar from a Word document:
```bash
calendar-sync sync my-calendar schedule.docx
```

List all calendars:
```bash
calendar-sync ls
```

Show calendar events:
```bash
calendar-sync show my-calendar
```

Export calendar to ICS:
```bash
calendar-sync export my-calendar -o calendar.ics
```

### Global Options

- `--verbose, -v`: Show debug output
- `--quiet, -q`: Only show errors
- `--version`: Show version and exit
- `--help`: Show help message

## Configuration

Configuration can be set via environment variables or a `.env` file:

- `CALENDAR_DIR`: Directory for storing calendar data
- `CALENDAR_FORMAT`: Default output format (`ics` or `json`)
- `CALENDAR_GIT_REMOTE_URL`: Git remote URL for syncing
- `DEFAULT_TEMPLATE`: Default template name for event processing

## License

See LICENSE file for details.
