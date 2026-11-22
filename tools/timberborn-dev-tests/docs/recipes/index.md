# Test setup recipe index

Search this index by symptom, required state or game system, then read only the linked section. No recipe files exist yet: each row points to authoring, the README or the game facts. Availability describes the current implementation. Evidence is from Timberborn 1.1.2.8.

| Need or search terms | Read | Availability |
| --- | --- | --- |
| Game crashes at load, another mod's exception, mod list, isolation, disabled mods, ModEnabled | [Authoring: add a mod adapter](../authoring.md#add-a-mod-adapter), [game facts](../../../../Steam/timberborn/game-facts.md#launching-and-testing) | The launcher isolates the mod plus its `RequiredMods`; the full-list check is pending in game |
| Player's mods left disabled, interrupted run, launcher killed, restore | [README: build and run](../../README.md#build-and-run) | `restore`, and every `run` restores first |
| Run refused "did not reach the game", registry, PlayerPrefs, agent launch | [AGENTS.md](../../AGENTS.md#who-runs-what), [game facts](../../../../Steam/timberborn/game-facts.md#launching-and-testing) | The user runs `run`; the starter probes every key it needs |
| Place a building, template name, no buildable spot, unbuilt building | [Authoring: Kit](../authoring.md#kit) | `Kit.Place`; spike-proven calls |
| Wait for a condition, timed out, prerequisite lost mid-window, setup-failed | [Authoring: waits](../authoring.md#waits) | `Wait.Until`, `UntilWait.TimedOut`, `Wait.While` |
| Fixture, load a save, mid-game state, save during a case | [Authoring: fixtures](../authoring.md#fixtures) | Absolute paths only; not run in game |
| Day, night, clock jump, time of day | [Authoring: Kit](../authoring.md#kit) | `Kit.SkipTo`, `HoursToday`, `IsDaytime` |
| Slow at speed, large population, timeouts, throttle above 30 beavers | [game facts](../../../../Steam/timberborn/game-facts.md#launching-and-testing) (Speed) | Raise `--timeout` or the batch's `WallLimit` |
| Flaky result, random, seed, exact value differs | [game facts](../../../../Steam/timberborn/game-facts.md#launching-and-testing) (no determinism) | Assert on ranges; there is no seed |
| Game window unfocused, background, ticks stop | [SPEC open risks](../../SPEC.md#open-risks) | Unresolved; `smoke` observes `wasUnfocused` |
| Startup error, starter exception, crash scene, FailOnModErrors, error marker | [Authoring: errors](../authoring.md#errors) | `Startup:` line; uncaught starter exception ends the run `interrupted` |
| Steps, soft checks, known gap, not implemented yet | [Authoring: recording a case](../authoring.md#recording-a-case) | `Step`, `Note`, `KnownGap`, `Conclude`; `diagnostic` batch pending in game |
| Developer DLL in package, release, perf | [Authoring: release check](../authoring.md#release-check) | Dev-file check built; the `perf.*` rule is D8 |

When a setup problem is solved and likely to recur, add a recipe file here with its symptom terms, cause, technique, failed approaches, game version and run id, then add its row. Keep expected mod behaviour and run histories in the owning mod.
