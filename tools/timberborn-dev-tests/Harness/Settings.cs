using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace TimberbornDevTests;

// The only thing a mod writes besides its batches: one subclass of HarnessSettings in its DevTests assembly. Harness.Settings
// finds it by reflection, so the mod can use its own namespace. A run without a mod DevTests DLL has none and runs only the
// runner's own batches.
public abstract class HarnessSettings
{
    // Shown in summaries and log lines.
    public abstract string DisplayName { get; }
    public abstract IEnumerable<Batch> CreateBatches();
    // Gameplay batches in run-all order.
    public abstract IEnumerable<string> RunAll { get; }

    // Built-in map a batch starts a new game on, unless it loads a fixture or the request names a map.
    public virtual string DefaultMap => Harness.BuiltinMap;
    public virtual string DefaultFaction => Harness.BuiltinFaction;

    // Runs on the game thread when a batch ends, however it ended. Restore any process-wide state a batch changed here.
    public virtual void OnBatchEnd() { }
}

public static class Harness
{
    public const string BuiltinMap = "_Mini", BuiltinFaction = "Folktails";
    private static bool searched;
    private static HarnessSettings settings;

    // The loaded mod's settings, or null for a run with no mod DevTests DLL.
    public static HarnessSettings Settings
    {
        get
        {
            if (!searched) { settings = Find(); searched = true; }
            return settings;
        }
    }

    private static HarnessSettings Find()
    {
        string runner = typeof(Harness).Assembly.GetName().Name;
        // Only assemblies built against the runner can hold a subclass; this also keeps other mods' broken assemblies (a
        // TypeLoadException in DeepFrontier, for one) out of the search.
        var types = AppDomain.CurrentDomain.GetAssemblies()
            .Where(a => a.GetReferencedAssemblies().Any(n => n.Name == runner))
            .SelectMany(LoadableTypes)
            .Where(t => typeof(HarnessSettings).IsAssignableFrom(t) && !t.IsAbstract).ToList();
        if (types.Count > 1)
            throw new InvalidOperationException("TimberbornDevTests needs at most one loaded HarnessSettings subclass; found " +
                string.Join(", ", types.Select(t => t.FullName)));
        return types.Count == 0 ? null : (HarnessSettings)Activator.CreateInstance(types[0]);
    }

    private static IEnumerable<Type> LoadableTypes(Assembly assembly)
    {
        try { return assembly.GetTypes(); }
        catch (ReflectionTypeLoadException ex) { return ex.Types.Where(t => t != null); }
    }
}

// Batches by id: the runner's own plus the mod's. Built once, before any game starts, so the main menu can read the
// requested batch's fixture.
public static class Batches
{
    private static Dictionary<string, Batch> all;

    public static Dictionary<string, Batch> All => all ??= Create();

    private static Dictionary<string, Batch> Create()
    {
        var batches = new Batch[] { new SmokeBatch(), new DiagnosticBatch() }.Concat(Harness.Settings?.CreateBatches() ?? Enumerable.Empty<Batch>());
        var result = new Dictionary<string, Batch>();
        foreach (var batch in batches)
        {
            if (result.ContainsKey(batch.Id)) throw new InvalidOperationException("two batches have the id " + batch.Id);
            result.Add(batch.Id, batch);
        }
        return result;
    }
}
