using System;
using System.Collections.Generic;
using System.Linq;

namespace RimWorldDevTests;

// Errors the game logs during a run, numbered so a case can read those logged since the batch's previous case finished.
// The prefix runs before the game's own message limit, so an earlier error flood can't hide a later case's error.
public static class CaseErrors
{
    private const int Kept = 500, PerCase = 5, LineLength = 300;
    private static readonly List<(long seq, string text)> Logged = new();
    private static long next;

    public static long Mark { get { lock (Logged) return next; } }

    // Harmony prefix on Verse.Log.Error(string), bound by position. Never blocks the original.
    public static void Record(string __0)
    {
        if (!TestRunner.Running) return;
        // The game may log from worker threads.
        lock (Logged)
        {
            Logged.Add((++next, __0 ?? ""));
            if (Logged.Count > Kept) Logged.RemoveRange(0, Logged.Count - Kept);
        }
    }

    // Errors in a case's window: since the batch's previous case finished, or since the case began if earlier.
    // A record read back from progress.json has no mark of its own.
    public static IEnumerable<string> For(CaseRecord c, long windowStart = -1)
    {
        long mark = c.ErrorMark < 0 ? windowStart : windowStart < 0 ? c.ErrorMark : Math.Min(c.ErrorMark, windowStart);
        return mark < 0 ? Enumerable.Empty<string>() : Since(mark).ToList();
    }

    // Distinct first lines of errors logged after the mark, capped, with a count of the rest.
    public static IEnumerable<string> Since(long mark)
    {
        List<(long seq, string text)> logged;
        lock (Logged) logged = Logged.ToList();
        var distinct = logged.Where(e => e.seq > mark)
            .Select(e => e.text.Split('\n')[0].Trim())
            .Select(t => t.Length > LineLength ? t.Substring(0, LineLength) + "…" : t)
            .Distinct().ToList();
        foreach (var line in distinct.Take(PerCase)) yield return "logged error: " + line;
        if (distinct.Count > PerCase) yield return $"logged error: (+{distinct.Count - PerCase} more distinct)";
    }
}
