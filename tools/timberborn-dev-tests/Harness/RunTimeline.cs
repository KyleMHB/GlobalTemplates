using System;
using System.Diagnostics;
using System.IO;
using Newtonsoft.Json;

namespace TimberbornDevTests;

// <run>/events.jsonl, one line per run, batch and case milestone. `tbtest.py timings` reads the batch and monotonicSeconds keys.
public static class RunTimeline
{
    private static string path;

    internal static void Configure(string dir) => path = Path.Combine(dir, "events.jsonl");

    public static void Event(string kind, string batch = null, string id = null, string detail = null)
    {
        if (path == null) return;
        try
        {
            File.AppendAllText(path, JsonConvert.SerializeObject(new
            {
                kind, batch, id, detail, utc = DateTime.UtcNow.ToString("o"),
                monotonicSeconds = Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency,
            }) + "\n");
        }
        // The timeline is evidence only; a locked file must not stop the run.
        catch (IOException) { }
    }
}
