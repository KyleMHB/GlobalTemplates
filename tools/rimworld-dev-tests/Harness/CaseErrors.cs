using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEngine;

namespace RimWorldDevTests;

// Errors the game logs during a run, numbered so a case can read those logged since the batch's previous case finished.
// The prefix runs before the game's own message limit, so an earlier error flood can't hide a later case's error.
public static class CaseErrors
{
    private const int Kept = 500, PerCase = 5, LineLength = 300;
    private static readonly List<(long seq, string text)> Logged = new();
    private static long next, naming;

    public static long Mark { get { lock (Logged) return next; } }
    // Count so far of errors naming the mod under test (HarnessSettings.ErrorMarker).
    public static long ModMark { get { lock (Logged) return naming; } }

    // Errors and exceptions logged through Verse.Log.Error on this thread right now. Unity reports those again through
    // logMessageReceivedThreaded; the depth keeps them from being counted twice. A finalizer lowers it, because Log.Error stops
    // calling Debug.LogError once the game's message limit is reached.
    [ThreadStatic] private static int inLogError;
    private static string[] modNames;

    public static void EnterLogError() => inLogError++;
    public static void ExitLogError() { if (inLogError > 0) inLogError--; }

    // ---- Allowances and warnings --------------------------------------------------------------------------------------------
    private static readonly List<(long seq, string text)> Warned = new();
    private static long nextWarning;
    private static LogAllowance[] allowedErrors, allowedWarnings;

    public static long WarningMark { get { lock (Warned) return nextWarning; } }

    // True when an allowance covers the line: its text is in the message and, when it names a frame, that frame is on the
    // stack. The stack is read only for an allowance whose text already matched.
    private static bool Allowed(LogAllowance[] allowances, string text, Func<string> stack)
    {
        if (allowances.Length == 0 || text == null) return false;
        string trace = null;
        foreach (var a in allowances)
        {
            if (string.IsNullOrEmpty(a.Text) || !text.Contains(a.Text)) continue;
            if (string.IsNullOrEmpty(a.Frame) || (trace ??= stack() ?? "").Contains(a.Frame)) return true;
        }
        return false;
    }

    private static bool AllowedError(string text, Func<string> stack) =>
        Allowed(allowedErrors ??= Harness.Settings.AllowedErrors.ToArray(), text, stack);

    // Harmony prefix on Verse.Log.Warning(string), bound by position. Never blocks the original. The runner's own lines and
    // allowed ones are not counted.
    public static void RecordWarning(string __0)
    {
        if (!TestRunner.Running || __0 == null || __0.StartsWith(Harness.Settings.LogPrefix) || __0.StartsWith("[RimWorldDevTests")) return;
        if (Allowed(allowedWarnings ??= Harness.Settings.AllowedWarnings.ToArray(), __0, () => Environment.StackTrace)) return;
        lock (Warned)
        {
            Warned.Add((++nextWarning, __0));
            if (Warned.Count > Kept) Warned.RemoveRange(0, Warned.Count - Kept);
        }
    }

    public static IEnumerable<string> WarningsFor(CaseRecord c, long windowStart = -1)
    {
        long mark = Window(c.WarningMark, windowStart);
        return mark < 0 ? Enumerable.Empty<string>() : Lines(Warned, mark, "logged warning: ").ToList();
    }

    public static int WarningCountFor(CaseRecord c, long windowStart = -1)
    {
        long mark = Window(c.WarningMark, windowStart);
        return mark < 0 ? 0 : (int)(WarningMark - mark);
    }

    // Harmony prefix on Verse.Log.Error(string), bound by position. Never blocks the original.
    public static void Record(string __0)
    {
        if (!TestRunner.Running || AllowedError(__0, () => Environment.StackTrace)) return;
        // The game may log from worker threads.
        lock (Logged)
        {
            Logged.Add((++next, __0 ?? ""));
            if (__0 != null && __0.Contains(Harness.Settings.ErrorMarker)) naming++;
            if (Logged.Count > Kept) Logged.RemoveRange(0, Logged.Count - Kept);
        }
    }

    // Unity's log, on whichever thread logged. Counts errors and uncaught exceptions that didn't go through Verse.Log.Error,
    // such as an exception thrown in a per-frame Harmony patch that the engine logs itself. One whose message or stack trace
    // names the mod under test counts as the mod's own. Never logs: that would re-enter this handler.
    public static void Unity(string condition, string stackTrace, LogType type)
    {
        if (type != LogType.Exception && type != LogType.Error || inLogError > 0 || !TestRunner.Running) return;
        if (AllowedError(condition, () => stackTrace)) return;
        string text = (type == LogType.Exception ? "uncaught exception: " : "Unity error: ") + (condition ?? "");
        bool mod = NamesMod(condition) || NamesMod(stackTrace);
        lock (Logged)
        {
            Logged.Add((++next, text));
            if (mod) naming++;
            if (Logged.Count > Kept) Logged.RemoveRange(0, Logged.Count - Kept);
        }
        if (mod) StartupLog.Add(text);
    }

    // The ErrorMarker, or a frame in the production assembly: its name or one of its namespaces followed by a type. Namespaces the
    // game also declares are left out.
    private static bool NamesMod(string text)
    {
        if (string.IsNullOrEmpty(text)) return false;
        if (text.Contains(Harness.Settings.ErrorMarker)) return true;
        foreach (var name in modNames ??= ModNames()) if (text.Contains(name)) return true;
        return false;
    }

    private static string[] ModNames()
    {
        var production = Harness.Settings.ProductionType.Assembly;
        IEnumerable<string> namespaces;
        try { namespaces = production.GetTypes().Select(t => t.Namespace); }
        catch (ReflectionTypeLoadException ex) { namespaces = ex.Types.Where(t => t != null).Select(t => t.Namespace); }
        var game = new[] { typeof(Verse.Log).Assembly, typeof(RimWorld.ThingDefOf).Assembly }
            .SelectMany(a => a.GetTypes()).Select(t => t.Namespace).Where(n => n != null).ToHashSet();
        return namespaces.Append(production.GetName().Name).Where(n => !string.IsNullOrEmpty(n) && !game.Contains(n))
            .Distinct().Select(n => n + ".").ToArray();
    }

    // Where a case's window starts: since the batch's previous case finished, or since the case began if earlier.
    // A record read back from progress.json has no mark of its own.
    private static long WindowMark(CaseRecord c, long windowStart) => Window(c.ErrorMark, windowStart);

    private static long Window(long caseMark, long windowStart) =>
        caseMark < 0 ? windowStart : windowStart < 0 ? caseMark : Math.Min(caseMark, windowStart);

    public static IEnumerable<string> For(CaseRecord c, long windowStart = -1)
    {
        long mark = WindowMark(c, windowStart);
        return mark < 0 ? Enumerable.Empty<string>() : Since(mark).ToList();
    }

    // Every error in the window, including repeats and those beyond the lines kept.
    public static int CountFor(CaseRecord c, long windowStart = -1)
    {
        long mark = WindowMark(c, windowStart);
        return mark < 0 ? 0 : (int)(Mark - mark);
    }

    // Distinct first lines of errors logged after the mark, capped, with a count of the rest.
    public static IEnumerable<string> Since(long mark) => Lines(Logged, mark, "logged error: ");

    private static IEnumerable<string> Lines(List<(long seq, string text)> source, long mark, string label)
    {
        List<(long seq, string text)> logged;
        lock (source) logged = source.ToList();
        var distinct = logged.Where(e => e.seq > mark)
            .Select(e => e.text.Split('\n')[0].Trim())
            .Select(t => t.Length > LineLength ? t.Substring(0, LineLength) + "…" : t)
            .Distinct().ToList();
        foreach (var line in distinct.Take(PerCase)) yield return label + line;
        if (distinct.Count > PerCase) yield return $"{label}(+{distinct.Count - PerCase} more distinct)";
    }
}
