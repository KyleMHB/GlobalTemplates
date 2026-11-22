# Timberborn agent read route

Use only the branch relevant to the task. Project instructions own design choices, expected values, run/deployment permissions and acceptance.

| Task | Start here | Read next only as needed |
| --- | --- | --- |
| Start a code mod (C#, Harmony, Bindito) | [Code mods](#code-mods) | [Game facts: code mods](game-facts.md#code-mods); the wiki's [Coding basics](https://github.com/mechanistry/timberborn-modding/wiki/Coding-basics) and [Timberborn architecture](https://github.com/mechanistry/timberborn-modding/wiki/Timberborn-architecture) |
| Add or change blueprints, translations or images without code | [Game facts: data mods](game-facts.md#data-mods) | The game's `StreamingAssets/Modding/ModTemplates/BerryJam` and `Blueprints.zip` for current paths and fields; the wiki's [Blueprints](https://github.com/mechanistry/timberborn-modding/wiki/Blueprints) |
| Change manifest.json metadata | [manifest.json template](timberborn-manifest-template.md) when template-backed metadata work is requested | Existing manifests in every `version-*` folder |
| Establish game behavior or version-sensitive facts | Project configuration and the installed game's decompiled assemblies | [Game facts](game-facts.md); search relevant types or headings. For what they leave open, the official wiki, then the `discord-search` skill |
| Publish or update a Workshop item | The `steam-workshop-utils` skill, then [Workshop page guide](../workshop-page-guide.md) for the description and artwork | [Game facts: publishing](game-facts.md#publishing). The skill has no Timberborn game context yet, so establish the route first as it requires for an unlisted game |
| Test a mod in game | No shared harness exists yet. [Timberborn Dev Tests](../../tools/timberborn-dev-tests/SPEC.md) is specified but not built, so don't assume its commands | Project instructions; [Game facts: launching and testing](game-facts.md#launching-and-testing) |

Facts are verified against game version 1.1.2.8. Before relying on one, compare `Timberborn_Data/StreamingAssets/Version.txt` with the version in [game facts](game-facts.md). Decompile the installed `Timberborn_Data/Managed` assemblies (ILSpy or `ilspycmd`) to settle anything else; the wiki tracks Experimental and the upstream example repository can lag. Add reusable discoveries to game facts with version scope, evidence and limits; keep mod-specific rules in their owning repository.

## Code mods

A mod is a folder under `<Documents>/Timberborn/Mods` holding `manifest.json`, the built DLL and any data folders. The game loads every DLL in that folder, then calls each `IModStarter.StartMod`; configurators register through `[Context("Game")]`, `MainMenu` or `MapEditor` (see [game facts](game-facts.md#code-mods)).

- Reference the game's assemblies from `<install>/Timberborn_Data/Managed` with `Private` false, and Harmony from its Workshop item, so no copy lands in the mod folder.
- Keep the install path in an untracked `Timberborn.local.props` next to the project, with `*.local.props` in the mod's `.gitignore`, as the RimWorld harness does:

  ~~~xml
  <Project>
    <PropertyGroup>
      <TimberbornPath>D:\Steam\steamapps\common\Timberborn</TimberbornPath>
      <!-- Set HarmonyPath too when Harmony is in another Steam library -->
    </PropertyGroup>
  </Project>
  ~~~

- The csproj imports it when present, defaults the path, targets `netstandard2.1` and copies its output into the Mods folder after build:

  ~~~xml
  <Import Project="Timberborn.local.props" Condition="Exists('Timberborn.local.props')" />
  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
    <TimberbornPath Condition="'$(TimberbornPath)' == ''">C:\Program Files (x86)\Steam\steamapps\common\Timberborn</TimberbornPath>
    <TimberbornManaged>$(TimberbornPath)\Timberborn_Data\Managed</TimberbornManaged>
    <HarmonyPath Condition="'$(HarmonyPath)' == ''">$(TimberbornPath)\..\..\workshop\content\1062090\3284904751\0Harmony.dll</HarmonyPath>
    <ModDeployDir>$([System.Environment]::GetFolderPath(SpecialFolder.MyDocuments))\Timberborn\Mods\$(AssemblyName)</ModDeployDir>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="$(TimberbornManaged)\Timberborn.*.dll;$(TimberbornManaged)\Bindito.*.dll;$(TimberbornManaged)\UnityEngine.dll;$(TimberbornManaged)\UnityEngine.CoreModule.dll" Private="false" />
    <Reference Include="0Harmony" HintPath="$(HarmonyPath)" Private="false" />
  </ItemGroup>
  <Target Name="DeployMod" AfterTargets="Build">
    <Copy SourceFiles="$(TargetPath);manifest.json" DestinationFolder="$(ModDeployDir)" />
  </Target>
  ~~~

  This shape is unverified: no csproj built this way has been loaded in this game version. Confirm the mod appears in the mod manager and its starter runs (check `Player.log`) before treating it as settled, then record the result in game facts.
- Use `IModEnvironment.ModPath` for mod files; `Assembly.Location` is empty.
- For support across game versions, ship `version-<game version>` folders, each with its own manifest and DLL.
