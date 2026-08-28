# Steam Workshop Utils

Steam Workshop Utils is a Codex skill project for bulk Steam Workshop metadata and comment analysis. It stores Workshop descriptions, metadata, collection membership, recent public comments, and extracted evidence signals in a local SQLite database so Codex can report conservative evidence about mod compatibility, multiplayer support, dependencies, version/build concerns, and user-reported errors.

## Features

- **Bulk Workshop sync** for pasted IDs, text files, JSON files, and Steam collection URLs.
- **Local SQLite cache** stored under the Codex data directory by default.
- **Recent comment retention** for the newest public comments per Workshop item, defaulting to 10 and configurable per sync.
- **Evidence reports** in Markdown, JSON, or self-contained HTML for incompatibility, MP support, dependency hints, version/build concerns, crashes, alternatives, problem-focused performance issues, and load-order warnings.
- **Template-driven checks** with a problem-focused Basic Check that defaults to a collapsible HTML webpage report.
- **Persistent resolution workflow** when the HTML report is run through the local server mode.
- **Named modlist resync diffs** that preview added, removed, unchanged, and missing-metadata mods before applying active-list changes.
- **Archived mod purge** for intentionally deleting removed mods from the local cache.
- **Manual refresh workflow** so reports read cache data without surprising network calls.
- **Generic local modlist workflow** for discovering documented game config paths without broad disk scans.

## Installation

This repository is the source project for the Codex skill. After validation, copy or install the skill folder to:

```text
~/.codex/skills/steam-workshop-utils
```

Restart Codex after installing or updating the skill so the new skill metadata is loaded.

## Usage

Sync a comma-delimited set of Workshop IDs:

```bash
python scripts/sync_workshop.py --ids "123456789,987654321"
```

Sync a Steam collection:

```bash
python scripts/sync_workshop.py --collection-url "https://steamcommunity.com/sharedfiles/filedetails/?id=1234567890"
```

Preview a named modlist resync:

```bash
python scripts/sync_workshop.py resync --list default --ids "123456789,987654321"
```

Apply the resync diff, syncing new and stale active mods:

```bash
python scripts/sync_workshop.py resync --list default --ids "123456789,987654321" --apply
```

Preview and apply archived-mod purge for a named list:

```bash
python scripts/sync_workshop.py purge-archived --list default
python scripts/sync_workshop.py purge-archived --list default --apply
```

Generate a Markdown report:

```bash
python scripts/report_workshop.py --ids "123456789,987654321" --format markdown
```

Generate the Basic Check webpage:

```bash
python scripts/report_workshop.py --ids "123456789,987654321" --check basic --output report.html --open
```

Run the Basic Check as a local server so resolved evidence can be saved back to SQLite:

```bash
python scripts/report_workshop.py --ids "123456789,987654321" --check basic --serve --open
```

Generate JSON for every cached item:

```bash
python scripts/report_workshop.py --all --format json
```

Report on a saved active modlist:

```bash
python scripts/report_workshop.py --list default --check basic --output report.html
```

## Configuration

- `STEAM_WEB_API_KEY`: optional Steam Web API key used for official metadata and collection requests.
- `STEAM_WORKSHOP_DB`: optional SQLite DB path override.
- `--db`: per-command SQLite DB path override.
- `--comments-limit`: number of newest public comments to retain per item. Defaults to `10`.
- `--check basic`: runs the Basic Check template. It defaults to HTML unless `--format` is explicitly supplied.
- `--format`: report format. Supported values are `markdown`, `json`, and `html`.
- `--output`: optional report output path.
- `--open`: opens an HTML report written with `--output`, or opens the local report URL when used with `--serve`.
- `--serve`: runs a foreground local web server on `127.0.0.1` with SQLite-backed resolve/unresolve controls.
- `resync --list NAME`: previews a supplied current mod set against a named saved modlist. Add `--apply` to persist active/archive changes.
- `purge-archived --list NAME`: previews archived entries for a named list. Add `--apply` to permanently delete those archived mods from the local cache.
- `report_workshop.py --list NAME`: reports on active mods in a named list. Add `--include-archived` for audit reports.

Static HTML reports are read-only. Use `--serve` when you want the page's Actions controls to persist resolved items in the database.

Reports are cache-only and do not refresh Steam implicitly. The Basic Check is evidence-based: it highlights snippets that need review, not authoritative compatibility, dependency, or target-version verdicts.

Purging archived entries is destructive: it deletes matching archived Workshop IDs from metadata, comments, evidence, failures, resolved evidence, and collection membership rows.

The default DB path is:

```text
~/.codex/data/steam-workshop/steam-workshop.sqlite
```

## Building from Source

No build step is required. The scripts use the Python standard library.

Prerequisite:

- Python 3.10 or newer.

## Testing and Validation

Validate the skill metadata:

```bash
python C:\Users\kylem\.codex\skills\.system\skill-creator\scripts\quick_validate.py E:\Coding\Skills\steam-workshop-utils
```

Run script syntax checks:

```bash
python -m py_compile scripts/sync_workshop.py scripts/report_workshop.py
```

Run report generation against a fixture DB or a previously synced DB:

```bash
python scripts/report_workshop.py --all --format markdown
```

## Contributing & Forking Policy

> Contributions, issues, and feature requests are welcome.
>
> **Forking Policy:** If your fork primarily consists of bug fixes or feature additions that align with the core vision of this project, I reserve the right to request that your changes be submitted as a Pull Request to this existing codebase rather than being published as a completely separate standalone release, package, listing, or distribution.

## License

> Released under the **MIT License**.
>
> **Attribution Requirement:** You are free to use and modify this code, provided that you credit me and link back to this project in any relevant public repository, package listing, project page, app/mod listing, Steam Workshop page, and in-project or in-game info file where applicable.

## Credits

- Steam Web API and Steam Community endpoints provide Workshop metadata and public comment data.
- Built for Codex skill workflows using the local skill creator tooling.
