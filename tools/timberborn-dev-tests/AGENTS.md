# Timberborn test harness: agent entry point

Use this guide for writing cases, changing harness code or triaging results. Read the target mod's instructions and `TESTING.md` for permission, expected behavior and required checks. This guide grants no run or deployment permission.

## Who runs what

The agent can run every command, including `run` and `restore`, with Steam running and Timberborn closed. Run those two with the sandbox switched off (`dangerouslyDisableSandbox`), one game at a time: they change the player's mod settings, and the user approves each command. Inside the Claude desktop app their registry writes would land in the app's private copy of the registry, so they rerun themselves outside it through WMI and print `Registry writes from here don't reach the game, so this runs outside the app package` ([game facts](../../Steam/timberborn/game-facts.md#launching-and-testing)). The outside process carries on if the command is stopped; its output is in `work/relay/<id>.log`. A run takes longer than a tool call's limit when its batch does, so run long batches in the background. For example: `python <templates>/tools/timberborn-dev-tests/tbtest.py --config <mod>/DevTests/devtests.json run smoke`.

To kill a run on purpose, stop the `python.exe` processes whose command line holds `tbtest.py`, then `Timberborn.exe`; the next `run` or `restore` puts the settings back. Read the real registry only from outside the package too (for example `reg.exe export` started through `Win32_Process.Create`), because a read from inside sees the private copy.

`latest`, `timings`, `list`, `prune` and `release-check` never start the game or write the registry.

## Read a run

Runs are in `work/runs/<run id>/` in this folder. Read in this order and stop once the cause is clear:

1. `summary.txt`: verdict, one line per case, steps of every case that didn't pass, the `Startup:` line, problems.
2. `report.json`: `status`, `cases[]` (Observed, Evidence, Steps, LoggedErrors), `batches[]`, `startupModErrors`, `isolationProbe`, `environment.assemblies` (runner, DevTests and mod assemblies as loaded).
3. `launcher.json`: the request, `modsSelected`/`modsDisabled`, `devFolder`, `modBuild`/`runnerHash`/`devBuildHash`/`requestHash`, `problems`, `protectedChanges` (files and PlayerPrefs values the run left changed), `exitCode`.
4. `Player.log`, then `events.jsonl` (timeline) and `batches.json` (what the game offered).

A run with no `report.json` was killed, crashed before the runner started, or timed out; `latest` says so and `launcher.json` has the problem.

## Read only what the task needs

| Task | Source |
| --- | --- |
| Commands, flags, exit codes, local paths, release check | [README](README.md) |
| Add a mod adapter or write a case | [Authoring](docs/authoring.md) |
| Find a pitfall or setup technique by symptom | [Recipe index](docs/recipes/index.md) |
| Game behaviour the harness relies on | [Game facts: launching and testing](../../Steam/timberborn/game-facts.md#launching-and-testing) |

For other subjects use `rg -n -i '<symptom or type>' docs Harness`. The design and open risks are in [SPEC.md](SPEC.md).

## What differs from RimWorld Dev Tests

The names and report shape follow [RimWorld Dev Tests](../rimworld-dev-tests/AGENTS.md), but only what a first mod needs is built. Don't assume these exist:

- No `guide` command, `close-session`, `self-check`, `status`, `lease` or recording. Each `run` starts and closes its own game.
- `run` takes one batch. There is no `run-all` batch: `RunAll` only orders the list in `batches.json` and `list`.
- No `--seed`, `--case`, `--mods`, `--language` or `--quit-on-finish`. The game has no seed to set.
- No mod sets: the set is always the mod plus its transitive `RequiredMods`.
- No `Remember`/`Recall`, `Wait.Reload`, `Wait.Seconds`, `SkipUnlessPassed`, `Kit.Require`, `AllowedErrors`, `AllowedWarnings` or `FailOnWarnings`.
- `--config` goes before the command: `tbtest.py --config <file> run <batch>`.
- No `install-dev`: each `run` installs the runner and the `devBuild` DLL into `Mods/<modId>DevTests` and removes it afterwards. Never copy a DevTests DLL into the mod's installed folder; the launcher refuses a run while one is there.
