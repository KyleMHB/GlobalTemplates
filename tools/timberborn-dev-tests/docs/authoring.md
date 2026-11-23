# Writing mod test cases

Status as of 2026-11-23: only the built-in `smoke` batch has run in game (run `20261123-004441-smoke`). Everything else here is built and unit-tested or compile-checked, with its in-game check still pending; sections say which.

## Locate the existing integration

Read the mod's `AGENTS.md` and `TESTING.md`. Find `DevTests/*.csproj`, its `HarnessSettings` subclass, `devtests.json`, the wrapper script and the approved expected values. Search the [recipe index](recipes/index.md) for the state a case needs before writing setup. Cases and mod-specific helpers stay in the mod's repository.

## Add a mod adapter

A mod adds a `DevTests/` folder with four parts.

**`devtests.json`.** `modId` is required: the `Id` in the mod's `manifest.json`. `list` and `release-check` find the mod's runs by it. `name` is optional and defaults to `modId`; it names the mod in summaries and marks its errors when the settings class sets no `ErrorMarker`. `devBuild` is the built DevTests DLL, relative to the mod root. Without it a run installs only the runner, which is enough for `smoke` with the mod loaded but not for the mod's own batches or the release check's perf rule.

```json
{ "name": "My Mod", "modId": "Author.MyMod", "devBuild": "DevTests/bin/DevTests/MyMod.DevTests.dll" }
```

The launcher keeps that mod and its transitive `RequiredMods` enabled and disables every other installed mod for the run. `OptionalMods` stay out. Ids match exactly. When a Local and a Workshop copy share an Id, the Local copy is used and the other is disabled. A missing mod or dependency is refused (exit 3) before anything changes.

**A developer-only csproj.** Keep it out of the production solution and package output. Name the assembly with `DevTests` in it, so `release-check` catches a stray copy. Set `DevTestsProductionDll` to the production DLL, then import the shared props, which add the game references and a project reference to the runner, all compile-only, so the output holds only the DevTests DLL:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <AssemblyName>MyMod.DevTests</AssemblyName>
    <OutputPath>bin\DevTests\</OutputPath>
    <DevTestsProductionDll>$(MSBuildThisFileDirectory)..\bin\Release\MyMod.dll</DevTestsProductionDll>
  </PropertyGroup>
  <Import Project="$(TIMBERBORN_DEV_TESTS_ROOT)\TimberbornDevTests.props" />
</Project>
```

If the production csproj sits above `DevTests/`, exclude `DevTests\**` from its `Compile` items, or the SDK compiles the cases into the production DLL. Game paths come from the harness's local props (see the [README](../README.md#local-paths)).

**One `HarnessSettings` subclass** in the DevTests assembly. The runner finds it by reflection among assemblies that reference `TimberbornDevTests`; more than one is an error. See [Settings](#settings).

**A wrapper script** in the mod, such as `tools/mymod_test.py`, that runs `tbtest.py` with the mod's config. `--config` must come before the command:

```python
"""My Mod adapter for the shared Timberborn Dev Tests launcher."""
from pathlib import Path
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = Path(os.environ.get("TIMBERBORN_DEV_TESTS_ROOT", "")) / "tbtest.py"

if __name__ == "__main__":
    if not LAUNCHER.is_file():
        sys.exit(f"shared harness not found: {LAUNCHER}; set TIMBERBORN_DEV_TESTS_ROOT to tools/timberborn-dev-tests")
    sys.argv = [str(LAUNCHER), "--config", str(ROOT / "DevTests" / "devtests.json")] + sys.argv[1:]
    runpy.run_path(str(LAUNCHER), run_name="__main__")
```

### Getting the DevTests DLL into the game

Build the DevTests project, then `run`. For each run the launcher creates a dev folder, `<Documents>/Timberborn/Mods/<modId>DevTests` (the `modId` without spaces), holding the runner it just built, the `devBuild` DLL and the run's `request.json`. Isolation keeps that folder enabled with its starter first, and the launcher removes it afterwards. The mod's installed folder is loaded as it is and never changed, so install the production build there as players get it.

The launcher refuses a run when `devBuild` is set but missing, when the installed mod folder holds a DevTests DLL or a DLL that references the runner (copied there by hand, it would load twice), or when the dev folder name is taken by another mod. A run without `--config` uses `Mods/TimberbornDevTests`.

## Settings

```csharp
public class MyModHarness : HarnessSettings
{
    public override string DisplayName => "My Mod";
    public override IEnumerable<Batch> CreateBatches() { yield return new MyModBatch(); }
    public override IEnumerable<string> RunAll { get { yield return "mymod-core"; } }
    public override bool FailOnModErrors => true;
}
```

- Required: `DisplayName` (summaries and logs), `CreateBatches()`, `RunAll` (gameplay batches in order; recorded in `batches.json` and shown by `list`, since `run` takes one batch).
- `DefaultMap` (`_Mini`) and `DefaultFaction` (`Folktails`) apply to every batch that doesn't set its own.
- `ErrorMarker` (defaults to `DisplayName`): text that marks a logged error as the mod's. A stack frame in a namespace of any DLL in the mod's folder also counts. Give a mod with a short or common name a distinctive marker.
- `FailOnModErrors`: any error naming the mod, at startup or during the run, fails the run even when every case passed. Recommended.
- `OnBatchEnd()`: runs on the game thread however the batch ended. Restore process-wide state the batch changed here.

Batch ids must be unique across the mod's batches and the built-in `smoke` and `diagnostic`. A throw while building the batches refuses the run (exit 3) with the message.

## Batches

A batch is one game (a new game on a built-in map, or a fixture save) plus segments that yield waits. Case code between waits runs with game time stopped.

```csharp
public class MyModBatch : Batch
{
    public override string Id => "mymod-core";
    public override IReadOnlyList<PlannedCase> Plan { get; } = new[] { new PlannedCase("mymod.gate-opens", Levels.PlayerWorkflow) };

    public override IEnumerable<Wait> Segment(int index, BatchContext ctx)
    {
        var c = ctx.Begin("mymod.gate-opens");
        var gate = Kit.Place(ctx, "MyGate.Folktails");
        c.Note("Developer placed a gate near the district centre");
        var built = Wait.Until(() => gate.IsFinished, 24f);
        yield return built;
        c.Step(!built.TimedOut, "beavers finish building the gate within a day");
        c.Conclude();
    }
}
```

- `Id`, `Plan` (every case the batch reports) and `Segment(index, ctx)` are required. `SegmentCount` defaults to 1.
- `Map`, `Faction`: the new game's map and faction. `run --map` overrides the map.
- `Fixture`: a save to load instead of a new game (see [Fixtures](#fixtures)).
- `WallLimit`: wall-clock limit once the game is ready, 10 minutes by default.
- `Diagnostic`: for the runner's own self-checks only; `PlannedCase` then takes an `expectedResult`.
- Levels: `Levels.PlayerWorkflow`, `Levels.Mechanical`, `Levels.Diagnostic`.

A planned case the batch never begins is reported as `error`. If a segment or a wait condition throws, the running case becomes `error` and the cases not yet begun become `skip [blocked]`.

## Waits

- `Wait.Hours(h)`: runs the game for `h` game hours at the batch speed.
- `Wait.Until(condition, maxHours)`: runs until the condition holds or `maxHours` pass. Keep the returned `UntilWait` and read its `TimedOut`; `ctx.TimedOut` holds only the latest `Until`'s result and other waits don't clear it.
- `Wait.Frames(n)`: lets frame-driven state catch up with time stopped.
- `Kit.SaveFixture(ctx, name)` returns a `SaveWait` to yield.
- `.While(() => problem or null)` on any wait: observes a prerequisite once a frame. The first problem it sees reaches `ctx.MeasurementProblem` for the checks before the next wait, and `Check` or `Conclude` then record `setup-failed` instead of a verdict.

The runner evaluates one wait per frame. Only `Hours` and `Until` advance time, at `ctx.Speed` (from `run --speed`, 30 by default, or `Kit.Speed`); the runner re-issues the speed if something else changes it.

## Recording a case

`ctx.Begin(id)` returns a `CaseScope` for a planned case. `ctx.Setup(line)` records batch setup; `ctx.Get<T>()` gets any game-context service; `ctx.Hours` is game hours since the settlement began.

- `Expect(key, value)`, `Observe(key, value)`, `Evidence(line)`, `Setup(line)` fill the record. Assert on ranges and on conditions held over a window, never exact values: the game seeds no randomness.
- Finish once with `Pass()`, `Fail(reason)`, `Check(met, reasonIfNot)`, `Error(reason)`, or a skip: `NotApplicable`, `SetupFailed`, `EnvironmentUnavailable`, or `Skip(reason, category)`.
- Steps: `Note(what)` adds context, `Step(met, what)` is a soft check that returns its condition, and `Conclude()` fails with the first failed step. Write steps as the player would see them. A failed step doesn't stop the case, so the summary shows what happened before and after it.
- `KnownGap(holds, what, why)`: a check that isn't true yet. While it doesn't hold, `Conclude` records a `known-gap` skip, listed under "Not covered" without failing the run. Once it holds the summary prints `KNOWN GAP NOW HOLDS`; make it a `Step`.

Give each behaviour the store description promises a case of its own. Put a canary case first when several cases share a fixture.

## Kit

All of these record what they changed in the batch's setup.

| Helper | What it does | In game |
| --- | --- | --- |
| `Kit.Place(ctx, template, maxRing = 12)` | Places a building by template name at the first spot the game accepts, in rings out from the first finished district centre. It starts unbuilt. Throws `SetupException` when there is no centre or spot. | Spike-proven calls; this helper pending |
| `Kit.Beavers(ctx)`, `Kit.Goods(ctx, goodId)` | Population; all stock of a good, including in transit. | `Beavers` in `smoke` |
| `Kit.HoursToday(ctx)`, `Kit.IsDaytime(ctx)` | Day clock readings. | Pending |
| `Kit.SkipTo(ctx, TimeOfDay)` | Jumps the clock to the next start of day or night without simulating the hours between. | Pending |
| `Kit.Speed(ctx, speed)` | Speed for later time-advancing waits (UI 1/3/7, dev 30/99). Speeds above 1 are cut for populations over 30. | Pending |
| `Kit.SaveFixture(ctx, name)` | Saves to `<run>/saves/<settlement>/<name>.timber`; yield the wait. | Pending |
| `Kit.NewGame`, `Kit.LoadFixture`, `Kit.FixturePath` | Used by the runner at the main menu. | `NewGame` in `smoke` |

The built-in `diagnostic` batch has four cases: an intended pass, fail, known gap and `PerfTiming` timing, which exercise Place, Until, SkipTo, the steps model and `PerfTiming`. Its summary should read `diagnostic: 4 of 4 reported as intended`; see `Harness/BuiltinBatches.cs`. Add a helper only when a mod's cases need it.

## Fixtures

A batch with `Fixture` loads a save instead of starting a new game. The runner copies it into `<run>/fixtures/<settlement>/` and loads the copy, so the original is never the live save. Autosave is suspended, and every save goes to the run folder.

An absolute path works. A bare name (with or without `.timber`) is looked up in the mod's `DevTests/Fixtures`, then the run folder. Loading and saving fixtures has not run in game.

## Errors

- Every case gets the errors logged in its window (`LoggedErrors`, first five lines in its evidence), whatever its result.
- In case code, log with `Debug.LogError`, never `Debug.LogException`: the game sends any logged exception to the crash scene.
- Errors naming the mod logged while the game loaded, up to the main menu, are startup errors: the summary's `Startup:` line and `startupModErrors` in `report.json`. The launcher gives the runner's starter top priority so it sees errors from the mod's starter. Later ones count as `modErrors`. Under `FailOnModErrors` either kind fails the run (exit 1).
- An uncaught exception in any mod's `IModStarter` always sends the game to the crash scene. The run ends `interrupted` (exit 2) whatever `FailOnModErrors` says.

The `Startup:` line and the crash path are built and unit-tested; their in-game check is pending.

## Release check

`release-check [mod_dir]` checks the package a release would ship: by default the installed copy of `--config`'s mod that a run would load. It fails on a DLL whose name contains `devtests`, a DLL that references `TimberbornDevTests`, any `request.json`, or a manifest with the runner's Id.

Per SPEC D8 it also requires the mod's `perf.*` cases. The case list comes from a run of the current `devBuild` (launcher.json `devBuildHash`), so pass `--config`; a case added since the last run fails until it runs. Each case whose Id starts with `perf.` in a non-diagnostic batch must have passed in its newest run, and that run's `modBuild` (the hashes of the production DLLs the game loaded) must match the package. The check fails when either doesn't hold, and warns when the mod defines no `perf.*` case.

Time a costly path with `PerfTiming.MsPerCall(call, calls)` (median ms per call over rounds, after a warm-up) and record it with `PerfTiming.Report(c, ms, callsPerRound, scale, situation)`. RimWorld's `PatchCost` is not ported, because the game ships no Harmony. There is no Dubs batch either: Timberborn has no Dubs Performance Analyzer.

## Run and report

```powershell
dotnet build DevTests/MyMod.DevTests.csproj -c Release
python tools/mymod_test.py run mymod-core
python tools/mymod_test.py latest
```

Run `run` as [AGENTS.md](../AGENTS.md#who-runs-what) describes. Read `summary.txt` first, then the cases in `report.json`. Record the game build, run id, result and coverage gaps in the mod's own ticket or testing record. A build establishes compilation, not in-game behaviour.
