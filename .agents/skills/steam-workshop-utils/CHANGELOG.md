# Changelog

## 2026-07-27

### Added

- Added Basic Check evidence for functional overlap and positive compatibility between selected mods.

## 2026-05-17

### Fixed

- Fixed HTML evidence linkification so Workshop IDs inside generated links are not reprocessed into broken nested anchors.
- Fixed comment sync identity so shifted Steam comment positions update existing cached comments instead of creating duplicate rows.
- Fixed comment retention cleanup so comments missing from the latest retained fetch window are removed.
- Fixed Steam Workshop comment fetching to use the creator SteamID and Workshop item ID in the Steam Community comment render URL.
- Fixed Basic Check HTML filters so matching and hiding propagate to parent question sections and mod cards.

### Changed

- Changed Basic Check dependency and version wording to describe evidence review instead of authoritative fulfillment or target-version verdicts.
- Changed local resolve/unresolve endpoints to require a per-server CSRF token and current-report fingerprint validation.
- Changed Basic Check performance matching to focus on negative performance reports and suppress positive or neutral phrases.
- Changed Basic Check comment handling so newer fixed/resolved comments suppress older problem evidence from active results.
- Changed Basic Check reports to show problem-only question results with collapsed HTML sections and reduced-noise evidence caps.
- Changed the default comment retention limit from 100 to 10 comments per Workshop item while keeping it configurable.

### Added

- Added named modlist resync diffs with preview/apply behavior, active/archive membership state, and stale refresh for applied resyncs.
- Added archived-mod purge with preview/apply behavior for permanently deleting archived cache rows from a named list.
- Added report filtering by named active modlist with optional archived inclusion.
- Added SQLite-backed manual evidence resolution with a foreground `--serve` report mode and local resolve/unresolve endpoints.
- Added collapsed Actions sections and collapsed resolved-evidence sections to HTML reports.
- Added a `resolved` evidence category for fixed, resolved, works-now, patched, and no-longer-crashes comments.
- Added template-driven reports with a Basic Check that defaults to HTML output.
- Added self-contained HTML webpage reports with dashboard summaries, filters, Workshop links, question sections, and detailed mod evidence.
- Added alternatives and performance evidence categories.
- Added Basic Check questions for game version compatibility and negative user sentiment.
- Added the initial `steam-workshop-utils` Codex skill project.
- Added bulk Steam Workshop metadata, collection, comment sync, and local SQLite caching scripts.
- Added Markdown and JSON evidence reporting for compatibility, multiplayer, dependency, version, error, and load-order signals.
- Added references for Steam Workshop data handling, evidence reporting, and generic local game modlist discovery.
