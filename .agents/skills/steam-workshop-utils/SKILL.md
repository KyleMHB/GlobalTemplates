---
name: steam-workshop-utils
description: Bulk Steam Workshop metadata and comment collection with local SQLite caching and evidence reports. Use when Codex needs to inspect Steam Workshop mods, sync descriptions and recent comments, expand Workshop collections, analyze conflicts, functional overlap, compatibility, or multiplayer-support evidence, search for dependency/error reports, or compare supplied Workshop IDs against cached mod intelligence.
---

# Steam Workshop Utils

## Overview

Use this skill to collect Steam Workshop item metadata, descriptions, and recent public comments into a local SQLite database, then generate conservative evidence reports for conflicts, functional overlap, positive compatibility, multiplayer support, dependency hints, version/build concerns, crash/error reports, and load-order warnings.

The scripts are designed for bulk mod lists. They avoid image/media downloads, use manual sync only, and treat extracted labels as evidence signals rather than definitive claims.

## Quick Start

Sync a pasted list of Workshop IDs:

```bash
python scripts/sync_workshop.py --ids "123,456,789"
```

Sync a Steam collection URL:

```bash
python scripts/sync_workshop.py --collection-url "https://steamcommunity.com/sharedfiles/filedetails/?id=1234567890"
```

Preview and apply a named modlist resync:

```bash
python scripts/sync_workshop.py resync --list default --ids "123,456,789"
python scripts/sync_workshop.py resync --list default --ids "123,456,789" --apply
```

Preview and apply archived cache cleanup:

```bash
python scripts/sync_workshop.py purge-archived --list default
python scripts/sync_workshop.py purge-archived --list default --apply
```

Generate the default Basic Check webpage:

```bash
python scripts/report_workshop.py --ids "123,456,789" --check basic --output report.html --open
```

Generate the Basic Check webpage for a saved active list:

```bash
python scripts/report_workshop.py --list default --check basic --output report.html
```

Run the Basic Check as a local webpage with persistent resolved-state controls:

```bash
python scripts/report_workshop.py --ids "123,456,789" --check basic --serve --open
```

Generate a Markdown report:

```bash
python scripts/report_workshop.py --ids "123,456,789" --format markdown
```

Generate JSON for downstream scripts:

```bash
python scripts/report_workshop.py --all --format json
```

## Workflow

1. Identify the mod source: pasted Workshop IDs, a text/JSON file, a Steam collection URL, or a game-specific enabled-mod list.
2. If a game-specific enabled-mod list is requested, research the documented config locations before inspecting local files. Check known paths only and report whether enabled/disabled state is actually represented.
3. Run `scripts/sync_workshop.py` to update the local cache. Sync is manual; reporting never refreshes Steam data implicitly.
4. Run `scripts/report_workshop.py` to summarize evidence from cached descriptions and comments.
5. When reporting compatibility, dependency, version, or multiplayer status, cite snippets and confidence. Do not convert weak evidence into hard claims.

## Scripts

### `scripts/sync_workshop.py`

Use for metadata/comment collection. It accepts:

- `--ids "1,2,3"` for pasted comma/space/newline-delimited IDs.
- `--input path/to/list.txt` for newline text, comma-delimited text, or JSON input.
- `--collection-url URL` or `--collection-id ID` for collection expansion.
- `--db path/to.sqlite` to override the default DB path.
- `--skip-comments` when only metadata is needed.
- `--comments-limit 10` to cap stored recent comments per item. Override this value when more comments are needed.
- `resync --list NAME` to compare a supplied current mod set against a saved named list. It previews by default and requires `--apply` to update active/archive state.
- `purge-archived --list NAME` to preview archived entries for a named list. It requires `--apply` to permanently delete archived mods from the local cache.

The script uses `STEAM_WEB_API_KEY` if present. It stores failures and continues through large lists.

### `scripts/report_workshop.py`

Use for cached analysis. It accepts:

- `--ids "1,2,3"` or `--input path/to/list.json`.
- `--all` to report on every cached item.
- `--check basic` to run the default template. The Basic Check defaults to HTML unless `--format` is supplied.
- `--format markdown`, `--format json`, or `--format html`.
- `--output report.html` to write output to a file.
- `--open` to open an HTML output file or `--serve` URL in the default browser.
- `--serve` to run a foreground local server on `127.0.0.1` so Mark resolved and Unresolve actions persist to SQLite. Static HTML output is read-only.
- `--category incompatibility --category errors` to focus the report.
- `--list NAME` to report on active items in a saved named modlist.
- `--include-archived` to include archived items when reporting with `--list`.

## References

- Read `references/api-and-data.md` when changing Steam endpoints, request behavior, or the database schema.
- Read `references/evidence-and-reports.md` when changing signal extraction or report wording.
- Read `references/local-modlists.md` when asked to discover currently enabled mods for a game.

## Safety

- Do not broadly scan the disk for game data. Use documented locations or user-provided paths.
- Do not download Workshop images or media.
- Do not hardcode Steam API keys or credentials.
- Do not claim a mod is compatible, incompatible, or multiplayer-safe without direct supporting evidence.
- Treat dependency and version/build checks as evidence review unless a structured source or explicit target version is provided.
- Do not run `purge-archived --apply` unless the user intentionally wants archived mods deleted from local cache tables.
