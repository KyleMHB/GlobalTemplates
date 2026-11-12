using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace RimWorldDevTests;

// Hash of the installed mod's runtime files (HarnessSettings.RuntimeFolders/RuntimeFiles), excluding PDBs and this DLL.
// rimtest.py computes the same hash from devtests.json, so a loaded build can be matched to the working tree.
internal static class RuntimeManifest
{
    // The mod's root folder. The production DLL may sit in a load folder (v1.6/Assemblies), so its grandparent is not always the root.
    public static string Root =>
        Verse.LoadedModManager.RunningModsListForReading.FirstOrDefault(m => string.Equals(m.PackageId, Harness.Settings.PackageId, StringComparison.OrdinalIgnoreCase))?.RootDir
        ?? Path.GetDirectoryName(Path.GetDirectoryName(Harness.Settings.ProductionDllPath));

    public static string Hash()
    {
        var s = Harness.Settings;
        var files = s.RuntimeFolders.Select(d => Path.Combine(Root, d)).Where(Directory.Exists)
            .SelectMany(d => Directory.GetFiles(d, "*", SearchOption.AllDirectories))
            .Concat(s.RuntimeFiles.Select(p => Path.Combine(Root, p)).Where(File.Exists))
            .Where(p => !p.EndsWith(".pdb", StringComparison.OrdinalIgnoreCase) && Path.GetFileName(p) != s.DevDllName && Path.GetFileName(p) != "RimWorldDevTests.dll" && !s.ExtraRuntimeExclusions.Contains(Path.GetFileName(p)))
            .Select(p => (name: Path.GetRelativePath(Root, p).Replace('\\', '/').ToLowerInvariant(), path: p))
            .OrderBy(p => p.name, StringComparer.Ordinal);
        var text = new StringBuilder();
        foreach (var p in files) text.Append(p.name).Append('\0').Append(Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p.path))).ToLowerInvariant()).Append('\n');
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text.ToString()))).ToLowerInvariant();
    }
}
