# Timberborn Dev Tests: specification

Status: T2–T8 built on branch `timberborn-dev-tests` 2026-11-23, with unit tests and build passing; in-game checks are listed under [Build status](#build-status). T1 not run; T9 is built separately. Game: Timberborn 1.1.2.8 (Windows, Steam). Evidence for every game behaviour cited here is in [Timberborn game facts: launching and testing](../../Steam/timberborn/game-facts.md#launching-and-testing). A spike outside this repository proved the full flow on 2026-11-23: launch, mods isolated, new game, building placed, 12 game hours at ×30, fixture saved, quit and restore.

## Goal

A developer-only harness that runs a Timberborn mod's test cases in the real game and reports `passed`/`failed` with evidence. It should be the counterpart of [RimWorld Dev Tests](../rimworld-dev-tests/README.md): the same commands, exit codes, run folders and release check, so agents and the user switch between games without relearning them.

Out of scope for the first build: recording, keeping one game open across commands, multiplayer or macOS, and mod sets beyond "the mod under test plus its declared dependencies".

## Decisions

| # | Decision | Reason |
| --- | --- | --- |
| D1 | Write the launcher as a game-agnostic core module plus a Timberborn adapter from the start. Move RimWorld onto the core only afterwards (T7), gated on its existing `tests/test_launcher.py` passing. | Several RimWorld mods depend on the RimWorld harness, so it must not break first. Writing the core against a second game keeps it honest. |
| D2 | The agent runs every command, with the sandbox switched off and the user approving each one. `run` and `restore` test whether a registry write reaches an ordinary process; if not, they rerun themselves outside the app package through WMI and stream the output back. Revised 2026-11-23, after T1. | T1 found the game never saw the agent's registry writes, even with the sandbox off. The cause is the Claude desktop app being a packaged Windows app, whose HKCU writes go to a private hive. A process started through WMI writes the real one. |
| D3 | Isolate mods by writing `ModEnabled.<source>.<folder>.<Id> = 0` for every mod outside the selected set, then restoring the settings key exactly. The selected set and the dev folder are written as `1`, and the dev folder gets a `ModPriority` so the runner's starter runs first and sees other mods' startup errors. After restoring, the launcher re-reads the key and reports any difference as a protected-data change. If a crash interrupts a run, the next start restores first, and `restore` does so on demand. | Proven in the spike, and the player's own mod list can crash the game at load. |
| D4 | Start a fresh game for each `run` command (main menu in about 3 s). Keeping one game open across commands is deferred until runs get slow. | It's simpler, and the lack of a persistent session costs little at this startup time. |
| D5 | Fixtures: a new game on a built-in map (`_Mini` by default) per batch, or a fixture save loaded from the mod's `DevTests/Fixtures` or the run folder. Every save goes to the run folder, with `Autosaver.Suspend()` on. | The game never touches the player's Saves folder. |
| D6 | Cases assert on ranges and on conditions held over a time window, never on exact values. | Randomness is unseeded and ticks depend on frame time. |
| D7 | The C# API mirrors RimWorld's `HarnessSettings` / `Batch` / `BatchContext` / `Wait` / `Kit` names, but includes only what the first real mod's cases need. | Agents already know the shape. Building helpers ahead of need only produces helpers nobody uses. |
| D8 | `release-check` fails when a developer DLL or marker is in the package, or when the mod's `perf.*` timing cases (a `PerfTiming` port) haven't passed against the packaged DLL. The `perf.*` case list comes from a run of the current DevTests build (matched by its hash), so the perf rule needs `--config`. It warns when the mod defines none. There is no Harmony patch-cost timing, because the game ships no Harmony, and no Dubs batch, because Timberborn has no Dubs Performance Analyzer. | This keeps the RimWorld rule that a release must be measured. |
| D9 | One game at a time. Before launching, the launcher refuses if any `Timberborn.exe` is running, including one the player started, and checks again after building the runner. Cleanup kills only processes that appeared after its own launch. | Steam allows one game per account, and the player's own game must never be touched. |

## Layout

```text
tools/dev-tests-core/          game-agnostic Python core (T2, adopted by RimWorld in T7)
tools/timberborn-dev-tests/
  tbtest.py                    CLI: Timberborn adapter over the core
  TimberbornDevTests.csproj    shared runner DLL (net standard 2.1, game refs Private=false)
  TimberbornDevTests.props     import for a mod's DevTests project
  *.local.props, tbtest.local.json   untracked install and Documents paths
  Harness/                     runner C#: starter, session, report, batches, Kit, Wait
  docs/                        AGENTS.md route, authoring, recipes
```

A mod adds `DevTests/` with a settings subclass, `devtests.json`, a developer-only csproj importing the props file, and a short wrapper script, as in RimWorld. `devtests.json` names the built DevTests DLL as `devBuild`. During a run only the runner and that DLL are installed, into a separate `Mods/<modId>DevTests` folder, and `run` refuses if a DevTests DLL is in the mod's installed folder. The production mod folder is left alone.

## Run lifecycle

1. Preflight:
   - refuse if Timberborn is running, or if a previous run left state that hasn't been restored
   - build hashes and the runtime manifest (runner, DevTests build, mod DLLs and request, in `launcher.json`)
   - snapshot the settings key and the protected data: Saves, ExperimentalSaves, Maps (Documents has no Settings folder; settings live in the PlayerPrefs key)
2. Install the developer DLLs and `request.json`, and disable the mods outside the set (D3).
3. Launch with `steam.exe -applaunch 1062090 -skipModManager -logFile <run>/Player.log`, then find `Timberborn.exe` by image name.
4. In game:
   - the starter probes the disable keys and fails fast if any are missing
   - the driver reaches the main menu and builds or loads the fixture
   - batches run, with a heartbeat written throughout
   - the driver writes `report.json` and quits
5. Afterwards:
   - restore the settings key and remove the developer folder
   - move error-report zips into the run folder
   - diff the protected data, ignoring `steam_autocloud.vdf`
   - write `summary.txt`
   - exit with RimWorld's codes: 0 pass, 1 failures, 2 timeout/crash/no report, 3 refusal, 4 launcher error

## Tickets

Each ticket fits one session and ends with its focused check passing. The blockers listed are hard ones.

| ID | Ticket | Blocked by | Done when |
| --- | --- | --- | --- |
| T1 | **Run-authority probe.** Done 2026-11-23: the in-game probe showed `hasKey=False` for an agent command run with the sandbox switch off, The cause was later traced to the app package, and D2 now relays runs outside it. | — | Done. |
| T2 | **Core and scaffold.** Create `dev-tests-core` with the game-agnostic parts of `rimtest.py`: config, run IDs and folders, exit codes, timeouts and process kill, error counting, `Player.log` capture, protected-data diff, `latest`/`timings`/`prune`. Create `timberborn-dev-tests` with local-paths files, the csproj/props and the spike's starter, heartbeat, report and quit ported in. Rewrite the spike's `harness.py` as the Timberborn adapter. | — | `tbtest.py run smoke` on a mod-less adapter produces a passing report from a new `_Mini` game. Core unit tests cover the moved code. |
| T3 | **Mod isolation and recovery.** Select the mod set from `devtests.json` (the mod plus the transitive `RequiredMods` from manifests), D3 disable and restore, restore at the next start, a `restore` command, and the in-game key probe. | T2 | A run with the player's full list loaded passes. A run killed mid-batch leaves the next start to restore the key exactly, confirmed by a before/after export the user runs. |
| T4 | **Case API.** `HarnessSettings`, `Batch`/`PlannedCase`/`BatchContext`, `Wait` (game hours, `Until`, `While`, frames), and `Kit` (new game, load fixture, place building by template, beavers, goods, day time, speed). Add per-case errors and the steps/`KnownGap` model from RimWorld authoring. | T2 | A sample batch with a passing case, a failing case and a known gap reports each correctly. |
| T5 | **CLI parity.** Add `list`, `latest`, `timings`, `prune`, `restore`, `release-check`, `--timeout`, `--startup-timeout` and `--keep-open`, plus `summary.txt` with startup errors naming the mod and `FailOnModErrors`. | T3, T4 | Each command runs against real runs. A logged error from a mod's starter shows on the `Startup:` line and fails under `FailOnModErrors`. An uncaught starter exception always reaches the crash scene and exits 2. |
| T6 | **Perf rule.** Port `PerfTiming` and enforce D8 in `release-check`. | T4, T5 | `release-check` fails a package without passing `perf.*` cases, passes one with them, and rejects a package containing a dev DLL. |
| T7 | **RimWorld onto the core.** Switch `rimtest.py` to `dev-tests-core`, with no behaviour change. | T5 | `tests/test_launcher.py` passes unchanged, and one RimWorld mod's `run-all` passes as before. |
| T8 | **Docs.** An `AGENTS.md` route, `README.md`, `docs/authoring.md` and a recipes index for the harness. Update the Timberborn agent guide's testing row, and move any facts learnt into game facts. | T5 | The guide points to the harness, and every listed command is documented. |
| T9 | **First real mod.** A `DevTests` adapter and cases for the first Timberborn mod, likely the Torii Gates and Lanterns port, whose adoption route is still undecided. It adds only the `Kit` helpers that mod needs. | T4, the mod's first build | That mod's batches run, and each behaviour its store description promises has a case. |

Each ticket's in-game check is a command the agent runs (D2), then reads the run folder. T2 to T6 are sequential in practice, because they share `tbtest.py` and the runner files. T7 and T8 can run in parallel once T5 is done.

## Build status

As of 2026-11-23 on `timberborn-dev-tests`. Unit tests (core, Timberborn, RimWorld) and `dotnet build -c Release` pass. The in-game checks below were run by the agent through the D2 relay. "Pending" means the in-game half of "Done when" hasn't been observed yet.

| ID | State | In-game check |
| --- | --- | --- |
| T1 | done | see the T1 row |
| T2 | done | `run smoke` passed (run `20261123-074958-smoke`), with the window unfocused |
| T3 | done | Staircase run passed with its 2 mods selected, 132 disabled and 0 probe mismatches (`20261123-075056-smoke`). A run killed mid-batch left 132 mods disabled; the next start restored 140 values and the before/after export of the real registry had 0 differences |
| T4 | done | `run diagnostic` reported 4 of 4 as intended (`20261123-075028-diagnostic`). Fixture load/save, the batch time limit and the case-exception path are not exercised yet |
| T5 | done | `list` and `timings` read a real run. A logged starter error shows on `Startup:` naming the mod, and fails the run (exit 1) under `FailOnModErrors`; an uncaught one exits 2 |
| T6 | done | `release-check --config` passed after `perf-check`, failed against a changed production DLL, and failed without `--config` |
| T7 | built | `test_launcher.py` passes unchanged; pending: one RimWorld mod's `run-all` |
| T8 | done | — |
| T9 | elsewhere | built in its own thread |

Known gap: `list` without `--config` can also match a killed run that has no `launcher.json`.

## Open risks

- `GameSpeedThrottler` slows populations over 30 beavers at speeds above 1. Large fixtures may need longer timeouts, or a dev-speed path.
- Workshop mods that ship code in `version-*` folders, which are matched case-insensitively, need the T3 manifest lookup to use the same folder the game chooses.
