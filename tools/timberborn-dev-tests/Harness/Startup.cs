using System;
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
        // Seam for mod isolation (T3): confirms from inside the game which disable keys the launcher's writes produced.
        foreach (string key in request.ProbePrefKeys ?? new string[0])
            Runner.Log($"PlayerPrefs probe {key}: hasKey={PlayerPrefs.HasKey(key)} value={PlayerPrefs.GetInt(key, -1)}");
        Runner.Log($"Active for run {request.RunId}, batch {request.Batch}");
        var driver = new GameObject("TimberbornDevTestsDriver");
        UnityEngine.Object.DontDestroyOnLoad(driver);
        driver.AddComponent<RunnerDriver>();
    }
}
