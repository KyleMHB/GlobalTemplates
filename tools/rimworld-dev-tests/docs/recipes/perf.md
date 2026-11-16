# Measuring a mod's tick cost

Keywords: performance, perf, ms per tick, Dubs Performance Analyzer, profiler, lag, TPS.

Players quote a mod's cost as Dubs Performance Analyzer's "Av" column: average milliseconds per tick, such as "0.01 ms". The shared `perf` batch (`Harness/PerfBatches.cs`) produces that figure for the mod's production assembly. Every adapter has it; nothing is needed beyond a mod set.

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
- The pass result means a measurement was taken. There is no shared budget; a mod that wants one asserts it in its own batch from the report or its spec.
- Dubs is driven by reflection over internal members, verified against Dubs 1.6.0.1's RimWorld 1.7 build on 2026-11-16 (Lumen Stones run `20261116-113653-perf-s1-7981cf67`: 1778 methods patched, 1800 ticks recorded, 0.0039 ms/tick on a bare quickstart colony). Its RimWorld 1.6 build lacks `Profiler.ChildAverage`, so there the case reports environment unavailable. A Dubs update that renames a member does the same and names the missing member. If that becomes a maintenance burden, ask Dubs's author for a public entry point covering these members.
- A mod batch with Id `perf` collides with this one; choose another Id.
- An early exit after patching starts cleanup without waiting for it; the next run waits before measuring.
