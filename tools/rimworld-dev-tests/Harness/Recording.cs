using System;
using System.IO;
using System.Text.Json;
using UnityEngine;
using Verse;

namespace RimWorldDevTests;

// Immutable marker files coordinate the external recorder without reading/writing the mutable progress file.
// No user preferences change. Hiding only skips this runner-owned colony's UI drawing.
public static class RunRecording
{
    private static RunRequest request;
    private static string dir;
    private static bool hideUI, finishing;
    private static DateTime readyAt, finishedAt;
    public static bool Enabled => request?.Record == true;

    public static void Configure(RunRequest run, string evidence)
    {
        request = run; dir = evidence;
        hideUI = finishing = false;
        readyAt = finishedAt = default;
    }

    private static string Marker(string name) => Path.Combine(dir, "capture-" + name + ".json");
    private static void Write(string name, object value)
    {
        string path = Marker(name);
        File.WriteAllText(path + ".tmp", JsonSerializer.Serialize(value));
        File.Move(path + ".tmp", path);
    }

    public static void Ready()
    {
        hideUI = request.HideUI;
        readyAt = DateTime.UtcNow;
        Write("ready", new { utc = readyAt.ToString("o"), window = "RimWorld.exe", hideUI, width = Screen.width, height = Screen.height });
    }

    public static string Problem()
    {
        if (File.Exists(Marker("failed"))) return "recorder failed; see recording.log and capture-failed.json";
        if (!File.Exists(Marker("started")) && DateTime.UtcNow - readyAt > TimeSpan.FromSeconds(30)) return "recorder did not confirm a captured frame within 30 seconds";
        return null;
    }

    public static bool CaptureStarted()
    {
        string problem = Problem();
        if (problem != null) throw new SetupException(problem);
        return File.Exists(Marker("started"));
    }

    public static bool Complete()
    {
        if (!Enabled) return false;
        finishing = true;
        finishedAt = DateTime.UtcNow;
        if (Current.ProgramState == ProgramState.Playing) Find.TickManager.CurTimeSpeed = TimeSpeed.Paused;
        Write("complete", new { utc = finishedAt.ToString("o") });
        return true;
    }

    public static void Frame()
    {
        if (!finishing) return;
        if (!File.Exists(Marker("stopped")) && DateTime.UtcNow - finishedAt < TimeSpan.FromSeconds(30)) return;
        finishing = hideUI = false;
        if (!request.KeepOpen) Root.Shutdown();
    }

    public static bool BeforeGUI()
    {
        if (!hideUI || !RunnerIdentity.Owned(Current.Game)) return true;
        // Keep a direct escape hatch while the normal main-menu shortcut is hidden.
        if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.Escape)
        {
            hideUI = false;
            TestRunner.Cancel();
            return true;
        }
        return false;
    }
}
