# Measuring a mod's performance

Keywords: performance, perf, ms per tick, Dubs Performance Analyzer, profiler, lag, TPS, Stopwatch, PerfTiming, patch overhead, raid, pawn generation.

Players quote a mod's cost as Dubs Performance Analyzer's "Av" column: average milliseconds per tick, such as "0.01 ms". The shared `perf` batch (`Harness/PerfBatches.cs`) produces that figure for the mod's production assembly. Every adapter has it; nothing is needed beyond a mod set.

A mod's performance test has two parts:

1. **The tick baseline:** the shared `perf` batch, which every mod runs unchanged.
2. **Targeted cases:** the mod's own `perf.*` cases, which time the paths a tick average misses. A patch on pawn generation, a raid handler or a map-load hook runs rarely, so its average over 1800 ticks is near zero even when one call stalls the game. Time the path directly with `PerfTiming` at the scale a player meets (see [Targeted timing](#targeted-timing)).

`release-check` fails when `devtests.json` has no `perf` set containing Dubs, when the current DevTests build has never been launched (the game writes the case list at start), or when the newest run of `perf.mod-tick` or of any case whose Id starts with `perf.` did not pass on the production DLL in the released folder. It warns when the mod has no targeted `perf.*` cases. Rerun them after every rebuild you intend to ship. On success it prints each case's run ID and the ms/tick figure.

## Running it

Add an unmapped `perf` set to `devtests.json`: the `default` list with Dubs after Harmony.

```json
"perf": ["brrainz.harmony", "dubwise.dubsperformanceanalyzer.steam", "ludeon.rimworld", "author.mymod"]
```

Then run `python tools/mymod_test.py run perf --mods perf`. Keep the set out of `batchModSets`: Dubs patches Harmony's constructor while it is loaded and its patches outlast its window, so it must not join `run-all`. Without Dubs active the case is skipped as environment unavailable.

## What the batch does

1. Waits for any earlier Dubs cleanup, and clears a previous run's patches when a reused session still holds them.
2. Runs the settings hook `PerfSetup(ctx)`. Override it to place the mod's content and start its normal work; the default measures a bare quickstart colony, where many mods cost nothing.
3. Opens the Dubs window, adds a Tick-category entry, and patches every method in the production DLL synchronously. The harness and dev DLLs are never profiled.
4. Warms up 300 ticks, resets the profilers, then measures 1800 ticks. Dubs keeps 2000 entries per profiler, so every measured tick is in the average.
5. Reports, closes the window and runs Dubs's cleanup, which unpatches everything.

Observations in `perf.mod-tick`:

| Key | Meaning |
| --- | --- |
| `modMsPerTick` | Headline: summed self time of the mod's methods, ms per tick. Self time excludes profiled callees, so nested methods are not counted twice. |
| `modMsPerTickInclusive` | Summed averages including callees; overstates cost when the mod's methods call each other. |
| `methodsCalled`, `patchedMethods` | Methods that ran during the window, and methods Dubs patched. |
| `worstSingleTickMs` | Highest single-method time in one tick; a spike indicator. |
| `wholeTickMs` | Dubs's whole-tick average, for scale. |
| `dubsVersion`, `measuredTicks` | Provenance and a guard that every tick was recorded. |

The evidence lists the ten most expensive methods by self time with calls per tick.

## Limits

- Ticks only. Draw, GUI and update-loop cost (`Update` and `GUI` categories in Dubs) are not measured.
- The figure depends on what `PerfSetup` builds. Compare runs only with the same setup, seed and mod set.
- The pass result means a measurement was taken. There is no shared budget; budgets belong in the mod's targeted cases and spec.
- Dubs is driven by reflection over internal members, verified against Dubs 1.6.0.1's RimWorld 1.7 build on 2026-11-16 (Lumen Stones run `20261116-113653-perf-s1-7981cf67`: 1778 methods patched, 1800 ticks recorded, 0.0039 ms/tick on a bare quickstart colony). Its RimWorld 1.6 build lacks `Profiler.ChildAverage`, so there the case reports environment unavailable. A Dubs update that renames a member does the same and names the missing member. If that becomes a maintenance burden, ask Dubs's author for a public entry point covering these members.
- A mod batch with Id `perf` collides with this one; choose another Id.
- An early exit after patching starts cleanup without waiting for it; the next run waits before measuring.

## Targeted timing

`PerfTiming` (`Harness/PerfTiming.cs`) times code with a Stopwatch, without Dubs, so targeted cases run in the mod's normal mod set.

- `PerfTiming.MsPerCall(call, calls)` returns the median ms per call over five rounds, after warmup. Use it for the mod's own methods.
- `PerfTiming.PatchCost(original, call, calls)` measures what the mod's Harmony patches add to a game method. Rounds alternate between patched and with the production assembly's patches on `original` removed; other mods' patches stay applied. The patches are restored with their owner, priority and ordering before it returns. It throws `SetupException` when the mod has no patch on `original`.
- `cost.Report(c, scale, situation)` records `addedMsPerCall`, `patchedMsPerCall`, `unpatchedMsPerCall`, `scale` and `addedMsAtScale`, with evidence lines.

For each patched or event-driven path, add a case with an Id starting `perf.` to one of the mod's batches:

```csharp
var c = ctx.Begin("perf.pawn-generation");
var request = new PawnGenerationRequest(PawnKindDefOf.Drifter, Faction.OfAncients, forceGenerateNewPawn: true, canGeneratePawnRelations: false);
var original = AccessTools.Method(typeof(PawnGenerator), nameof(PawnGenerator.GeneratePawn), new[] { typeof(PawnGenerationRequest) });
var cost = PerfTiming.PatchCost(original, () => Find.WorldPawns.PassToWorld(PawnGenerator.GeneratePawn(request), PawnDiscardDecideMode.Discard), calls: 50);
cost.Report(c, scale: 150, situation: "one large raid");
c.Expect("addedMsAtScale", "< 5").Check(cost.AddedMsPerCall * 150 < 5, "patch adds too much to a large raid");
```

- Choose the scale from a real situation: pawns in a large raid, things on a busy map, items in a full stockpile. State it in the case so the figure can be judged.
- Take the budget from the mod's spec. Many mods load together, so a cost that seems small alone still adds up; budget each path well under what a player would notice.
- Clean up what the timed call creates, as the example discards each pawn, or later rounds measure a growing world. Force new pawns, or the generator may hand back existing world pawns.
- Timing is noisy. Use enough calls for each round to take several milliseconds, and compare runs on the same machine and setup.
