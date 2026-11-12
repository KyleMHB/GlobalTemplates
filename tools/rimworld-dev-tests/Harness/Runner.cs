using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using RimWorld;
using RimWorld.Planet;
using UnityEngine;
using Verse;

namespace RimWorldDevTests;

// Marks a game as runner-owned. Kept outside the game's component lists so user saves never gain a DevTests class;
// a null id is not written, so only runner saves carry the key.
public static class RunnerIdentity
{
    public static string Prefix => Harness.Settings.IdentityPrefix;
    private static readonly ConditionalWeakTable<Game, StrongBox<string>> ids = new();

    public static string Of(Game game) => game != null && ids.TryGetValue(game, out var box) ? box.Value : null;
    public static void Set(Game game, string id) => ids.GetOrCreateValue(game).Value = id;
    public static bool Owned(Game game) => Of(game)?.StartsWith(Prefix) == true;

    internal static void Expose(Game game)
    {
        string id = Of(game);
        Scribe_Values.Look(ref id, Harness.Settings.ScribeKey);
        if (Scribe.mode == LoadSaveMode.LoadingVars && id != null) Set(game, id);
    }
}

// The one public seam: choose batches and seed, start, cancel, read the report. Launch arguments and the
// developer menu both call it; batches stay behind it.
public static class TestRunner
{
    public const string RunAll = "run-all";
    public static string EvidenceRoot => Path.Combine(GenFilePaths.SaveDataFolderPath, Harness.Settings.EvidenceFolder);
    private static string ActivePointer => Path.Combine(EvidenceRoot, "active.txt");

    private static Controller controller;
    public static bool Running => controller != null;
    public static Progress LastReport { get; private set; }
    public static string LastRunDir { get; private set; }

    public static IReadOnlyList<string> BatchIds => Batches.All.Keys.ToList();

    public static List<string> Expand(string batch) => batch == RunAll ? Batches.RunAll.ToList() : new List<string> { batch };

    // Returns null when the run started, otherwise why it was refused.
    public static string Start(RunRequest request, string runId = null)
    {
        if (Current.ProgramState == ProgramState.Playing && !RunnerIdentity.Owned(Current.Game))
            return "an unrelated colony is active; return to the main menu or start from a runner-owned test colony";
        if (controller != null) return "a test run is already in progress";
        Recover();
        if (request.Batches.Count == 0) request.Batches = Expand(request.Batch);
        var unknown = request.Batches.Where(b => !Batches.All.ContainsKey(b)).ToList();
        if (unknown.Count > 0) return "unknown batch: " + string.Join(", ", unknown) + ". Known: " + string.Join(", ", BatchIds) + ", " + RunAll;
        if (request.SaveAs != null)
        {
            if (request.Batches.Count != 1 || !Batches.All[request.Batches[0]].IsShowcase) return "--save-as requires a single showcase";
            string name = request.SaveAs;
            if (string.IsNullOrWhiteSpace(name) || name != name.Trim() || name.EndsWith('.') || name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 ||
                name.StartsWith(RunnerIdentity.Prefix, StringComparison.OrdinalIgnoreCase) || name.EndsWith(".rws", StringComparison.OrdinalIgnoreCase))
                return "save-as must be a plain save name without an extension or runner prefix";
            if (File.Exists(GenFilePaths.FilePathForSavedGame(name))) return "save already exists, refusing to overwrite: " + name;
        }
        if (Current.ProgramState != ProgramState.Playing && Current.ProgramState != ProgramState.Entry)
            return "the game is still loading";
        Batches.ResetForRun();
        var batches = request.Batches.Select(id => Batches.All[id]).ToList();
        foreach (var b in batches)
            if (b.Prepare(request) is { } refusal) return refusal;
        runId ??= $"{DateTime.Now:yyyyMMdd-HHmmss}-{string.Join("+", request.Batches)}-s{request.Seed}";
        string dir = Path.Combine(EvidenceRoot, runId);
        if (Directory.Exists(dir)) return "evidence directory already exists, refusing to overwrite: " + dir;
        Directory.CreateDirectory(dir);
        RunTimeline.Configure(dir);
        RunTimeline.Event("run-start", detail: request.Batch);
        RunRecording.Configure(request, dir);
        TestPresentation.Reset(!batches.Any(b => b.IsShowcase));
        foreach (var b in batches) b.Archive(request, dir);
        var progress = new Progress { RunId = runId, Request = request, StartedUtc = DateTime.UtcNow.ToString("o"), Stage = Controller.LeaveGame };
        File.WriteAllText(ActivePointer, dir);
        controller = new Controller(progress, dir);
        controller.Save();
        Log.Message($"{Harness.Settings.LogPrefix}Run {runId} started. Evidence: {dir}");
        return null;
    }

    public static void Cancel() => controller?.RequestCancel("cancelled by request");
    public static void SaveShowcase() => controller?.SaveShowcase();

    internal static void Frame()
    {
        LaunchArguments.TryStart();
        RunnerSession.Frame();
        DebugLogHider.Frame();
        controller?.Frame();
        TestCamera.Frame();
        Harness.Settings.OnFrame();
        RunRecording.Frame();
    }

    internal static void Finished(Progress progress, string dir)
    {
        LastReport = progress;
        LastRunDir = dir;
        controller = null;
        if (File.Exists(ActivePointer) && File.ReadAllText(ActivePointer) == dir) File.Delete(ActivePointer);
    }

    // A run left "running" by a killed or crashed process is closed as interrupted before anything else starts.
    public static void Recover()
    {
        if (!File.Exists(ActivePointer)) return;
        string dir = File.ReadAllText(ActivePointer).Trim();
        string path = Path.Combine(dir, "progress.json");
        if (File.Exists(path))
        {
            var progress = Progress.Read(path);
            if (progress.Status == RunStatus.Running)
            {
                Controller.Close(progress, RunStatus.Interrupted, "the game process ended before the run finished (recovered on the next start)");
                Controller.WriteOutputs(progress, dir);
                Log.Warning($"{Harness.Settings.LogPrefix}Recovered interrupted run {progress.RunId}: {dir}");
            }
        }
        File.Delete(ActivePointer);
    }
}

internal class Controller
{
    public const string LeaveGame = "leave-game", AwaitEntry = "await-entry", Quickstart = "quickstart", AwaitMap = "await-map",
        RunSegment = "segment", AwaitLoad = "await-load";
    private const double FrameBudgetMs = 30;
    private static readonly TimeSpan SceneLimit = TimeSpan.FromMinutes(5);

    private Progress progress;
    private readonly string dir;
    private Batch batch;
    private BatchContext ctx;
    private IEnumerator<Wait> segment;
    private Wait wait;
    private DateTime stageStarted = DateTime.UtcNow, batchStarted;
    private string cancelReason, quickstartError;
    private bool recordingReady;

    public Controller(Progress progress, string dir)
    {
        this.progress = progress;
        this.dir = dir;
    }

    private string ProgressPath => Path.Combine(dir, "progress.json");
    private BatchRecord Record => progress.BatchRecords.Count > progress.BatchIndex ? progress.BatchRecords[progress.BatchIndex] : null;
    private string BatchId => progress.Request.Batches[progress.BatchIndex];
    private string Identity => $"{RunnerIdentity.Prefix}{progress.RunId}/{BatchId}";

    public void Save() => progress.Write(ProgressPath);

    public void RequestCancel(string reason) => cancelReason ??= reason;

    private void Stage(string stage)
    {
        progress.Stage = stage;
        RunTimeline.Event("stage", BatchId, detail: stage);
        stageStarted = DateTime.UtcNow;
        Save();
    }

    public void Frame()
    {
        try
        {
            if (cancelReason != null) { Finish(RunStatus.Cancelled, cancelReason); return; }
            switch (progress.Stage)
            {
                case LeaveGame:
                    if (Current.ProgramState == ProgramState.Playing) GenScene.GoToMainMenu();
                    Stage(AwaitEntry);
                    break;
                case AwaitEntry:
                    if (Current.ProgramState == ProgramState.Entry && Current.Game == null) Stage(Quickstart);
                    else if (DateTime.UtcNow - stageStarted > SceneLimit) Finish(RunStatus.Interrupted, "timed out returning to the main menu");
                    break;
                case Quickstart:
                    StartQuickstart();
                    break;
                case AwaitMap:
                    if (quickstartError != null) { EndBatch("quickstart failed: " + quickstartError); break; }
                    if (MapReady()) { ResumeFromFile(); PrepareMap(); StartSegment(0); }
                    else if (DateTime.UtcNow - stageStarted > SceneLimit) EndBatch("map generation exceeded the wall-clock limit");
                    break;
                case AwaitLoad:
                    if (MapReady()) { ResumeFromFile(); ArchiveSave(); ctx.Setup($"Reloaded runner save {progress.CurrentSave}"); StartSegment(progress.Segment + 1); }
                    else if (DateTime.UtcNow - stageStarted > SceneLimit) EndBatch("reload exceeded the wall-clock limit");
                    break;
                case RunSegment:
                    Find.TickManager.CurTimeSpeed = TimeSpeed.Paused;
                    if (DateTime.UtcNow - batchStarted > batch.WallLimit) EndBatch($"batch exceeded its wall-clock limit of {batch.WallLimit.TotalMinutes:0} minutes");
                    else Step();
                    break;
            }
        }
        catch (Exception ex)
        {
            Log.Error(Harness.Settings.LogPrefix + "Runner error: " + ex);
            if (progress.Stage == RunSegment || progress.Stage == AwaitMap || progress.Stage == AwaitLoad) EndBatch("runner exception: " + ex.Message);
            else Finish(RunStatus.Interrupted, "runner exception: " + ex.Message);
        }
    }

    private bool MapReady() =>
        Current.ProgramState == ProgramState.Playing && Find.CurrentMap != null && RunnerIdentity.Of(Current.Game) == Identity;

    // Scene loads replace the game; the progress file, not memory, says where the run stands.
    private void ResumeFromFile()
    {
        var stored = Progress.Read(ProgressPath);
        if (stored.RunId != progress.RunId) throw new InvalidOperationException("progress file belongs to another run");
        progress = stored;
        batch = Batches.All[BatchId];
        ctx = new BatchContext(progress, Record, batch) { Save = Save };
        TestPresentation.Changed(progress, batch);
    }

    private void StartQuickstart()
    {
        batch = Batches.All[BatchId];
        TestCamera.Reset(!batch.IsShowcase);
        var record = new BatchRecord { Id = batch.Id, Identity = Identity, MapSize = batch.MapSize, Planned = batch.Plan.Select(p => p.Id).ToList() };
        progress.BatchRecords.Add(record);
        TestPresentation.Changed(progress, batch);
        progress.Segment = 0;
        quickstartError = null;
        Stage(AwaitMap);
        Quickstarter.Queue(Identity, progress.Request.Seed, batch.MapSize, ex => quickstartError = ex.Message);
    }

    private void PrepareMap()
    {
        var record = Record;
        var map = Find.CurrentMap;
        Find.TickManager.CurTimeSpeed = TimeSpeed.Paused;
        record.WorldSeed = Find.World.info.seedString;
        record.StartingTile = map.Tile;
        record.Setup.Add($"Fresh seeded quickstart: Crashlanded, Cassandra Rough, world seed '{record.WorldSeed}', tile {map.Tile} ({map.Biome.defName}), map {map.Size.x}x{map.Size.z}");
        // 2026-11-08: with the progression modpack every map came out 126x384 whatever size was requested.
        if (map.Size.x != batch.MapSize || map.Size.z != batch.MapSize)
            record.Setup.Add($"Map is {map.Size.x}x{map.Size.z}, not the requested {batch.MapSize}x{batch.MapSize}: another mod changed the generated size; layout searches cover the larger dimension");
        var wild = map.mapPawns.AllPawnsSpawned.Where(p => p.RaceProps.Animal && p.Faction == null).ToList();
        foreach (var animal in wild) animal.Destroy(DestroyMode.Vanish);
        record.Setup.Add($"Developer removed {wild.Count} wild animal(s), and no new wild animals spawn in a runner colony, so nothing can turn them against test pawns");
        record.Setup.Add("Autosave suppressed for this runner-owned colony (user autosave settings unchanged)");
        record.Setup.Add("Storyteller incidents and weather changes suppressed; weather set to Clear");
        record.Setup.Add("Time advanced only by runner single ticks; game otherwise paused");
        record.Setup.Add("Randomness: world, starting tile and colonists seeded; simulation randomness after map generation is not seeded. A scoped-stream prototype did not reproduce simulation draws; see test-triage-efficiency ticket 03.");
        map.weatherManager.curWeather = map.weatherManager.lastWeather = WeatherDefOf.Clear;
        // Named up front, so vanilla's "name your colony" dialog never opens on the runner's colony. It's cosmetic (the runner ticks
        // the game itself), but it clutters the screen during visual checks.
        Faction.OfPlayer.Name = Harness.Settings.ColonyName;
        if (map.Parent is Settlement settlement) NamePlayerSettlementDialogUtility.Named(settlement, Harness.Settings.ColonyName + " Site");
        record.Setup.Add("Colony and settlement named by the runner, so the naming dialog doesn't open");
        record.Setup.Add("Runner tops up food and recreation for colonists, prisoners and slaves when below 30%, checked every 250 ticks; rest is not touched");
        if (progress.Environment.Count == 0) progress.Environment = EnvironmentInfo.Capture();
        batchStarted = DateTime.UtcNow;
        Save();
    }

    private void StartSegment(int index)
    {
        progress.Segment = index;
        segment = batch.Segment(index, ctx).GetEnumerator();
        wait = null;
        if (batchStarted == default) batchStarted = DateTime.UtcNow;
        Stage(RunSegment);
    }

    private void Step()
    {
        if (progress.Request.Record && !batch.IsShowcase)
        {
            if (!recordingReady) { RunRecording.Ready(); recordingReady = true; }
            // A recorder failure affects every remaining batch, so it ends the run once instead of each batch in turn.
            string failure = RunRecording.Problem();
            if (failure != null) { Finish(RunStatus.Interrupted, failure); return; }
            if (!RunRecording.CaptureStarted()) return;
        }
        var clock = Stopwatch.StartNew();
        while (clock.Elapsed.TotalMilliseconds < FrameBudgetMs)
        {
            if (ctx.CancelRequested) { RequestCancel("cancelled by the batch (diagnostic cancellation check)"); return; }
            if (wait == null)
            {
                bool more;
                Kit.KeepResearch(ctx);
                Harness.Settings.MaintainSetup(ctx);
                try { more = segment.MoveNext(); }
                catch (Exception ex)
                {
                    Log.Error(Harness.Settings.LogPrefix + "Case exception: " + ex);
                    // 2026-11-06: an error flood earlier in a run-all can stop the game log, leaving an exception with no location.
                    // The top stack frames go into the batch's setup record as well.
                    if (ex is not SetupException)
                        ctx.Setup("Exception stack (top frames): " + string.Join(" | ", (ex.StackTrace ?? "none").Split('\n').Select(l => l.Trim()).Where(l => l.Length > 0).Take(6)));
                    EndBatch("exception: " + ex.GetType().Name + ": " + ex.Message);
                    return;
                }
                if (!more)
                {
                    if (progress.Segment + 1 < batch.SegmentCount) StartSegment(progress.Segment + 1);
                    else EndBatch(null);
                    return;
                }
                wait = ctx.LastWait = segment.Current;
                RunTimeline.Event("wait-start", batch.Id, detail: wait?.GetType().Name);
                continue;
            }
            switch (wait)
            {
                case TickWait t:
                    if (t.Remaining <= 0) { EndWait(); break; }
                    Tick(t);
                    t.Remaining--;
                    break;
                case UntilWait u:
                    if (u.Condition()) { ctx.TimedOut = false; EndWait(); break; }
                    if (u.Remaining <= 0) { ctx.TimedOut = true; EndWait(); break; }
                    Tick(u);
                    u.Remaining--;
                    break;
                case FrameWait f:
                    if (--f.Remaining <= 0) EndWait();
                    return;
                case ReloadWait:
                    EndWait();
                    Reload();
                    return;
                case RecordingWait:
                    if (RunRecording.CaptureStarted()) EndWait();
                    return;
                case RealtimeWait r:
                    double now = Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
                    while (r.Simulate && r.NextTick < Math.Min(now, r.Deadline) && clock.Elapsed.TotalMilliseconds < FrameBudgetMs)
                    {
                        Tick(r);
                        r.NextTick += 1d / 60;
                    }
                    if (Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency >= r.Deadline) { EndWait(); break; }
                    return;
            }
        }
    }

    // Round 4: over days of game time colonists ran out of food and recreation, and their moods collapsed. They left ceremonies,
    // broke mentally, or couldn't take ritual roles. Food and recreation are topped up when low, every pass. Rest isn't touched,
    // because sleep cases control it.
    private static void Sustain()
    {
        if (Find.TickManager.TicksGame % 250 != 0 || Find.CurrentMap == null) return;
        foreach (var p in Find.CurrentMap.mapPawns.AllPawnsSpawned)
        {
            if (p.Dead || !(p.IsColonist || p.IsPrisonerOfColony || p.IsSlaveOfColony) || p.needs == null) continue;
            if (p.needs.food != null && p.needs.food.CurLevelPercentage < 0.3f) p.needs.food.CurLevelPercentage = 1f;
            if (p.needs.joy != null && p.needs.joy.CurLevelPercentage < 0.3f) p.needs.joy.CurLevelPercentage = 1f;
        }
    }

    private void Tick(Wait w)
    {
        Sustain();
        Kit.ApplyPowerHolds();
        Harness.Settings.BeforeTick();
        w.EveryTick?.Invoke();
        Find.TickManager.DoSingleTick();
        Kit.KeepResearch(ctx);
        Harness.Settings.MaintainSetup(ctx);
        w.AfterTick?.Invoke();
        WallCheck();
        SnapDrawPositions();
    }

    // 2026-11-07: at the runner's speed (many ticks per frame) the per-frame draw tween lagged walking pawns by several cells and
    // slid them in straight lines across walls (one pawn was drawn 7 cells from its cell, over a wall). The
    // user saw pawns "stuck in walls". Drawn positions snap to each pawn's cell after every simulated tick. Presentation only:
    // positions, paths and jobs are unchanged.
    private static void SnapDrawPositions()
    {
        if (Find.CurrentMap == null) return;
        foreach (var p in Find.CurrentMap.mapPawns.AllPawnsSpawned) p.Drawer?.tweener?.ResetTweenedPosToRoot();
    }

    // 2026-11-07: the user still saw pawns stuck in walls, and the game logged no unwalkable-cell warning, because a held pawn
    // never paths. Every 30 ticks, any spawned pawn on an impassable cell is logged once per pawn and cell, and disclosed in the
    // batch setup, so the run shows which batch and case put it there. It observes only; nothing is moved.
    private readonly HashSet<(int, IntVec3)> wallSightings = new();
    private void WallCheck()
    {
        var map = Find.CurrentMap;
        if (map == null || ctx == null || Find.TickManager.TicksGame % 30 != 0) return;
        foreach (var p in map.mapPawns.AllPawnsSpawned)
        {
            // WalkableBy: small animals may cross fences (a squirrel was flagged on an AncientFence).
            // Drawn: a recorded run showed pawns over a ward's wall while no pawn stood on a wall
            // cell, so the cell under the drawn position is checked too (a pawn pulled back each tick is drawn mid-step).
            var drawn = p.DrawPos.ToIntVec3();
            bool onWall = !p.Position.WalkableBy(map, p);
            // Only a drawn position a full cell or more from the pawn's cell counts; ordinary drawing leans a pawn up to about 0.7 of
            // a cell, and flying birds cross rock.
            bool drawnOnWall = !onWall && !p.Flying && (p.DrawPos - p.Position.ToVector3Shifted()).MagnitudeHorizontal() >= 1f
                && drawn.InBounds(map) && !drawn.WalkableBy(map, p) && drawn.GetDoor(map) == null;
            if (!onWall && !drawnOnWall) continue;
            var cell = onWall ? p.Position : drawn;
            if (!wallSightings.Add((p.thingIDNumber, cell))) continue;
            var blocker = cell.GetEdifice(map)?.def.defName ?? "impassable terrain";
            var running = progress.Cases.LastOrDefault(c => c.Batch == batch.Id && c.Result == Results.Running)?.Id ?? "between cases";
            var line = onWall
                ? $"Wall check: {p.LabelShort} stood on blocked cell {cell} ({blocker})"
                : $"Wall check: {p.LabelShort} at {p.Position} was drawn over blocked cell {cell} ({blocker}), draw position {p.DrawPos.x:0.00},{p.DrawPos.z:0.00}, moving {p.pather?.Moving}, next cell {p.pather?.nextCell}";
            line += $" at tick {Find.TickManager.TicksGame}, during {running}, job {p.CurJobDef?.defName ?? "none"}, lord {Verse.AI.Group.LordUtility.GetLord(p)?.LordJob?.GetType().Name ?? "none"}";
            Log.Warning(Harness.Settings.LogPrefix + "" + batch.Id + ": " + line);
            ctx.Setup(line);
        }
    }

    private void EndWait()
    {
        RunTimeline.Event("wait-end", batch.Id, detail: wait?.GetType().Name);
        wait = null;
    }

    private void Reload()
    {
        string name = $"{RunnerIdentity.Prefix}{progress.RunId}-{batch.Id}-{progress.Segment}".Replace('/', '-');
        progress.CurrentSave = name;
        Stage(AwaitLoad);
        GameDataSaveLoader.SaveGame(name);
        if (!File.Exists(GenFilePaths.FilePathForSavedGame(name))) { EndBatch("runner save was not written: " + name); return; }
        GameDataSaveLoader.LoadGame(name);
    }

    public void SaveShowcase()
    {
        string name = progress.Request.SaveAs;
        if (name == null) return;
        if (!batch.IsShowcase || !RunnerIdentity.Owned(Current.Game)) throw new SetupException("only the runner-owned showcase can be exported");
        string path = GenFilePaths.FilePathForSavedGame(name);
        if (File.Exists(path)) throw new SetupException("refusing to overwrite save: " + name);
        string identity = RunnerIdentity.Of(Current.Game);
        try
        {
            // The exported colony must run normally, including incidents and autosaves, even with DevTests loaded.
            RunnerIdentity.Set(Current.Game, null);
            GameDataSaveLoader.SaveGame(name);
        }
        finally { RunnerIdentity.Set(Current.Game, identity); }
        if (!File.Exists(path)) throw new SetupException("showcase save was not written: " + name);
        string hash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        File.WriteAllText(Path.Combine(dir, "showcase-save.json"), System.Text.Json.JsonSerializer.Serialize(new
        {
            file = Path.GetFileName(path), sha256 = hash, phase = "base-built-before-tour", runnerOwned = false,
        }));
        ctx.Setup("Exported editable colony before camera tour: " + path + "; SHA-256 " + hash + "; runner ownership omitted");
    }

    // Test saves leave the user's save folder once loaded.
    private void ArchiveSave()
    {
        string source = GenFilePaths.FilePathForSavedGame(progress.CurrentSave);
        string target = Path.Combine(dir, "saves", Path.GetFileName(source));
        Directory.CreateDirectory(Path.GetDirectoryName(target));
        if (File.Exists(source)) File.Move(source, target);
        foreach (var c in progress.Cases.Where(c => c.Batch == Record.Id && c.Result == Results.Running)) c.Evidence.Add("save: " + target);
        Save();
    }

    // Closes the current batch. A reason means it ended early: its unrecorded cases are skipped with that reason.
    private void EndBatch(string reason)
    {
        // Settings a batch changed in memory never outlive it, even when it ends on an exception or cancellation.
        Harness.Settings.OnBatchEnd();
        segment?.Dispose();
        Kit.ClearResearchGuard();
        Kit.ClearPowerHolds();
        var record = Record;
        if (record != null)
        {
            foreach (var c in progress.Cases.Where(c => c.Batch == record.Id && c.Result == Results.Running))
            {
                c.Result = Results.Error;
                c.Reason = reason ?? "case started but never finished";
                c.CaptureFailure(CaseErrors.For(c, ctx?.ErrorMark ?? -1));
            }
            if (reason != null)
                foreach (var planned in batch.Plan.Where(p => progress.Case(record.Id, p.Id) == null))
                    progress.Cases.Add(new CaseRecord { Id = planned.Id, Batch = record.Id, Level = planned.Level, Diagnostic = batch.Diagnostic,
                        ExpectedResult = planned.ExpectedResult, Result = Results.Skip, CoverageReason = CoverageReasons.Blocked,
                        Prerequisites = new() { record.Id + "/batch-setup" }, Reason = "batch ended early: " + reason });
            record.Status = reason == null ? RunStatus.Complete : "ended-early";
            record.Reason = reason ?? "";
            record.Ticks = Current.Game != null ? Find.TickManager.TicksGame : 0;
            RunTimeline.Event("batch-end", record.Id, detail: record.Status);
        }
        segment = null;
        wait = null;
        progress.BatchIndex++;
        if (progress.BatchIndex < progress.Request.Batches.Count) Stage(LeaveGame);
        else Finish(RunStatus.Complete, "");
    }

    internal static void Close(Progress progress, string status, string reason)
    {
        foreach (var c in progress.Cases.Where(c => c.Result == Results.Running))
        {
            c.Result = Results.Error;
            c.Reason = status + " while the case was running: " + reason;
            c.CaptureFailure(CaseErrors.For(c));
        }
        foreach (var b in progress.BatchRecords.Where(b => b.Status == RunStatus.Running)) b.Status = status;
        progress.Status = status;
        progress.Reason = reason;
        progress.FinishedUtc = DateTime.UtcNow.ToString("o");
    }

    internal static void WriteOutputs(Progress progress, string dir)
    {
        progress.Write(Path.Combine(dir, "progress.json"));
        File.WriteAllText(Path.Combine(dir, "report.json"), progress.ReportJson());
        File.WriteAllText(Path.Combine(dir, "summary.txt"), progress.Summary(dir));
    }

    private void Finish(string status, string reason)
    {
        Harness.Settings.OnBatchEnd();
        segment?.Dispose();
        segment = null;
        Kit.ClearResearchGuard();
        Kit.ClearPowerHolds();
        RunTimeline.Event("run-end", detail: status);
        Harness.Settings.OnRunEnd(status);
        TestCamera.Reset(false);
        Close(progress, status, reason);
        WriteOutputs(progress, dir);
        Log.Message(Harness.Settings.LogPrefix + "" + progress.Summary(dir));
        TestRunner.Finished(progress, dir);
        if (progress.Request.Origin == "session")
        {
            if (Current.ProgramState == ProgramState.Playing) GenScene.GoToMainMenu();
            return;
        }
        if (RunRecording.Complete()) return;
        if (progress.Request.Origin == "launch" && !progress.Request.KeepOpen)
        {
            Root.Shutdown();
            return;
        }
        if (Current.ProgramState == ProgramState.Playing) Find.TickManager.CurTimeSpeed = TimeSpeed.Paused;
        Messages.Message($"{Harness.Settings.DisplayName} test run {status}. Summary: {Path.Combine(dir, "summary.txt")}", MessageTypeDefOf.NeutralEvent, false);
    }
}

// The vanilla developer quick test with a fixed seed, a small map and a temperate starting tile.
internal static class Quickstarter
{
    public static void Queue(string identity, int seed, int mapSize, Action<Exception> failed)
    {
        LongEventHandler.QueueLongEvent(delegate
        {
            Rand.PushState(seed);
            try
            {
                Current.ProgramState = ProgramState.Entry;
                Game.ClearCaches();
                Current.Game = new Game();
                RunnerIdentity.Set(Current.Game, identity);
                Current.Game.InitData = new GameInitData();
                Current.Game.Scenario = ScenarioDefOf.Crashlanded.scenario;
                Find.Scenario.PreConfigure();
                Current.Game.storyteller = new Storyteller(StorytellerDefOf.Cassandra, DifficultyDefOf.Rough);
                Current.Game.World = WorldGenerator.GenerateWorld(0.3f, Harness.Settings.ArgPrefix + "test" + seed, OverallRainfall.Normal, OverallTemperature.Normal,
                    OverallPopulation.Normal, LandmarkDensity.Normal);
                Find.World.info.name = identity;
                var tile = TileFinder.RandomSettlementTileFor(Faction.OfPlayer, true, Temperate);
                if (!tile.Valid) tile = TileFinder.RandomStartingTile();
                if (!tile.Valid) throw new InvalidOperationException("no valid starting tile in the seeded world");
                Find.GameInitData.startingTile = tile;
                Find.GameInitData.mapSize = mapSize;
                Find.Scenario.PostIdeoChosen();
                Find.GameInitData.PrepForMapGen();
                Find.Scenario.PreMapGenerate();
            }
            catch (Exception ex)
            {
                failed(ex);
                throw;
            }
            finally
            {
                Rand.PopState();
            }
        }, "Play", "GeneratingMap", false, ex => { Log.Error(Harness.Settings.LogPrefix + "Quickstart failed: " + ex); failed(ex); });
    }

    private static bool Temperate(PlanetTile tile)
    {
        var t = Find.WorldGrid[tile];
        return t.PrimaryBiome == BiomeDefOf.TemperateForest && (t.hilliness == Hilliness.Flat || t.hilliness == Hilliness.SmallHills)
            && Mathf.Abs(Find.WorldGrid.LongLatOf(tile).y) < 35f;
    }
}

internal static class EnvironmentInfo
{
    public static Dictionary<string, object> Capture()
    {
        string dll = Harness.Settings.ProductionDllPath;
        var environment = new Dictionary<string, object>
        {
            ["runtimeHash"] = RuntimeManifest.Hash(),
            ["developerHash"] = Sha256(Harness.Settings.DevDllPath),
            ["harnessHash"] = Sha256(typeof(TestRunner).Assembly.Location),
            ["game"] = new Dictionary<string, string> { ["version"] = VersionControl.CurrentVersionStringWithRev },
            ["modBuild"] = new Dictionary<string, string> { ["path"] = dll, ["sha256"] = File.Exists(dll) ? Sha256(dll) : null },
            ["modCount"] = LoadedModManager.RunningModsListForReading.Count,
            ["mods"] = LoadedModManager.RunningModsListForReading.Select(m => m.PackageId + (m.ModMetaData?.ModVersion is { Length: > 0 } v ? "@" + v : "")).ToList(),
            ["dlc"] = new Dictionary<string, bool>
            {
                ["royalty"] = ModsConfig.RoyaltyActive, ["ideology"] = ModsConfig.IdeologyActive, ["biotech"] = ModsConfig.BiotechActive,
                ["anomaly"] = ModsConfig.AnomalyActive, ["odyssey"] = ModsConfig.OdysseyActive,
            },
        };
        Harness.Settings.AddEnvironment(environment);
        return environment;
    }

    public static string Sha256(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
}
