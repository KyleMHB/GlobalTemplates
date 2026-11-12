using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using RimWorld;
using Verse;
using Verse.AI;

namespace RimWorldDevTests;

public class SetupException : Exception
{
    public SetupException(string message) : base(message) { }
}

// Shared developer setup through the game's own god-mode build path. Shared across mods;
// every action is disclosed through the caller's setup log.
public static class Kit
{
    private static readonly AccessTools.FieldRef<Designator_Place, Rot4> placingRot = AccessTools.FieldRefAccess<Designator_Place, Rot4>("placingRot");

    public static ThingDef Def(string name) => DefDatabase<ThingDef>.GetNamed(name);
    public static ThingDef DefOrNull(string name) => DefDatabase<ThingDef>.GetNamedSilentFail(name);
    public static bool Near(float a, float b, float tolerance) => Math.Abs(a - b) <= tolerance;

    // Setup preconditions checked before a case measures anything. Returns true when every one held; otherwise records the case
    // as a setup failure naming what didn't hold, so a broken setup never shows up as a wrong value.
    public static bool Require(BatchContext ctx, string id, params (bool held, string what)[] preconditions)
    {
        var failed = preconditions.Where(p => !p.held).Select(p => p.what).ToList();
        if (failed.Count == 0) return true;
        ctx.Begin(id).SetupFailed("setup precondition not met: " + string.Join("; ", failed));
        return false;
    }

    public static void SkipRemaining(BatchContext ctx, Batch batch, string reason, string category)
    {
        foreach (var p in batch.Plan.Where(p => ctx.ResultOf(p.Id) == null)) ctx.Begin(p.Id).Skip(reason, category);
    }

    // ---- Research ----------------------------------------------------------------------------------------------------------
    // Research granted as setup is re-completed if another mod un-researches it (seen with a research-altering mod, 2026-11-08).
    private static readonly HashSet<ResearchProjectDef> granted = new(), regranted = new();

    public static void Research(BatchContext ctx, params string[] names)
    {
        foreach (var name in names)
        {
            var project = DefDatabase<ResearchProjectDef>.GetNamedSilentFail(name);
            if (project == null) { ctx.Setup("Research not loaded, not completed: " + name); continue; }
            granted.Add(project);
            if (project.IsFinished) continue;
            Find.ResearchManager.FinishProject(project, doCompletionDialog: false, doCompletionLetter: false);
            ctx.Setup("Developer research completed: " + name);
        }
    }

    public static void KeepResearch(BatchContext ctx)
    {
        if (granted.Count == 0 || ctx == null || Current.Game == null) return;
        foreach (var project in granted)
        {
            if (project.IsFinished) continue;
            try { Find.ResearchManager.FinishProject(project, doCompletionDialog: false, doCompletionLetter: false); }
            catch (Exception e) { if (regranted.Add(project)) ctx.Setup($"Developer could not re-complete research {project.defName}: {e.Message}"); continue; }
            if (regranted.Add(project)) ctx.Setup($"Developer re-completed research {project.defName} after something else un-researched it");
        }
    }

    internal static void ClearResearchGuard() { granted.Clear(); regranted.Clear(); }

    // ---- Power ------------------------------------------------------------------------------------------------------------
    // A refrigerated container has no power net in these batches. Its CompPowerTrader.PowerOn is held at the requested value each
    // tick and disclosed; this exercises the mod's response to power, not vanilla power networks.
    private static readonly Dictionary<CompPowerTrader, bool> powerHolds = new();

    public static void HoldPower(BatchContext ctx, Thing thing, bool on)
    {
        var power = thing.TryGetComp<CompPowerTrader>() ?? throw new SetupException(thing.def.defName + " has no CompPowerTrader");
        powerHolds[power] = on;
        power.PowerOn = on;
        ctx.Setup($"Developer holds {thing.def.defName} {thing.ThingID} PowerOn={on} each tick (no power net)");
    }

    internal static void ApplyPowerHolds()
    {
        foreach (var hold in powerHolds)
            if (hold.Key.parent is { Spawned: true } && hold.Key.PowerOn != hold.Value) hold.Key.PowerOn = hold.Value;
    }

    internal static void ClearPowerHolds() => powerHolds.Clear();

    // ---- Layout -----------------------------------------------------------------------------------------------------------
    // Finds the first clear, open-sky, buildable rectangle nearest the map centre (seed-stable), clears plants and loose things,
    // and discloses what went.
    public static CellRect Area(BatchContext ctx, int width, int height)
    {
        var map = ctx.Map;
        float radius = Math.Min(GenRadial.MaxRadialPatternRadius - 1f, Math.Max(30f, Math.Max(map.Size.x, map.Size.z) / 2f));
        foreach (var loose in new[] { false, true })
            foreach (var anchor in GenRadial.RadialCellsAround(map.Center, radius, true))
            {
                var rect = new CellRect(anchor.x, anchor.z, width, height);
                if (!rect.Cells.All(c => Clear(map, c, loose))) continue;
                var plants = rect.Cells.SelectMany(c => c.GetThingList(map)).OfType<Plant>().Distinct().ToList();
                foreach (var plant in plants) plant.Destroy();
                var items = rect.Cells.SelectMany(c => c.GetThingList(map)).Where(t => t.def.category is ThingCategory.Item or ThingCategory.Filth).Distinct().ToList();
                string labels = string.Join(", ", items.GroupBy(t => t.def.defName).Select(g => g.Sum(t => t.stackCount) + " " + g.Key));
                foreach (var t in items) t.Destroy();
                ctx.Setup($"Layout area {rect}; {plants.Count} plants removed" + (items.Count > 0 ? "; developer cleared loose things: " + labels : ""));
                TestCamera.Area(map, rect);
                return rect;
            }
        throw new SetupException($"no clear {width}x{height} area near the map centre");
    }

    private static bool Clear(Map map, IntVec3 c, bool allowLoose) =>
        c.InBounds(map) && !c.Fogged(map) && !c.Roofed(map) && c.GetEdifice(map) == null && c.GetFirstPawn(map) == null &&
        (allowLoose ? c.GetThingList(map).All(t => t.def.category is ThingCategory.Item or ThingCategory.Filth or ThingCategory.Plant) : c.GetFirstItem(map) == null) &&
        map.terrainGrid.TerrainAt(c).affordances.Contains(TerrainAffordanceDefOf.Heavy) &&
        !c.GetThingList(map).Any(t => t.def.category == ThingCategory.Building);

    // Steel walls around an outer rectangle, an optional door and a constructed roof over the interior.
    public static Room Room(BatchContext ctx, CellRect outer, IntVec3? door = null)
    {
        var map = ctx.Map;
        int walls = 0;
        foreach (var cell in outer.EdgeCells)
        {
            if (door.HasValue && cell == door.Value) continue;
            Place(ctx, ThingDefOf.Wall, cell, Rot4.North, ThingDefOf.Steel, quiet: true);
            walls++;
        }
        if (door.HasValue) Place(ctx, ThingDefOf.Door, door.Value, Rot4.North, ThingDefOf.Steel, quiet: true);
        foreach (var cell in outer.ContractedBy(1).Cells) map.roofGrid.SetRoof(cell, RoofDefOf.RoofConstructed);
        ctx.Setup($"God-mode placed {walls} steel walls around {outer}{(door.HasValue ? " with a door at " + door.Value : "")}; developer constructed roof over the interior");
        return outer.ContractedBy(1).CenterCell.GetRoom(map);
    }

    public static Thing Place(BatchContext ctx, string def, IntVec3 cell, Rot4? rot = null, ThingDef stuff = null) =>
        Place(ctx, Def(def), cell, rot ?? Rot4.North, stuff);

    public static Thing Place(BatchContext ctx, ThingDef def, IntVec3 cell, Rot4 rot, ThingDef stuff, bool quiet = false)
    {
        var map = ctx.Map;
        if (def.MadeFromStuff && stuff == null) stuff = GenStuff.DefaultStuffFor(def);
        if (!def.MadeFromStuff) stuff = null;
        var footprint = GenAdj.OccupiedRect(cell, rot, def.Size);
        var occupied = footprint.Cells.SelectMany(c => c.GetThingList(map)).Where(t => t.def.category is ThingCategory.Building or ThingCategory.Item or ThingCategory.Pawn).ToList();
        if (occupied.Count > 0) throw new SetupException($"footprint of {def.defName} at {cell} is occupied by {string.Join(", ", occupied.Select(t => t.LabelShort))}");
        bool godMode = DebugSettings.godMode;
        Thing placed;
        try
        {
            DebugSettings.godMode = true;
            var designator = new Designator_Build(def);
            if (stuff != null) designator.SetStuffDef(stuff);
            placingRot(designator) = rot;
            var accepted = designator.CanDesignateCell(cell);
            if (!accepted.Accepted) throw new SetupException($"cannot place {def.defName} at {cell}: {accepted.Reason}");
            designator.DesignateSingleCell(cell);
            placed = footprint.Cells.SelectMany(c => c.GetThingList(map)).FirstOrDefault(t => t.def == def)
                ?? throw new SetupException($"god-mode placement of {def.defName} at {cell} produced nothing");
        }
        finally
        {
            DebugSettings.godMode = godMode;
        }
        if (placed.Stuff != stuff || placed.Rotation != rot)
            throw new SetupException($"{def.defName} placed with stuff {placed.Stuff?.defName ?? "none"} facing {placed.Rotation}, requested {stuff?.defName ?? "none"} facing {rot}");
        TestCamera.Include(map, footprint);
        if (!quiet) ctx.Setup($"God-mode placed {def.defName} ({placed.ThingID}) stuff {placed.Stuff?.defName ?? "none"} at {placed.Position} facing {placed.Rotation}, faction {placed.Faction?.Name ?? "none"}");
        return placed;
    }

    // ---- Pawns ------------------------------------------------------------------------------------------------------------
    // Removes the quickstart colonists, so no other pawn can take a bill, haul a product or deconstruct a fixture.
    public static void RemoveStartingColonists(BatchContext ctx)
    {
        var colonists = ctx.Map.mapPawns.FreeColonistsSpawned.ToList();
        foreach (var p in colonists) { p.DeSpawn(); Find.WorldPawns.PassToWorld(p); }
        ctx.Setup($"Developer despawned {colonists.Count} quickstart colonist(s) to world pawns so only test pawns act (game-over check suppressed)");
    }

    // A capable worker for one work type at priority 1, with every other work type off.
    public static Pawn Worker(BatchContext ctx, IntVec3 cell, WorkTypeDef work, SkillDef skill = null)
    {
        if (!cell.InBounds(ctx.Map) || !cell.Walkable(ctx.Map)) throw new SetupException($"pawn destination {cell} is blocked");
        for (int i = 0; i < 20; i++)
        {
            var pawn = PawnGenerator.GeneratePawn(new PawnGenerationRequest(PawnKindDefOf.Colonist, Faction.OfPlayer, forceGenerateNewPawn: true,
                canGeneratePawnRelations: false, mustBeCapableOfViolence: false, allowAddictions: false));
            if (pawn.WorkTypeIsDisabled(work) || !pawn.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation)) continue;
            GenSpawn.Spawn(pawn, cell, ctx.Map);
            TestCamera.Include(ctx.Map, pawn.OccupiedRect());
            pawn.workSettings.EnableAndInitialize();
            foreach (var w in DefDatabase<WorkTypeDef>.AllDefsListForReading)
                if (!pawn.WorkTypeIsDisabled(w)) pawn.workSettings.SetPriority(w, w == work ? 1 : 0);
            if (skill != null) pawn.skills.GetSkill(skill).Level = 10;
            if (pawn.timetable != null) for (int h = 0; h < 24; h++) pawn.timetable.SetAssignment(h, TimeAssignmentDefOf.Work);
            pawn.needs?.rest?.SetInitialLevel();
            if (pawn.needs?.rest != null) pawn.needs.rest.CurLevelPercentage = 1f;
            ctx.Setup($"Developer spawned colonist {pawn.LabelShort} at {cell}: only {work.defName} enabled (priority 1){(skill == null ? "" : $", {skill.defName} 10")}, all-work timetable, rested");
            return pawn;
        }
        throw new SetupException($"no generated colonist could do {work.defName} in 20 attempts");
    }

    public static Action All(params Action[] actions) => () => { foreach (var a in actions) a?.Invoke(); };

    // Keeps a worker rested so a long bill doesn't end in sleep. Food and joy are already topped up by the runner.
    public static Action KeepRested(Pawn pawn) => () =>
    {
        if (pawn?.needs?.rest != null && pawn.needs.rest.CurLevelPercentage < 0.5f) pawn.needs.rest.CurLevelPercentage = 1f;
    };

    // ---- Counting ---------------------------------------------------------------------------------------------------------
    // Every unit of a def on the map: spawned stacks plus what pawns carry or hold in inventory.
    public static int CountOnMap(Map map, ThingDef def)
    {
        int spawned = map.listerThings.ThingsOfDef(def).Where(t => t.Spawned).Sum(t => t.stackCount);
        int held = map.mapPawns.AllPawnsSpawned.Sum(p =>
            (p.carryTracker?.CarriedThing?.def == def ? p.carryTracker.CarriedThing.stackCount : 0) +
            (p.inventory?.innerContainer?.Where(t => t.def == def).Sum(t => t.stackCount) ?? 0));
        return spawned + held;
    }

    public static HashSet<int> StackIds(Map map, ThingDef def) => map.listerThings.ThingsOfDef(def).Select(t => t.thingIDNumber).ToHashSet();

    public static IEnumerable<Thing> NewStacks(Map map, ThingDef def, HashSet<int> before) =>
        map.listerThings.ThingsOfDef(def).Where(t => t.Spawned && !before.Contains(t.thingIDNumber));
}
