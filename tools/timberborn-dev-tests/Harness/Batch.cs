using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Bindito.Core;
using Timberborn.TimeSystem;

namespace TimberbornDevTests;

public class PlannedCase
{
    public string Id { get; }
    public string Level { get; }
    // Diagnostic batches only: the result the runner must report for this case.
    public string ExpectedResult { get; }

    public PlannedCase(string id, string level, string expectedResult = null)
    {
        Id = id;
        Level = level;
        ExpectedResult = expectedResult;
    }
}

public static class Levels
{
    public const string PlayerWorkflow = "player-workflow", Mechanical = "mechanical", Diagnostic = "diagnostic";
}

// A batch is one fixture (a new game on a built-in map, or a fixture save) plus segments. Each segment yields waits; the
// runner evaluates the current wait once a frame, and case code between waits runs with game time stopped.
public abstract class Batch
{
    public abstract string Id { get; }
    public virtual bool Diagnostic => false;
    // Built-in map for the batch's new game; the request's map wins when it names one.
    public virtual string Map => Harness.Settings?.DefaultMap ?? Harness.BuiltinMap;
    public virtual string Faction => Harness.Settings?.DefaultFaction ?? Harness.BuiltinFaction;
    // A fixture save to load instead of a new game (D5): an absolute path, or a .timber name looked up in the request's
    // FixtureDir (the mod's DevTests/Fixtures), then the run folder. The runner loads a copy in the run folder.
    public virtual string Fixture => null;
    // Wall-clock limit for the whole batch once its game is ready.
    public virtual TimeSpan WallLimit => TimeSpan.FromMinutes(10);
    public abstract IReadOnlyList<PlannedCase> Plan { get; }
    public virtual int SegmentCount => 1;
    public abstract IEnumerable<Wait> Segment(int index, BatchContext ctx);
}

public class SetupException : Exception
{
    public SetupException(string message) : base(message) { }
}

public abstract class Wait
{
    // The first lost prerequisite this window observed, or null.
    public string Problem { get; private set; }
    internal Func<string> Prerequisite;

    // True for waits that run the game at the batch's speed; the others hold time still.
    internal virtual bool AdvancesTime => false;

    // Observes a prerequisite while the wait runs, sampled once a frame (at x30 a frame spans a tick or more, so a lapse
    // shorter than a frame can go unseen). The problem belongs to this wait, so it reaches only the checks between this wait
    // and the next one.
    public Wait While(Func<string> problem)
    {
        var earlier = Prerequisite;
        Prerequisite = () => earlier?.Invoke() ?? problem();
        return this;
    }

    internal void Observe()
    {
        if (Problem == null && Prerequisite != null) Problem = Prerequisite();
    }

    // Runs the game for this many game hours at the batch speed.
    public static Wait Hours(float hours) => new HoursWait { Duration = hours };

    // Runs the game until the condition holds or maxHours of game time pass; TimedOut tells which.
    public static UntilWait Until(Func<bool> condition, float maxHours) => new UntilWait { Condition = condition, MaxHours = maxHours };

    // Lets frame-driven state catch up with game time stopped.
    public static Wait Frames(int frames) => new FrameWait { Remaining = frames };
}

public class HoursWait : Wait
{
    public float Duration;
    internal float Start = float.NaN;
    internal override bool AdvancesTime => true;
}

// TimedOut is this wait's own result. ctx.TimedOut holds the latest Until's result and is not cleared by other waits, so keep
// the wait in a variable when another wait runs before the check.
public class UntilWait : Wait
{
    public Func<bool> Condition;
    public float MaxHours;
    internal float Start = float.NaN;
    public bool TimedOut { get; internal set; }
    internal override bool AdvancesTime => true;
}

public class FrameWait : Wait { public int Remaining; }

// Waits for a queued save to complete (Kit.SaveFixture), with game time stopped.
public class SaveWait : Wait
{
    public string Path { get; internal set; }
    public bool Done { get; internal set; }
}

public class BatchContext
{
    private readonly IContainer container;
    private readonly Batch batch;
    internal readonly BatchRecord Record;
    public bool TimedOut { get; internal set; }
    // The most recent wait, set by the runner as each starts. Checks after it read its window's problem.
    internal Wait LastWait;
    public string MeasurementProblem => LastWait?.Problem;
    // Errors logged after this mark belong to the next case to finish: it moves on whenever a case finishes.
    internal long ErrorMark = CaseErrors.Mark;

    internal BatchContext(IContainer container, BatchRecord record, Batch batch, float speed)
    {
        this.container = container;
        Record = record;
        this.batch = batch;
        Speed = speed;
    }

    public RunRequest Request => Runner.Request;
    public string BatchId => batch.Id;
    // Game speed for waits that advance time (Kit.Speed changes it).
    public float Speed { get; internal set; }

    // Any game-context service, as the game's own classes receive it.
    public T Get<T>() => container.GetInstance<T>();

    // Game hours since the settlement began (day number plus the part of today that has passed).
    public float Hours => Get<IDayNightCycle>().PartialDayNumber * 24f;

    public void Setup(string line) => Record.Setup.Add(line);

    public CaseScope Begin(string id)
    {
        var planned = batch.Plan.FirstOrDefault(p => p.Id == id) ?? throw new ArgumentException("Case not in the batch plan: " + id);
        var existing = RunReport.Case(batch.Id, id);
        if (existing != null && existing.Result != Results.Running) throw new InvalidOperationException("Case already recorded: " + id);
        var c = existing ?? new CaseRecord
        {
            Id = id, Batch = batch.Id, Level = planned.Level, Diagnostic = batch.Diagnostic, ExpectedResult = planned.ExpectedResult,
            StartHours = Hours, ErrorMark = ErrorMark,
        };
        if (existing == null) RunReport.Cases.Add(c);
        return new CaseScope(c, this);
    }
}

public class CaseScope
{
    private readonly CaseRecord record;
    private readonly BatchContext ctx;

    internal CaseScope(CaseRecord record, BatchContext ctx)
    {
        this.record = record;
        this.ctx = ctx;
    }

    public CaseScope Setup(string line) { record.Setup.Add(line); return this; }
    public CaseScope Expect(string key, object value) { record.Expected[key] = Format(value); return this; }
    public CaseScope Observe(string key, object value) { record.Observed[key] = Format(value); return this; }
    public CaseScope Evidence(string line) { record.Evidence.Add(line); return this; }

    public static string Format(object value) => value switch
    {
        null => "null",
        float f => f.ToString("0.#####", CultureInfo.InvariantCulture),
        double d => d.ToString("0.#####", CultureInfo.InvariantCulture),
        bool b => b ? "true" : "false",
        IFormattable x => x.ToString(null, CultureInfo.InvariantCulture),
        _ => value.ToString(),
    };

    public void Pass() => Finish(Results.Pass, "");
    public void Fail(string reason) => Finish(Results.Fail, reason);
    // Every skip declares its coverage meaning (CoverageReasons).
    public void Skip(string reason, string category) { record.CoverageReason = category; Finish(Results.Skip, reason); }
    public void NotApplicable(string reason) => Skip(reason, CoverageReasons.NotApplicable);
    public void SetupFailed(string reason) => Skip(reason, CoverageReasons.SetupFailed);
    public void EnvironmentUnavailable(string reason) => Skip(reason, CoverageReasons.Environment);
    public void Error(string reason) => Finish(Results.Error, reason);

    // ---- Step transcript ---------------------------------------------------------------------------------------------------
    // A case told as steps in the player's words. A failed step does not stop the case, so the record shows what had happened
    // when it went wrong and every check after it; Conclude finishes the case from the steps.

    // A line of context that checks nothing: a building placed, a setting changed.
    public CaseScope Note(string what) { record.Steps.Add("        " + what); return this; }

    // A soft check. Returns the condition, so a case can stop where the rest would be moot.
    public bool Step(bool met, string what)
    {
        record.Steps.Add((met ? PassedStep : FailedStep) + what);
        return met;
    }

    // Something the case checks that is not true yet, with the reason: the mod doesn't do it, or the mod it needs isn't loaded.
    // The check still runs. While it doesn't hold the case concludes as a known-gap skip; once it holds the step reads FIXED and
    // the summary says to make it a Step.
    public CaseScope KnownGap(bool holds, string what, string why)
    {
        if (holds) { record.Steps.Add("  FIXED " + what + " (a known gap that now holds: make it a Step)"); record.FixedGaps++; }
        else record.Steps.Add(GapStep + what + ": " + why);
        return this;
    }

    private const string PassedStep = "  PASS  ", FailedStep = ">>FAIL  ", GapStep = "  GAP   ";

    // Finishes a case built from steps: a lost window prerequisite is a setup failure, a failed step fails with the first one,
    // an open known gap skips, otherwise it passes.
    public void Conclude()
    {
        string failed = record.Steps.FirstOrDefault(s => s.StartsWith(FailedStep));
        var gaps = record.Steps.Where(s => s.StartsWith(GapStep)).ToList();
        if (ctx.MeasurementProblem != null) SetupFailed(ctx.MeasurementProblem);
        else if (failed != null) Fail(failed.Substring(FailedStep.Length));
        else if (gaps.Count > 0)
            Skip("known gap, " + gaps[0].Substring(GapStep.Length) + (gaps.Count > 1 ? $" (and {gaps.Count - 1} more)" : ""), CoverageReasons.KnownGap);
        else Pass();
    }

    // Pass when the observation meets the expectation, otherwise fail with the reason.
    public void Check(bool met, string reasonIfNot)
    {
        if (ctx.MeasurementProblem != null) { SetupFailed(ctx.MeasurementProblem); return; }
        if (met) Pass();
        else Fail(reasonIfNot);
    }

    private void Finish(string result, string reason)
    {
        if (record.Result != Results.Running) throw new InvalidOperationException("Case already finished: " + record.Id);
        record.Result = result;
        record.Reason = reason;
        record.CaptureOutcome(ctx.ErrorMark);
        ctx.ErrorMark = CaseErrors.Mark;
        record.GameHours = ctx.Hours - record.StartHours;
    }
}
