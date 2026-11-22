using Bindito.Core;
using Timberborn.Autosaving;
using Timberborn.Beavers;
using Timberborn.SingletonSystem;
using Timberborn.TimeSystem;
using Timberborn.UILayoutSystem;
using UnityEngine;

namespace TimberbornDevTests;

[Context("Game")]
public class GameConfigurator : Configurator
{
    protected override void Configure()
    {
        if (Runner.Active) Bind<GameRunner>().AsSingleton();
    }
}

// Waits for the game to be ready, then runs the requested batch. The only batch so far is the runner's own "smoke" check;
// the case API (T4) replaces RunSmoke with its batch registry.
public class GameRunner : ILoadableSingleton, IUpdatableSingleton
{
    public const string SmokeBatch = "smoke", SmokeCase = "smoke.new-game";
    private enum Step { WaitForUi, Settle, Running, Done }

    private readonly EventBus eventBus;
    private readonly Autosaver autosaver;
    private readonly SpeedManager speedManager;
    private readonly IDayNightCycle dayNightCycle;
    private readonly BeaverPopulation beaverPopulation;

    private Step step = Step.WaitForUi;
    private int settleFrames;
    private float startDay, startRealtime;
    private int beaversAtStart;
    // Whether game time kept advancing while the window was in the background at some point (SPEC open risk).
    private bool wasUnfocused;

    public GameRunner(EventBus eventBus, Autosaver autosaver, SpeedManager speedManager, IDayNightCycle dayNightCycle,
        BeaverPopulation beaverPopulation)
    {
        this.eventBus = eventBus;
        this.autosaver = autosaver;
        this.speedManager = speedManager;
        this.dayNightCycle = dayNightCycle;
        this.beaverPopulation = beaverPopulation;
    }

    public void Load()
    {
        // A new game's settlement points at the player's Documents/Timberborn/Saves; suspending stops both the periodic
        // autosave and the save on quit (AutosaverUnityAdapter.OnApplicationQuit).
        autosaver.Suspend();
        eventBus.Register(this);
        Runner.Stage = "game-loading";
        RunReport.Data["gameSceneLoadedAtSeconds"] = Time.realtimeSinceStartup;
        Runner.Log("Game scene loading; autosaver suspended.");
    }

    // Posted last by GameInitializer, after the starting beavers spawn and the speed is set to 1, for new games and loads.
    [OnEvent]
    public void OnShowPrimaryUI(ShowPrimaryUIEvent _)
    {
        if (step == Step.WaitForUi) step = Step.Settle;
    }

    public void UpdateSingleton()
    {
        if (RunReport.Written) return;
        switch (step)
        {
            case Step.Settle:
                if (++settleFrames < 5) return;
                RunReport.Data["gameReadyAtSeconds"] = Time.realtimeSinceStartup;
                if (Runner.Request.Batch != SmokeBatch)
                {
                    step = Step.Done;
                    RunReport.Finish(RunStatus.Refused, $"unknown batch {Runner.Request.Batch}; this runner build only has {SmokeBatch}");
                    return;
                }
                beaversAtStart = beaverPopulation.NumberOfBeavers;
                startDay = dayNightCycle.PartialDayNumber;
                startRealtime = Time.realtimeSinceStartup;
                speedManager.ChangeSpeed(Runner.Request.Speed);
                Runner.Stage = "running";
                step = Step.Running;
                break;
            case Step.Running:
                RunSmoke();
                break;
        }
    }

    // Passes when a new game starts with beavers and game time advances at the requested speed without exceptions, which
    // proves the launch, the main-menu start and the in-game hooks work, and whether ticks run while the window is unfocused.
    private void RunSmoke()
    {
        if (!Application.isFocused) wasUnfocused = true;
        float hours = (dayNightCycle.PartialDayNumber - startDay) * 24f;
        if (hours < Runner.Request.GameHours) return;
        step = Step.Done;
        speedManager.ChangeSpeed(0f);
        float wall = Time.realtimeSinceStartup - startRealtime;
        var observed = new
        {
            gameHours = hours,
            wallSeconds = wall,
            requestedSpeed = Runner.Request.Speed,
            beaversAtStart,
            beaversAtEnd = beaverPopulation.NumberOfBeavers,
            wasUnfocused,
            exceptions = RunReport.ExceptionCount,
        };
        string reason = beaversAtStart == 0 ? "the new game started without beavers"
            : RunReport.ExceptionCount > 0 ? $"{RunReport.ExceptionCount} exception(s) logged; see report errors"
            : null;
        RunReport.Cases.Add(new CaseRecord
        {
            Id = SmokeCase, Batch = SmokeBatch, Result = reason == null ? Results.Pass : Results.Fail, Reason = reason, Observed = observed,
        });
        RunReport.Finish(RunStatus.Complete);
    }
}
