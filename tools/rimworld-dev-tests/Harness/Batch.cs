using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using Verse;

namespace RimWorldDevTests;

public record PlannedCase(string Id, string Level, string ExpectedResult = null);

public static class Levels
{
    public const string PlayerWorkflow = "player-workflow", Mechanical = "mechanical", Diagnostic = "diagnostic";
}

// A batch is a fresh quickstart plus segments. Each segment yields waits; a Reload wait must end its segment,
// because iterators do not survive the scene load. State that crosses a reload goes through ctx.Memo.
public abstract class Batch
{
    public abstract string Id { get; }
    public virtual int MapSize => Harness.Settings.DefaultMapSize;
    public virtual bool Diagnostic => false;
    // Wall-clock limit for the whole batch once its map is ready.
    public virtual TimeSpan WallLimit => TimeSpan.FromMinutes(15);
    public abstract IReadOnlyList<PlannedCase> Plan { get; }
    public abstract int SegmentCount { get; }
    public abstract IEnumerable<Wait> Segment(int index, BatchContext ctx);

    // A showcase drives its own camera, overlay and recording handshake, and may export its colony with --save-as.
    // The runner's test camera, progress panel and recording gate are for every other batch.
    public virtual bool IsShowcase => false;
    // Reads request inputs before any evidence exists. Returns a refusal, or null when the batch can run.
    public virtual string Prepare(RunRequest request) => null;
    // Preserves the inputs Prepare read in the new evidence directory.
    public virtual void Archive(RunRequest request, string dir) { }
}

public abstract class Wait
{
    public Action EveryTick;
    public Action AfterTick;

    // The first lost prerequisite this window observed, or null.
    public string Problem { get; private set; }

    // Observe prerequisites after each actual simulation tick, including the last tick of a window. The problem belongs to
    // this wait, so it reaches only the checks between this wait and the next one.
    public Wait While(Func<string> problem)
    {
        AfterTick += () => Problem ??= problem();
        return this;
    }

    public static Wait Ticks(int ticks, Action everyTick = null) => new TickWait { Remaining = ticks, EveryTick = everyTick };

    // Ticks until the condition holds or the tick limit passes; ctx.TimedOut tells which.
    public static UntilWait Until(Func<bool> condition, int maxTicks, Action everyTick = null) =>
        new UntilWait { Condition = condition, Remaining = maxTicks, EveryTick = everyTick };

    // Lets frame-driven state (sky glow, glow grid) catch up without advancing the simulation.
    public static Wait Frames(int frames) => new FrameWait { Remaining = frames };

    // Saves a runner-owned game and loads it again. Must be the last wait of its segment.
    public static Wait Reload() => new ReloadWait();
    public static Wait Recorder() => new RecordingWait();
    public static Wait Seconds(double seconds, bool simulate = false)
    {
        double now = Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
        return new RealtimeWait { Deadline = now + seconds, NextTick = now, Simulate = simulate };
    }
}

public class TickWait : Wait { public int Remaining; }
// TimedOut is this wait's own result. ctx.TimedOut holds the latest Until's result and is not cleared by other waits, so keep
// the wait in a variable when another wait runs before the check.
public class UntilWait : Wait { public Func<bool> Condition; public int Remaining; public bool TimedOut { get; internal set; } }
public class FrameWait : Wait { public int Remaining; }
public class ReloadWait : Wait { }
public class RecordingWait : Wait { }
public class RealtimeWait : Wait { public double Deadline, NextTick; public bool Simulate; }

public class BatchContext
{
    private readonly Progress progress;
    private readonly BatchRecord record;
    private readonly Batch batch;
    public bool TimedOut { get; internal set; }
    public bool CancelRequested { get; private set; }
    // The most recent wait, set by the runner as each starts. Checks after it read its window's problem.
    internal Wait LastWait;
    public string MeasurementProblem => LastWait?.Problem;
    // Errors logged after this mark belong to the next case to finish: it moves on whenever a case finishes.
    internal long ErrorMark = CaseErrors.Mark;

    internal BatchContext(Progress progress, BatchRecord record, Batch batch)
    {
        this.progress = progress;
        this.record = record;
        this.batch = batch;
    }

    public int Seed => progress.Request.Seed;
    public string SaveAs => progress.Request.SaveAs;
    public Map Map => Find.CurrentMap;
    public int Now => Find.TickManager.TicksGame;
    internal Action Save;

    public void Setup(string line)
    {
        record.Setup.Add(line);
        RunTimeline.Event("setup", batch.Id, detail: line);
        if (throttled && Stopwatch.GetTimestamp() - lastSave < Stopwatch.Frequency / 2) { savePending = true; return; }
        Save();
        lastSave = Stopwatch.GetTimestamp();
        savePending = false;
    }

    // 2026-11-07: rewriting the whole progress file after each of ~3,200 showcase placements made recorded builds stutter.
    // While throttled, setup lines still reach the record and timeline at once, but the file is written at most twice a
    // second; ending the throttle writes anything still pending. A crash can lose up to half a second of setup lines.
    private bool throttled, savePending;
    private long lastSave;
    public void ThrottleSetupSaves(bool on)
    {
        throttled = on;
        if (!on && savePending) { Save(); savePending = false; }
    }

    public void Remember(string key, string value) { progress.Memo[batch.Id + "." + key] = value; Save(); }
    public string Recall(string key) => progress.Memo.TryGetValue(batch.Id + "." + key, out var v) ? v : null;
    public float RecallFloat(string key) => float.Parse(Recall(key) ?? "NaN", CultureInfo.InvariantCulture);

    public string ResultOf(string id) => progress.Case(batch.Id, id)?.Result;

    // Used only by diagnostics that exercise cancellation through the same path as the developer menu.
    public void RequestCancel() => CancelRequested = true;

    public CaseScope Begin(string id, string phase = null)
    {
        var planned = batch.Plan.FirstOrDefault(p => p.Id == id) ?? throw new ArgumentException("Case not in the batch plan: " + id);
        var existing = progress.Case(batch.Id, id);
        if (existing != null && existing.Result != Results.Running) throw new InvalidOperationException("Case already recorded: " + id);
        var c = existing ?? new CaseRecord
        {
            Id = id, Batch = batch.Id, Level = planned.Level, Diagnostic = batch.Diagnostic,
            ExpectedResult = planned.ExpectedResult, StartTick = Now, ErrorMark = ErrorMark,
        };
        if (existing == null) { progress.Cases.Add(c); RunTimeline.Event("case-start", batch.Id, id); }
        if (phase != null) c.Phase = phase;
        Save();
        return new CaseScope(c, this);
    }

    // Records a skip without running when a prerequisite case did not pass.
    public bool SkipUnlessPassed(string id, params string[] prerequisites)
    {
        foreach (var p in prerequisites)
        {
            if (ResultOf(p) == Results.Pass) continue;
            Begin(id).Blocked($"prerequisite {p} did not pass ({ResultOf(p) ?? "not run"})", p);
            return true;
        }
        return false;
    }

    internal void Saved() => Save();
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
    public CaseScope Subject(params Pawn[] pawns)
    {
        foreach (var pawn in pawns.Where(p => p != null))
            record.SubjectStates[pawn.ThingID] = () =>
            {
                // Read during interruption and batch-end paths too, so a pawn whose state can't be read never stops the record.
                try
                {
                    var bed = pawn.Spawned && !pawn.Dead ? RimWorld.RestUtility.CurrentBed(pawn) : null;
                    return $"subject: {pawn.ThingID} ({pawn.LabelShort}), {(pawn.Dead ? "dead" : "alive")}, downed {pawn.Downed}, " +
                        $"job {pawn.CurJobDef?.defName ?? "none"}, position {pawn.Position}, bed {bed?.ThingID ?? "none"}";
                }
                catch (Exception ex) { return $"subject: {pawn.ThingID}: state unavailable ({ex.GetType().Name}: {ex.Message})"; }
            };
        return this;
    }
    public CaseScope Phase(string phase) { record.Phase = phase; ctx.Saved(); return this; }

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
    // Every new skip must declare its coverage meaning; old reports without it remain unclassified.
    public void Skip(string reason, string category) { record.CoverageReason = category; Finish(Results.Skip, reason); }
    public void NotApplicable(string reason) => Skip(reason, CoverageReasons.NotApplicable);
    public void SetupFailed(string reason) => Skip(reason, CoverageReasons.SetupFailed);
    public void EnvironmentUnavailable(string reason) => Skip(reason, CoverageReasons.Environment);
    public void Blocked(string reason, params string[] prerequisites)
    {
        record.Prerequisites.AddRange(prerequisites);
        Skip(reason, CoverageReasons.Blocked);
    }
    public void Error(string reason) => Finish(Results.Error, reason);

    // Player-workflow cases only, when the AI didn't finish in the window. The preconditions prove the AI had what it needed
    // (a reachable worker, the items, the bill); any unmet one makes this a setup failure, so a broken setup is never deferred.
    public void WorkflowInconclusive(string reason, params (bool held, string what)[] preconditions)
    {
        if (record.Level != Levels.PlayerWorkflow) { Error("workflow-inconclusive is only for player-workflow cases: " + reason); return; }
        if (preconditions.Length == 0) { Error("workflow-inconclusive needs preconditions: " + reason); return; }
        var failed = preconditions.Where(p => !p.held).Select(p => p.what).ToList();
        if (failed.Count > 0) SetupFailed("workflow precondition not met: " + string.Join("; ", failed));
        else Skip(reason, CoverageReasons.WorkflowInconclusive);
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
        record.Ticks = Find.TickManager.TicksGame - record.StartTick;
        RunTimeline.Event("case-end", record.Batch, record.Id, result);
        ctx.Saved();
    }
}
