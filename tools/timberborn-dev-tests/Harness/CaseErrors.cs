using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace TimberbornDevTests;

// Errors naming the mod under test: its ErrorMarker in the text, or a stack frame in one of its assemblies' namespaces. Those
// logged while the game loaded (from the runner's starter, which the launcher's ModPriority puts first, until the main menu)
// are startup errors; later ones count during the run. Either kind fails the run under HarnessSettings.FailOnModErrors.
public static class ModErrors
{
    private const int StartupKept = 50;
    private static readonly object Sync = new();
    private static readonly List<string> startup = new();
    private static string[] names = Array.Empty<string>();
    private static bool loading = true;
    private static int during, loggedDuring;

    public static string Marker { get; private set; }
    public static bool FailOnModErrors { get; private set; }

    public static List<string> Startup { get { lock (Sync) return startup.ToList(); } }
    public static int During { get { lock (Sync) return during; } }
    public static int LoggedDuring { get { lock (Sync) return loggedDuring; } }

    // Called from the runner's starter, after every mod's assemblies are loaded and before any other mod's starter runs.
    internal static void Configure(RunRequest request)
    {
        HarnessSettings settings = null;
        // A broken settings class must not stop the runner's starter: the main menu reports it when it builds the batches.
        try { settings = Harness.Settings; }
        catch (Exception ex) { Runner.Log("HarnessSettings unavailable for the startup check: " + ex.Message); }
        Marker = settings?.ErrorMarker ?? request.ModName;
        FailOnModErrors = settings?.FailOnModErrors ?? false;
        if (Marker == null) return;
        var wanted = new HashSet<string>(request.ModAssemblies ?? new List<string>());
        var assemblies = AppDomain.CurrentDomain.GetAssemblies();
        var game = new HashSet<string>(assemblies.Where(IsGame).SelectMany(Namespaces));
        names = assemblies.Where(a => wanted.Contains(a.GetName().Name)).SelectMany(Namespaces)
            .Where(n => !game.Contains(n)).Distinct().Select(n => n + ".").ToArray();
        Runner.Log($"Mod errors: marker '{Marker}', {names.Length} namespace(s) from {wanted.Count} assembly name(s)");
    }

    private static bool IsGame(Assembly a)
    {
        string name = a.GetName().Name;
        return name == typeof(Harness).Assembly.GetName().Name || name == "mscorlib" || name == "netstandard" ||
               new[] { "Timberborn.", "Unity", "Bindito.", "System", "Newtonsoft." }.Any(name.StartsWith);
    }

    private static IEnumerable<string> Namespaces(Assembly a)
    {
        Type[] types;
        try { types = a.GetTypes(); }
        catch (ReflectionTypeLoadException ex) { types = ex.Types.Where(t => t != null).ToArray(); }
        return types.Select(t => t.Namespace).Where(n => !string.IsNullOrEmpty(n));
    }

    private static bool Names(string text) =>
        !string.IsNullOrEmpty(text) && (text.Contains(Marker) || names.Any(text.Contains));

    // The message's first line, plus the mod's first stack frame when only the stack names the mod (an exception thrown in its
    // starter), so the summary shows where.
    private static string Line(string condition, string stackTrace)
    {
        string line = (condition ?? "").Split('\n')[0].Trim();
        if (Names(condition)) return line;
        string frame = (stackTrace ?? "").Split('\n').Select(l => l.Trim()).FirstOrDefault(Names);
        return frame == null ? line : $"{line} (at {frame})";
    }

    // From RunReport's threaded log hook, for every error, exception and assert.
    internal static void Record(string condition, string stackTrace)
    {
        if (Marker == null) return;
        bool mod = Names(condition) || Names(stackTrace);
        lock (Sync)
        {
            if (loading)
            {
                if (mod && startup.Count < StartupKept) startup.Add(Line(condition, stackTrace));
                return;
            }
            loggedDuring++;
            if (mod) during++;
        }
    }

    // The game reached the main menu (or the run ended first): errors from now on are the run's.
    internal static void EndStartup()
    {
        lock (Sync) loading = false;
    }

    public static bool Fails => FailOnModErrors && (During > 0 || Startup.Count > 0);
}

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
