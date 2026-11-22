using System.Collections.Generic;
using Timberborn.TimeSystem;
using UnityEngine;

namespace TimberbornDevTests;

// The runner's check of itself: a new game starts with beavers and game time advances at the requested speed without
// exceptions, which proves the launch, the main-menu start and the in-game hooks work, and whether time runs while the
// window is unfocused (RunReport.WasUnfocused).
public class SmokeBatch : Batch
{
    public const string BatchId = "smoke", CaseId = "smoke.new-game";
    public override string Id => BatchId;
    public override bool Diagnostic => true;
    public override IReadOnlyList<PlannedCase> Plan { get; } = new[] { new PlannedCase(CaseId, Levels.Diagnostic, Results.Pass) };

    public override IEnumerable<Wait> Segment(int index, BatchContext ctx)
    {
        var c = ctx.Begin(CaseId).Expect("gameHours", ">= " + ctx.Request.GameHours).Expect("beaversAtStart", "> 0");
        int beaversAtStart = Kit.Beavers(ctx);
        float startHours = ctx.Hours, startRealtime = Time.realtimeSinceStartup;
        yield return Wait.Hours(ctx.Request.GameHours);
        float hours = ctx.Hours - startHours;
        c.Observe("gameHours", hours).Observe("wallSeconds", Time.realtimeSinceStartup - startRealtime).Observe("requestedSpeed", ctx.Speed)
            .Observe("beaversAtStart", beaversAtStart).Observe("beaversAtEnd", Kit.Beavers(ctx)).Observe("wasUnfocused", RunReport.WasUnfocused)
            .Observe("exceptions", RunReport.ExceptionCount);
        string reason = beaversAtStart == 0 ? "the new game started without beavers"
            : hours < ctx.Request.GameHours ? $"only {hours:0.##} game hours passed"
            : RunReport.ExceptionCount > 0 ? $"{RunReport.ExceptionCount} exception(s) logged; see report errors"
            : null;
        c.Check(reason == null, reason);
    }
}

// Runner self-checks of the case API. Each case declares the result the runner must report, so a run where every case is
// reported as intended passes; none of them is gameplay evidence.
public class DiagnosticBatch : Batch
{
    // The timing case is not named perf.*: release-check counts only a mod's own perf cases.
    public const string PassCase = "diag.pass", FailCase = "diag.fail", GapCase = "diag.known-gap", TimingCase = "diag.perf-timing";
    public override string Id => "diagnostic";
    public override bool Diagnostic => true;
    // The placed building's template is the Folktails one.
    public override string Faction => "Folktails";

    public override IReadOnlyList<PlannedCase> Plan { get; } = new[]
    {
        new PlannedCase(PassCase, Levels.Diagnostic, Results.Pass),
        new PlannedCase(FailCase, Levels.Diagnostic, Results.Fail),
        new PlannedCase(GapCase, Levels.Diagnostic, Results.Skip),
        new PlannedCase(TimingCase, Levels.Diagnostic, Results.Pass),
    };

    public override IEnumerable<Wait> Segment(int index, BatchContext ctx)
    {
        // Exercises Kit and every wait through the steps model; ranges only (D6), since nothing in the game is seeded.
        var pass = ctx.Begin(PassCase);
        int beavers = Kit.Beavers(ctx), berries = Kit.Goods(ctx, "Berries");
        pass.Observe("beavers", beavers).Observe("berries", berries);
        pass.Step(beavers > 0, "the new settlement starts with beavers");
        pass.Step(berries > 0, "the settlement starts with berries in stock");
        var flag = Kit.Place(ctx, "LumberjackFlag.Folktails");
        pass.Note("Developer placed a lumberjack flag near the district centre");
        var built = Wait.Until(() => flag.IsFinished, 24f);
        built.While(() => Kit.Beavers(ctx) == 0 ? "every beaver was gone" : null);
        float before = ctx.Hours;
        yield return built;
        pass.Observe("hoursToBuild", ctx.Hours - before);
        pass.Step(!built.TimedOut, "beavers finish building it within 24 game hours");
        yield return Wait.Frames(2);
        Kit.SkipTo(ctx, TimeOfDay.Nighttime);
        pass.Step(!Kit.IsDaytime(ctx), "moving the clock to the night makes it night");
        before = ctx.Hours;
        yield return Wait.Hours(1f);
        pass.Observe("hoursWaited", ctx.Hours - before);
        pass.Step(ctx.Hours - before >= 1f, "an hour's wait runs at least one game hour");
        pass.Conclude();

        // Proves a failed step fails the case, and that an error logged in its window reaches its evidence.
        var fail = ctx.Begin(FailCase);
        Debug.LogError("[TimberbornDevTests diagnostic] Intentional diagnostic error for " + FailCase);
        fail.Step(true, "a step that holds is listed before the failure");
        fail.Step(1 == 2, "intentional: 1 is 2");
        fail.Step(true, "a step after the failure still runs");
        fail.Conclude();

        // Proves an open known gap skips the case without failing the run.
        var gap = ctx.Begin(GapCase);
        gap.Step(true, "a step that holds");
        gap.KnownGap(false, "something the runner doesn't do yet", "intentional diagnostic gap");
        gap.Conclude();

        // Proves PerfTiming measures in game: a goods count is cheap, so its time is above zero and far below a frame.
        var timing = ctx.Begin(TimingCase);
        double ms = PerfTiming.MsPerCall(() => Kit.Goods(ctx, "Berries"), calls: 200);
        PerfTiming.Report(timing, ms, 200, 100, "a hundred stock lookups in one frame");
        timing.Step(ms > 0, "a timed call takes measurable time");
        timing.Step(ms < 5, "one stock lookup takes under 5 ms");
        timing.Conclude();
    }
}
