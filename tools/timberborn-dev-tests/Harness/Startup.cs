using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using Newtonsoft.Json;
using Timberborn.ModManagerScene;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace TimberbornDevTests;

public static class Runner
{
    public static RunRequest Request { get; private set; }
    public static bool Active => Request != null;
    public static string Stage = "mod-started";

    public static void Log(string message) => Debug.Log("[TimberbornDevTests] " + message);

    internal static void Activate(RunRequest request)
    {
        Request = request;
        Directory.CreateDirectory(request.RunDir);
        RunTimeline.Configure(request.RunDir);
        RunTimeline.Event("run-start", detail: request.Batch);
        ModErrors.Configure(request);
        RunReport.StartCounting();
    }
}

// Runs before asset bundles load and before any Bindito context, so a mod that crashes the load later still leaves the
// driver alive to report (it survives into 3-CrashScene).
public class DevTestsStartup : IModStarter
{
    public void StartMod(IModEnvironment modEnvironment)
    {
        // Assembly.Location is empty for byte-loaded mod assemblies; ModPath is the only reliable way to find our files.
        string requestPath = Path.Combine(modEnvironment.ModPath, "request.json");
        if (!File.Exists(requestPath))
        {
            Runner.Log("Inactive: no request.json in " + modEnvironment.ModPath);
            return;
        }
        var request = JsonConvert.DeserializeObject<RunRequest>(File.ReadAllText(requestPath));
        Runner.Activate(request);
        RunReport.Data["runId"] = request.RunId;
        RunReport.Data["startedUtc"] = DateTime.UtcNow.ToString("o");
        RunReport.Data["environment"] = new
        {
            pid = Process.GetCurrentProcess().Id,
            commandLine = Environment.GetCommandLineArgs(),
            unityVersion = Application.unityVersion,
            gameVersion = Timberborn.Versioning.GameVersions.CurrentVersion.Formatted,
            consoleLogPath = Application.consoleLogPath,
        };
        string probeFailure = ProbeIsolation(JsonConvert.DeserializeObject<IsolationProbe>(File.ReadAllText(requestPath)));
        if (probeFailure != null)
        {
            // Any other mod's later load could crash the game, so stop before it gets the chance.
            Runner.Log("Isolation probe failed: " + probeFailure);
            RunReport.Finish(RunStatus.Refused, probeFailure);
            return;
        }
        Runner.Log($"Active for run {request.RunId}, batch {request.Batch}");
        var driver = new GameObject("TimberbornDevTestsDriver");
        UnityEngine.Object.DontDestroyOnLoad(driver);
        driver.AddComponent<RunnerDriver>();
    }

    // The launcher's mod isolation, read from the same request.json: each ModEnabled key it wrote and the value written.
    private class IsolationProbe
    {
        public Dictionary<string, int> ProbePrefs = new();
    }

    // Registry writes the game cannot see (an agent-sandboxed launcher, SPEC D2) leave mods enabled that should be off.
    // Returns why the isolation did not reach the game, or null when every key reads back as written.
    private static string ProbeIsolation(IsolationProbe probe)
    {
        var wrong = new List<string>();
        int disabled = 0;
        foreach (var pair in probe.ProbePrefs ?? new Dictionary<string, int>())
        {
            if (pair.Value == 0) disabled++;
            if (!PlayerPrefs.HasKey(pair.Key)) wrong.Add(pair.Key + " missing");
            else if (PlayerPrefs.GetInt(pair.Key) != pair.Value) wrong.Add($"{pair.Key}={PlayerPrefs.GetInt(pair.Key)}, expected {pair.Value}");
        }
        RunReport.Data["isolationProbe"] = new { keys = probe.ProbePrefs?.Count ?? 0, disabled, wrong = wrong.Count, first = wrong.GetRange(0, Math.Min(5, wrong.Count)) };
        Runner.Log($"Isolation probe: {probe.ProbePrefs?.Count ?? 0} key(s), {disabled} disabled, {wrong.Count} wrong");
        if (wrong.Count == 0) return null;
        return $"{wrong.Count} of {probe.ProbePrefs.Count} mod enable key(s) did not reach the game ({string.Join("; ", wrong.GetRange(0, Math.Min(3, wrong.Count)))}); "
               + "run tbtest.py from your own terminal, not an agent's sandboxed session";
    }
}
