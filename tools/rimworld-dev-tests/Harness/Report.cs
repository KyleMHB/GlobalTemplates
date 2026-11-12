using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace RimWorldDevTests;

public static class Results
{
    public const string Pass = "pass", Fail = "fail", Skip = "skip", Error = "error", Running = "running";
}

public static class RunStatus
{
    public const string Running = "running", Complete = "complete", Cancelled = "cancelled", Interrupted = "interrupted", Refused = "refused";
}

public static class CoverageReasons
{
    public const string NotApplicable = "not-applicable", SetupFailed = "setup-failed", Blocked = "blocked", Environment = "environment", Unclassified = "unclassified";
    // A player-workflow case whose AI had what it needed but didn't finish in the window. Doesn't count against coverage;
    // A mod's triage command can escalate a case that is inconclusive three runs in a row.
    public const string WorkflowInconclusive = "workflow-inconclusive";
}

public class RunRequest
{
    public string Batch = "";
    public List<string> Batches = new();
    public int Seed = 1;
    // "launch" quits at the end; "menu" leaves it paused; "session" returns to the main menu for another request.
    public string Origin = "menu";
    public bool KeepOpen;
    public string BlueprintPath;
    public string SaveAs;
    public bool Record;
    public bool HideUI = true;
}

public class CaseRecord
{
    // Runtime callbacks never enter progress.json; batches re-register loaded subjects after a reload.
    internal readonly Dictionary<string, Func<string>> SubjectStates = new();
    // Runtime only: the error-log position when this case began, or -1 for a record read back from progress.json.
    internal long ErrorMark = -1;
    public string Id = "", Batch = "", Level = "", Result = Results.Running, Reason = "";
    // Diagnostic cases exercise the runner itself; ExpectedResult is the outcome the runner must report for them.
    public bool Diagnostic;
    public string ExpectedResult;
    public string Phase;
    public string CoverageReason;
    public List<string> Prerequisites = new();
    public Dictionary<string, string> Expected = new(), Observed = new();
    public List<string> Setup = new(), Evidence = new();
    public int Ticks;
    public int StartTick;

    // A failing case records the errors logged in its window (CaseErrors.For) and the state of each registered subject.
    // The reason is already in Reason.
    internal void CaptureFailure(IEnumerable<string> loggedErrors)
    {
        if (!(Result is Results.Fail or Results.Error || Result == Results.Skip && CoverageReason == CoverageReasons.SetupFailed)) return;
        Evidence.AddRange(loggedErrors);
        foreach (var state in SubjectStates.Values) Evidence.Add(state());
    }
}

public class BatchRecord
{
    public string Id = "", Identity = "", Status = RunStatus.Running, Reason = "";
    public int MapSize, StartingTile = -1;
    public string WorldSeed = "";
    public List<string> Setup = new();
    public List<string> Planned = new();
    public int Ticks;
}

// The single file the runner trusts across scene loads and process deaths. Rewritten after every case and stage change.
public class Progress
{
    public int Schema = 1;
    public string RunId = "", Status = RunStatus.Running, StartedUtc = "", FinishedUtc, Reason = "";
    public RunRequest Request = new();
    public int BatchIndex, Segment;
    public string Stage = "";
    public string CurrentSave;
    public Dictionary<string, string> Memo = new();
    public Dictionary<string, object> Environment = new();
    public List<BatchRecord> BatchRecords = new();
    public List<CaseRecord> Cases = new();

    private static readonly JsonSerializerOptions Options = new() { IncludeFields = true, WriteIndented = true };

    public static Progress Read(string path) => JsonSerializer.Deserialize<Progress>(File.ReadAllText(path), Options);

    public void Write(string path)
    {
        string temp = path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(this, Options));
        File.Move(temp, path, true);
    }

    // Case ids are scoped to their batch: two batches may plan the same id (both have dark.reload).
    public CaseRecord Case(string batch, string id) => Cases.LastOrDefault(c => c.Batch == batch && c.Id == id);

    public IEnumerable<(string batch, string id)> PendingCases() =>
        from b in BatchRecords from id in b.Planned where Case(b.Id, id) == null select (b.Id, id);

    // Planned batches not yet started also count as pending, by name.
    public IEnumerable<string> PendingBatches() => Request.Batches.Skip(BatchRecords.Count);

    public bool AssertionsPass => Cases.Where(c => !c.Diagnostic).All(c => c.Result is Results.Pass or Results.Skip);
    public bool CoverageComplete => Cases.Where(c => !c.Diagnostic).All(c => c.Result is Results.Pass or Results.Fail || c.Result == Results.Skip && c.CoverageReason is CoverageReasons.NotApplicable or CoverageReasons.WorkflowInconclusive)
        && !PendingCases().Any() && !PendingBatches().Any();

    public bool OverallPass =>
        Status == RunStatus.Complete && !PendingCases().Any() && !PendingBatches().Any() &&
        BatchRecords.All(b => b.Status == RunStatus.Complete) &&
        CoverageComplete &&
        Cases.All(c => c.Diagnostic ? c.Result == c.ExpectedResult : c.Result is Results.Pass or Results.Skip);

    public string ReportJson()
    {
        var gameplay = Cases.Where(c => !c.Diagnostic).ToList();
        var diagnostic = Cases.Where(c => c.Diagnostic).ToList();
        object Counts(List<CaseRecord> list) => new Dictionary<string, int>
        {
            ["pass"] = list.Count(c => c.Result == Results.Pass), ["fail"] = list.Count(c => c.Result == Results.Fail),
            ["skip"] = list.Count(c => c.Result == Results.Skip), ["error"] = list.Count(c => c.Result == Results.Error),
        };
        var report = new Dictionary<string, object>
        {
            ["schema"] = 2, ["runId"] = RunId, ["status"] = Status, ["reason"] = Reason, ["overallPass"] = OverallPass,
            ["assertionsPass"] = AssertionsPass, ["coverageComplete"] = CoverageComplete,
            ["coverageGaps"] = gameplay.Where(c => c.Result == Results.Skip).GroupBy(c => c.CoverageReason ?? CoverageReasons.Unclassified).ToDictionary(g => g.Key, g => g.Count()),
            ["startedUtc"] = StartedUtc, ["finishedUtc"] = FinishedUtc, ["request"] = Request,
            ["game"] = Environment.GetValueOrDefault("game"), ["modBuild"] = Environment.GetValueOrDefault("modBuild"),
            ["environment"] = Environment,
            ["counts"] = new Dictionary<string, object>
            {
                ["planned"] = BatchRecords.Sum(b => b.Planned.Count), ["completed"] = Cases.Count(c => c.Result != Results.Running),
                ["pending"] = PendingCases().Count(), ["pendingBatches"] = PendingBatches().ToList(),
                ["gameplay"] = Counts(gameplay), ["diagnostic"] = Counts(diagnostic),
                ["diagnosticMismatches"] = diagnostic.Count(c => c.Result != c.ExpectedResult),
            },
            ["batches"] = BatchRecords, ["cases"] = Cases,
            ["pending"] = PendingCases().Select(p => p.batch + "/" + p.id).ToList(),
        };
        return JsonSerializer.Serialize(report, Options);
    }

    // Read first by agents: counts, outcome and one line per case that needs a look.
    public string Summary(string runDir)
    {
        var text = new StringBuilder();
        text.AppendLine($"{Harness.Settings.DisplayName} test run {RunId}: {Status.ToUpperInvariant()}, overall {(OverallPass ? "PASS" : "NOT PASSED")}");
        if (!string.IsNullOrEmpty(Reason)) text.AppendLine("Reason: " + Reason);
        text.AppendLine($"Request: {string.Join(", ", Request.Batches)} seed {Request.Seed} ({Request.Origin})");
        var gameplay = Cases.Where(c => !c.Diagnostic).ToList();
        text.AppendLine($"Assertions: {(AssertionsPass ? "no failures" : "NOT PASSED")}; coverage: {(CoverageComplete ? "complete for applicable cases" : "INCOMPLETE")}");
        text.AppendLine($"Gameplay: {gameplay.Count(c => c.Result == Results.Pass)} pass, {gameplay.Count(c => c.Result == Results.Fail)} fail, " +
                        $"{gameplay.Count(c => c.Result == Results.Skip)} skip, {gameplay.Count(c => c.Result == Results.Error)} error");
        var diagnostic = Cases.Where(c => c.Diagnostic).ToList();
        if (diagnostic.Count > 0)
            text.AppendLine($"Diagnostic (runner self-checks): {diagnostic.Count(c => c.Result == c.ExpectedResult)} of {diagnostic.Count} reported as intended");
        int pending = PendingCases().Count();
        text.AppendLine($"Pending: {pending} cases" + (PendingBatches().Any() ? ", batches not started: " + string.Join(", ", PendingBatches()) : ""));
        foreach (var c in Cases)
        {
            bool notable = c.Diagnostic ? c.Result != c.ExpectedResult : c.Result != Results.Pass;
            if (!notable) continue;
            string intended = c.Diagnostic ? $" (intended {c.ExpectedResult})" : "";
            string coverage = c.Result == Results.Skip ? $" [{c.CoverageReason ?? CoverageReasons.Unclassified}]" : "";
            text.AppendLine($"  {c.Result.ToUpperInvariant()}{coverage} {c.Batch}/{c.Id}{intended}: {c.Reason}");
        }
        foreach (var b in BatchRecords.Where(b => b.Status != RunStatus.Complete)) text.AppendLine($"  BATCH {b.Id} {b.Status}: {b.Reason}");
        foreach (var (batch, id) in PendingCases()) text.AppendLine($"  PENDING {batch}/{id}");
        text.AppendLine("Report: " + Path.Combine(runDir, "report.json"));
        return text.ToString();
    }
}
