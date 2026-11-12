# Guarding measurements

Keywords: prerequisite, guard, setup failure, coverage, control, comparison, reload.

Record setup interventions independently of design-sourced expected values. Setup establishes a required state; the guard observes whether that state held. Keep maintenance in `EveryTick` and observation in `Wait.While`, which runs after each simulated tick. Repair on the next tick must not erase the first lost prerequisite.

Illustrative pattern, using a bed helper only after it is available in the consuming mod:

```csharp
var maintain = BedRest(patient, bed); // the mod's own helper; not in the shared DLL.
yield return Wait.Until(() => BedProblem(patient, bed) == null, 300, maintain);
if (!Kit.Require(ctx, "effect", BedProblem(patient, bed) == null
    ? (true, "patient in bed") : (false, "patient not in bed"))) yield break;
var check = ctx.Begin("effect").Subject(patient).Expect("change", expected);
yield return Wait.Ticks(window, maintain).While(() => BedProblem(patient, bed));
check.Observe("change", observed).Check(observed == expected, "effect differed");
```

The values and effect reading above belong to the actual case, not this recipe. `Kit.Require` creates a setup-failed record only on failure; a successful call allows `Begin` for the same planned ID. `CaseScope.Check` converts a lost window prerequisite into setup failure. Guard occupancy or required injury, not whether the measured effect succeeded.

Use `SkipUnlessPassed` for dependent controls. A failed positive control cannot establish a negative result. Distinguish setup failure, missing optional content, unavailable environment, blocked comparisons and mod assertions. Preserve coverage gaps and interrupted cases; a build or absence of exceptions is not gameplay coverage.

After reload, reacquire pawns, buildings and other game objects; reconstruct actions and registrations. Persist measurements through `ctx.Remember`/`Recall`, not object references in an old iterator.

Available in the shared library: `Harness/Batch.cs` (`Wait.While`, `BatchContext`, `CaseScope`, `SkipUnlessPassed`), `Harness/Kit.cs` (`Require`), `Harness/Report.cs` (assertions and coverage). Diagnostic cases exercise the result categories. A 2026-11-08 run reported all 13 diagnostic outcomes as intended. This does not verify every mod's choice of prerequisites.
