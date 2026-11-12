using LudeonTK;
using Verse;

namespace RimWorldDevTests;

// Dev mode opens the Debug log window on any logged error, including at startup, and it stays open over recordings.
// While a test run is active it is closed and kept from reopening. Errors still reach Player.log and the run report.
internal static class DebugLogHider
{
    public static void Frame()
    {
        if (TestRunner.Running && Find.WindowStack?.WindowOfType<EditWindow_Log>() is { } log) log.Close(false);
    }

    // Prefix on the log's auto-open methods.
    public static bool AllowOpen() => !TestRunner.Running;
}
