using System;
using System.Collections.Generic;
using System.Diagnostics;

namespace TimberbornDevTests;

// Stopwatch timing for a mod's costly paths, ported from RimWorld Dev Tests. A case calls the path directly, many times, at
// a stated scale, and gets an Id starting "perf." so release-check requires it to pass on the DLL being shipped (D8).
// RimWorld's PatchCost is left out: the game ships no Harmony (it comes from a Workshop mod), and the runner must load
// without it.
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

    // Records a MsPerCall figure at a stated scale, such as 200 buildings placed at once. `scale` is how many calls that
    // situation makes; the total is what a player would see in one frame.
    public static CaseScope Report(CaseScope c, double msPerCall, int callsPerRound, int scale, string situation)
    {
        return c.Observe("msPerCall", msPerCall)
            .Observe("scale", scale)
            .Observe("msAtScale", msPerCall * scale)
            .Evidence($"{CaseScope.Format(msPerCall)} ms/call, median of rounds of {callsPerRound} calls")
            .Evidence($"At {scale} calls ({situation}): {CaseScope.Format(msPerCall * scale)} ms");
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

    private static double Median(List<double> values)
    {
        values.Sort();
        int mid = values.Count / 2;
        return values.Count % 2 == 1 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
    }
}
