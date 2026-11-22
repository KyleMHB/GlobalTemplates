using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using UnityEngine;

namespace TimberbornDevTests;

public static class Results
{
    public const string Pass = "pass", Fail = "fail", Error = "error", Skip = "skip";
}

// report.json "status"; the launcher maps it to an exit code (devtests_core.result_code).
public static class RunStatus
{
    public const string Complete = "complete", Refused = "refused", Interrupted = "interrupted", Cancelled = "cancelled";
}

// What the launcher asks for, written to <dev folder>/request.json before launch: the game passes no custom arguments
// through Steam reliably, and the file sits next to the runner DLL.
public class RunRequest
{
    public string RunId;
    public string RunDir;
    public string Batch = "smoke";
    // "new" starts a new game on Map. Loading a fixture save comes with the case API (T4).
    public string Mode = "new";
    public string Faction = "Folktails";
    public string Map = "_Mini";
    public string SettlementName;
    public float Speed = 30f;
    public float GameHours = 2f;
    // When the launcher will kill the game (UTC milliseconds), less a margin; 0 when no launcher set a limit.
    public long DeadlineUtcMs;
    // PlayerPrefs keys the launcher wrote to disable other mods; the starter logs what the game sees (T3 makes it fail fast).
    public string[] ProbePrefKeys = new string[0];
}

public class CaseRecord
{
    public string Id;
    public string Batch;
    public string Result;
    public string Reason;
    public object Observed;
}

// Collects the run's evidence and writes report.json once, then quits the game.
public static class RunReport
{
    public static readonly Dictionary<string, object> Data = new();
    public static readonly List<CaseRecord> Cases = new();
    private static readonly List<string> errors = new();
    private static int errorCount, exceptionCount;
    private static bool written;

    public static bool Written => written;

    public static int ExceptionCount
    {
        get { lock (errors) return exceptionCount; }
    }

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
    }

    public static void Finish(string status, string reason = null)
    {
        if (written) return;
        written = true;
        var request = Runner.Request;
        Data["status"] = status;
        Data["reason"] = reason;
        Data["stage"] = Runner.Stage;
        Data["request"] = request;
        Data["cases"] = Cases;
        Data["finishedUtc"] = DateTime.UtcNow.ToString("o");
        Data["realtimeSinceStartup"] = Time.realtimeSinceStartup;
        lock (errors)
        {
            Data["errorCount"] = errorCount;
            Data["exceptionCount"] = exceptionCount;
            Data["errors"] = errors.ToArray();
            Data["overallPass"] = status == RunStatus.Complete && Cases.Count > 0 && Cases.TrueForAll(c => c.Result == Results.Pass);
        }
        string path = Path.Combine(request.RunDir, "report.json");
        File.WriteAllText(path + ".tmp", JsonConvert.SerializeObject(Data, Formatting.Indented));
        File.Copy(path + ".tmp", path, true);
        File.Delete(path + ".tmp");
        Runner.Log($"Report written ({status}): {path}. Quitting.");
        Application.Quit();
    }
}
