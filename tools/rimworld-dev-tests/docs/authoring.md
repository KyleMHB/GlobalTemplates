# Writing mod test cases

## Locate the existing integration

Read the mod's `AGENTS.md` and relevant `TESTING.md` sections. Find `DevTests/*.csproj`, its `HarnessSettings` subclass, `devtests.json`, launcher wrapper and approved expected-value rows. Search the [recipe index](recipes/index.md) for the required state before writing setup. Use the mod's existing batches as examples.

Cases and mod-specific instrumentation stay in the mod repository. A mod adapter is a `DevTests/` folder with a settings class (for example `ModHarness.cs`), `devtests.json` and a developer-only `.csproj`. Import `RimWorldDevTests.props`, set the production DLL path and output developer assemblies outside the runtime package. The import builds the shared DLL incrementally. For window capture use `guide recording`. The current shared runner accepts one loaded `HarnessSettings` subclass per process. Check the production target separately; this harness targets the installed RimWorld 1.7 runtime.

## Implement a case

1. Start from a design-sourced expected value. Record prerequisites, intervention, measurement, guard and cleanup in the mod's expected-value row. Separate a controlled mechanical reading from a real player workflow.
   Test a plain rule (a formula, threshold or table with no `Verse` or `RimWorld` references) in the mod's unit tests, linked into the test project as source. The game case then shows only that the game's values reach the rule. For items that come in tiers, check every tier's stats and research in one table-driven case that names each failing row, and run one gameplay workflow per mechanism, with the best tier.
2. Add a `PlannedCase` to the batch's `Plan`. Implement it in `Segment` using `BatchContext`, `Kit` and yielded `Wait` instances. Inspect the matching recipe and helper implementation before reusing them; a helper a recipe describes is not necessarily exported by the shared DLL.
   Most waits tick as fast as the frame budget allows, so few frames draw. `Wait.Seconds(seconds, simulate: true)` ticks at game pace (60 a second) for real seconds, so every frame draws; use it only where a check needs drawn frames or real time, or a recording should show game pace. `Wait.Seconds(seconds, true, speed)` ticks at `speed` times game pace: speed 3 still draws a frame every few ticks in a third of the real time. Keep speed 1 when recording (`RunRecording.Enabled`) and for checks that measure real time, such as frame timing or real-time animation clocks.
3. Establish prerequisites before the measurement. Use `Kit.Require` for instantaneous readings, and `Wait.While` for conditions that must hold throughout a window. See `guide measurements` for an example. Register measured pawns with `Subject` for failure evidence.
   `ctx.TimedOut` holds the latest `Wait.Until` result and other waits do not clear it. When another wait runs before the check, keep the wait (`var arrived = Wait.Until(...); yield return arrived;`) and read `arrived.TimedOut`. An exception thrown by a condition, a per-tick callback or a settings hook ends the batch as a case exception with its top stack frames, the same as one thrown in the segment.
4. Save state needed across a reload with `ctx.Remember`. `Wait.Reload()` ends its segment; reacquire game objects in the next segment. Stop maintenance and clear registrations when a case ends; batch cleanup handles only registered shared state.
   Each batch starts a fresh colony, so setup that one batch made (factions, zones, research) is gone in the next; put shared setup in a helper each batch calls. Defs and mod settings are process-wide and outlive the colony. Restore any you change in `HarnessSettings.OnBatchEnd`, which runs even when a batch ends early, not at the end of a segment. See [environment](recipes/environment.md).
5. Register a new batch in the mod's settings and run-all order when appropriate. Batches take no options: to run one variant of a batch, register one batch ID per variant (`<mod>-screens-<variant>`) from a single class that takes the variant in its constructor. Every batch in a run writes to one evidence folder, so screenshot and file names must be unique across the run, or a later batch overwrites an earlier one's file without warning. Build the developer project, then perform only the authorized focused check. A build establishes compilation, not in-game behavior.

## Run and report

Use the mod's wrapper and project paths, for example:

```powershell
dotnet build DevTests/MyMod.DevTests.csproj -c Release
python tools/mymod_test.py run mymod-batch mymod-other --seed 1
```

`run` reuses an idle launcher-owned process; each batch gets a disposable colony. Name several batches in one `run`: it groups them by mod set, so batches that share a set share a launch. Leave the session open for the next run. Close it (`close-session`) before changing loaded DLLs or running `release-check`, or when the user wants RimWorld closed. A runtime mismatch requires deliberate deployment under the mod's rules. Never attach to a user's colony. Read `summary.txt` first, then relevant cases in `report.json` and log excerpts. The summary counts logged errors and lists passing cases that ran over them; each case's evidence holds the first lines, and the run folder has a copy of `Player.log`. Errors containing the settings class's `ErrorMarker` count as the mod's own, so give a mod with a short or common name a distinctive marker. Set `FailOnModErrors` to make such an error fail the run; it is the recommended setting, especially for a mod that patches other mods.

The count covers errors logged through `Verse.Log.Error` and also Unity errors and uncaught exceptions that bypass it, such as an exception thrown inside a per-frame Harmony patch (for example on `Root_Play.Update`) that the engine logs itself. An error that reaches both counts once. Such an entry counts as the mod's own when its message or stack trace contains the `ErrorMarker`, the production assembly's name or one of its namespaces, so it counts toward `ModErrors` and `FailOnModErrors`. Case evidence shows these as `uncaught exception:` or `Unity error:`. Built 2026-11-17 and compile-checked; no run has yet observed an uncaught mod exception.

Plan a case that only writes evidence, such as a screenshot or clip, at `Levels.Evidence`. The summary and `report.json` (`counts.evidence`) count those apart from behaviour checks, so the `Gameplay` line means behaviour checked; a failed evidence case still fails the run. `Levels.Diagnostic` stays for the harness's own self-checks. A skipped case and a batch that never ran are not coverage, even in a run reported as PASS: the summary lists every skip under "Not covered" and every registered batch outside `RunAll` that the run didn't include under "Not run, outside run-all" (also `unscheduledBatches` in `report.json`). `run <batch> --case <id or glob>` (repeatable; `*` and `?`, full case ids, case-insensitive) runs only the matching cases, for iterating on a few cases. The run id ends in `-cases`, and the summary says FILTERED. Every other planned case is reported as a `not-selected` skip, even if its code ran, and is not counted as a gap. A pattern that matches no planned case is refused (exit 3), and a batch with no selected case is left out of a multi-batch run. Batch code still runs in full unless it guards a case's setup and waits with `ctx.Selected(id)`, so filtering saves time only in batches that do. Unselected cases whose code runs still record their results during the batch, so `SkipUnlessPassed` prerequisites keep working. `release-check` ignores not-selected cases. Added 2026-11-18. A filtered run is never a release or seam run. `timings [run]` prints each batch's wall clock from the run's `events.jsonl`, slowest first, for the latest run by default. Measure before speeding a suite up; a few batches usually hold most of the time. Evidence is under `work/userdata/<argPrefix>/<evidenceFolder>` in this checkout; `latest` reads it without launching a game.

## Mod sets

The launcher starts RimWorld with `-savedatafolder=work/userdata/<argPrefix>`, so the player's `ModsConfig.xml`, Prefs, mod settings and saves are never written and need no backup. Each launch writes that folder's `ModsConfig.xml` from `devtests.json`:

```json
"modSets": { "default": ["brrainz.harmony", "ludeon.rimworld", "author.mymod"], "other": ["brrainz.harmony", "ludeon.rimworld", "author.othermod", "author.mymod"] },
"batchModSets": { "mymod-with-other": "other" }
```

- A batch uses its `batchModSets` entry, otherwise `default` (required). `run-all` uses the union of `default` and every mapped set; unmapped sets are optional variants for `--mods <set>`.
- An unmapped set's batches run only when named with `--mods <set>`, never in `run-all`. Name in the mod's `TESTING.md` or instructions when each one runs, usually the Full tier, or it never runs.
- Build each set from what its mods expect, DLCs included, not the smallest list that loads; a dependency missing a DLC it assumes can log enough errors to hide a real one. See [environment](recipes/environment.md).
- List packageIds in load order, DLCs included. The launcher refuses a set with an uninstalled mod, a missing dependency or a `loadAfter`/`loadBefore` violation; it never adds or reorders mods.
- Every mod must pass the shared `perf` batch, which reports the mod's Dubs ms/tick, and its own `perf.*` cases, which time patched and event-driven paths with `PerfTiming`. `release-check` fails without an unmapped `perf` set that adds Dubs Performance Analyzer, or without passing runs of those cases on the DLL being released, and warns when the mod defines no `perf.*` cases. Override `PerfSetup` when a bare colony would not exercise the mod; see `guide perf`.
- `--mods full` uses the player's active list and mod settings, adding the mod under test if missing.
- Mod settings start at defaults. A set that needs other values reads `DevTests/modsettings/<set>/Mod_*.xml`. Settings are process-wide, so `run-all` refuses to merge sets when any of them has a settings folder; run those batches separately.
- A mod that installs a built package rather than its repository layout sets `"runtimeRoot"` (for example `artifacts/package/<Mod>`). The installed mod is compared with that folder, and `productionDll` is relative to it.
- A settings class that overrides `ExtraRuntimeExclusions` lists the same file names in `"runtimeExclusions"`. `runtimeFolders` and `runtimeFiles` must match `RuntimeFolders` and `RuntimeFiles` too; when the hashes disagree, the launcher names the entry that differs.
- An idle session with a different set is closed and relaunched. `Prefs.xml` is copied from the player once, when the folder is created; every launch then sets its language to English and its autosave interval to one day.
- RimWorld 1.7 still writes `Player.log` to the player's `Logs` folder.

Record the game build, mod/DLC set, run ID, observed result and coverage gaps in the owning mod's ticket or testing record. Keep passing diagnostics separate from gameplay coverage. Preserve and restore temporary configuration changes. Promote a reusable discovery through `guide maintaining` before declaring the setup correction complete.
