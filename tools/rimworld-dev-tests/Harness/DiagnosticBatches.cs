using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;

namespace RimWorldDevTests;

// Runner self-checks. Each case declares the result the runner must report; none of them is gameplay evidence.
public class DiagnosticBatch : Batch
{
    public override string Id => "diagnostic";
    public override bool Diagnostic => true;
    public override int SegmentCount => 1;

    public override IReadOnlyList<PlannedCase> Plan { get; } = new[]
    {
        new PlannedCase("diag.known-pass", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag.unmet-assertion", Levels.Diagnostic, Results.Fail),
        new PlannedCase("diag.dependent-skip", Levels.Diagnostic, Results.Skip),
        new PlannedCase("diag.optional-unavailable", Levels.Diagnostic, Results.Skip),
        new PlannedCase("diag.missing-required-def", Levels.Diagnostic, Results.Error),
        new PlannedCase("diag.timeout", Levels.Diagnostic, Results.Error),
        new PlannedCase("diag.refuse-unrelated-colony", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag.autosave-suppressed", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag.coverage-setup", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag.coverage-optional", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag.coverage-blocked", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag.coverage-inconclusive", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag.window-invalid", Levels.Diagnostic, Results.Skip),
    };

    public override IEnumerable<Wait> Segment(int index, BatchContext ctx)
    {
        // Seed-dependent observations; two runs with the same seed must report the same values.
        var known = ctx.Begin("diag.known-pass").Expect("colonists", 3);
        yield return Wait.Ticks(60);
        var colonists = ctx.Map.mapPawns.FreeColonists.OrderBy(p => p.thingIDNumber).ToList();
        known.Observe("colonists", colonists.Count).Observe("worldSeed", Find.World.info.seedString).Observe("tile", (int)ctx.Map.Tile)
            .Observe("firstColonist", colonists.FirstOrDefault()?.Name?.ToStringFull).Observe("mapSize", ctx.Map.Size.x)
            .Observe("ticksAdvanced", ctx.Now);
        known.Check(colonists.Count == 3, $"expected 3 starting colonists, saw {colonists.Count}");

        ctx.Begin("diag.unmet-assertion").Subject(colonists.FirstOrDefault()).Expect("value", 2).Observe("value", 1).Check(1 == 2, "intentional: 1 is not 2");

        if (!ctx.SkipUnlessPassed("diag.dependent-skip", "diag.unmet-assertion"))
            ctx.Begin("diag.dependent-skip").Fail("ran although its prerequisite failed");

        var optional = ctx.Begin("diag.optional-unavailable");
        if (!ModsConfig.IsActive("rimworlddevtests.absent-optional")) optional.NotApplicable("optional content not loaded: rimworlddevtests.absent-optional");
        else optional.Fail("an optional mod that should not exist is active");

        // A required definition that is missing is an error, never a skip.
        var required = ctx.Begin("diag.missing-required-def").Subject(colonists.FirstOrDefault()).Expect("ThingDef", "RimWorldDevTests_Absent");
        if (DefDatabase<ThingDef>.GetNamedSilentFail("RimWorldDevTests_Absent") == null)
        {
            // Proves a logged error reaches the failing case's evidence (CaseErrors).
            Log.Error("[RimWorldDevTests diagnostic] Intentional diagnostic error: required definition missing: RimWorldDevTests_Absent");
            required.Error("required definition missing: RimWorldDevTests_Absent");
        }
        else required.Pass();

        var timeout = ctx.Begin("diag.timeout").Subject(colonists.FirstOrDefault()).Expect("condition", "never true").Expect("tickLimit", 120);
        yield return Wait.Until(() => false, 120);
        if (ctx.TimedOut) timeout.Error("timed out after 120 ticks waiting for a condition");
        else timeout.Fail("an impossible condition was reported as met");

        // Exercise the seam's ownership guard: with the identity removed, this colony looks unrelated.
        var refuse = ctx.Begin("diag.refuse-unrelated-colony").Expect("refused", true);
        string identity = RunnerIdentity.Of(Current.Game);
        RunnerIdentity.Set(Current.Game, null);
        string refusal;
        try { refusal = TestRunner.Start(new RunRequest { Batch = "diagnostic", Seed = ctx.Seed }, "should-not-start"); }
        finally { RunnerIdentity.Set(Current.Game, identity); }
        refuse.Observe("refused", refusal != null).Observe("reason", refusal);
        refuse.Check(refusal != null && refusal.Contains("unrelated colony"), "the runner did not refuse a start over an unrelated colony");

        // A full autosave interval passes without a save while this colony is runner-owned.
        var autosave = ctx.Begin("diag.autosave-suppressed").Expect("autosavesWritten", 0).Setup("Advanced one autosave interval (Prefs.AutosaveIntervalDays)");
        var before = AutosaveStamps();
        int interval = (int)(Prefs.AutosaveIntervalDays * GenDate.TicksPerDay) + 10;
        autosave.Observe("intervalTicks", interval);
        yield return Wait.Ticks(interval);
        int written = AutosaveStamps().Count(kv => !before.TryGetValue(kv.Key, out var t) || t != kv.Value);
        autosave.Observe("autosavesWritten", written).Check(written == 0, $"{written} autosave files were written or changed");

        Progress Example(string category) => new()
        {
            Status = RunStatus.Complete,
            BatchRecords = new() { new BatchRecord { Id = "example", Status = RunStatus.Complete, Planned = new() { "case" } } },
            Cases = new() { new CaseRecord { Batch = "example", Id = "case", Result = Results.Skip, CoverageReason = category } },
        };
        var setup = Example(CoverageReasons.SetupFailed);
        ctx.Begin("diag.coverage-setup").Check(setup.AssertionsPass && !setup.CoverageComplete && !setup.OverallPass,
            "a failed setup was accepted as complete coverage");
        var optionalExample = Example(CoverageReasons.NotApplicable);
        ctx.Begin("diag.coverage-optional").Check(optionalExample.CoverageComplete && optionalExample.OverallPass,
            "explicitly absent optional content prevented an applicable pass");
        var blocked = Example(CoverageReasons.Blocked);
        ctx.Begin("diag.coverage-blocked").Check(!blocked.CoverageComplete && !blocked.OverallPass,
            "a blocked dependent case was accepted as complete coverage");
        var inconclusive = Example(CoverageReasons.WorkflowInconclusive);
        ctx.Begin("diag.coverage-inconclusive").Check(inconclusive.CoverageComplete && inconclusive.OverallPass,
            "an inconclusive player workflow prevented an applicable pass");
        // Simulates the runner having just finished a window whose prerequisite was lost.
        var previous = ctx.LastWait;
        ctx.LastWait = Wait.Ticks(0).While(() => "intentional prerequisite loss between observations");
        ctx.LastWait.AfterTick();
        ctx.Begin("diag.window-invalid").Subject(colonists.FirstOrDefault()).Check(true, "an invalid window passed");
        ctx.LastWait = previous;
    }

    private static Dictionary<string, System.DateTime> AutosaveStamps() =>
        new System.IO.DirectoryInfo(GenFilePaths.SavedGamesFolderPath).GetFiles("Autosave-*").ToDictionary(f => f.Name, f => f.LastWriteTimeUtc);
}

// Cancellation through the same path as the developer menu: one case passes, one is cut off, one never starts.
public class DiagnosticCancelBatch : Batch
{
    public override string Id => "diagnostic-cancel";
    public override bool Diagnostic => true;
    public override int SegmentCount => 1;

    public override IReadOnlyList<PlannedCase> Plan { get; } = new[]
    {
        new PlannedCase("diag-cancel.before", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag-cancel.during", Levels.Diagnostic, Results.Error),
        new PlannedCase("diag-cancel.after", Levels.Diagnostic, Results.Pass),
    };

    public override IEnumerable<Wait> Segment(int index, BatchContext ctx)
    {
        ctx.Begin("diag-cancel.before").Pass();
        ctx.Begin("diag-cancel.during");
        yield return Wait.Ticks(30);
        ctx.RequestCancel();
        yield return Wait.Ticks(30);
        ctx.Begin("diag-cancel.after").Pass();
    }
}

// Never finishes: the launcher's wall-clock limit kills the game, and the next start must recover the run.
public class DiagnosticStallBatch : Batch
{
    public override string Id => "diagnostic-stall";
    public override bool Diagnostic => true;
    public override int SegmentCount => 1;
    public override System.TimeSpan WallLimit => System.TimeSpan.FromHours(2);

    public override IReadOnlyList<PlannedCase> Plan { get; } = new[]
    {
        new PlannedCase("diag-stall.before", Levels.Diagnostic, Results.Pass),
        new PlannedCase("diag-stall.forever", Levels.Diagnostic, Results.Error),
        new PlannedCase("diag-stall.after", Levels.Diagnostic, Results.Pass),
    };

    public override IEnumerable<Wait> Segment(int index, BatchContext ctx)
    {
        ctx.Begin("diag-stall.before").Pass();
        var forever = ctx.Begin("diag-stall.forever");
        yield return Wait.Until(() => false, int.MaxValue, () => System.Threading.Thread.Sleep(1));
        forever.Error("stall ended unexpectedly");
        ctx.Begin("diag-stall.after").Pass();
    }
}
