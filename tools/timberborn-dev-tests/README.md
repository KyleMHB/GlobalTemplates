# Timberborn Dev Tests

Shared C# runner and Python launcher for Timberborn mod developer tests. Each mod supplies its own cases and settings class. The runner builds into `TimberbornDevTests.dll`; `tbtest.py` installs it for one run, starts a fresh game through Steam, waits for the report and puts the player's settings back. Commands, exit codes and run folders follow [RimWorld Dev Tests](../rimworld-dev-tests/README.md).

Agents start at [AGENTS.md](AGENTS.md).

## Add a mod

Each mod adds a `DevTests/` folder:

1. A developer-only project outside the production solution and package output. Set `DevTestsProductionDll`, then import `TimberbornDevTests.props`. The import adds compile-only game references and a project reference to the runner.
2. One `HarnessSettings` subclass with the mod's display name, batches and run-all order.
3. `devtests.json` with the mod's manifest `modId` and an optional `name`.
4. A short Python wrapper in the mod, such as `tools/mymod_test.py`, that runs this folder's `tbtest.py` with `--config DevTests/devtests.json` placed before the command.

See [Authoring](docs/authoring.md) for each part and how the DevTests DLL reaches the game. No developer DLL belongs in a release package.

## Local paths

Defaults assume Steam's standard folder, `C:\Program Files (x86)\Steam\steamapps\common\Timberborn`. For another location, create these untracked files next to this README:

- `TimberbornDevTests.local.props` for builds:

  ```xml
  <Project>
    <PropertyGroup>
      <TimberbornPath>D:\SteamLibrary\steamapps\common\Timberborn</TimberbornPath>
    </PropertyGroup>
  </Project>
  ```

  Set `TimberbornManaged` instead when the game's `Managed` folder is somewhere else.
- `tbtest.local.json` for the launcher: `{ "gameDir": "D:/SteamLibrary/steamapps/common/Timberborn" }`. The `TIMBERBORN_DIR` environment variable overrides `gameDir`. Add `"documentsDir"` only if the game's Documents folder isn't the Windows one; the launcher otherwise finds it as the game does, following OneDrive redirection.

## Build and run

Run `run` and `restore` from your own terminal, with Steam running and Timberborn closed. The game ignores registry changes made from an agent's session.

From the mod root, for example:

```powershell
dotnet build DevTests/MyMod.DevTests.csproj -c Release
python tools/mymod_test.py run mymod-core
python tools/mymod_test.py run smoke --hours 24
python tools/mymod_test.py latest
python tools/mymod_test.py list
python tools/mymod_test.py release-check
```

Or from this folder: `python tbtest.py [--config <mod>/DevTests/devtests.json] <command>`. Without `--config`, `run` disables every installed mod and runs only the built-in batches.

`run <batch>` builds the runner, installs it into `<Documents>/Timberborn/Mods/TimberbornDevTests` with a `request.json`, and disables every installed mod except the one under test and its `RequiredMods`. It then starts a new game, or loads the batch's fixture, and runs that one batch. Afterwards it puts the game's settings key back exactly, removes the runner, and checks that `Saves`, `ExperimentalSaves` and `Maps` were not changed. The built-in batches are `smoke` (a new game runs for a few game hours) and `diagnostic` (the runner checks its own case reporting). Options:

| Option | Default | Effect |
| --- | --- | --- |
| `--map <name>` | the batch's map, `_Mini` | Built-in map for the new game. |
| `--hours <h>` | 2 | Game hours the `smoke` batch runs. |
| `--speed <s>` | 30 | Game speed while waits run (UI speeds 1, 3, 7; dev speeds 30, 99). |
| `--timeout <s>` | 600 | Wall-clock limit for the whole run. The game closes the run with a report 15 s before it and is killed at it. |
| `--startup-timeout <s>` | 120 | Seconds from launch until the runner must start in the game. Otherwise the run reports `STARTUP FAILED` and the game is killed. Raise it for a large mod set. |
| `--keep-open` | off | Leaves the game paused after the report. Close it to finish cleanup. |

The other commands start no game:

- `restore` puts back the settings key and removes the runner after a run whose launcher was killed. The next `run` does this first anyway. It refuses while Timberborn is running.
- `latest [--batch <id>]` prints the newest run's summary, or says the newest run has no report because its game was killed, crashed or never started the runner.
- `timings [run]` prints each batch's wall clock in a run, slowest first, for the latest run by default.
- `list` prints the batches and run-all order the game reported in the mod's newest run. It has nothing to show until a run reaches the main menu.
- `release-check [mod_dir]` checks a package, by default the installed copy of `--config`'s mod.
- `prune [--keep <n>]` deletes all but the newest `n` run folders (20 by default). Nothing else deletes runs.

Exit codes: 0 pass, 1 failures or isolation breach, 2 timeout, crash, failed startup or no report, 3 refusal, 4 launcher error.

The launcher refuses to start while any Timberborn is running, including one you opened, because Steam runs one game at a time. It also refuses when Steam is closed or when the mod or a dependency isn't installed.

## Runs and evidence

Each run gets a folder under `work/runs/<run id>/` with `summary.txt`, `report.json`, `launcher.json`, `Player.log`, `events.jsonl`, `batches.json` and any error-report zips the game wrote. The game logs straight into the run folder, so your own `Player.log` is left alone. Saves made during a run also go there.

Each case's evidence includes the errors logged during it. The summary's `Startup:` line lists errors naming the mod that were logged while the game loaded. A mod that sets `FailOnModErrors` fails any run that logged an error naming it.

The game seeds no randomness, so cases check ranges, not exact values.

## Release check

`release-check` fails when the package holds a DevTests DLL, a DLL that references the runner, a `request.json` or the runner's manifest. It also fails unless every `perf.*` case the mod defines has passed against the production DLL in that package, and warns when the mod defines none. Timberborn has no Dubs Performance Analyzer, so there is no shared perf batch.

## Tooling tests

From this folder run `python -m unittest discover -s tests` for the launcher, and `python -m unittest discover -s tests` in `../dev-tests-core` for the shared core. `dotnet build TimberbornDevTests.csproj -c Release` builds the runner against the installed game.
