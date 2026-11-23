using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using HarmonyLib;
using RimWorld;
using RimWorld.Planet;
using Verse;

namespace RimWorldDevTests;

// Starts a colony the way a player does: New colony on the main menu, then every page the scenario asks for, each left
// through the code behind its own Next button. The quickstart builds the game in code and opens none of these pages, so
// a mod that breaks world generation settings, site selection, the ideoligion choice or the colonist page is only seen here.
// The runner makes the choices a player must make (difficulty, seed, landing site) and leaves everything else at the
// page's defaults. A page a mod adds is left through its Next button as it stands.
internal class NewGameFlow
{
    // The last flow this process ran, for the batch that reports on it.
    public static NewGameFlow Last { get; private set; }

    // A page gets this many frames on screen before Next, so code that runs while it draws has run.
    private const int DrawnFrames = 10;
    private static readonly TimeSpan PageLimit = TimeSpan.FromMinutes(1);

    public readonly List<string> Pages = new();
    public readonly List<string> Confirmed = new();
    public readonly long ErrorMark = CaseErrors.Mark, ModErrorMark = CaseErrors.ModMark;
    public string SeedString { get; }
    public PlanetTile Tile { get; private set; } = PlanetTile.Invalid;
    public float PlanetCoverage { get; private set; }
    public string Error { get; private set; }
    public double Seconds => clock.Elapsed.TotalSeconds;

    private readonly string identity, batchId;
    private readonly int seed, mapSize;
    private readonly Stopwatch clock = Stopwatch.StartNew(), idle = Stopwatch.StartNew();
    private Page current;
    private int shown;
    private bool clicked;

    public NewGameFlow(string identity, string batchId, int seed, int mapSize)
    {
        this.identity = identity;
        this.batchId = batchId;
        this.seed = seed;
        this.mapSize = mapSize;
        SeedString = Harness.Settings.ArgPrefix + "test" + seed;
        Last = this;
    }

    public string Where => current == null ? "the main menu" : current.GetType().Name;

    // The main menu's New colony button does exactly this.
    public void Begin() => Find.WindowStack.Add(new Page_SelectScenario());

    public void Frame()
    {
        if (Error != null || Current.ProgramState != ProgramState.Entry) return;
        if (LongEventHandler.AnyEventNowOrWaiting) { idle.Restart(); return; }
        // Page_SelectScenario's Next creates the game; from then on it is this run's.
        if (Current.Game != null && RunnerIdentity.Of(Current.Game) == null) RunnerIdentity.Set(Current.Game, identity);

        var box = Find.WindowStack.WindowOfType<Dialog_MessageBox>();
        if (box != null)
        {
            Confirmed.Add(box.text.ToString());
            var confirm = box.buttonAAction;
            box.Close();
            confirm?.Invoke();
            idle.Restart();
            return;
        }

        var page = Find.WindowStack.Windows.OfType<Page>().LastOrDefault();
        if (page != current && page != null)
        {
            current = page;
            shown = 0;
            clicked = false;
            Pages.Add(page.GetType().Name);
            RunTimeline.Event("new-game-page", batchId, detail: page.GetType().FullName);
            idle.Restart();
            return;
        }
        if (idle.Elapsed > PageLimit)
        {
            Error = page == null ? $"no page opened after {Where}" : $"{Where} was still open {PageLimit.TotalSeconds:0} s after Next";
            return;
        }
        if (page == null || clicked || ++shown < DrawnFrames) return;

        clicked = true;
        idle.Restart();
        // Seeded per page, so what a page generates synchronously (the starting colonists) repeats with the seed.
        Rand.PushState(Gen.HashCombineInt(seed, Pages.Count));
        try
        {
            Choose(page);
            if ((bool)Next(page, "CanDoNext").Invoke(page, null)) Next(page, "DoNext").Invoke(page, null);
            // Page_CreateWorldParams answers false and moves on itself once the world is generated.
            else if (!LongEventHandler.AnyEventNowOrWaiting) Error = $"{Where} refused Next (CanDoNext returned false)";
        }
        catch (Exception ex)
        {
            var cause = ex is System.Reflection.TargetInvocationException { InnerException: { } inner } ? inner : ex;
            Log.Error(Harness.Settings.LogPrefix + $"New game failed on {Where}: {cause}");
            Error = $"{Where} threw {cause.GetType().Name}: {cause.Message}";
        }
        finally
        {
            Rand.PopState();
        }
    }

    private static System.Reflection.MethodInfo Next(Page page, string name) =>
        AccessTools.Method(page.GetType(), name) ?? throw new MissingMethodException(page.GetType().FullName, name);

    // What a player has to pick before Next is accepted.
    private void Choose(Page page)
    {
        switch (page)
        {
            case Page_SelectScenario:
                Set(page, "curScen", ScenarioDefOf.Crashlanded.scenario);
                break;
            case Page_SelectStoryteller:
                Set(page, "storyteller", StorytellerDefOf.Cassandra);
                Set(page, "difficulty", DifficultyDefOf.Rough);
                Set(page, "difficultyValues", new Difficulty(DifficultyDefOf.Rough));
                Find.GameInitData.permadeathChosen = true;
                Find.GameInitData.permadeath = false;
                break;
            case Page_CreateWorldParams:
                Set(page, "seedString", SeedString);
                PlanetCoverage = (float)Field(page, "planetCoverage").GetValue(page);
                break;
            case Page_SelectStartingSite:
                var tile = TileFinder.RandomSettlementTileFor(Faction.OfPlayer, true, Quickstarter.Temperate);
                // The page has already picked a random valid tile; keep it when the world has no temperate one.
                if (!tile.Valid) tile = Find.GameInitData.startingTile;
                Find.WorldInterface.SelectedTile = Tile = tile;
                Find.GameInitData.mapSize = mapSize;
                break;
            case Page_ChooseIdeoPreset:
                var selection = Field(page, "presetSelection");
                selection.SetValue(page, Enum.Parse(selection.FieldType, "Classic"));
                break;
        }
    }

    private static System.Reflection.FieldInfo Field(Page page, string name) =>
        AccessTools.Field(page.GetType(), name) ?? throw new MissingFieldException(page.GetType().FullName, name);

    private static void Set(Page page, string name, object value) => Field(page, name).SetValue(page, value);
}

// The player's route into a colony, from the main menu to the first ticks on the generated map. Runs in every run-all.
public class NewGameBatch : Batch
{
    public const string BatchId = "new-game";
    public override string Id => BatchId;
    public override bool NewGamePages => true;
    // The size the starting-site page offers by default; generation steps a mod adds see a normal map.
    public override int MapSize => 250;
    public override int SegmentCount => 1;

    public override IReadOnlyList<PlannedCase> Plan { get; } = new[]
    {
        new PlannedCase("new-game.pages", Levels.PlayerWorkflow),
        new PlannedCase("new-game.world", Levels.PlayerWorkflow),
        new PlannedCase("new-game.colony", Levels.PlayerWorkflow),
        new PlannedCase("new-game.no-mod-errors", Levels.PlayerWorkflow),
    };

    public override IEnumerable<Wait> Segment(int index, BatchContext ctx)
    {
        var flow = NewGameFlow.Last;
        var map = ctx.Map;

        var pages = ctx.Begin("new-game.pages").Observe("pages", string.Join(" > ", flow.Pages)).Observe("seconds", Math.Round(flow.Seconds, 1));
        foreach (string text in flow.Confirmed) pages.Note("Confirmed a dialog: " + text.Replace('\n', ' '));
        var expected = new List<string> { nameof(Page_SelectScenario), nameof(Page_SelectStoryteller), nameof(Page_CreateWorldParams), nameof(Page_SelectStartingSite) };
        if (ModsConfig.IdeologyActive) expected.Add(nameof(Page_ChooseIdeoPreset));
        expected.Add(nameof(Page_ConfigureStartingPawns));
        int at = -1;
        foreach (string name in expected)
        {
            int found = flow.Pages.IndexOf(name, at + 1);
            if (pages.Step(found >= 0, $"{name} opened in its place")) at = found;
        }
        pages.Conclude();

        var world = ctx.Begin("new-game.world").Expect("worldSeed", flow.SeedString).Expect("tile", flow.Tile.ToString())
            .Observe("worldSeed", Find.World.info.seedString).Observe("tile", map.Tile.ToString())
            .Observe("planetCoverage", flow.PlanetCoverage).Observe("biome", map.Biome.defName).Observe("worldTiles", Find.WorldGrid.TilesCount);
        world.Step(Find.World.info.seedString == flow.SeedString, "the world was generated from the seed typed on the world page");
        world.Step(map.Tile == flow.Tile, "the colony map is on the landing site that was selected");
        world.Step(map.Parent is Settlement { Faction: { IsPlayer: true } }, "the landing site became the player's settlement");
        world.Step(Find.FactionManager.AllFactionsVisible.Any(f => !f.IsPlayer), "the world has other factions");
        world.Conclude();

        var colony = ctx.Begin("new-game.colony").Expect("colonists", 3);
        int before = Find.TickManager.TicksGame;
        yield return Wait.Ticks(120);
        // A start from the pages lands the colonists in drop pods; only the quickstart places them at once.
        var landed = Wait.Until(() => map.mapPawns.FreeColonistsSpawned.Count >= 3, 2500);
        yield return landed;
        var colonists = map.mapPawns.FreeColonistsSpawned.OrderBy(p => p.thingIDNumber).ToList();
        colony.Observe("landedAtTick", landed.TimedOut ? "never" : Find.TickManager.TicksGame);
        colony.Observe("colonists", colonists.Count).Observe("firstColonist", colonists.FirstOrDefault()?.Name?.ToStringFull)
            .Observe("mapSize", $"{map.Size.x}x{map.Size.z}").Observe("storyteller", Find.Storyteller.def.defName)
            .Observe("difficulty", Find.Storyteller.difficultyDef.defName);
        colony.Step(colonists.Count == 3, $"three colonists landed from their drop pods (saw {colonists.Count})");
        colony.Step(Find.TickManager.TicksGame - before >= 120, "the colony ran for at least 120 ticks");
        colony.Step(Find.Storyteller.def == StorytellerDefOf.Cassandra && Find.Storyteller.difficultyDef == DifficultyDefOf.Rough,
            "the storyteller and difficulty chosen on the storyteller page are in the game");
        colony.Conclude();

        long modErrors = CaseErrors.ModMark - flow.ModErrorMark;
        ctx.Begin("new-game.no-mod-errors").Expect("modErrors", 0).Observe("modErrors", modErrors).Observe("allErrors", CaseErrors.Mark - flow.ErrorMark)
            .Check(modErrors == 0, $"{modErrors} error(s) naming {Harness.Settings.ErrorMarker} were logged between New colony and the first ticks; see Player.log");
    }
}
