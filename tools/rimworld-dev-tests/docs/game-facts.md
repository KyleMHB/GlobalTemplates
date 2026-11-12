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

## Random state

`Verse.Rand.set_Seed` logs an error only when `stateStack` is empty. `PushState(seed)` first saves the current compressed seed/iteration state, then seeds; `PopState` restores it. `StateCompressed` is private. `Verse.Root.Update` calls `EnsureStateStackEmpty`, which warns and pops leaked states each frame, so a state cannot remain pushed across frames. A scoped-stream prototype preserved draws across frame waits but not across simulation ticks. Equal creation seeds do not establish repeatable simulation.
