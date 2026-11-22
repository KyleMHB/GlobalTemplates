using System;
using System.Linq;
using Bindito.Core;
using Timberborn.GameSceneLoading;
using Timberborn.MapRepositorySystem;
using Timberborn.SingletonSystem;

namespace TimberbornDevTests;

[Context("MainMenu")]
public class MainMenuConfigurator : Configurator
{
    protected override void Configure()
    {
        if (Runner.Active) Bind<MainMenuStarter>().AsSingleton();
    }
}

// Starts the requested game from the main menu without any clicks, through the same loader the New Game panel uses.
public class MainMenuStarter : IUpdatableSingleton
{
    // MainMenuInitializer finishes through callbacks (player data, intro, welcome box); waiting a few frames lets it
    // settle before the scene is replaced.
    private const int SettleFrames = 30;
    private readonly GameSceneLoader gameSceneLoader;
    private readonly MapRepository mapRepository;
    private int frames;
    private bool started;

    public MainMenuStarter(GameSceneLoader gameSceneLoader, MapRepository mapRepository)
    {
        this.gameSceneLoader = gameSceneLoader;
        this.mapRepository = mapRepository;
    }

    public void UpdateSingleton()
    {
        if (started || RunReport.Written || ++frames < SettleFrames) return;
        started = true;
        var request = Runner.Request;
        RunReport.Data["mainMenuReachedAtSeconds"] = UnityEngine.Time.realtimeSinceStartup;
        Runner.Stage = "main-menu";
        Batch batch;
        try
        {
            if (!Batches.All.TryGetValue(request.Batch ?? "", out batch))
            {
                RunReport.Finish(RunStatus.Refused, $"unknown batch {request.Batch}; batches: {string.Join(", ", Batches.All.Keys.OrderBy(k => k))}");
                return;
            }
        }
        catch (Exception ex)
        {
            RunReport.Finish(RunStatus.Refused, "the batches could not be built: " + ex.Message);
            return;
        }
        var record = new BatchRecord { Id = batch.Id, Planned = batch.Plan.Select(p => p.Id).ToList() };
        RunReport.Batches.Add(record);
        string refusal;
        if (batch.Fixture != null)
        {
            record.Fixture = "save " + batch.Fixture;
            Runner.Stage = "loading-fixture";
            Runner.Log($"Loading fixture {batch.Fixture} for batch {batch.Id}");
            refusal = Kit.LoadFixture(gameSceneLoader, request, batch.Fixture);
        }
        else
        {
            string faction = request.Faction ?? batch.Faction, map = request.Map ?? batch.Map;
            record.Fixture = $"new game: {faction} on {map}";
            Runner.Stage = "starting-new-game";
            Runner.Log($"Starting new game: {faction} on {map} as {request.SettlementName}");
            refusal = Kit.NewGame(gameSceneLoader, mapRepository, faction, map, request.SettlementName);
        }
        if (refusal != null)
        {
            record.Status = "ended-early";
            record.Reason = refusal;
            RunReport.Finish(RunStatus.Refused, refusal);
        }
    }
}
