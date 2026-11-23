using System;
using System.Diagnostics;
using System.IO;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace TimberbornDevTests;

// Survives scene loads: keeps the game simulating while unfocused, writes the heartbeat, closes the run at the launcher's
// deadline or after a crash, and polls the inbox, whichever Bindito context is live.
public class RunnerDriver : MonoBehaviour
{
    private const string CrashScene = "3-CrashScene";
    private float nextBeat;

    private void Update()
    {
        // Set every frame for this launcher-owned process only; the player's RunInBackground setting is never written.
        Application.runInBackground = true;
        // Whether game time ran with the window in the background at some point (SPEC open risk; the smoke case reports it).
        if (!Application.isFocused && Time.timeScale > 0f && Runner.Stage == "running") RunReport.WasUnfocused = true;
        if (RunReport.Written || Time.unscaledTime < nextBeat) return;
        nextBeat = Time.unscaledTime + 1f;
        var request = Runner.Request;
        string scene = SceneManager.GetActiveScene().name;
        WriteHeartbeat(request, scene);
        if (scene == CrashScene)
        {
            RunReport.Finish(RunStatus.Interrupted, $"the game crashed into {CrashScene} at stage {Runner.Stage}; see Player.log");
            return;
        }
        string inbox = Path.Combine(request.RunDir, "inbox.json");
        if (File.Exists(inbox))
        {
            string command = File.ReadAllText(inbox).Trim();
            File.Delete(inbox);
            Runner.Log("Inbox command: " + command);
            if (command.Contains("quit")) RunReport.Finish(RunStatus.Cancelled, "quit requested through the inbox");
        }
        if (request.DeadlineUtcMs > 0 && DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() > request.DeadlineUtcMs)
            RunReport.Finish(RunStatus.Interrupted, $"the run reached the launcher's time limit at stage {Runner.Stage}");
    }

    private static void WriteHeartbeat(RunRequest request, string scene)
    {
        string beat = JsonConvert.SerializeObject(new
        {
            runId = request.RunId,
            pid = Process.GetCurrentProcess().Id,
            stage = Runner.Stage,
            scene,
            timeScale = Time.timeScale,
            unscaledTime = Time.unscaledTime,
            utcMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
        });
        string path = Path.Combine(request.RunDir, "heartbeat.json");
        try
        {
            File.WriteAllText(path + ".tmp", beat);
            File.Copy(path + ".tmp", path, true);
        }
        // The launcher may hold the file open while reading it; skip this beat.
        catch (IOException) { }
    }
}
