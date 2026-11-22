# Timberborn game facts

Verified 2026-11-22 against Timberborn 1.1.2.8-ffc2de0-sw (Steam build 26072923, Unity 6000.5.11f1, Windows) by decompiling the installed `Timberborn_Data/Managed` assemblies with ILSpy, reading the game's bundled `StreamingAssets/Modding` folder, surveying 286 subscribed Workshop manifests, and reading the [official modding wiki](https://github.com/mechanistry/timberborn-modding/wiki) (pages edited October to December 2025). The wiki tracks the Experimental branch, so it can run ahead of Stable. Recheck against another build before relying on a fact: `Timberborn_Data/StreamingAssets/Version.txt` holds the build string and `VersionNumbers.json` its `CurrentVersion`.

Facts marked *wiki only* were not confirmed in this build's code.

## Paths

- **Game assemblies:** `<install>/Timberborn_Data/Managed` (Windows); the wiki gives `<install>/Contents/Resources/Data/Managed` on macOS. Harmony is not among them.
- **Local mods:** `<Documents>/Timberborn/Mods/<ModFolder>`. `Timberborn.PlatformUtilities.UserDataFolder` resolves `<Documents>` with `Environment.SpecialFolder.MyDocuments`, so on a OneDrive-redirected machine it is `OneDrive/Documents`, not `%USERPROFILE%/Documents`. On macOS it adds an extra `Documents` segment. The game creates the folder on start.
- **Workshop mods:** `<steam library>/steamapps/workshop/content/1062090/<ItemId>`. Steam owns these folders; leave them unedited.
- **Log:** `%USERPROFILE%/AppData/LocalLow/Mechanistry/Timberborn/Player.log`, with `Player-prev.log` from the previous launch. Manifest and version-folder failures are logged there as warnings.
- **Bundled modding kit:** `StreamingAssets/Modding` holds `Blueprints.zip` (every base-game `*.blueprint.json`), `Localizations.zip`, `UI.zip`, `Shaders.zip`, example models and `ModTemplates/` (`Empty`, `BerryJam` blueprints-only, `TailsAndBanners` textures). These templates are the closest example of this build's layout; the [upstream repository](https://github.com/mechanistry/timberborn-modding) and its forks may lag.

## Mod discovery and manifest

- `Timberborn.Modding.ModRepository.GetModDirectory`: if a mod folder contains any `version-*` subfolder, the game ignores the root and loads the subfolder with the highest version not above the current game version. No match logs a warning and skips the mod. Some Workshop items ship `Version-1.1`; that this matches on Windows is inferred from the case-insensitive file system, not observed, and macOS behaviour is unverified.
- `ManifestLoader` reads `manifest.json` from the chosen folder and only these keys: `Name`, `Version`, `Id`, `MinimumGameVersion` (required, read without a default), `Description`, `RequiredMods`, `OptionalMods` (optional). Each dependency entry reads `Id` and an optional `MinimumVersion`, defaulting to `0`. Other keys seen in Workshop manifests (`ModIOID`, `AuthorName`, `Author`) are ignored. The game parses it with Newtonsoft `JObject.Parse` (`SerializedObjectReaderWriter.ReadJson`), which by Newtonsoft's defaults tolerates trailing commas and raw newlines in strings. Nine surveyed Workshop manifests that strict parsers reject ship in published mods; loading them in game was not tested. A missing required key or other exception logs `Failed to load mod manifest` and skips the mod.
- `Timberborn.Versioning.Version.Create` drops anything after the first `-`, then `int.Parse`s each dot-separated part. A non-numeric part fails the manifest. A string starting with `v` parses as `0.0.0.0`.
- An empty `Id` skips the mod. Duplicate `Id`s within the same source both load and show the folder name in the mod manager.
- `MinimumGameVersion` and missing or outdated `RequiredMods` only raise warning icons in the mod manager (`Timberborn.ModdingUI.ModWarningUpdater`); they do not stop the mod loading.

## Load order

`ModSorter.Sort` orders mods by `Name`, then repeatedly takes the mod with the fewest unresolved `RequiredMods` plus `OptionalMods`, then applies the player's mod-manager priority. Assemblies load and starters run in that order. Mods run only when the player enabled mods (`ModdedState.IsModded`).

## Code mods

- `Timberborn.ModManagerScene.ModCodeStarter` runs after the mod manager scene. It calls `Assembly.Load(File.ReadAllBytes(...))` on every `*.dll` anywhere under the chosen mod folder, then instantiates every non-abstract `IModStarter` with a parameterless constructor and calls `StartMod(IModEnvironment)`. Consequences:
  - Any DLL left in the folder loads, including copied game references or a second Harmony. Ship only the mod's own assemblies.
  - `Assembly.Location` is empty for byte-loaded assemblies. Use `IModEnvironment.ModPath` (the chosen version folder) or `OriginPath` (the mod's root).
- **Configurators:** Bindito's `ContainerDefinition.InstallAll(contextName)` scans every loaded assembly for non-abstract `IConfigurator` types carrying `[Context("<name>")]` and installs them in that scene. The game's own configurators use `MainMenu`, `Game`, `MapEditor` and `Bootstrapper`. Mods use the first three. *Wiki only:* mods can also use `Bootstrapper`, the global context; nothing read here shows its container is built after mod assemblies load. One class can carry several `Context` attributes. Subclass `Bindito.Core.Configurator` for `Bind<T>()` and `MultiBind<T>()`.
- **Harmony:** not shipped with the game. Mods depend on the Workshop item [Harmony](https://steamcommunity.com/sharedfiles/filedetails/?id=3284904751) (manifest `Id` `Harmony`, version 2.4.1 at review, bundles `0Harmony.dll`), declared as `{ "Id": "Harmony", "MinimumVersion": "2.3.3" }` in `RequiredMods` in every surveyed code mod. Its author's repository documents usage. Patch from `IModStarter.StartMod`.
- **Target framework:** the surveyed code mod targets `.NETStandard,Version=v2.1`. A non-Unity csproj with that target has not been built and loaded against this build.
- `ExternalModFinder` flags the session as unofficially modded when BepInEx is loaded.

## Data mods

- Blueprint files end `.blueprint.json` (`BlueprintAsset.Extension`); `.optional.blueprint.json` applies only when the target exists. A file at a new path adds a blueprint; one at an existing path merges into it.
- Merge keywords in `Timberborn.SerializationSystem.JsonKeywords`: `#append`, `#remove`, `#delete`, `#nested`. *Wiki only:* lists are replaced unless suffixed, `#remove` needs the whole element, and a higher-priority mod applies its changes first. `#nested` is undocumented.
- *Wiki only:* localisations are `Localizations/<lang>_<suffix>.csv` with `ID,Text,Comment` columns; images take an optional `<file>.meta.json`; `AssetBundles/*_win` and `*_mac` load per OS.

## Publishing

- **Steam Workshop:** the in-game uploader (mod manager, main menu) reads `Name` and `Description` from the manifest and uses `thumbnail.png` or `thumbnail.jpg` from the mod root, under 1 MB (*wiki only* for the limit). It writes `workshop_data.json` (`ItemId`, `Name`, `Visibility`, `Tags`, update flags) into the mod folder; later uploads reuse that `ItemId`. Tags seen include `Mod`, `Update 1.0`, `Update 1.1`.
- **mod.io:** *wiki only*: create the entry on mod.io and upload a ZIP by hand; players install it into the local Mods folder. No mod.io assembly ships in `Managed`.

## Debugging

`-skipModManager` skips the startup mod manager (observed). *Wiki only:* `Alt+~` opens the console; `Shift+Alt+Z` toggles dev mode.

## Launching and testing

From a harness spike on 2026-11-22/23 against this build, and from building [Timberborn Dev Tests](../../tools/timberborn-dev-tests/README.md) on it. Items marked *decompile* were read from code and have not run in game.

- **Launch:** `steam.exe -applaunch 1062090 -skipModManager -logFile <path>` passes the arguments to `Timberborn.exe` with no Steam dialog, and `Application.consoleLogPath` becomes `<path>`, so the player's `Player.log` is not rotated. Steam is the game's parent process, so find the process by image name. *Decompile:* a direct `Timberborn.exe` launch hits `SteamAPI.RestartAppIfNecessary`, relaunches through Steam and drops the arguments. Steam allows one running game per account.
- **Mod enabled state:** PlayerPrefs `ModEnabled.<Steam Workshop|Local>.<folder>.<Id>` in `HKCU\Software\Mechanistry\Timberborn`; registry value names add Unity's `_h<djb2-xor hash>` suffix. A missing key means enabled, and keys for unsubscribed mods stay behind. A test run must isolate mods: one Workshop mod's crash at load stops the game before the main menu.
- **Registry writes from a sandboxed agent session don't reach the game.** The same launcher's `ModEnabled` writes were invisible to `PlayerPrefs.HasKey` in game when it ran from the agent's tools, but visible (`hasKey=True value=0`) when the user ran it from their own terminal. Running the agent's command with the sandbox switch off (`dangerouslyDisableSandbox`) didn't help either: the probe still showed `hasKey=False`. So the user must run any launcher that changes PlayerPrefs, and the agent can't check the real registry afterwards. Probe the keys from inside the game.
- **Mod priority:** *decompile:* PlayerPrefs `ModPriority.<source>.<folder>.<Id>` holds the mod manager's priority. `ModSorter` orders by sorted index minus priority, and `ModCodeStarter` runs starters in that order, so a priority above every index runs a mod's starter first. The game rewrites the value after sorting. The harness writes `ModPriority.Local.TimberbornDevTests.TimberbornDevTests` = 100000 so its starter sees errors logged by the mod's starter; an in-game check of that order is pending.
- **Duplicate Ids across sources:** *decompile:* a Local and a Workshop copy of one `Id` both load, since the game flags duplicates only within a source. Disable one when testing the other.
- **Early mod code:** `IModStarter.StartMod` runs before asset bundles load and before any Bindito context. A `DontDestroyOnLoad` object created there keeps running in `3-CrashScene`, so it can still write a report and quit.
- **Starter exceptions:** *decompile:* `ModCodeStarter.Start` has no catch, so an uncaught exception in any mod's `StartMod` escapes it. Later starters never run and `ExceptionListener` loads `3-CrashScene`. Such a run always goes to the crash scene; only an error the game survives (logged, or caught and logged) can be judged afterwards. `ExceptionListener` also sends any `Debug.LogException` to the crash scene, so harness and case code log with `Debug.LogError`.
- **Crash signature:** "First uncaught exception" in the log, a switch to scene `3-CrashScene`, and an error-report zip in `<Documents>/Timberborn/Error reports`. Every launch also rewrites `steam_autocloud.vdf` files under `<Documents>/Timberborn` and Unity `unity.player_session*` PlayerPrefs, so exclude those from before/after checks. `<Documents>/Timberborn` has no `Settings` folder (settings live in PlayerPrefs), and mods rewrite their own files in `PlayerData` at load (observed in the spike's non-isolated run), so a before/after check can't cover `PlayerData` either.
- **Starting a game from code (observed).** From the `MainMenu` context, `GameSceneLoader.StartNewGameInstantly(factionId, MapFileReference.FromResource(map), settlementName)` started a Folktails game on the built-in `_Mini` map with no prompts: main menu after about 3 s, 13 beavers, a district centre and 130 berries at start. A non-empty name skips the naming prompt. Built-in maps come from `MapRepository.GetBuiltinMapNames()` (22 in this build); factions are `Folktails` and `IronTeeth`. *Decompile:* `StartSaveGameInstantly(new SaveReference(save, new SettlementReference(name, dir)))` loads from any folder `dir`, and `-saveName X -settlementName Y` auto-loads a save, but only from the player's Saves folder.
- **Placing a building (observed):** `TemplateNameMapper.GetTemplate("LumberjackFlag.Folktails")`, `PreviewPlacerFactory` for coordinates, then `BlockObjectPlacerService.GetMatchingPlacer(spec).Place(...)`. The building was placed unfinished and finished within 12 game hours.
- **Saves (observed):** `Autosaver.Suspend()` when the `Game` scene loads kept every save out of the player's folder, and `GameSaver.QueueSaveSkippingNameValidation` wrote a fixture `.timber` into a run folder. *Decompile:* the 10-minute autosave and the saves on quit and on returning to the menu otherwise write to the current settlement's folder.
- **Speed:** `SpeedManager.ChangeSpeed(30)` sets `Time.timeScale` to 30 (observed), which gave 12 game hours in 7.7 s of wall time at 30–60 fps on `_Mini`. *Decompile:* UI speeds are 0/1/3/7 and the dev speeds are ×0.25/×30/×99. `GameSpeedThrottler` cuts speeds above 1 to 0.4–1.0× for populations of 30–200. Ticks are 0.6 s, 768 per day, driven by frame time. The harness's first `smoke` run (`20261123-004441-smoke`, observed) played 2.03 game hours of a new `_Mini` game at ×30 in 1.25 s of wall time, with 13 beavers at start and end and no exceptions. The window stayed focused (`wasUnfocused: false`), so whether ticks run while it is unfocused is still open.
- *Decompile:* **no determinism.** `UnityEngine.Random` is never seeded, and beaver ages, weather and ticks per frame vary. Assert on ranges.
- *Decompile:* **useful services:** `BeaverPopulation.NumberOfBeavers`, `ResourceCountingService.GetGlobalResourceCount(id).AllStock`, `IDayNightCycle.PartialDayNumber`, `BlockObjectPlacerService.GetMatchingPlacer(spec).Place(...)`, and `ShowPrimaryUIEvent` as the game-ready signal.
