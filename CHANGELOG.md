# Changelog

<!-- Agent read route: read only the newest relevant release; locate older versions by searching `^## ` headings. -->

## 2026-11-28

### Fixed

- The Dev Tests launcher no longer crashes before a batch runs once a running game uses more than 1 GB of memory. `tasklist` then prints a thousands separator that isn't valid UTF-8, and decoding it failed.

## 2026-11-23

### Added

- Added Timberborn Dev Tests in `tools/timberborn-dev-tests`, a harness that runs a mod's test cases in the real game. `tbtest.py run <batch>` installs the runner and the mod's DevTests DLL into a separate `Mods/<modId>DevTests` folder, so the installed mod is left as players get it. It keeps only the mod under test and its required mods enabled, starts a fresh game through Steam, and writes a run folder with a summary and report. Afterwards it puts the player's mod settings back exactly and checks their saves were untouched. The commands, exit codes and case API (`HarnessSettings`, `Batch`, `Wait`, `Kit`, steps and known gaps) follow RimWorld Dev Tests. It also has `restore`, `latest`, `timings`, `list`, `release-check` and `prune`. An agent can launch runs too: inside the Claude desktop app, whose registry writes the game never sees, `run` and `restore` rerun themselves outside the app and stream their output back. The game-agnostic parts of the launcher are in `tools/dev-tests-core`. The Timberborn agent guide now points to the harness, and the game facts gained what building it showed about mod priority, starter exceptions and the crash scene.

- RimWorld Dev Tests has a shared `new-game` batch that starts a colony the way a player does: New colony, then every new-game page (scenario, storyteller, world generation, landing site, ideoligion, colonists), each left through its own Next button. The quickstart every other batch uses opens none of those pages. `run-all` now runs it after `diagnostic` for every mod, which adds well under a minute on the sets tried. A mod's own batch can start the same way by overriding `Batch.NewGamePages`. `guide authoring` has a "New game" section.
- Added `tools/tickets/tickets.py`, which prints one line per `.scratch/` ticket with its status and blockers. `--open` hides finished tickets. `AGENTS.md` tells agents to run it before reading tickets to work out what is left.
- Added `tools/copy-lint/copy_lint.py`, which fails on em dashes and on the banned words it reads from `writing-copy.md`, in the same files as the unslop scope. With `--staged` it checks only added lines and changed description fields, so older copy does not block a commit. A line with `copy-lint: allow` is skipped. The pre-commit hooks of Spearfishing, Loot Scavenging, Lumen Stones, LFS UI Rethemed and Torii Gates and Lanterns run it.
- `AGENTS.md` now sets a model for every subagent: Sonnet for exploration, research, merging and review, and for implementers unless their ticket says `Recommended model: opus`.

### Changed

- Steam descriptions gain a Discord badge beside Ko-fi and GitHub when the author profile has a `discord-url`.
- `writing-copy.md` now holds the one list of files that get `unslop`: README, changelog, Steam and website descriptions, and the description field of `About.xml`, `mod.json` and a Timberborn `manifest.json`. The `unslop` skill and `AGENTS.md`, which each listed different files, now match it.
- Workshop art guidance now covers preview images and gallery art, not only illustrated pages. It sets text in the game's own font by default and says where `RimWordFont.ttf` is kept. The RimWorld read route links to it.
- The author profile says new mod and submod ideas go in the mod-ideas repo, even when the session is open in a related mod's repo.
- The RimWorld art guide starts a new design with one view, compared side by side with a vanilla sprite of the same role, before making the other facings. It adds quarter-turn layouts for directional objects, matches joins between materials to that reference, and covers repairing a dark patch on an opaque surface. An author profile can point to a local copy of the extracted game textures with `rimworld-art-source`.
- RimWorld Dev Tests games now load one at a time: a launch waits until any other test game reaches the main menu, so two startups can't race for the shared `Player.log` or a mod's files. Batches still run in parallel. `lease take`, which deploy scripts call, also waits while another test game is loading that mod.

## 2026-11-22

### Added

- Added Timberborn modding guidance under `Steam/timberborn`: a read route for starting code and data mods, a `manifest.json` template, and game facts checked against game version 1.1.2.8. They cover mod folders, version folders, load order, Harmony and configurator contexts. `AGENTS.md` and `template-routing.md` now point to them. `tools/timberborn-dev-tests/SPEC.md` plans a Timberborn test harness, and the game facts record what a harness spike proved in game.

- RimWorld Dev Tests reports errors naming the mod that were logged while the game loaded. Every summary has a `Startup:` line, `report.json` lists them in `startupModErrors`, and under `FailOnModErrors` they fail the run. Mods no longer need their own startup-log batch.
- Several mods' RimWorld Dev Tests can run at once, each in its own game, up to `maxGames` in `rimtest.local.json` (default 3). Install leases are now per installed mod, so only checkouts of the same mod take turns. A run waits for a free game slot instead of failing, and the `perf` batch and recorded runs wait until no other game is running a batch. A run's summary says how many other test games were running.

### Changed

- RimWorld Dev Tests copies `Player.log` into a run only when it came from that run's game, since every game on the machine writes the same file.
- `devlog-post` drafts Discord posts only. It no longer asks which platforms you post to or drafts for X or Bluesky.
- `devlog-post` no longer ends posts with a question or call to action, except a vote's voting instructions.

## 2026-11-20

### Added

- Added the `unslop` skill to `.agents/skills`, so the skill the public-copy templates call for ships with the repository. Link it like the other bundled skills.
- `unslop` gained a final check that the rewrite kept every name, number, command, link and claim, and rules 34 to 40 for one-line closers, staged run-ups, rebuttals of claims nobody made, repeated sentence openings, headings repeated in the first sentence, writing about the document, and re-explaining what the reader knows.

## 2026-11-19

### Added

- RimWorld Dev Tests cases can be written as steps: `CaseScope.Step`, `Note` and `Conclude`. A failed step no longer ends the case, and the summary prints every step under a failing case.
- Added `CaseScope.KnownGap` to RimWorld Dev Tests for a check that isn't true yet. The case is skipped as `known-gap` without failing the run, and the summary says when the gap starts to hold.
- RimWorld Dev Tests counts warnings logged during a run, per case and in total. `FailOnWarnings` makes them fail the run, and `AllowedWarnings` and `AllowedErrors` exclude expected lines, optionally only when a named method is on the logging call's stack.
- Added `Kit.RemoveTendable` to RimWorld Dev Tests, and `Kit.Worker` now calls it, so a generated colonist no longer becomes a patient on some seeds.
- Added `looseOrderSets` to `devtests.json`, for mod sets that break a `loadAfter` or `loadBefore` rule on purpose to test an integration in the order players get wrong.
- RimWorld Dev Tests `release-check` now fails on a `Patches` file whose root is not `<Patch>` and on a Workshop preview over 1 MiB. It warns when XML names a class the production DLL doesn't hold.
- Added engine pitfalls reported by the Shift Change mod's tests to the RimWorld Dev Tests game facts, marked as not yet verified on 1.7.

### Changed

- A failing case's subject line in RimWorld Dev Tests evidence now names the job driver and toil the pawn stopped on.
- The testing template asks for a list of what the tests don't cover, including passing checks narrower than they look.

## 2026-11-18

### Added

- Added the Clip Compare tool under `tools/` and its `clip-compare` skill, which join video clips into a labelled before-and-after video for sharing.
- Added a devlog template for `DEVLOG.md`, a per-project log of moments worth showing to players. Agents add an entry when a session produces one, so the old version's captures are recorded while they still exist.
- Added the `devlog-post` skill, which turns a devlog entry into an image or clip and draft post text for Discord and social media.
- Added the `discord-search` skill, which searches a Discord channel for answers to one development question through the signed-in browser, without exporting the channel or using the account token. Author profiles gained an optional `discord-channels` section for it.

## 2026-11-17

### Added

- Added a RimWorld Dev Tests recipe for checking that a mod's Harmony patches are still applied after a dependency update (`guide patches`).
- RimWorld Dev Tests has a `Levels.Evidence` case level for cases that only write a screenshot or clip. The summary and `report.json` count these separately from behaviour checks.
- RimWorld Dev Tests summaries now list skipped cases as not covered. They also list registered batches outside `run-all` that the run didn't include, so a PASS no longer hides them.
- Added `rimtest.py timings [run]`, which prints each batch's wall clock in a run, slowest first.
- Added `Kit.PatchCounts(owner)` to RimWorld Dev Tests for counting a mod's Harmony patches per patch method.

### Changed

- The testing template replaces its smoke test with test tiers: Quick for each change, Visual for art, and Full at seams such as a merge to main, a dependency or game update, or a release. The agent instructions now save the full suite for those seams.
- RimWorld Dev Tests error counts now include Unity errors and uncaught exceptions that never went through `Verse.Log.Error`, such as one thrown in a per-frame Harmony patch. An error that goes through both is counted once. One whose stack trace names the mod's assembly or namespaces counts toward `ModErrors` and `FailOnModErrors`, so runs that passed before may now report more errors.
- The RimWorld Dev Tests authoring guide and environment recipe now cover state that leaks between batches, batch variants, unique evidence file names, and the DLCs that dependencies expect.


### Added

- Added a shared `perf` batch to RimWorld Dev Tests that drives Dubs Performance Analyzer and reports a mod's average ms per tick, the figure players quote. Each mod enables it with a `perf` mod set.
- Added `PerfTiming` to RimWorld Dev Tests for timing code the tick average misses, such as patches on pawn generation. It can measure what a mod's Harmony patches add to a game method by timing with them applied and removed.

### Changed

- RimWorld Dev Tests `release-check` now fails unless the released production DLL passed the `perf` batch and the mod's own `perf.*` timing cases, so every mod is performance-tested before release. It warns when a mod has no `perf.*` cases.

### Fixed

- Pawns in RimWorld Dev Tests runs and recordings now face the way they walk. Ticks run while the game is paused skip vanilla's facing update, so before this every pawn kept its spawn facing (north) and appeared to walk backwards or sideways.

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
