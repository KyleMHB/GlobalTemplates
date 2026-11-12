using System.Collections.Generic;
using System.IO;
using System.Linq;
using HarmonyLib;
using LudeonTK;
using RimWorld;
using Verse;

namespace RimWorldDevTests;

[StaticConstructorOnStartup]
public static class DevTestsStartup
{
    static DevTestsStartup()
    {
        var s = Harness.Settings;
        var harmony = new Harmony(s.HarmonyId);
        harmony.Patch(AccessTools.Method(typeof(Root), nameof(Root.Update)), postfix: new HarmonyMethod(typeof(DevTestsStartup), nameof(AfterRootUpdate)));
        harmony.Patch(AccessTools.Method(typeof(Game), "ExposeSmallComponents"), postfix: new HarmonyMethod(typeof(DevTestsStartup), nameof(AfterExposeSmallComponents)));
        harmony.Patch(AccessTools.Method(typeof(UIRoot_Play), nameof(UIRoot_Play.UIRootOnGUI)), postfix: new HarmonyMethod(typeof(TestPresentation), nameof(TestPresentation.Draw)));
        harmony.Patch(AccessTools.Method(typeof(UIRoot_Play), nameof(UIRoot_Play.UIRootOnGUI)), prefix: new HarmonyMethod(typeof(RunRecording), nameof(RunRecording.BeforeGUI)));
        var skip = new HarmonyMethod(typeof(DevTestsStartup), nameof(SkipForRunnerColony));
        // Autosave, incidents, weather, wild animals, random mood breaks, prison breaks and game over never run in a runner-owned
        // colony. Each prefix returns true unless the current game carries this runner's identity, so the user's games are untouched.
        harmony.Patch(AccessTools.Method(typeof(Autosaver), nameof(Autosaver.AutosaverTick)), prefix: skip);
        harmony.Patch(AccessTools.Method(typeof(Storyteller), nameof(Storyteller.StorytellerTick)), prefix: skip);
        harmony.Patch(AccessTools.Method(typeof(WeatherDecider), nameof(WeatherDecider.WeatherDeciderTick)), prefix: skip);
        // 2026-11-08: a modpack ability made wild animals berserk and they killed test pawns.
        if (AccessTools.Method(typeof(WildAnimalSpawner), nameof(WildAnimalSpawner.WildAnimalSpawnerTick)) is { } wildSpawner)
            harmony.Patch(wildSpawner, prefix: skip);
        else Log.Warning(s.LogPrefix + "WildAnimalSpawner.WildAnimalSpawnerTick not found; wild animals can still spawn");
        // 2026-11-07: mood breaks stalled ceremonies and destroyed fixtures mid-batch.
        harmony.Patch(AccessTools.Method(typeof(Verse.AI.MentalBreaker), nameof(Verse.AI.MentalBreaker.TryDoRandomMoodCausedMentalBreak)), prefix: skip);
        // Batches that remove every colonist must not start the game-over countdown.
        harmony.Patch(AccessTools.Method(typeof(GameEnder), nameof(GameEnder.CheckOrUpdateGameOver)), prefix: skip);
        foreach (var m in AccessTools.GetDeclaredMethods(typeof(PrisonBreakUtility)).Where(m => m.Name == "StartPrisonBreak")
            .Concat(AccessTools.GetDeclaredMethods(typeof(SlaveRebellionUtility)).Where(m => m.Name == "StartSlaveRebellion")))
            harmony.Patch(m, prefix: skip);
        // The Debug log window stays closed during runs, so it never covers the progress panel.
        foreach (var auto in new[] { AccessTools.Method(typeof(Log), "TryOpenLogWindow"), AccessTools.Method(typeof(EditWindow_Log), "TryAutoOpen") })
            if (auto != null) harmony.Patch(auto, prefix: new HarmonyMethod(typeof(DebugLogHider), nameof(DebugLogHider.AllowOpen)));
        var logError = AccessTools.Method(typeof(Log), nameof(Log.Error), new[] { typeof(string) });
        harmony.Patch(logError, prefix: new HarmonyMethod(typeof(CaseErrors), nameof(CaseErrors.Record)));
        harmony.Patch(logError, prefix: new HarmonyMethod(typeof(StartupLog), nameof(StartupLog.Record)));
        harmony.Patch(AccessTools.Method(typeof(Verse.AI.Pawn_JobTracker), nameof(Verse.AI.Pawn_JobTracker.StartJob)), postfix: new HarmonyMethod(typeof(JobStarts), nameof(JobStarts.After)));
        RunnerSession.Read();
        LaunchArguments.Read();
        Log.Message(s.LogPrefix + "Developer test runner loaded. Evidence: " + TestRunner.EvidenceRoot);
    }

    private static void AfterRootUpdate()
    {
        if (!LongEventHandler.ShouldWaitForEvent) TestRunner.Frame();
    }

    private static void AfterExposeSmallComponents(Game __instance) => RunnerIdentity.Expose(__instance);

    private static bool SkipForRunnerColony() => !RunnerIdentity.Owned(Current.Game);
}

// Errors naming the mod under test, from the moment DevTests loaded, whether or not a run is active. Errors logged before this
// assembly's static constructor ran are not seen here; read Verse.Log.Messages too, and the launcher scans Player.log.
public static class StartupLog
{
    private static readonly List<string> logged = new();
    public static void Record(string __0)
    {
        if (__0 == null || !__0.Contains(Harness.Settings.ErrorMarker)) return;
        lock (logged) if (logged.Count < 50) logged.Add(__0.Split('\n')[0]);
    }

    // Distinct first lines of every error naming the mod, from the game's log queue and from this hook.
    public static List<string> ModErrors()
    {
        var queued = Log.Messages.Where(m => m.type == LogMessageType.Error && m.text != null && m.text.Contains(Harness.Settings.ErrorMarker))
            .Select(m => m.text.Split('\n')[0]).ToList();
        lock (logged) return queued.Concat(logged).Distinct().ToList();
    }
}

// Counts DoBill and other job starts per pawn, job def and target, so a job that starts and ends inside one tick is still seen.
// Harmony postfix on Pawn_JobTracker.StartJob; the job is bound by position. Observes only.
public static class JobStarts
{
    private static readonly Dictionary<(int pawn, string job, int target), int> starts = new();

    public static void After(Verse.AI.Job __0, Pawn ___pawn)
    {
        if (!TestRunner.Running || __0?.def == null || ___pawn == null || __0.targetA.Thing == null) return;
        var key = (___pawn.thingIDNumber, __0.def.defName, __0.targetA.Thing.thingIDNumber);
        starts[key] = starts.TryGetValue(key, out int n) ? n + 1 : 1;
    }

    public static int Count(JobDef job, Pawn pawn, Thing target) =>
        starts.TryGetValue((pawn.thingIDNumber, job.defName, target.thingIDNumber), out int n) ? n : 0;
}

// -<prefix>Test=<batch|run-all> -<prefix>Seed=<n> [-<prefix>RunId=<id>] [-<prefix>KeepOpen=true]: run once loaded, then quit.
public static class LaunchArguments
{
    private static RunRequest pending;
    private static string runId;
    public static bool LauncherOwned { get; internal set; }

    public static void Read()
    {
        string p = Harness.Settings.ArgPrefix;
        if (!GenCommandLine.TryGetCommandLineArg(p + "Test", out string batch)) return;
        LauncherOwned = true;
        int seed = GenCommandLine.TryGetCommandLineArg(p + "Seed", out string s) && int.TryParse(s, out int n) ? n : 1;
        GenCommandLine.TryGetCommandLineArg(p + "RunId", out runId);
        GenCommandLine.TryGetCommandLineArg(p + "Blueprint", out string blueprint);
        GenCommandLine.TryGetCommandLineArg(p + "SaveAs", out string saveAs);
        pending = new RunRequest { Batch = batch, Seed = seed, Origin = "launch",
            BlueprintPath = blueprint, SaveAs = saveAs,
            Record = GenCommandLine.TryGetCommandLineArg(p + "Record", out string recording) && recording == "true",
            HideUI = !GenCommandLine.TryGetCommandLineArg(p + "ShowUI", out string showUI) || showUI != "true",
            KeepOpen = GenCommandLine.TryGetCommandLineArg(p + "KeepOpen", out string keepOpen) && keepOpen == "true" };
    }

    public static void TryStart()
    {
        if (pending == null || Current.ProgramState != ProgramState.Entry || LongEventHandler.AnyEventNowOrWaiting) return;
        var request = pending;
        pending = null;
        string refusal = TestRunner.Start(request, runId);
        if (refusal == null) return;
        Log.Error(Harness.Settings.LogPrefix + "Launch request refused: " + refusal);
        WriteRefusal(request, refusal);
        Root.Shutdown();
    }

    // The launcher still needs a report to read when a request is refused.
    internal static void WriteRefusal(RunRequest request, string refusal, string refusedRunId = null)
    {
        string id = refusedRunId ?? runId;
        if (id == null) return;
        string dir = Path.Combine(TestRunner.EvidenceRoot, id);
        if (Directory.Exists(dir)) return;
        Directory.CreateDirectory(dir);
        if (request.Batches.Count == 0) request.Batches = new List<string> { request.Batch };
        var progress = new Progress { RunId = id, Request = request, Status = RunStatus.Refused, Reason = refusal, StartedUtc = System.DateTime.UtcNow.ToString("o") };
        Controller.WriteOutputs(progress, dir);
    }
}

// Developer menu (Dev mode > Debug actions > "<mod> tests"). The category is fixed at compile time, so it reads "Developer tests";
// the batch list and messages name the mod.
public static class DevMenu
{
    [DebugAction("Developer tests", "Run test batch...", allowedGameStates = AllowedGameStates.Invalid)]
    private static void RunBatch()
    {
        var options = TestRunner.BatchIds.Append(TestRunner.RunAll).Select(id => new FloatMenuOption($"{Harness.Settings.DisplayName}: {id}", () =>
            Find.WindowStack.Add(new FloatMenu(new[] { 1, 2, 3 }.Select(seed =>
                new FloatMenuOption("seed " + seed, () => Start(id, seed))).ToList())))).ToList();
        Find.WindowStack.Add(new FloatMenu(options));
    }

    private static void Start(string batch, int seed)
    {
        string refusal = TestRunner.Start(new RunRequest { Batch = batch, Seed = seed, Origin = "menu" });
        Messages.Message(refusal == null ? $"{Harness.Settings.DisplayName} test run started: {batch} seed {seed}" : $"{Harness.Settings.DisplayName} test run refused: " + refusal,
            refusal == null ? MessageTypeDefOf.NeutralEvent : MessageTypeDefOf.RejectInput, false);
    }

    [DebugAction("Developer tests", "Cancel test run", allowedGameStates = AllowedGameStates.Invalid)]
    private static void CancelRun() => TestRunner.Cancel();

    [DebugAction("Developer tests", "Show last test summary", allowedGameStates = AllowedGameStates.Invalid)]
    private static void ShowSummary()
    {
        string text = TestRunner.LastReport?.Summary(TestRunner.LastRunDir) ?? "No test run has finished in this session. Evidence: " + TestRunner.EvidenceRoot;
        Find.WindowStack.Add(new Dialog_MessageBox(text));
    }
}
