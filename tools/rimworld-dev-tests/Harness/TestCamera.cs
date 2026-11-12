using System;
using System.Collections.Generic;
using Verse;

namespace RimWorldDevTests;

// Setup helpers own the bounds, so new cases need no camera metadata. Map ids survive runner reloads;
// selecting another layout replaces its bounds instead of keeping every earlier test area in view.
public static class TestCamera
{
    private static readonly Dictionary<int, CellRect> areas = new();
    private static bool enabled;

    public static void Reset(bool enable)
    {
        enabled = enable;
        areas.Clear();
    }

    public static void Area(Map map, CellRect rect)
    {
        if (!enabled || !RunnerIdentity.Owned(Current.Game)) return;
        areas[map.uniqueID] = rect;
    }

    public static void Include(Map map, CellRect rect)
    {
        if (!enabled || !RunnerIdentity.Owned(Current.Game)) return;
        if (areas.TryGetValue(map.uniqueID, out var existing))
            rect = CellRect.FromLimits(Math.Min(existing.minX, rect.minX), Math.Min(existing.minZ, rect.minZ),
                Math.Max(existing.maxX, rect.maxX), Math.Max(existing.maxZ, rect.maxZ));
        areas[map.uniqueID] = rect;
    }

    public static void Frame()
    {
        if (!enabled || !TestRunner.Running || Current.ProgramState != ProgramState.Playing ||
            !RunnerIdentity.Owned(Current.Game) || Find.CurrentMap == null || Find.Camera == null) return;
        if (!areas.TryGetValue(Find.CurrentMap.uniqueID, out var rect)) return;
        // Centre the test in the unobstructed left viewport and fit both axes there.
        float reserved = TestPresentation.ReservedWidthFraction;
        float aspect = Find.Camera.aspect;
        float size = Math.Max(rect.Height / 2f + 2f, (rect.Width / 2f + 2f) / (aspect * (1f - reserved)));
        var centre = rect.CenterVector3 + Find.Camera.transform.right * (size * aspect * reserved);
        Find.CameraDriver.SetRootPosAndSize(centre, size);
    }
}
