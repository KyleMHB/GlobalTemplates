using System.IO;
using System.Linq;
using Timberborn.Beavers;
using Timberborn.BlockObjectTools;
using Timberborn.BlockSystem;
using Timberborn.Coordinates;
using Timberborn.EntitySystem;
using Timberborn.GameDistricts;
using Timberborn.GameSaveRepositorySystem;
using Timberborn.GameSaveRuntimeSystem;
using Timberborn.GameSceneLoading;
using Timberborn.MapRepositorySystem;
using Timberborn.ResourceCountingSystem;
using Timberborn.TemplateSystem;
using Timberborn.TimeSystem;
using UnityEngine;

namespace TimberbornDevTests;

// Shared developer setup through the game's own services. Every action that changes the game is disclosed in the batch's
// setup record.
public static class Kit
{
    // ---- Fixtures (D5): every game a batch plays is runner-owned and saves only into the run folder --------------------------

    // Starts a new game on a built-in map from the main menu. Returns a refusal, or null once the load has started.
    public static string NewGame(GameSceneLoader loader, MapRepository maps, string faction, string map, string settlement)
    {
        var names = maps.GetBuiltinMapNames().OrderBy(n => n).ToList();
        if (!names.Contains(map)) return $"no built-in map {map}; built-in maps: {string.Join(", ", names)}";
        // A non-empty settlement name skips the naming prompt; the game-context runner suspends the autosaver on load.
        loader.StartNewGameInstantly(faction, MapFileReference.FromResource(map), settlement);
        return null;
    }

    // Finds a batch's fixture save: an absolute path, or a name in the request's FixtureDir, then the run folder.
    public static string FixturePath(RunRequest request, string fixture)
    {
        if (Path.IsPathRooted(fixture)) return File.Exists(fixture) ? fixture : null;
        string name = fixture.EndsWith(".timber") ? fixture : fixture + ".timber";
        foreach (var dir in new[] { request.FixtureDir, request.RunDir })
            if (!string.IsNullOrEmpty(dir) && File.Exists(Path.Combine(dir, name))) return Path.Combine(dir, name);
        return null;
    }

    // Loads a copy of the fixture from <run>/fixtures/<settlement>, so the original is never the live save. Returns a refusal,
    // or null once the load has started.
    public static string LoadFixture(GameSceneLoader loader, RunRequest request, string fixture)
    {
        string source = FixturePath(request, fixture);
        if (source == null) return $"fixture {fixture} not found in {request.FixtureDir ?? "(no fixture folder)"} or {request.RunDir}";
        string root = Path.Combine(request.RunDir, "fixtures");
        string settlement = request.SettlementName;
        string save = Path.GetFileNameWithoutExtension(source);
        Directory.CreateDirectory(Path.Combine(root, settlement));
        File.Copy(source, Path.Combine(root, settlement, save + ".timber"), true);
        loader.StartSaveGameInstantly(new SaveReference(save, new SettlementReference(settlement, root)));
        return null;
    }

    // Saves the game to <run>/saves/<settlement>/<name>.timber, for use as a fixture. Yield the returned wait; it ends once the
    // save is written, with game time stopped.
    public static SaveWait SaveFixture(BatchContext ctx, string name)
    {
        string root = Path.Combine(ctx.Request.RunDir, "saves");
        string settlement = ctx.Request.SettlementName;
        var wait = new SaveWait { Path = Path.Combine(root, settlement, name + ".timber") };
        ctx.Get<GameSaver>().QueueSaveSkippingNameValidation(new SaveReference(name, new SettlementReference(settlement, root)), () => wait.Done = true);
        ctx.Setup("Developer saved the game to " + wait.Path);
        return wait;
    }

    // ---- Buildings ---------------------------------------------------------------------------------------------------------

    // Places a building by template name as the player's build tool would, at the first spot the game's own validation
    // accepts, in rings outward from the first finished district centre. It starts unbuilt: beavers build it. Throws
    // SetupException when there is no district centre or no buildable spot.
    public static BlockObject Place(BatchContext ctx, string template, int maxRing = 12)
    {
        var spec = ctx.Get<TemplateNameMapper>().GetTemplate(template);
        var placeable = spec.GetSpec<PlaceableBlockObjectSpec>();
        var blockSpec = spec.GetSpec<BlockObjectSpec>();
        var center = ctx.Get<DistrictCenterRegistry>().FinishedDistrictCenters.FirstOrDefault()
            ?? throw new SetupException("no finished district centre to place " + template + " near");
        Vector3Int origin = center.CenterCoordinates;
        var previewPlacer = ctx.Get<PreviewPlacerFactory>().Create(placeable);
        try
        {
            for (int ring = 2; ring <= maxRing; ring++)
            for (int dx = -ring; dx <= ring; dx++)
            for (int dy = -ring; dy <= ring; dy++)
            {
                if (Mathf.Max(Mathf.Abs(dx), Mathf.Abs(dy)) != ring) continue;
                // A few levels up and down, for uneven terrain.
                foreach (int dz in new[] { 0, 1, -1, 2, -2 })
                {
                    var candidate = new Placement(origin + new Vector3Int(dx, dy, dz), Orientation.Cw0, FlipMode.Unflipped);
                    var buildable = previewPlacer.GetBuildableCoordinates(new[] { candidate }).ToList();
                    if (buildable.Count == 0) continue;
                    var at = buildable[0];
                    ctx.Get<BlockObjectPlacerService>().GetMatchingPlacer(blockSpec).Place(new EntitySetup.Builder(blockSpec.Blueprint), at);
                    var placed = ctx.Get<EntityRegistry>().Entities.Select(e => e.GetComponent<BlockObject>())
                        .FirstOrDefault(b => b != null && b.Coordinates == at.Coordinates && b.GetComponent<TemplateSpec>()?.IsNamed(template) == true)
                        ?? throw new SetupException($"{template} was placed at {at.Coordinates} but no such building is there");
                    ctx.Setup($"Developer placed {template} at {at.Coordinates}, {ring} cells from the district centre at {origin}");
                    return placed;
                }
            }
        }
        finally
        {
            previewPlacer.HideAllPreviews();
        }
        throw new SetupException($"no buildable spot for {template} within {maxRing} cells of the district centre at {origin}");
    }

    // ---- Readings ------------------------------------------------------------------------------------------------------------

    public static int Beavers(BatchContext ctx) => ctx.Get<BeaverPopulation>().NumberOfBeavers;

    // Every unit of a good the settlement holds, in stock or in transit (ResourceCount.AllStock).
    public static int Goods(BatchContext ctx, string goodId) => ctx.Get<ResourceCountingService>().GetGlobalResourceCount(goodId).AllStock;

    public static float HoursToday(BatchContext ctx) => ctx.Get<IDayNightCycle>().HoursPassedToday;
    public static bool IsDaytime(BatchContext ctx) => ctx.Get<IDayNightCycle>().IsDaytime;

    // ---- Time ----------------------------------------------------------------------------------------------------------------

    // Moves the clock forward to the next start of day or night without simulating the hours between, as the game's own
    // weather fast-forward does.
    public static void SkipTo(BatchContext ctx, TimeOfDay timeOfDay)
    {
        var cycle = ctx.Get<IDayNightCycle>();
        float hours = cycle.HoursToNextStartOf(timeOfDay);
        cycle.JumpTimeInHours(hours);
        // HoursToTicks may round a tick short of the boundary.
        if (cycle.IsDaytime != (timeOfDay == TimeOfDay.Daytime)) cycle.JumpTimeInHours(cycle.TicksToHours(1));
        ctx.Setup($"Developer moved the clock {hours:0.##} game hours forward to the start of {timeOfDay}");
    }

    // Game speed for the batch's time-advancing waits (UI speeds 1/3/7; dev speeds 30/99).
    public static void Speed(BatchContext ctx, float speed)
    {
        ctx.Speed = speed;
        ctx.Setup($"Speed set to x{speed}");
    }
}
