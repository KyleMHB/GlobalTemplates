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
        // Fixture saves (Mode "load") arrive with the case API's Kit (T4).
        if (request.Mode != "new")
        {
            RunReport.Finish(RunStatus.Refused, $"request mode '{request.Mode}' is not supported by this runner build");
            return;
        }
        var maps = mapRepository.GetBuiltinMapNames().OrderBy(n => n).ToList();
        if (!maps.Contains(request.Map))
        {
            RunReport.Finish(RunStatus.Refused, $"no built-in map {request.Map}; built-in maps: {string.Join(", ", maps)}");
            return;
        }
        Runner.Stage = "starting-new-game";
        Runner.Log($"Starting new game: {request.Faction} on {request.Map} as {request.SettlementName}");
        // A non-empty settlement name skips the naming prompt; the game-context runner suspends the autosaver on load, so
        // the settlement's folder in the player's Saves is never written.
        gameSceneLoader.StartNewGameInstantly(request.Faction, MapFileReference.FromResource(request.Map), request.SettlementName);
    }
}
