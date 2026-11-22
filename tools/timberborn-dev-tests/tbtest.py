"""Launcher for the Timberborn developer test harness (TimberbornDevTests): the Timberborn adapter over dev-tests-core.

  python tbtest.py run smoke [--map _Mini] [--hours H] [--speed S] [--timeout S] [--startup-timeout S]
  python tbtest.py restore | latest | prune [--keep N]

`run` builds the runner, installs it into Documents/Timberborn/Mods/TimberbornDevTests with a request.json, disables every
other mod through the game's own PlayerPrefs keys, launches Timberborn through Steam with its log in the run folder, waits
for report.json, then restores the PlayerPrefs key exactly, removes the runner and checks the player's data was untouched.
Each run starts a fresh game (D4). Run folders are under work/runs.

The user runs `run` and `restore` from their own terminal: registry writes made from an agent's sandboxed session never
reach the game (SPEC D2). If a run is interrupted, the next `run` refuses until `restore` puts the key back.

Exit codes: 0 pass, 1 failures or isolation breach, 2 timeout, crash or no report, 3 refusal, 4 launcher error.
"""
import argparse
import base64
import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HARNESS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_ROOT.parent / "dev-tests-core"))
import devtests_core as core

APP_ID = "1062090"
PROCESS = "Timberborn.exe"
GAME_VERSION = (1, 1, 2, 8)
DEFAULT_GAME_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Timberborn"
LOCAL_FILE = HARNESS_ROOT / "tbtest.local.json"
WORK = HARNESS_ROOT / "work"
EVIDENCE = WORK / "runs"
# Present only while a run has changed the player's environment (PlayerPrefs, the runner folder).
STATE = WORK / "state.json"
PROJECT = HARNESS_ROOT / "TimberbornDevTests.csproj"
RUNNER_BUILD = HARNESS_ROOT / "bin/Release/TimberbornDevTests.dll"
RUNNER_FOLDER = RUNNER_ID = "TimberbornDevTests"
PREFS_KEY = r"Software\Mechanistry\Timberborn"
# The player's data a run must not touch. Steam rewrites steam_autocloud.vdf in synced folders on every launch.
# PlayerData is left out: mods write their own files there at load (seen in the spike's non-isolated run), so it would flag
# every run that loads such a mod.
PROTECTED_FOLDERS = ("Saves", "ExperimentalSaves", "Maps")
IGNORED_CHANGES = ("steam_autocloud.vdf",)
# Launcher-side run files: a run folder holding only these is a run whose game never reported.
LAUNCHER_FILES = ("launcher.json", "heartbeat.json")
RUN_FILES = core.RUN_FILES + LAUNCHER_FILES
PROBE_KEYS = 2


# ---- Paths -----------------------------------------------------------------------------------------------------------------

def documents():
    """The game uses Environment.SpecialFolder.MyDocuments, which follows OneDrive redirection."""
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
    return Path(buf.value)


@dataclass
class Paths:
    game_dir: Path
    user_data: Path  # <Documents>/Timberborn

    @property
    def mods(self):
        return self.user_data / "Mods"

    @property
    def workshop(self):
        return self.game_dir.parents[1] / "workshop/content" / APP_ID

    @property
    def error_reports(self):
        return self.user_data / "Error reports"

    @property
    def protected(self):
        return [self.user_data / name for name in PROTECTED_FOLDERS]

    @property
    def default_log(self):
        return Path(os.environ["USERPROFILE"]) / "AppData/LocalLow/Mechanistry/Timberborn/Player.log"


def resolve_paths():
    """TIMBERBORN_DIR, then gameDir in the untracked tbtest.local.json, then the default Steam location; documentsDir in the
    local file overrides the Documents lookup."""
    game_dir = core.local_path("TIMBERBORN_DIR", LOCAL_FILE, "gameDir", DEFAULT_GAME_DIR)
    docs = core.local_value(LOCAL_FILE, "documentsDir")
    return Paths(game_dir, (Path(docs) if docs else documents()) / "Timberborn")


# ---- PlayerPrefs (HKCU registry) ---------------------------------------------------------------------------------------------

def unity_pref_name(key):
    """Unity stores PlayerPrefs key K as registry value K_h<djb2-xor hash of its UTF-8 bytes>."""
    h = 5381
    for b in key.encode("utf-8"):
        h = ((h * 33) ^ b) & 0xFFFFFFFF
    return f"{key}_h{h}"


def restore_plan(snapshot, current):
    """What returns the key to the snapshot exactly: values to delete, and values to write back."""
    removals = sorted(name for name in current if name not in snapshot)
    writes = {name: value for name, value in snapshot.items() if current.get(name) != value}
    return removals, writes


class RegistryPrefs:
    """The game's PlayerPrefs key. Values are [type, data], with binary data as {"b64": ...} so a snapshot is JSON."""

    def read(self):
        import winreg
        values = {}
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, PREFS_KEY)
        except FileNotFoundError:
            return values
        with key:
            i = 0
            while True:
                try:
                    name, data, kind = winreg.EnumValue(key, i)
                except OSError:
                    break
                values[name] = [kind, {"b64": base64.b64encode(data).decode()} if isinstance(data, bytes) else data]
                i += 1
        return values

    def apply(self, removals, writes):
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, PREFS_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
            for name in removals:
                winreg.DeleteValue(key, name)
            for name, (kind, data) in writes.items():
                winreg.SetValueEx(key, name, 0, kind, base64.b64decode(data["b64"]) if isinstance(data, dict) else data)

    def restore(self, snapshot):
        removals, writes = restore_plan(snapshot, self.read())
        self.apply(removals, writes)
        return len(removals) + len(writes)


# ---- Mod discovery (mirrors Timberborn.Modding.ModRepository) -------------------------------------------------------------

@dataclass(frozen=True)
class InstalledMod:
    source: str  # "Steam Workshop" or "Local"
    folder: str
    mod_id: str

    @property
    def enabled_key(self):
        return f"ModEnabled.{self.source}.{self.folder}.{self.mod_id}"


def version_tuple(text):
    parts = [int(p) for p in text.split(".") if p.isdigit()]
    return tuple(parts + [0] * (4 - len(parts)))


def manifest_id(folder, game_version=GAME_VERSION):
    """The Id the game reads for a mod folder: from the highest version-* subfolder not above the game version."""
    # Directory.GetDirectories("version-*") is case-insensitive on Windows; several mods ship "Version-1.1".
    versions = [d for d in folder.iterdir() if d.is_dir() and d.name.lower().startswith("version-")]
    if versions:
        eligible = [d for d in versions if version_tuple(d.name[len("version-"):]) <= game_version]
        if not eligible:
            return None
        folder = max(eligible, key=lambda d: version_tuple(d.name[len("version-"):]))
    manifest = folder / "manifest.json"
    if not manifest.is_file():
        return None
    text = manifest.read_text(encoding="utf-8-sig", errors="replace")
    try:
        return json.loads(text).get("Id")
    except json.JSONDecodeError:
        # Some community manifests are not strict JSON (the game's reader is lenient); fall back to the Id field.
        match = re.search(r'"Id"\s*:\s*"([^"]+)"', text)
        return match.group(1) if match else None


def installed_mods(workshop, mods, game_version=GAME_VERSION):
    """Every mod the game would load besides the runner, Workshop first."""
    found = []
    for source, base in (("Steam Workshop", Path(workshop)), ("Local", Path(mods))):
        for folder in sorted(base.iterdir()) if base.is_dir() else []:
            if not folder.is_dir() or (source == "Local" and folder.name == RUNNER_FOLDER):
                continue
            mod_id = manifest_id(folder, game_version)
            if mod_id:
                found.append(InstalledMod(source, folder.name, mod_id))
    return found


def disable_values(mods):
    """Isolation (D3): a 0 for each mod's enable key. T3 narrows the list to the mods outside the selected set."""
    return {unity_pref_name(mod.enabled_key): [4, 0] for mod in mods}  # 4 = REG_DWORD


# ---- Request, install and launch -------------------------------------------------------------------------------------------

def build_request(run_id, run_dir, batch, map_name, speed, hours, deadline_ms, probe_keys=()):
    return {"RunId": run_id, "RunDir": str(run_dir), "Batch": batch, "Mode": "new", "Map": map_name,
            "SettlementName": f"DevTests-{run_id}", "Speed": speed, "GameHours": hours, "DeadlineUtcMs": deadline_ms,
            "ProbePrefKeys": list(probe_keys)}


def runner_manifest():
    return {"Name": "Timberborn Dev Tests (developer only)", "Version": "0.1.0", "Id": RUNNER_ID, "MinimumGameVersion": "1.1.0.0",
            "Description": "Developer test runner installed and removed by tbtest.py. Does nothing without request.json.",
            "RequiredMods": []}


def install_runner(dlls, mods_dir, request):
    """A fresh runner folder: the DLLs, its manifest and the request. The game loads every DLL in it, so nothing else."""
    target = Path(mods_dir) / RUNNER_FOLDER
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for dll in dlls:
        shutil.copy2(dll, target / Path(dll).name)
    (target / "manifest.json").write_text(json.dumps(runner_manifest(), indent=2), encoding="utf-8")
    (target / "request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    return target


def launch_command(steam_exe, log_path):
    # A direct Timberborn.exe launch restarts through Steam and drops the arguments; -applaunch passes them through.
    return [str(steam_exe), "-applaunch", APP_ID, "-skipModManager", "-logFile", str(log_path)]


def steam_exe():
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
        return winreg.QueryValueEx(key, "SteamExe")[0]


def build_runner():
    subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "-nologo", "-v", "q"], check=True)
    return [RUNNER_BUILD]


# ---- Summary ---------------------------------------------------------------------------------------------------------------

def write_summary(run_dir, run_id, report, launcher):
    problems = launcher.get("problems") or []
    if report is None:
        verdict = "NO REPORT"
    else:
        verdict = "PASS" if report.get("overallPass") and not problems else "FAIL"
    lines = [f"Run {run_id}: {verdict}"]
    if report is None:
        lines.append("  no report.json: the game was killed, crashed or never reached the runner")
    else:
        lines.append(f"  status {report.get('status')}" + (f": {report['reason']}" if report.get("reason") else "")
                     + f"; errors {report.get('errorCount')}, exceptions {report.get('exceptionCount')}")
        for case in report.get("cases") or []:
            lines.append(f"  {str(case.get('Result')).upper()} {case.get('Id')}" + (f": {case['Reason']}" if case.get("Reason") else ""))
            if case.get("Observed") is not None:
                lines.append(f"    observed {json.dumps(case['Observed'])[:400]}")
    log = launcher.get("logErrors")
    if log and (log.get("exceptions") or log.get("crashed")):
        lines.append(f"  Player.log: {log['exceptions']} exception(s){', crashed' if log.get('crashed') else ''}; first: "
                     + "; ".join(log.get("first", [])[:3]))
    lines += [f"  PROBLEM: {p}" for p in problems]
    lines.append(f"  folder: {run_dir}")
    text = "\n".join(lines) + "\n"
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    (Path(run_dir) / "summary.txt").write_text(text, encoding="utf-8")
    return text


# ---- Commands --------------------------------------------------------------------------------------------------------------

def restore(paths, prefs):
    if not STATE.is_file():
        print("Nothing to restore.")
        return 0
    if core.pids(PROCESS):
        print("REFUSED: Timberborn is still running; close it first (Unity writes PlayerPrefs on exit).")
        return 3
    state = json.loads(STATE.read_text(encoding="utf-8"))
    changed = prefs.restore(state["prefs"])
    shutil.rmtree(paths.mods / RUNNER_FOLDER, ignore_errors=True)
    STATE.unlink()
    print(f"Restored {changed} PlayerPrefs value(s) from run {state.get('runId')}; removed {paths.mods / RUNNER_FOLDER}.")
    return 0


def refusal(paths):
    if STATE.is_file():
        return "a previous run did not restore the player's environment; run `python tbtest.py restore` first"
    if core.pids(PROCESS):
        return "Timberborn is running; the launcher only drives a game it starts itself, and Steam allows one game at a time"
    if not core.pids("steam.exe"):
        return "Steam is not running; the game needs it"
    if not paths.game_dir.is_dir():
        return f"no Timberborn at {paths.game_dir}; set gameDir in {LOCAL_FILE.name} or TIMBERBORN_DIR"
    return None


def run(args, paths, prefs):
    reason = refusal(paths)
    if reason:
        print("REFUSED:", reason)
        return 3
    dlls = build_runner()
    run_id = core.new_run_id(args.batch)
    run_dir = EVIDENCE / run_id
    run_dir.mkdir(parents=True)
    started = time.monotonic()
    deadline = started + args.timeout
    mods = installed_mods(paths.workshop, paths.mods)
    request = build_request(run_id, run_dir, args.batch, args.map, args.speed, args.hours, core.game_deadline(deadline),
                            [m.enabled_key for m in mods[:PROBE_KEYS]])
    snapshot = prefs.read()
    protected_before, reports_before = core.tree_snapshot(*paths.protected), core.tree_snapshot(paths.error_reports)
    STATE.write_text(json.dumps({"runId": run_id, "prefs": snapshot}), encoding="utf-8")
    launcher = {"runId": run_id, "request": request, "problems": [], "modsDisabled": len(mods)}
    timed_out = False
    print(f"Run {run_id}: evidence {run_dir}", flush=True)
    try:
        timed_out = drive(args, paths, prefs, mods, dlls, request, run_dir, launcher, started, deadline)
    finally:
        launcher["wallSeconds"] = round(time.monotonic() - started, 1)
        # Preflight refused any running Timberborn, so one running now is the launcher's own.
        for pid in core.pids(PROCESS):
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, check=False)
        if core.wait_for(lambda: not core.pids(PROCESS), 30):
            launcher["prefsRestored"] = prefs.restore(snapshot)
            shutil.rmtree(paths.mods / RUNNER_FOLDER, ignore_errors=True)
            STATE.unlink(missing_ok=True)
        else:
            launcher["problems"].append("Timberborn did not exit; close it, then run `python tbtest.py restore`")
        launcher["errorReportsMoved"] = core.move_new_files(reports_before, paths.error_reports, run_dir)
        changes = core.snapshot_diff(protected_before, core.tree_snapshot(*paths.protected), ignore=IGNORED_CHANGES)
        launcher["protectedChanges"] = changes
        if changes:
            launcher["problems"].append(f"player data changed during the run: {changes[:5]}")
        if not (run_dir / "Player.log").is_file() and core.keep_log(paths.default_log, run_dir):
            launcher["playerLogSource"] = str(paths.default_log)
        launcher["logErrors"] = core.log_errors(run_dir / "Player.log")
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    code = core.NO_REPORT if timed_out or report is None else core.result_code(report, launcher["problems"])
    launcher["exitCode"] = code
    (run_dir / "launcher.json").write_text(json.dumps(launcher, indent=2), encoding="utf-8")
    print(write_summary(run_dir, run_id, report, launcher))
    if report is None:
        print(f"Last {core.LOG_TAIL_LINES} lines of {run_dir / 'Player.log'}:\n{core.tail(run_dir / 'Player.log')}")
    return code


def drive(args, paths, prefs, mods, dlls, request, run_dir, launcher, started, deadline):
    """Isolate, install, launch and wait for the report. True when the run hit its time limit."""
    # Isolation only writes values; the finally block in run() restores the snapshot taken before this.
    prefs.apply([], disable_values(mods))
    install_runner(dlls, paths.mods, request)
    command = launch_command(steam_exe(), run_dir / "Player.log")
    launcher["command"] = command
    subprocess.Popen(command)
    pid = core.wait_for(lambda: (core.pids(PROCESS) or [None])[0], args.startup_timeout)
    if not pid:
        launcher["problems"].append(f"Timberborn.exe did not start within {args.startup_timeout} s of steam -applaunch")
        return False
    launcher["pid"] = pid
    launcher["processSeenAfterSeconds"] = round(time.monotonic() - started, 1)
    print(f"Timberborn started (pid {pid}).", flush=True)
    process = core.GameProcess(pid)
    report_path = run_dir / "report.json"
    try:
        while process.alive() and not report_path.is_file() and time.monotonic() < deadline:
            time.sleep(1)
        if report_path.is_file() and not process.wait(60):
            launcher["problems"].append("the game wrote its report but did not quit within 60 s; killed")
        timed_out = not report_path.is_file() and process.alive()
        if timed_out:
            print(f"Game timed out after {args.timeout} s; killing it.")
        process.kill()
        launcher["exitedAfterSeconds"] = round(time.monotonic() - started, 1)
        return timed_out
    finally:
        process.close()


def run_command(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    launch = commands.add_parser("run", help="launch Timberborn and run a batch in a new game (user's terminal only)")
    launch.add_argument("batch", help="batch to run; this runner build has only smoke")
    launch.add_argument("--map", default="_Mini", help="built-in map for the new game")
    launch.add_argument("--hours", type=float, default=2.0, help="game hours the smoke batch runs")
    launch.add_argument("--speed", type=float, default=30.0, help="game speed while it runs (dev speeds: 30, 99)")
    launch.add_argument("--timeout", type=int, default=600,
                        help=f"wall-clock seconds for the whole run; the game closes it {core.DEADLINE_GRACE} s before and is killed at it")
    launch.add_argument("--startup-timeout", type=int, default=120, help="seconds for Timberborn.exe to appear after steam -applaunch")
    commands.add_parser("restore", help="put back the PlayerPrefs key and remove the runner after an interrupted run")
    commands.add_parser("latest", help="print the latest run's summary without launching Timberborn")
    pruner = commands.add_parser("prune", help="delete old run folders")
    pruner.add_argument("--keep", type=int, default=20)
    args = parser.parse_args(argv)
    if args.command == "latest":
        return core.latest(EVIDENCE, run_files=RUN_FILES, unfinished_files=LAUNCHER_FILES)
    if args.command == "prune":
        if args.keep < 1:
            parser.error("--keep must be at least 1")
        return core.prune(EVIDENCE, args.keep, run_files=RUN_FILES)
    paths, prefs = resolve_paths(), RegistryPrefs()
    if args.command == "restore":
        return restore(paths, prefs)
    if args.timeout <= 0 or args.startup_timeout <= 0:
        parser.error("--timeout and --startup-timeout must be greater than zero")
    WORK.mkdir(parents=True, exist_ok=True)
    return run(args, paths, prefs)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    return core.guarded(run_command, argv)


if __name__ == "__main__":
    sys.exit(main())
