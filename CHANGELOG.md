# Changelog

<!-- Agent read route: read only the newest relevant release; locate older versions by searching `^## ` headings. -->

## 2026-11-13

### Added

- Added the Contact Sheet tool under `tools/` and its `contact-sheet` skill, which render before-and-after sheets of artwork for sharing.

## 2026-11-12

### Added

- Added measured vanilla rendering figures, fit-to-vanilla advice, outline defaults and weapon orientation to the RimWorld artwork guide.
- Added the RimWorld Dev Tests harness and RimWorld Mask Editor under `tools/`, with game paths set per machine instead of hardcoded.
- Added author profiles under `profiles/`; the README and Steam description templates take the Ko-fi link and AI disclosure from the profile your instructions name.
- Added install steps for Codex and Claude Code to the README.
- Added the RimWorld Translate tool under `tools/` and its `rimworld-translate` skill.
- Added translatable-by-default rules for new RimWorld mods to the RimWorld agent guide: prefixed Keyed keys, no hardcoded English in C#, and a build check that enforces it.
- Added `list`, `self-check` and `prune` commands to the RimWorld Dev Tests launcher, and unit tests for its mod-set, manifest and exit-code logic.
- Added logged-error counts to RimWorld Dev Tests reports, with an opt-in `FailOnModErrors` setting that fails a run when the mod under test logs an error.

### Changed

- Made RimWorld Dev Tests close a run with a report shortly before the launcher's time limit, and report a runner that fails to start at once instead of waiting out the limit.
- Moved the day-long autosave self-check out of `run-all` into its own `diagnostic-autosave` batch.
- Made developer DLLs left behind by a stopped launcher inactive in games the launcher did not start. `install-dev` now writes a marker file that enables the developer menu.
- Pinned the language and autosave interval in the harness's copy of `Prefs.xml`, and kept a copy of `Player.log` in each run folder.

- Made approval final in the RimWorld artwork guide: approved art changes only when its author asks for a redo.
- Removed references to specific mods so the templates and guides apply to any project.
- Replaced the Workshop skill's scraped comment test data with anonymized example data.

### Fixed

- Fixed template validation for the Steam description's AI disclosure section.
- Fixed `latest` in RimWorld Dev Tests showing an older run when the newest one was killed or crashed.
- Fixed the launcher ignoring `ExtraRuntimeExclusions`; `devtests.json` now takes a matching `runtimeExclusions` list.
- Fixed launcher crashes exiting with the same code as test failures; they now exit with code 4.
- Fixed exceptions from wait conditions and per-tick callbacks being reported as runner errors without a stack.
- Fixed the launcher hashing every player save twice per run.

## 2026-11-09

### Added

- Added shared Git rules to the agent instructions: when to commit and branch, one change per commit, a single commit-message style, and cleanup of merged branches.

## 2026-11-08

### Changed

- Made template discovery, skill lookup and engineering workflow routing independent of a specific agent or local checkout path.
- Made RimWorld test tooling and Workshop publication guidance use configured paths and available browser capabilities.
- Gave the Workshop cache an agent-neutral default while preserving access to existing Codex caches and explicit path overrides.

### Added

- Added a RimWorld agent read route pointing to the RimWorld Dev Tests harness and its topic-based testing recipes.
- Added a general RimWorld artwork guide for sprites, material masks and rendering; mod-specific requirements stay in each mod.

## 2026-11-04

### Changed

- Added a brief and an opening hook to the Steam description template, kept the Description short, and added sentence checks and a self-score before delivery.
- Added a one-line status notice at the top of Steam descriptions for forks and for obsolete or discontinued mods.
- Added Steam's 8,000-character description limit, moved release notes to Change Notes, and added bug-report guidance to the Steam description template.
- Added common save, Combat Extended and multiplayer questions to the compatibility section, and asked for required items to be linked in the Workshop sidebar.
- Added load-order consistency checks to the RimWorld `About.xml` template.
- Made the Workshop preview tool print the description length and warn when it exceeds 8,000 characters.

## 2026-10-31

### Added

- Added a guide for illustrated Steam Workshop pages and a local preview tool for Steam descriptions.
- Added a routing reference for the Matt Pocock engineering skills.

### Changed

- Changed the README template to leave out test results, keep Links last, and report an unconfirmed license.
- Limited `unslop` in the Wayward and RimWorld templates to the description, so mod names stay stable.
- Moved the changelog read route into an HTML comment so it stays out of the rendered page.
- Aligned `TESTING.md` and changelog triggers across `AGENTS.md`, `templates.json`, and the templates.
- Reworded the `unslop` steps to match the installed skill, which has no presets, gates, or validation scripts.
- Stated that an explicit `implement` or `implement-spec` request also authorizes the tests and review those skills define.
- Made Steam item-row image rules apply only to illustrated pages and added license guidance for original mods that do not use GPLv3.

### Fixed

- Restored the writing rules in `AGENTS.md` that the `unslop` fallback relies on.
- Fixed the preview tool so it accepts uppercase tags and bare `[url]` links, and reports bad links without a traceback.

### Internal

- Made the template validator run on Windows PowerShell 5.1 and check the supporting files.

## 2026-09-06

### Changed

- Reduced the catalog to README, changelog, testing, Steam description, Wayward metadata, and RimWorld metadata templates.
- Moved the `setup-matt-pocock-skills` policy into the installed skill, including its local issue, triage, domain-layout, instruction-file, conflict, and validation defaults.
- Clarified that changelog updates may be created automatically when they are materially useful, while new testing guides require an explicit request and existing guides may receive material updates.
- Removed the personal forking request from generated README and Steam Workshop copy.

## 2026-09-05

### Changed

- Marked five template outputs as public-facing and required Unslop validation for their reader-visible copy.
- Audited the five public template instructions with Unslop and replaced vague changelog and Steam guidance with concrete criteria.
- Updated the template manifest to schema version 2 with an explicit `publicFacing` classification.

### Internal

- Added validator coverage for public-copy classification, instructions, and fallback disclosure.

## 2026-09-04

### Changed

- Clarified when ordinary, project-memory, and changelog templates may activate.
- Defined guarded permission for validated local commits.
- Standardized the required workflow-template headings and made Steam Links conditional.

### Internal

- Expanded template validation to detect orphaned templates, structural contract violations, and malformed Steam BBCode.
- Added positive and negative validator coverage for the stricter contract.
