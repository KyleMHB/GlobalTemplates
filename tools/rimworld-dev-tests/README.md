# RimWorld Dev Tests

Shared C# runner and Python launcher for RimWorld mod developer tests. Each mod supplies its own cases and settings. The runner builds into `RimWorldDevTests.dll`; changing a mod's cases rebuilds its test assembly while MSBuild reuses the unchanged runner DLL.

For agent instructions, run `python rimtest.py guide`; use `guide recipes` to find setup techniques and pitfalls without reading the full documentation.

## Add a mod

Each mod adds a `DevTests/` folder:

1. Create a developer-only project outside the production solution and package output. Set `DevTestsProductionDll`, then import `RimWorldDevTests.props`. The import adds game references and a project reference to the shared runner. Its default paths target a standard Steam install of RimWorld 1.7 and Workshop Harmony; see [Local paths](#local-paths) to change them.
2. Implement one `HarnessSettings` subclass with the mod name, argument prefix, package ID, production type, batches and run-all order. The shared DLL requires exactly one loaded settings subclass per process.
3. Write batches using `Batch`, `BatchContext`, `Wait` and `Kit`. Expected values belong in the mod's own specification. Reload waits must end their segment; persist cross-reload measurements through `ctx.Remember`/`ctx.Recall`.
4. Add `DevTests/devtests.json` matching the settings, including `modSets` with a `default` mod list and an unmapped `perf` set that adds Dubs Performance Analyzer (see [Mod sets](docs/authoring.md#mod-sets) and [Perf](docs/recipes/perf.md)). Add a short Python wrapper in the mod, such as `tools/mymod_test.py`, that runs this folder's `rimtest.py` with `--config DevTests/devtests.json`.

Both projects target the installed 1.7 runtime. Keep production compatibility targets separate. Shared output stays in `bin/`; mod developer output stays outside `Assemblies/`. No developer DLL belongs in a release package.

## Local paths

Defaults assume Steam's standard folder, `C:\Program Files (x86)\Steam\steamapps\common\RimWorld`, with Harmony from the Workshop. For another location, create these untracked files next to this README:

- `RimWorldDevTests.local.props` for builds:

  ```xml
  <Project>
    <PropertyGroup>
      <RimWorldPath>D:\Steam\steamapps\common\RimWorld</RimWorldPath>
    </PropertyGroup>
  </Project>
  ```

  Set `HarmonyPath` there too when Harmony is not under the same Steam library.
- `rimtest.local.json` for the launcher: `{ "gameDir": "D:/Steam/steamapps/common/RimWorld" }`. The `RIMWORLD_DIR` environment variable overrides it.

## Build and run

From the mod root, for example:

```powershell
dotnet build DevTests/MyMod.DevTests.csproj -c Release
python tools/mymod_test.py run run-all --seed 1 --timeout 1800
python tools/mymod_test.py run mymod-batch --seed 1
python tools/mymod_test.py run mymod-batch mymod-other --seed 1
python tools/mymod_test.py close-session
python tools/mymod_test.py release-check
python tools/mymod_test.py list
python tools/mymod_test.py latest
python tools/mymod_test.py prune --keep 20
```

`list` prints the batches and mod sets the game reported at its last launcher start, and `run` refuses an unknown batch from that list without starting the game. `latest` prints the newest run's summary, or says that the newest run has no report because its game was killed or crashed. `timings [run]` prints each batch's wall clock in a run, slowest first. `prune` deletes all but the newest run folders; nothing else removes evidence.

Build once, then run batches without rebuilding. `run` starts or reuses one launcher-owned process and returns to the main menu after each command. The in-game panel lists case progress and the camera includes fixtures. Close the session before rebuilding any loaded DLL; changed production, adapter, harness or runtime hashes require a new process. Assemblies are loaded for the life of that process.

`--timeout` (900 seconds by default) covers the whole command, game startup included. The launcher passes the limit to the game, which closes the run with a report 15 seconds before it. The launcher kills a game that does not respond. Raise it for `run-all`, where each batch may use its own limit of 15 minutes. `--startup-timeout` (300 seconds) limits how long a newly launched game may take to load with the runner ready, so a runner that fails to start is reported at once instead of after the full timeout.

Exit codes: 0 pass, 1 failures or isolation breach, 2 timeout, interrupted run, failed startup or no report, 3 refusal, 4 launcher error.

`--quit-on-finish` runs a fresh process that exits after the batch. `--keep-open` leaves a fresh process paused at completion until you close it. `install-dev` installs both DLLs and a marker file for Dev mode > Debug actions > Developer tests. Close the game and use `remove-dev` afterwards.

Several mods' tests can run at once, each in its own game: up to `maxGames` in `rimtest.local.json` (default 3, about 1.5 GB of memory each with a small mod set). Leases are per installed mod, so only checkouts of the same mod take turns. A run waits for a free game slot until its `--timeout`; idle sessions keep their slot until `close-session`. Two games never load each other's mod, and the `perf` batch, the `perf` set and `--record` runs wait until no other game is running a batch, since load from other games skews timings and captures. A run's summary says how many other test games were running when it started. `status` lists them.

The launcher refuses a RimWorld it did not start, and mismatched installed files. It installs both developer DLLs, checks user saves and autosave preferences, and removes the DLLs on `close-session` or fresh-process completion. If the launcher is stopped before it can remove them, the DLLs stay in the mod folder but do nothing in a game the launcher did not start; the next run or `remove-dev` removes them. Runtime manifests exclude both developer DLLs; separate hashes identify them. `release-check` rejects any DevTests DLL or marker in the target package, and fails unless the mod's production DLL in that package passed the `perf` batch and every `perf.*` timing case the mod defines. It warns when the mod defines none (see [Perf](docs/recipes/perf.md)).

## Shared behavior and limits

The runner provides a session inbox and heartbeat, progress reports, panel and camera, runner-owned quickstarts and saves, per-case errors, timeout and interrupted-run recovery, and simulation controls scoped to runner colonies. Launcher processes run while unfocused without changing the player's saved preference. Diagnostics deliberately produce failures, skips and errors; their declared outcomes are checked separately from gameplay results. `run-all` starts with the quick `diagnostic` batch. `self-check` runs every diagnostic batch, including the day-long autosave check, cancellation, a stop at the time limit and recovery after a killed game, and verifies each outcome.

Every run counts the errors the game logged, in total and those naming the mod under test. The count includes Unity errors and uncaught exceptions that never went through `Verse.Log.Error`, such as one thrown in a per-frame Harmony patch, without counting an error twice; one whose stack trace names the mod's assembly or namespaces counts as the mod's. The summary shows both counts and lists each passing case that ran over logged errors. A mod that sets `FailOnModErrors` in its settings class fails any run that logged an error naming it.

Every run also reports errors naming the mod that were logged while the game loaded, before the process's first run, such as a bad def or a patch that failed. The summary prints a `Startup:` line with the first five, and `report.json` lists them in `startupModErrors`. Under `FailOnModErrors` they fail the run too. The game keeps only its newest 1000 log messages, so when the log was already full the summary says startup was not checked; run in a fresh launch.

Each run folder also keeps a copy of `Player.log`. Every game on the machine writes that one file and replaces it at launch, so when another test game launched after this one the copy is skipped and `Player.log.txt` says so. The harness's copy of `Prefs.xml` keeps the player's display settings but always uses English and a one-day autosave interval.

World and colony creation use the requested seed. Simulation after map generation is not deterministically seeded. Passing cases establish only their measured behavior. The caller manages any temporary mod-list change and restores it afterwards.

Each mod keeps its cases, settings adapter and mod-specific hooks, such as showcase layouts or triage commands, in its own repository. Common recording capture and recorder handshakes live here.

## Record a run

Use `python tools/mymod_test.py run mymod-batch --record --show-ui --ffmpeg <path-to>/ffmpeg.exe`, substituting the consuming mod's wrapper and batch. Recording uses a fresh process and writes `build.mp4`, capture markers and recording diagnostics to the evidence directory. FFmpeg needs Windows gfxcapture support; nothing is downloaded automatically. Use `python rimtest.py guide recording` for setup, output files and limits.

## Tooling tests

Run `python -m unittest discover -s tests -v` for the launcher and recorder tests. Build the consuming mod's developer project to check its C# adapter and the shared DLL together. Gameplay and live capture validation follow that mod's run scope; a build or simulated recorder test is not a game run.
