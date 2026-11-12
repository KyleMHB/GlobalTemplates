# Writing mod test cases

## Locate the existing integration

Read the mod's `AGENTS.md` and relevant `TESTING.md` sections. Find `DevTests/*.csproj`, its `HarnessSettings` subclass, `devtests.json`, launcher wrapper and approved expected-value rows. Search the [recipe index](recipes/index.md) for the required state before writing setup. Use the mod's existing batches as examples.

Cases and mod-specific instrumentation stay in the mod repository. A mod adapter is a `DevTests/` folder with a settings class (for example `ModHarness.cs`), `devtests.json` and a developer-only `.csproj`. Import `RimWorldDevTests.props`, set the production DLL path and output developer assemblies outside the runtime package. The import builds the shared DLL incrementally. For window capture use `guide recording`. The current shared runner accepts one loaded `HarnessSettings` subclass per process. Check the production target separately; this harness targets the installed RimWorld 1.7 runtime.

## Implement a case

1. Start from a design-sourced expected value. Record prerequisites, intervention, measurement, guard and cleanup in the mod's expected-value row. Separate a controlled mechanical reading from a real player workflow.
2. Add a `PlannedCase` to the batch's `Plan`. Implement it in `Segment` using `BatchContext`, `Kit` and yielded `Wait` instances. Inspect the matching recipe and helper implementation before reusing them; a helper a recipe describes is not necessarily exported by the shared DLL.
3. Establish prerequisites before the measurement. Use `Kit.Require` for instantaneous readings, and `Wait.While` for conditions that must hold throughout a window. See `guide measurements` for an example. Register measured pawns with `Subject` for failure evidence.
   `ctx.TimedOut` holds the latest `Wait.Until` result and other waits do not clear it. When another wait runs before the check, keep the wait (`var arrived = Wait.Until(...); yield return arrived;`) and read `arrived.TimedOut`. An exception thrown by a condition, a per-tick callback or a settings hook ends the batch as a case exception with its top stack frames, the same as one thrown in the segment.
4. Save state needed across a reload with `ctx.Remember`. `Wait.Reload()` ends its segment; reacquire game objects in the next segment. Stop maintenance and clear registrations when a case ends; batch cleanup handles only registered shared state.
5. Register a new batch in the mod's settings and run-all order when appropriate. Build the developer project, then perform only the authorized focused check. A build establishes compilation, not in-game behavior.

## Run and report

Use the mod's wrapper and project paths, for example:

```powershell
dotnet build DevTests/MyMod.DevTests.csproj -c Release
python tools/mymod_test.py run mymod-batch --seed 1
python tools/mymod_test.py close-session
python tools/mymod_test.py release-check
```

`run` reuses an idle launcher-owned process; each batch gets a disposable colony. Close the session before changing loaded DLLs. A runtime mismatch requires deliberate deployment under the mod's rules. Never attach to a user's colony. Read `summary.txt` first, then relevant cases in `report.json` and log excerpts. The summary counts logged errors and lists passing cases that ran over them; each case's evidence holds the first lines, and the run folder has a copy of `Player.log`. Errors containing the settings class's `ErrorMarker` count as the mod's own, so give a mod with a short or common name a distinctive marker. Set `FailOnModErrors` to make such an error fail the run. Evidence is under `work/userdata/<argPrefix>/<evidenceFolder>` in this checkout; `latest` reads it without launching a game.

## Mod sets

The launcher starts RimWorld with `-savedatafolder=work/userdata/<argPrefix>`, so the player's `ModsConfig.xml`, Prefs, mod settings and saves are never written and need no backup. Each launch writes that folder's `ModsConfig.xml` from `devtests.json`:

```json
"modSets": { "default": ["brrainz.harmony", "ludeon.rimworld", "author.mymod"], "other": ["brrainz.harmony", "ludeon.rimworld", "author.othermod", "author.mymod"] },
"batchModSets": { "mymod-with-other": "other" }
```

- A batch uses its `batchModSets` entry, otherwise `default` (required). `run-all` uses the union of `default` and every mapped set; unmapped sets are optional variants for `--mods <set>`.
- List packageIds in load order, DLCs included. The launcher refuses a set with an uninstalled mod, a missing dependency or a `loadAfter`/`loadBefore` violation; it never adds or reorders mods.
- `--mods full` uses the player's active list and mod settings, adding the mod under test if missing.
- Mod settings start at defaults. A set that needs other values reads `DevTests/modsettings/<set>/Mod_*.xml`. Settings are process-wide, so `run-all` refuses to merge sets when any of them has a settings folder; run those batches separately.
- A mod that installs a built package rather than its repository layout sets `"runtimeRoot"` (for example `artifacts/package/<Mod>`). The installed mod is compared with that folder, and `productionDll` is relative to it.
- A settings class that overrides `ExtraRuntimeExclusions` lists the same file names in `"runtimeExclusions"`. `runtimeFolders` and `runtimeFiles` must match `RuntimeFolders` and `RuntimeFiles` too; when the hashes disagree, the launcher names the entry that differs.
- An idle session with a different set is closed and relaunched. `Prefs.xml` is copied from the player once, when the folder is created; every launch then sets its language to English and its autosave interval to one day.
- RimWorld 1.7 still writes `Player.log` to the player's `Logs` folder.

Record the game build, mod/DLC set, run ID, observed result and coverage gaps in the owning mod's ticket or testing record. Keep passing diagnostics separate from gameplay coverage. Preserve and restore temporary configuration changes. Promote a reusable discovery through `guide maintaining` before declaring the setup correction complete.
