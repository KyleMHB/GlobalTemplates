using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using Verse;

namespace RimWorldDevTests;

// Measures the mod's cost the way players quote it: Dubs Performance Analyzer's average milliseconds per tick for the
// mod's own methods. Dubs is driven through reflection so the harness has no build dependency on it, and only the
// production assembly is profiled, so the harness and dev DLLs never count against the mod.
//
// Dubs keeps patches applied after its window closes, and always patches Harmony's constructor while active, so the
// perf mod set must stay out of run-all: run it with `run perf --mods perf`.
public class PerfBatch : Batch
{
    public const string DubsPackageId = "dubwise.dubsperformanceanalyzer.steam";
    public const int WarmupTicks = 300;
    // Dubs keeps 2000 entries per profiler; a window under that keeps every measured tick in the average.
    public const int MeasuredTicks = 1800;
    private const int TopMethods = 10;
    internal const int CleanupFrameLimit = 600;

    public override string Id => "perf";
    public override int SegmentCount => 1;

    public override IReadOnlyList<PlannedCase> Plan { get; } = new[]
    {
        new PlannedCase("perf.mod-tick", Levels.Mechanical, Results.Pass),
    };

    public override IEnumerable<Wait> Segment(int index, BatchContext ctx)
    {
        var perf = ctx.Begin("perf.mod-tick").Expect("measuredTicks", MeasuredTicks)
            .Setup($"Profiled only {Harness.Settings.ProductionType.Assembly.GetName().Name}.dll with Dubs Performance Analyzer (Tick category)");
        if (!ModsConfig.IsActive(DubsPackageId))
        {
            perf.EnvironmentUnavailable($"Dubs Performance Analyzer is not active ({DubsPackageId}); run with --mods perf");
            yield break;
        }
        var dubs = DubsApi.Resolve(out string missing);
        if (dubs == null)
        {
            perf.EnvironmentUnavailable($"this Dubs Performance Analyzer version does not expose {missing}");
            yield break;
        }
        perf.Observe("dubsVersion", dubs.Version);

        var production = Harness.Settings.ProductionType.Assembly;
        string entryName = Harness.Settings.DisplayName + "-devtests-perf";

        // A reused session may still hold a previous run's patches, which would leave the assembly "already patched".
        foreach (var wait in dubs.WaitForCleanup()) yield return wait;
        if (dubs.IsAssemblyPatched(production) || dubs.EntryExists(entryName))
        {
            dubs.Cleanup();
            foreach (var wait in dubs.WaitForCleanup()) yield return wait;
        }
        if (dubs.CleaningUp)
        {
            perf.SetupFailed($"Dubs did not finish cleaning up within {CleanupFrameLimit} frames");
            yield break;
        }

        foreach (var wait in Harness.Settings.PerfSetup(ctx)) yield return wait;

        bool threaded = dubs.DisableThreadedPatching;
        Window window = null;
        try
        {
            window = dubs.OpenWindow();
            // Synchronous patching, so the methods are profiled before warm-up starts.
            dubs.DisableThreadedPatching = true;
            dubs.PatchAssembly(entryName, production);
            dubs.DisableThreadedPatching = threaded;

            int patched = dubs.PatchedMethods.Count(m => m.DeclaringType?.Assembly == production);
            perf.Observe("patchedMethods", patched).Observe("dubsPaused", dubs.Paused);
            if (patched == 0)
            {
                perf.SetupFailed($"Dubs patched no methods from {production.GetName().Name}.dll");
                yield break;
            }

            yield return Wait.Ticks(WarmupTicks);
            dubs.ResetProfilers();
            yield return Wait.Ticks(MeasuredTicks);

            int entries = dubs.LogCount;
            perf.Observe("measuredTicks", entries);
            if (entries != MeasuredTicks)
            {
                perf.SetupFailed($"Dubs recorded {entries} ticks of {MeasuredTicks}; profiling was paused or not attached to the tick");
                yield break;
            }
            Report(perf, dubs.Collect(production, entries), dubs.RootAverage(entries));
        }
        finally
        {
            dubs.DisableThreadedPatching = threaded;
            // Closing resets Dubs's data, so it happens only after the report.
            if (window != null) Find.WindowStack.TryRemove(window, doCloseSound: false);
            dubs.Cleanup();
        }
        foreach (var wait in dubs.WaitForCleanup()) yield return wait;
        perf.Pass();
    }

    private static void Report(CaseScope perf, List<MethodCost> costs, double? tickAverage)
    {
        // Self time does not count a nested profiled method twice, so it is the headline figure.
        double self = costs.Sum(c => c.Self);
        perf.Observe("modMsPerTick", Math.Round(self, 4)).Observe("modMsPerTickInclusive", Math.Round(costs.Sum(c => c.Average), 4))
            .Observe("methodsCalled", costs.Count).Observe("worstSingleTickMs", Math.Round(costs.Select(c => c.Max).DefaultIfEmpty().Max(), 4));
        if (tickAverage is double tick) perf.Observe("wholeTickMs", Math.Round(tick, 4));
        perf.Evidence($"Mod self time {self:0.####} ms/tick over {MeasuredTicks} ticks (Dubs \"Av\", summed self time of the mod's own methods)");
        foreach (var c in costs.OrderByDescending(c => c.Self).Take(TopMethods))
            perf.Evidence($"{c.Label}: self {c.Self:0.####} ms, avg {c.Average:0.####} ms, max {c.Max:0.###} ms, {c.Calls / MeasuredTicks:0.##} calls/tick");
    }
}

internal record MethodCost(string Label, double Average, double Self, double Max, float Calls);

// Every Dubs member the batch uses, resolved once. A missing member names itself so a Dubs update reports clearly.
internal class DubsApi
{
    private Type analyzer, guiController, profileController, transplanting, utility, settings, windowType, category;

    public static DubsApi Resolve(out string missing)
    {
        var api = new DubsApi();
        missing = api.Bind();
        return missing == null ? api : null;
    }

    private string Bind()
    {
        string Need(ref Type t, string name) => (t = AccessTools.TypeByName(name)) == null ? name : null;
        return Need(ref analyzer, "Analyzer.Profiling.Analyzer") ?? Need(ref guiController, "Analyzer.Profiling.GUIController")
            ?? Need(ref profileController, "Analyzer.Profiling.ProfileController") ?? Need(ref transplanting, "Analyzer.Profiling.MethodTransplanting")
            ?? Need(ref utility, "Analyzer.Profiling.Utility") ?? Need(ref settings, "Analyzer.Settings")
            ?? Need(ref windowType, "Analyzer.Window_Analyzer") ?? Need(ref category, "Analyzer.Profiling.Category")
            ?? Missing(analyzer, "CurrentlyCleaningUp", "CurrentlyPaused", "GetCurrentLogCount", "Cleanup")
            ?? Missing(guiController, "AddEntry", "SwapToEntry", "EntryByName", "ResetProfilers")
            ?? Missing(utility, "PatchAssemblyFull", "patchedAssemblies") ?? Missing(transplanting, "patchedMeths")
            ?? Missing(profileController, "Profiles") ?? Missing(settings, "disableThreadedPatching")
            ?? (AccessTools.TypeByName("Analyzer.Profiling.Profiler") is { } profiler
                ? Missing(profiler, "meth", "label", "CollectStatistics", "ChildAverage") : "Analyzer.Profiling.Profiler");
    }

    private static string Missing(Type type, params string[] names) =>
        names.Where(n => AccessTools.Method(type, n) == null && AccessTools.Property(type, n) == null && AccessTools.Field(type, n) == null)
            .Select(n => type.FullName + "." + n).FirstOrDefault();

    private object Get(Type t, string name) => AccessTools.Property(t, name) is { } p ? p.GetValue(null) : AccessTools.Field(t, name).GetValue(null);
    private object Call(Type t, string name, params object[] args) => AccessTools.Method(t, name).Invoke(null, args);

    public string Version => AccessTools.TypeByName("Analyzer.Modbase") is { } m && AccessTools.Field(m, "analyzerVersion") is { } f
        ? f.GetValue(null)?.ToString() : "unknown";
    public bool CleaningUp => (bool)Get(analyzer, "CurrentlyCleaningUp");
    public bool Paused => (bool)Get(analyzer, "CurrentlyPaused");
    public int LogCount => (int)Get(analyzer, "GetCurrentLogCount");
    public bool DisableThreadedPatching
    {
        get => (bool)Get(settings, "disableThreadedPatching");
        set => AccessTools.Field(settings, "disableThreadedPatching").SetValue(null, value);
    }
    public IEnumerable<MethodInfo> PatchedMethods => ((IEnumerable)Get(transplanting, "patchedMeths")).OfType<MethodInfo>().ToList();
    public bool IsAssemblyPatched(Assembly assembly) => ((IEnumerable<string>)Get(utility, "patchedAssemblies")).Contains(assembly.FullName);
    public bool EntryExists(string name) => Call(guiController, "EntryByName", name) != null;

    // Cleanup runs on a background task that unpatches everything; waiting in frames keeps the game from ticking meanwhile.
    public void Cleanup() => Call(analyzer, "Cleanup");
    public IEnumerable<Wait> WaitForCleanup()
    {
        yield return Wait.Frames(2);
        for (int i = 0; i < PerfBatch.CleanupFrameLimit && CleaningUp; i++) yield return Wait.Frames(1);
    }

    public Window OpenWindow()
    {
        var window = (Window)Activator.CreateInstance(windowType);
        Find.WindowStack.Add(window);
        return window;
    }

    public void PatchAssembly(string entryName, Assembly assembly)
    {
        Call(guiController, "AddEntry", entryName, Enum.Parse(category, "Tick"));
        Call(guiController, "SwapToEntry", entryName);
        Call(utility, "PatchAssemblyFull", entryName, new List<Assembly> { assembly });
    }

    public void ResetProfilers() => Call(guiController, "ResetProfilers");

    public double? RootAverage(int entries) =>
        AccessTools.Method(profileController, "CollectRootAverage") is { } m ? Convert.ToDouble(m.Invoke(null, new object[] { entries })) : null;

    public List<MethodCost> Collect(Assembly assembly, int entries)
    {
        var result = new List<MethodCost>();
        foreach (var profiler in ((IDictionary)Get(profileController, "Profiles")).Values)
        {
            var type = profiler.GetType();
            if (!(AccessTools.Field(type, "meth").GetValue(profiler) is MethodBase meth) || meth.DeclaringType?.Assembly != assembly) continue;
            var args = new object[] { entries, null, null, null, null, null };
            AccessTools.Method(type, "CollectStatistics").Invoke(profiler, args);
            float calls = (float)args[4];
            if (calls == 0) continue;
            double average = (double)args[1];
            double child = (double)AccessTools.Method(type, "ChildAverage").Invoke(profiler, new object[] { entries });
            string label = AccessTools.Field(type, "label").GetValue(profiler) as string ?? meth.DeclaringType.Name + "." + meth.Name;
            result.Add(new MethodCost(label, average, Math.Max(0, average - child), (double)args[2], calls));
        }
        return result;
    }
}
