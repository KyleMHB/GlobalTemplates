# Vanilla facts used by test triage

Verified 2026-11-06 to 2026-11-09 against RimWorld 1.7.5000 rev1275 by reading `Assembly-CSharp.dll`, `Waylith.dll` and `UnityStubs.dll` IL and the shipped XML. Recheck against another game build before relying on a fact. Any IL reader works, such as ILSpy or `dotnet-ildasm`.

## Unfocused and minimized windows

Waylith, the 1.7 engine, does not use Unity's player loop. `Waylith.EngineApplication.RunFrame` skips the entire frame, game update included, and calls `Glfw.WaitEventsTimeout(0.1)` whenever the window is unfocused, unless `Waylith.EngineWindow.RunInBackground` is true (or the `HideWindow` option is set). On regaining focus it logs `[Vulkan] Focus regained after N s idle` in Player.log.

`UnityEngine.Application.runInBackground` reads and writes that same static through `Waylith.UnityCompat.UnityAppState`. `Verse.PrefsData.Apply` sets it from the player's "Run in background" option. To keep a tool-launched process running, set `Application.runInBackground = true` directly rather than changing `Prefs`, and reassert it, since `PrefsData.Apply` can reset it. The runner does this every frame for launcher-started processes (`Harness/RunnerSession.cs`).

Minimized is a separate path: frames, `OnUpdate` and mod per-frame hooks still run, but rendering is skipped (`Rendering resumed after N s minimized`), and a quickstart's map-generation long event made no progress until the window was restored.

## Stats

- **Gear offsets:** `RimWorld.StatWorker.StatOffsetFromGear` runs the stat's `parts` through `TransformValue`. Core `Defs/Stats/Stats_Basics_Special.xml`, `PsychicSensitivityOffset`, supplies `StatPart_Quality`: Normal x0.83, Good x1.0, Legendary x1.5. These are the stat's configured factors, not `StatPart_Quality` constructor defaults.
- **Neural heat:** Core `Defs/Stats/Stats_Pawns_General.xml`, `PsychicEntropyRecoveryRate`, has `StatPart_Pain` with factor 3. `StatPart_Pain.PainFactor` returns 1 + pain x factor, so the multiplier is 1 + 3 x pain.
- **Clamped stats:** Core `Defs/Stats/Stats_Pawns_WorkGeneral.xml` sets `PlantWorkSpeed.minValue` to 0.1. Ideology `Defs/StatDefs/Stats_Pawns_Social.xml` sets `SlaveSuppressionFallRate.minValue` to 0 and, with Biotech, applies a biological-age offset curve (3, -0.5), (13, -0.3), (16, 0). `StatWorker_SuppressionFallRate.GetValueUnfinalized` and `CurrentFallRateBasedOnSuppression` supply base rates 0.05, 0.1 or 0.2. The negative age offset can therefore clamp a young slave's reading to zero, but a sufficiently old adolescent can have a positive reading. Use an adult subject for offset-ratio measurements.
- **Item wealth sum:** `RimWorld.WealthWatcher.CalculateWealthItems` (private) gathers `ThingRequestGroup` 3 recursively through `WealthItemsFilter`, skips things not `SpawnedOrAnyParentSpawned` or on fogged `PositionHeld` cells, and adds `MarketValue * stackCount`. It contains exactly one `Thing.get_MarketValue` call, so a single-call transpiler can reweight item wealth without touching market value elsewhere.

## Content loading

- **Load-folder shadowing:** `Verse.DirectXmlLoader.XmlAssetsInModFolder` computes a path relative to each selected content folder and calls `Dictionary.TryAdd`. For matching relative Defs paths across load folders, the first file wins, rather than merging both files.

## Pawns, beds and rooms

- **In bed:** `RimWorld.RestUtility.InBed(Pawn)` calls `CurrentBed(Pawn)`, which calls `CurrentBed(Pawn, out int?)`. That overload returns null unless the pawn is spawned, has a current job and `GetPosture().InBed()`; otherwise it returns the first `Building_Bed` on the pawn's cell whose sleeping slot holds the pawn. A pawn standing on its bed cell (for example in `Wait`) is not in bed. Patch the two-argument overload to change every caller.
- **Bed head:** `RimWorld.BedUtility.GetSlotPos` puts sleeping slots (the head) on the occupied rect's minZ row for a north-facing bed, minX for east, maxZ for south and maxX for west. The head is the end opposite the facing.
- **Prison-cell state:** `Verse.Room.Notify_RoomShapeChanged` recomputes `isPrisonCell` and sets every bed in a prison cell `ForPrisoners`. `Building_Bed.SpawnSetup` sets a newly spawned bed for prisoners when its room is a prison cell. Refresh the room after marking its bed, and keep colonist and prisoner wards separate.
- **Prisoner escape:** `RimWorld.JobGiver_PrisonerEscape.ShouldStartEscaping` checks prisoner eligibility and district escape paths; a district touching the map edge qualifies. The think tree's `Pawn_GuestTracker.ShouldWaitInsteadOfEscaping` gate suppresses escape while `TicksGame < ticksWhenAllowedToEscapeAgain`, with a held map and a spawned free colonist. Merely placing a prisoner outdoors does not make it stay there.
- **Ceremony cleanup:** `Verse.AI.Group.Lord.Cleanup` calls `LordJob.Cleanup`, cleans up toils, ends eligible pawns' current jobs (with `startNewJob`), then calls `LordJob.PostCleanup`. `RitualBehaviorWorker_Trial.Cleanup` calls `Pawn_GuestTracker.WaitInsteadOfEscapingFor`; Conversion, Execution and PrisonerSacrifice call it in `PostCleanup`. A pawn can choose a job before a PostCleanup escape grace is applied.
- **Target-unreachable fail trigger:** `RimWorld.StageFailTrigger_TargetPawnUnreachable.Failed` calls `ReachabilityUtility.CanReach(PawnWithRole(takerId), PawnWithRole(takeeId), Touch, Deadly)` with no null check, so it throws a NullReferenceException on every lord tick while the taker role is empty.
- **Meditation:** `RimWorld.JobDriver_Meditate.MeditationTick` calls `JoyUtility.JoyTickCheckEnd` with `GoToNextToil`; full joy advances the meditation job out of its meditation toil. Holding psyfocus alone does not keep a pawn meditating.
- **Apparel optimizer storage gate:** `RimWorld.JobGiver_OptimizeApparel.TryGiveJob` returns null while `TicksGame < mindState.nextApparelOptimizeTick`; `Pawn_MindState.Notify_OutfitChanged` sets that tick to now. Among map apparel it only considers things the policy filter allows that are `StoreUtility.IsInAnyStorage`, not forbidden and not burning. Apparel loose on the ground is never picked, even by a naked pawn, so put test apparel in a stockpile. Observed in game as well as in IL.

## Buildings

- **Cooler sides:** `RimWorld.Building_Cooler.TickRare` cools the room at `Position + IntVec3.South.RotatedBy(Rotation)` and pushes heat to the `North` side. A cooler cools the side opposite its facing: in a room's south wall it faces south.

## Languages

Verified 2026-11-22 against RimWorld 1.7.5014 rev1195 by decompiling `Verse.LanguageDatabase`, `Verse.LoadedLanguage`, `Verse.Prefs` and `RimWorld.IO.TarDirectory`. Vanilla languages other than English ship as `Data/Core/Languages/<Name (Native)>.tar`, and a `TarDirectory` takes the archive's name without `.tar`, so `LoadedLanguage.folderName` is the full name, such as `Russian (Русский)`. `LanguageDatabase.SelectLanguage` writes `Prefs.LangFolderName = lang.folderName`, so `Prefs.xml` stores the full name. `InitAllMetadata` picks the active language with `folderName == Prefs.LangFolderName`, an exact match. A short name such as `Russian` matches nothing, and the game falls back to English without logging an error. The short `LegacyFolderName` (the text before ` (`) is only used to merge a mod's `Languages/Russian` folder into the vanilla language. The launcher's `--language` resolves short names to full names for this reason. Runtime-observed 2026-11-22 on 1.7.5014: Loot Scavenging run `20261122-020914-lootscavenging-smoke-s1-a52a069e` with `--language Russian` wrote `Russian (Русский)` to Prefs, and the game loaded it (`environment.language`). With Core, Harmony and one mod, vanilla Russian logs a warning that its translation data has 38 errors; that line is the game's, not the mod's.

## Random state

`Verse.Rand.set_Seed` logs an error only when `stateStack` is empty. `PushState(seed)` first saves the current compressed seed/iteration state, then seeds; `PopState` restores it. `StateCompressed` is private. `Verse.Root.Update` calls `EnsureStateStackEmpty`, which warns and pops leaked states each frame, so a state cannot remain pushed across frames. A scoped-stream prototype preserved draws across frame waits but not across simulation ticks. Equal creation seeds do not establish repeatable simulation.

## Reported by other projects, not verified here

From the Shift Change mod's `docs/TESTING.md` (github.com/beverage/shift-change), which cites decompiled RimWorld 1.6.4871. None has been rechecked against 1.7 IL or seen in a run of this harness. Verify one before a case depends on it, then move it to its section above.

- **Jobs are pooled:** a finished job goes back to `JobMaker`'s pool and is handed out again for the pawn's next job, so a `Job` reference held across its own end becomes a different job. Hold `pawn.jobs.curDriver`, which is built per job, and read the `JobCondition` the job ended with: the driver also changes when a job fails its reservations before doing anything.
- **Generated colonists are not tended:** `PawnGenerator` tends a new pawn's conditions only when it is not joining the player. A colonist who rolled asthma or similar starts untended, and `HealthAIUtility.ShouldSeekMedicalRestUrgent` then treats them as an urgent patient. `Kit.Worker` removes such conditions.
- **An eating pawn reserves its food:** a pawn that is eating holds a claim on the food (`PhysicalInteractionReservationManager`) that no other pawn can reserve past, whatever its faction. A wild animal eating a case's ingredients blocks the job the case waits for. Runner colonies remove wild animals, so this needs another eater.
- **Speed cannot be set during the fade-in:** `TickManager`'s speed setter and `Pause` do nothing while a new game fades in. Shift Change sets the `curTimeSpeed` field directly.
- **Path requests are served by the map:** `Pawn_PathFollower` waits on a request that `Map.MapPreTick` serves from `TickManager.DoSingleTick`. Ticking one pawn alone leaves it one cell short forever. The runner steps `DoSingleTick`, so cases are not affected; never tick a pawn by itself.
- **Stranger in black:** when a colony that has held three colonists loses its last one, `StorytellerComp_Triggered` queues `StrangerInBlackJoin` 180 ticks later. The runner skips `Storyteller.StorytellerTick` in its colonies, which should stop the queued incident from firing; that has not been checked.
- **Odyssey vacuum drifts:** `VacuumComponent` exchanges air between neighbouring rooms every 250 ticks, so a vacuum value a case sets moves unless it is held each tick (`EveryTick`).
