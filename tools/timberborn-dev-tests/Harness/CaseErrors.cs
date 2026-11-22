using System.Collections.Generic;
using System.Linq;

namespace TimberbornDevTests;

// Errors the game logs during a run, numbered so a finished case can read those logged since the batch's previous case
// finished. Fed from RunReport's threaded log hook, so errors raised during parallel ticking count too.
public static class CaseErrors
{
    private const int Kept = 500, PerCase = 5, LineLength = 300;
    private static readonly List<(long seq, string text)> Logged = new();
    private static long next;

    public static long Mark { get { lock (Logged) return next; } }

    internal static void Record(string text)
    {
        lock (Logged)
        {
            Logged.Add((++next, text ?? ""));
            if (Logged.Count > Kept) Logged.RemoveRange(0, Logged.Count - Kept);
        }
    }

    // Every error after the mark, including repeats and those beyond the lines kept.
    public static int CountSince(long mark) => mark < 0 ? 0 : (int)(Mark - mark);

    // Distinct first lines of errors logged after the mark, capped, with a count of the rest.
    public static IEnumerable<string> Since(long mark)
    {
        if (mark < 0) return Enumerable.Empty<string>();
        List<(long seq, string text)> logged;
        lock (Logged) logged = Logged.ToList();
        var distinct = logged.Where(e => e.seq > mark)
            .Select(e => e.text.Split('\n')[0].Trim())
            .Select(t => t.Length > LineLength ? t.Substring(0, LineLength) + "..." : t)
            .Distinct().ToList();
        var lines = distinct.Take(PerCase).Select(l => "logged error: " + l).ToList();
        if (distinct.Count > PerCase) lines.Add($"logged error: (+{distinct.Count - PerCase} more distinct)");
        return lines;
    }
}
