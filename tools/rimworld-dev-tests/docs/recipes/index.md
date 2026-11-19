# Test setup recipe index

Search this index by symptom, required state or game type. Read only the matching file or linked source section. Availability below describes the current implementation, not the desired one. Evidence comes from RimWorld 1.7.5000 rev1275 unless the recipe says otherwise.

| Need or search terms | Read | Availability |
| --- | --- | --- |
| Wall, blocked cell, footprint, interaction cell, sliding, tween, facing, rotation, walking backwards | [Placement](placement.md) | Shared validation/observer; shared facing update |
| Bed, patient, LayDown, downed, CurrentBed, asleep, prisoner room | [Beds](beds.md) | Mod-local helpers; game facts shared |
| Prerequisite, guard, setup failure, coverage, control, reload | [Measurements](measurements.md) | Shared `Kit.Require`, `Wait.While`, `SkipUnlessPassed` |
| Session, focus, minimize, seed, research lost, wild animals, modpack, mod list, ModsConfig, foreign patch before startup, conflict gate | [Environment](environment.md) | Shared runner plus local modpack examples |
| Meditation, joy full, Meditate ends, psyfocus | [game facts](../game-facts.md#pawns-beds-and-rooms) | Holding psyfocus cannot measure its natural gain |
| Worker, work priority, research, bills, job never starts | `Harness/Kit.cs` (`Worker`) | Shared `Kit.Worker` |
| Apparel never picked up, optimize apparel, outfit policy, wear, gear up | [game facts](../game-facts.md#pawns-beds-and-rooms) | Put test apparel in a stockpile |
| Performance, ms per tick, Dubs Performance Analyzer, lag, Stopwatch, patch overhead | [Perf](perf.md) | Shared `perf` batch with a `perf` mod set, plus the mod's own `perf.*` cases timed with `PerfTiming` |
| Harmony patch silently off, patch count, dependency update, target renamed | [Patches](patches.md) | Shared `Kit.PatchCounts`; minimums stay in the mod |
| Def or setting leaked between batches, setup missing in a later batch, DLC missing from a mod set | [Environment](environment.md) | `HarnessSettings.OnBatchEnd`; mod-local helpers |
| Steps, soft checks, transcript, known gap, not implemented yet, negative needs a positive | [Authoring](../authoring.md#implement-a-case), [Measurements](measurements.md) | Shared `CaseScope.Step`, `Note`, `KnownGap`, `Conclude`; compile-checked only |
| Warning, expected log line, allowance, noisy mod list | [Authoring](../authoring.md#run-and-report) | Shared `AllowedWarnings`, `AllowedErrors`, `FailOnWarnings`; compile-checked only |
| Colonist needs tending, urgent patient, flaky by seed, canary case | [Environment](environment.md) | Shared `Kit.RemoveTendable`, used by `Kit.Worker` |
| Wrong load order, loadAfter ignored, integration both ways | [Authoring](../authoring.md#mod-sets) | `looseOrderSets` in `devtests.json` |
| Job reference changed, job pooled, food reserved by an eater, speed will not change, stranger in black | [game facts](../game-facts.md#reported-by-other-projects-not-verified-here) | Reported for 1.6, not verified on 1.7 |
| Stat offset, quality, pain, clamp, age, gear | [game facts](../game-facts.md#stats) | Versioned facts; use an adult subject for offset ratios |

To add or revise a recipe, use [maintenance](../maintaining.md). Store expected mod behavior and run histories in the owning mod; link the evidence here.
