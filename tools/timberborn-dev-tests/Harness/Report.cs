using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using UnityEngine;

namespace TimberbornDevTests;

public static class Results
{
    public const string Pass = "pass", Fail = "fail", Skip = "skip", Error = "error", Running = "running";
}

// report.json "status"; the launcher maps it to an exit code (devtests_core.result_code).
public static class RunStatus
{
    public const string Complete = "complete", Refused = "refused", Interrupted = "interrupted", Cancelled = "cancelled";
}

// Why a case was skipped: every skip names one, so the summary can tell a known gap from a broken setup.
public static class CoverageReasons
{
    public const string NotApplicable = "not-applicable", SetupFailed = "setup-failed", Blocked = "blocked", Environment = "environment";
    // A case with an open CaseScope.KnownGap: something not true yet, with its reason recorded. Listed as not covered, but it
    // doesn't fail the run.
    public const string KnownGap = "known-gap";
}

// What the launcher asks for, written to <dev folder>/request.json before launch: the game passes no custom arguments
// through Steam reliably, and the file sits next to the runner DLL.
public class RunRequest
{
    public string RunId;
    public string RunDir;
    public string Batch = "smoke";
    // Override the batch's faction and built-in map when set; ignored for a batch that loads a fixture.
    public string Faction;
    public string Map;
    // Where a batch's relative Fixture name is looked up first (the mod's DevTests/Fixtures); the run folder is tried next.
    public string FixtureDir;
    public string SettlementName;
    public float Speed = 30f;
    // Game hours the smoke batch runs.
    public float GameHours = 2f;
    // When the launcher will kill the game (UTC milliseconds), less a margin; 0 when no launcher set a limit.
    public long DeadlineUtcMs;
}

public class CaseRecord
{
    public string Id, Batch, Level, Result = Results.Running, Reason;
    // Diagnostic cases exercise the runner itself; ExpectedResult is the outcome the runner must report for them.
    public bool Diagnostic;
    public string ExpectedResult;
    public string CoverageReason;
    public Dictionary<string, string> Expected = new(), Observed = new();
    public List<string> Setup = new(), Evidence = new();
    // The case as steps in the player's words (CaseScope.Step, Note, KnownGap), each with its marker in the margin.
    public List<string> Steps = new();
    // Known gaps that held this time: each should become a Step.
    public int FixedGaps;
    // Errors the game logged in this case's window, whatever its result: a passing case can still have run over errors.
    public int LoggedErrors;
    public float StartHours, GameHours;
    // The error-log position where this case's window starts (CaseErrors.Mark).
    [JsonIgnore] internal long ErrorMark = -1;

    internal void CaptureOutcome(long windowStart)
    {
        long mark = ErrorMark < 0 ? windowStart : Math.Min(ErrorMark, windowStart);
        LoggedErrors = CaseErrors.CountSince(mark);
        Evidence.AddRange(CaseErrors.Since(mark));
    }
}

public class BatchRecord
{
    public string Id, Status = "running", Reason, Fixture;
    public List<string> Setup = new(), Planned = new();
    public float GameHours, WallSeconds;
}

// Collects the run's evidence and writes report.json once, then quits the game.
public static class RunReport
{
    public static readonly Dictionary<string, object> Data = new();
    public static readonly List<CaseRecord> Cases = new();
    public static readonly List<BatchRecord> Batches = new();
    private static readonly List<string> errors = new();
    private static int errorCount, exceptionCount;
    private static bool written;

    public static bool Written => written;

    public static int ExceptionCount
    {
        get { lock (errors) return exceptionCount; }
    }

    // Set by the driver when game time ran while the window was in the background (SPEC open risk).
    public static bool WasUnfocused;

    internal static void StartCounting()
    {
        // The threaded event also sees errors raised off the main thread (parallel ticking).
        Application.logMessageReceivedThreaded += OnLog;
    }

    private static void OnLog(string condition, string stackTrace, LogType type)
    {
        if (type != LogType.Error && type != LogType.Exception && type != LogType.Assert) return;
        lock (errors)
        {
            if (type == LogType.Exception) exceptionCount++; else errorCount++;
            if (errors.Count < 50) errors.Add($"{type}: {condition}\n{stackTrace}".Trim());
        }
        CaseErrors.Record((type == LogType.Exception ? "uncaught exception: " : type + ": ") + condition);
    }

    public static CaseRecord Case(string batch, string id) => Cases.FirstOrDefault(c => c.Batch == batch && c.Id == id);

    // Closes the open batch however the run ends (batch end, deadline, crash scene, inbox quit): a case still running is an
    // error, and a planned case never begun is a blocked skip, so an interrupted report never under-reports.
    internal static void CloseBatch(BatchRecord batch, IEnumerable<PlannedCase> plan, bool diagnostic, string reason)
    {
        if (batch == null || batch.Status != "running") return;
        foreach (var c in Cases.Where(c => c.Batch == batch.Id && c.Result == Results.Running))
        {
            c.Result = Results.Error;
            c.Reason = reason ?? "case started but never finished";
            c.CaptureOutcome(CaseErrors.Mark);
        }
        foreach (var planned in plan.Where(p => Case(batch.Id, p.Id) == null))
            Cases.Add(new CaseRecord
            {
                Id = planned.Id, Batch = batch.Id, Level = planned.Level, Diagnostic = diagnostic, ExpectedResult = planned.ExpectedResult,
                Result = reason == null ? Results.Error : Results.Skip, CoverageReason = reason == null ? null : CoverageReasons.Blocked,
                Reason = reason == null ? "planned case never recorded by the batch" : "batch ended early: " + reason,
            });
        batch.Status = reason == null ? RunStatus.Complete : "ended-early";
        batch.Reason = reason;
    }

    private static bool OverallPass(string status) =>
        status == RunStatus.Complete && Cases.Count > 0 && Batches.All(b => b.Status == RunStatus.Complete) &&
        Cases.All(c => c.Diagnostic ? c.Result == c.ExpectedResult : c.Result is Results.Pass or Results.Skip);

    // Hook for the open batch's runner, so a deadline or crash closes its cases before the report is written.
    internal static Action<string> BeforeFinish;

    public static void Finish(string status, string reason = null)
    {
        if (written) return;
        try { BeforeFinish?.Invoke(reason ?? status); }
        catch (Exception ex) { Runner.Log("Closing the open batch failed: " + ex.Message); }
        written = true;
        var request = Runner.Request;
        Data["status"] = status;
        Data["reason"] = reason;
        Data["stage"] = Runner.Stage;
        Data["request"] = request;
        Data["wasUnfocused"] = WasUnfocused;
        Data["batches"] = Batches;
        Data["cases"] = Cases;
        Data["finishedUtc"] = DateTime.UtcNow.ToString("o");
        Data["realtimeSinceStartup"] = Time.realtimeSinceStartup;
        lock (errors)
        {
            Data["errorCount"] = errorCount;
            Data["exceptionCount"] = exceptionCount;
            Data["errors"] = errors.ToArray();
        }
        Data["overallPass"] = OverallPass(status);
        string path = Path.Combine(request.RunDir, "report.json");
        File.WriteAllText(path + ".tmp", JsonConvert.SerializeObject(Data, Formatting.Indented));
        File.Copy(path + ".tmp", path, true);
        File.Delete(path + ".tmp");
        Runner.Log($"Report written ({status}): {path}. Quitting.");
        Application.Quit();
    }
}
