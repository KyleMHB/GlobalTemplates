using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using Verse;

namespace RimWorldDevTests;

// A local inbox for sequential launcher commands: rimtest.py keeps one
// RimWorld process at the main menu and sends each batch as a request file. Only a process started with -<prefix>Session listens.
internal static class RunnerSession
{
    private static string token, productionHash, developerHash, harnessHash, runtimeHash;
    private static DateTime nextPoll;
    private static readonly JsonSerializerOptions options = new() { IncludeFields = true };
    private static string StatusPath => Path.Combine(TestRunner.EvidenceRoot, "session.json");
    private static string RequestPath => Path.Combine(TestRunner.EvidenceRoot, "session-request.json");

    internal sealed class Request
    {
        public string Session = null, Command = null, RunId = null, Batch = null;
        public int Seed = 1;
    }

    public static void Read()
    {
        if (!GenCommandLine.TryGetCommandLineArg(Harness.Settings.ArgPrefix + "Session", out token)) return;
        LaunchArguments.LauncherOwned = true;
        productionHash = Hash(Harness.Settings.ProductionDllPath);
        developerHash = Hash(Harness.Settings.DevDllPath);
        harnessHash = Hash(typeof(RunnerSession).Assembly.Location);
        runtimeHash = RuntimeManifest.Hash();
        Directory.CreateDirectory(TestRunner.EvidenceRoot);
    }

    private static string Hash(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    public static void Frame()
    {
        // Waylith skips whole frames while the window is unfocused unless run-in-background is set (docs/game-facts.md, verified
        // 2026-11-07). Forced for launcher-started processes only; the player's saved preference is not changed, and it is
        // reasserted each frame because PrefsData.Apply can reset it.
        if (LaunchArguments.LauncherOwned) UnityEngine.Application.runInBackground = true;
        if (token == null || DateTime.UtcNow < nextPoll) return;
        nextPoll = DateTime.UtcNow.AddMilliseconds(250);
        bool idle = !TestRunner.Running && Current.ProgramState == ProgramState.Entry && Current.Game == null &&
            !LongEventHandler.AnyEventNowOrWaiting;
        bool unrelated = Current.ProgramState == ProgramState.Playing && !RunnerIdentity.Owned(Current.Game);
        string state = TestRunner.Running ? "running" : idle ? "idle" : unrelated ? "unrelated-colony" : "loading";
        string temp = StatusPath + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(new
        {
            session = token, pid = Process.GetCurrentProcess().Id, state,
            productionHash, developerHash, harnessHash, runtimeHash, heartbeat = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
        }));
        // A launcher may briefly hold the previous status file open while reading on Windows.
        try { File.Move(temp, StatusPath, true); }
        catch (IOException) { return; }
        if (TestRunner.Running || !File.Exists(RequestPath)) return;
        Request request;
        try { request = JsonSerializer.Deserialize<Request>(File.ReadAllText(RequestPath), options); }
        catch (JsonException ex)
        {
            File.Delete(RequestPath);
            Log.Error(Harness.Settings.LogPrefix + "Invalid session request: " + ex.Message);
            return;
        }
        File.Delete(RequestPath);
        if (request?.Session != token) return;
        if (request.Command == "close")
        {
            if (idle) Root.Shutdown();
            return;
        }
        if (request.Command != "run" || string.IsNullOrEmpty(request.RunId) || Path.GetFileName(request.RunId) != request.RunId) return;
        var run = new RunRequest { Batch = request.Batch, Seed = request.Seed, Origin = "session" };
        if (!idle)
        {
            LaunchArguments.WriteRefusal(run, "session is no longer idle at the main menu", request.RunId);
            return;
        }
        string refusal = TestRunner.Start(run, request.RunId);
        if (refusal != null) LaunchArguments.WriteRefusal(run, refusal, request.RunId);
    }
}
