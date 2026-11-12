using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;

namespace RimWorldDevTests;

public static class RunTimeline
{
    private static string path;
    public static void Configure(string dir) => path = Path.Combine(dir, "events.jsonl");
    public static void Event(string kind, string batch = null, string id = null, string detail = null)
    {
        if (path == null) return;
        File.AppendAllText(path, JsonSerializer.Serialize(new
        {
            kind, batch, id, detail, utc = DateTime.UtcNow.ToString("o"),
            monotonicSeconds = Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency,
        }) + "\n");
    }
}
