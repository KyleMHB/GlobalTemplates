using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using HarmonyLib;

namespace RimWorldDevTests;

// Targeted Stopwatch timing for code the tick average misses: event-driven paths such as pawn
// generation, raids or UI. A case calls the path directly, many times, at a stated scale.
public static class PerfTiming
{
    // Median ms per call over `rounds` rounds of `calls` calls each, after `warmup` untimed calls.
    public static double MsPerCall(Action call, int calls, int rounds = 5, int warmup = 10)
    {
        for (int i = 0; i < warmup; i++) call();
        var samples = new List<double>(rounds);
        for (int r = 0; r < rounds; r++) samples.Add(TimeRound(call, calls));
        return Median(samples);
    }

    // What the production assembly's Harmony patches on `original` add to `call`. Rounds alternate
    // between patched and with those patches temporarily removed; other mods' patches stay applied.
    // The removed patches are restored with their owner, priority and ordering before returning.
    public static PatchCost PatchCost(MethodBase original, Action call, int calls, int rounds = 5, int warmup = 10)
    {
        var production = Harness.Settings.ProductionType.Assembly;
        var info = Harmony.GetPatchInfo(original);
        var ours = new List<(Patch patch, string kind)>();
        if (info != null)
        {
            ours.AddRange(info.Prefixes.Where(p => p.PatchMethod.DeclaringType?.Assembly == production).Select(p => (p, "prefix")));
            ours.AddRange(info.Postfixes.Where(p => p.PatchMethod.DeclaringType?.Assembly == production).Select(p => (p, "postfix")));
            ours.AddRange(info.Transpilers.Where(p => p.PatchMethod.DeclaringType?.Assembly == production).Select(p => (p, "transpiler")));
            ours.AddRange(info.Finalizers.Where(p => p.PatchMethod.DeclaringType?.Assembly == production).Select(p => (p, "finalizer")));
        }
        string name = original.DeclaringType?.Name + "." + original.Name;
        if (ours.Count == 0) throw new SetupException($"{production.GetName().Name} has no Harmony patch on {name}");

        for (int i = 0; i < warmup; i++) call();
        var patched = new List<double>(rounds);
        var unpatched = new List<double>(rounds);
        for (int r = 0; r < rounds; r++)
        {
            patched.Add(TimeRound(call, calls));
            var removed = new List<(Patch patch, string kind)>();
            try
            {
                Unpatch(original, ours, removed);
                for (int i = 0; i < warmup; i++) call();
                unpatched.Add(TimeRound(call, calls));
            }
            finally { Restore(original, removed); }
            for (int i = 0; i < warmup; i++) call();
        }
        return new PatchCost(name, ours.Count, calls, Median(patched), Median(unpatched));
    }

    private static double TimeRound(Action call, int calls)
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
        var watch = Stopwatch.StartNew();
        for (int i = 0; i < calls; i++) call();
        watch.Stop();
        return watch.Elapsed.TotalMilliseconds / calls;
    }

    private static void Unpatch(MethodBase original, List<(Patch patch, string kind)> patches, List<(Patch patch, string kind)> removed)
    {
        foreach (var entry in patches)
        {
            new Harmony(entry.patch.owner).Unpatch(original, entry.patch.PatchMethod);
            removed.Add(entry);
        }
    }

    private static void Restore(MethodBase original, List<(Patch patch, string kind)> patches)
    {
        foreach (var (patch, kind) in patches)
        {
            var method = new HarmonyMethod(patch.PatchMethod, patch.priority, patch.before, patch.after, patch.debug);
            var harmony = new Harmony(patch.owner);
            switch (kind)
            {
                case "prefix": harmony.Patch(original, prefix: method); break;
                case "postfix": harmony.Patch(original, postfix: method); break;
                case "transpiler": harmony.Patch(original, transpiler: method); break;
                default: harmony.Patch(original, finalizer: method); break;
            }
        }
    }

    private static double Median(List<double> values)
    {
        values.Sort();
        int mid = values.Count / 2;
        return values.Count % 2 == 1 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
    }
}

public sealed class PatchCost
{
    public string Method { get; }
    public int Patches { get; }
    public int CallsPerRound { get; }
    public double PatchedMsPerCall { get; }
    public double UnpatchedMsPerCall { get; }
    public double AddedMsPerCall => PatchedMsPerCall - UnpatchedMsPerCall;

    public PatchCost(string method, int patches, int callsPerRound, double patched, double unpatched)
    {
        Method = method; Patches = patches; CallsPerRound = callsPerRound;
        PatchedMsPerCall = patched; UnpatchedMsPerCall = unpatched;
    }

    // Records the cost at a stated scale, such as 150 pawns generated for one large raid.
    // `scale` is how many calls that situation makes; the total is what a player would see at once.
    public CaseScope Report(CaseScope c, int scale, string situation)
    {
        return c.Observe("addedMsPerCall", AddedMsPerCall)
            .Observe("patchedMsPerCall", PatchedMsPerCall)
            .Observe("unpatchedMsPerCall", UnpatchedMsPerCall)
            .Observe("scale", scale)
            .Observe("addedMsAtScale", AddedMsPerCall * scale)
            .Evidence($"{Patches} patch(es) on {Method}: {CaseScope.Format(PatchedMsPerCall)} ms/call patched, {CaseScope.Format(UnpatchedMsPerCall)} unpatched, median of rounds of {CallsPerRound} calls")
            .Evidence($"At {scale} calls ({situation}): {CaseScope.Format(AddedMsPerCall * scale)} ms added");
    }
}
