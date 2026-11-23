using System;
using System.Collections.Generic;
using System.Linq;
using Bindito.Core;
using Timberborn.Autosaving;
using Timberborn.SingletonSystem;
using Timberborn.TimeSystem;
using Timberborn.UILayoutSystem;
using UnityEngine;

namespace TimberbornDevTests;

[Context("Game")]
public class GameConfigurator : Configurator
{
    protected override void Configure()
    {
        if (Runner.Active) Bind<GameRunner>().AsSingleton();
    }
}

// Waits for the game to be ready, then runs the requested batch: segment code between waits runs with game time stopped,
// and the current wait is evaluated once a frame. Waits that advance time run the game at the batch's speed.
public class GameRunner : ILoadableSingleton, IUpdatableSingleton
{
    private enum Step { WaitForUi, Settle, Running, Done }
    // Waits that finish at once (zero hours, a condition already true) chain within a frame up to this many.
    private const int MaxWaitsPerFrame = 100;

    private readonly EventBus eventBus;
    private readonly Autosaver autosaver;
    private readonly SpeedManager speedManager;
    private readonly IContainer container;

    private Step step = Step.WaitForUi;
    private int settleFrames;
    private Batch batch;
    private BatchRecord record;
    private BatchContext ctx;
    private IEnumerator<Wait> segment;
    private int segmentIndex;
    private Wait wait;
    private float batchStartRealtime, batchStartHours;

    public GameRunner(EventBus eventBus, Autosaver autosaver, SpeedManager speedManager, IContainer container)
    {
        this.eventBus = eventBus;
        this.autosaver = autosaver;
        this.speedManager = speedManager;
        this.container = container;
    }

    public void Load()
    {
        // A new game's settlement points at the player's Documents/Timberborn/Saves; suspending stops both the periodic
        // autosave and the save on quit (AutosaverUnityAdapter.OnApplicationQuit).
        autosaver.Suspend();
        eventBus.Register(this);
        Runner.Stage = "game-loading";
        RunReport.Data["gameSceneLoadedAtSeconds"] = Time.realtimeSinceStartup;
        Runner.Log("Game scene loading; autosaver suspended.");
    }

    // Posted last by GameInitializer, after the starting beavers spawn and the speed is set to 1, for new games and loads.
    [OnEvent]
    public void OnShowPrimaryUI(ShowPrimaryUIEvent _)
    {
        if (step == Step.WaitForUi) step = Step.Settle;
    }

    public void UpdateSingleton()
    {
        if (RunReport.Written || step == Step.Done) return;
        if (step == Step.Settle)
        {
            if (++settleFrames < 5) return;
            RunReport.Data["gameReadyAtSeconds"] = Time.realtimeSinceStartup;
            StartBatch();
            return;
        }
        if (step == Step.Running) Advance();
    }

    private void StartBatch()
    {
        // The main menu refused unknown batches, so this lookup holds.
        batch = Batches.All[Runner.Request.Batch];
        record = RunReport.Batches.Last(b => b.Id == batch.Id);
        record.Planned = batch.Plan.Select(p => p.Id).ToList();
        ctx = new BatchContext(container, record, batch, Runner.Request.Speed);
        RunReport.BeforeFinish = reason => EndBatch(reason, finish: false);
        batchStartRealtime = Time.realtimeSinceStartup;
        batchStartHours = ctx.Hours;
        record.Setup.Add("Autosave suspended for this runner-owned game; saves go only to the run folder");
        record.Setup.Add("Randomness is not seeded; cases assert on ranges (D6)");
        Runner.Stage = "running";
        RunTimeline.Event("batch-start", batch.Id);
        step = Step.Running;
        SetSpeed(0f);
        StartSegment(0);
    }

    private void StartSegment(int index)
    {
        segmentIndex = index;
        segment = batch.Segment(index, ctx).GetEnumerator();
        wait = null;
    }

    private void Advance()
    {
        if (Time.realtimeSinceStartup - batchStartRealtime > batch.WallLimit.TotalSeconds)
        {
            EndBatch($"the batch passed its wall-clock limit of {batch.WallLimit.TotalMinutes:0.#} min");
            return;
        }
        // Case code runs until it yields a wait that isn't done yet, so the code after a finished wait runs in the same frame,
        // before the game advances. A wait condition or prerequisite that throws is the case's, as is a throw in the segment.
        for (int waits = 0; waits < MaxWaitsPerFrame; waits++)
        {
            if (wait == null)
            {
                bool more;
                try { more = segment.MoveNext(); }
                catch (Exception ex) { CaseException(ex, "case code"); return; }
                if (!more)
                {
                    if (segmentIndex + 1 < batch.SegmentCount) { StartSegment(segmentIndex + 1); continue; }
                    EndBatch(null);
                    return;
                }
                wait = ctx.LastWait = segment.Current;
                if (wait == null) { CaseException(new InvalidOperationException("the segment yielded null; yield a Wait"), "case code"); return; }
            }
            try
            {
                if (!Done(wait)) { wait.Observe(); break; }
            }
            catch (Exception ex) { CaseException(ex, "a " + wait.GetType().Name + " condition or prerequisite"); return; }
            wait = null;
        }
        SetSpeed(wait != null && wait.AdvancesTime ? ctx.Speed : 0f);
    }

    private bool Done(Wait w)
    {
        switch (w)
        {
            case HoursWait h:
                if (float.IsNaN(h.Start)) h.Start = ctx.Hours;
                return ctx.Hours - h.Start >= h.Duration;
            case UntilWait u:
                if (float.IsNaN(u.Start)) u.Start = ctx.Hours;
                if (u.Condition()) { u.TimedOut = ctx.TimedOut = false; return true; }
                if (ctx.Hours - u.Start >= u.MaxHours) { u.TimedOut = ctx.TimedOut = true; return true; }
                return false;
            case FrameWait f:
                return --f.Remaining < 0;
            case SaveWait s:
                return s.Done;
            default:
                throw new InvalidOperationException("unknown wait " + w?.GetType().Name);
        }
    }

    // Re-issued every frame it differs, so anything else that changes the speed (a game event pausing it) can't stall a wait.
    private void SetSpeed(float speed)
    {
        if (speedManager.CurrentSpeed != speed) speedManager.ChangeSpeed(speed);
    }

    private void CaseException(Exception ex, string where)
    {
        // LogError, not LogException: the game's ExceptionListener sends any logged exception to the crash scene.
        Debug.LogError($"[TimberbornDevTests] Case exception in {where}: {ex}");
        if (ex is not SetupException)
            record.Setup.Add("Exception stack (top frames): " + string.Join(" | ",
                (ex.StackTrace ?? "none").Split('\n').Select(l => l.Trim()).Where(l => l.Length > 0).Take(6)));
        EndBatch($"exception in {where}: {ex.GetType().Name}: {ex.Message}");
    }

    private void EndBatch(string reason, bool finish = true)
    {
        if (step == Step.Done) return;
        step = Step.Done;
        RunReport.BeforeFinish = null;
        segment?.Dispose();
        RunReport.CloseBatch(record, batch.Plan, batch.Diagnostic, reason);
        RunTimeline.Event("batch-end", batch.Id, detail: reason);
        record.GameHours = ctx.Hours - batchStartHours;
        record.WallSeconds = Time.realtimeSinceStartup - batchStartRealtime;
        try { Harness.Settings?.OnBatchEnd(); }
        catch (Exception ex) { Debug.LogError("[TimberbornDevTests] OnBatchEnd threw: " + ex); }
        speedManager.ChangeSpeed(0f);
        if (finish) RunReport.Finish(RunStatus.Complete);
    }
}
