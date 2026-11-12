using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace RimWorldDevTests;

// The only thing a mod writes besides its batches: one subclass of HarnessSettings in its DevTests assembly.
// Harness.Settings finds it by reflection, so the mod can use its own namespace. These must match the mod's devtests.json
// for the shared launcher (rimtest.py): ArgPrefix (argPrefix), EvidenceFolder (evidenceFolder), RuntimeFolders
// (runtimeFolders), RuntimeFiles (runtimeFiles) and ExtraRuntimeExclusions (runtimeExclusions). The launcher names a
// runtime entry that disagrees after a run.
public abstract class HarnessSettings
{
    // Shown in summaries, the progress panel, messages and the developer-menu category.
    public abstract string DisplayName { get; }
    // Launch arguments become -<prefix>Test, -<prefix>Seed, -<prefix>RunId, -<prefix>Session, -<prefix>KeepOpen.
    public abstract string ArgPrefix { get; }
    // packageId of the mod under test, lowercase as RimWorld reports it.
    public abstract string PackageId { get; }
    // Any type from the production assembly, so the harness can hash it and find the installed mod folder.
    public abstract Type ProductionType { get; }
    public abstract IEnumerable<Batch> CreateBatches();
    // Gameplay batches in run-all order. The diagnostic self-check is always run first.
    public abstract IEnumerable<string> RunAll { get; }

    public virtual string LogPrefix => $"[{DisplayName} tests] ";
    public virtual string IdentityPrefix => ArgPrefix.ToUpperInvariant() + "Test-";
    public virtual string ScribeKey => ArgPrefix + "TestRunId";
    public virtual string EvidenceFolder => new string(DisplayName.Where(char.IsLetterOrDigit).ToArray()) + "Tests";
    public virtual string HarmonyId => PackageId + ".devtests";
    public virtual string ColonyName => DisplayName + " Test Colony";
    // Not read: the developer-menu category is fixed at compile time ("Developer tests"). Kept so existing overrides compile.
    public virtual string MenuCategory => DisplayName + " tests";
    // Errors containing this text count as the mod's own: startup-check batches read them, and every run reports how many
    // were logged. A short or common name matches unrelated errors; override it with something distinctive.
    public virtual string ErrorMarker => DisplayName;
    // When true, a run that logged any error containing ErrorMarker does not pass overall, even if every case passed.
    public virtual bool FailOnModErrors => false;
    // Folders and files deployment copies; the launcher hashes the same set. Missing entries are ignored.
    public virtual string[] RuntimeFolders => new[] { "About", "Assemblies", "Defs", "Patches", "Languages", "Textures", "Sounds" };
    public virtual string[] RuntimeFiles => new[] { "LoadFolders.xml" };
    public virtual int DefaultMapSize => 75;

    // Hooks. Each runs on the game thread.
    public virtual void BeforeTick() { }
    public virtual void MaintainSetup(BatchContext context) { }
    public virtual void OnFrame() { }
    public virtual void OnRunEnd(string status) { }
    public virtual string[] ExtraRuntimeExclusions => Array.Empty<string>();
    public virtual void OnBatchEnd() { }
    public virtual void AddEnvironment(Dictionary<string, object> environment) { }
    public virtual string ShortCaseName(string caseId, string batchId) => null;

    public string DevDllPath => GetType().Assembly.Location;
    public string DevDllName => System.IO.Path.GetFileName(DevDllPath);
    public string ProductionDllPath => ProductionType.Assembly.Location;
}

public static class Harness
{
    private static HarnessSettings settings;

    public static HarnessSettings Settings => settings ??= Find();

    private static HarnessSettings Find()
    {
        var types = Verse.GenTypes.AllTypes
            .Where(t => typeof(HarnessSettings).IsAssignableFrom(t) && !t.IsAbstract).ToList();
        if (types.Count != 1)
            throw new InvalidOperationException($"RimWorldDevTests needs exactly one loaded HarnessSettings subclass; found {types.Count}" +
                (types.Count > 1 ? " (" + string.Join(", ", types.Select(t => t.FullName)) + "); another mod's developer DLLs are still installed, remove them with its remove-dev command" : ""));
        return (HarnessSettings)Activator.CreateInstance(types[0]);
    }
}

// Batches and their order: the shared diagnostics plus the mod's own.
public static class Batches
{
    public static readonly Dictionary<string, Batch> All = Create();

    // Repeated commands in one process must not reuse a previous run's fixtures.
    public static void ResetForRun()
    {
        All.Clear();
        foreach (var entry in Create()) All.Add(entry.Key, entry.Value);
    }

    private static Dictionary<string, Batch> Create() =>
        new Batch[] { new DiagnosticBatch(), new DiagnosticAutosaveBatch(), new DiagnosticCancelBatch(), new DiagnosticStallBatch() }
            .Concat(Harness.Settings.CreateBatches()).ToDictionary(b => b.Id);

    public static IEnumerable<string> RunAll => new[] { "diagnostic" }.Concat(Harness.Settings.RunAll);
}
