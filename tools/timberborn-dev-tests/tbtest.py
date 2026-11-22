"""Launcher for the Timberborn developer test harness (TimberbornDevTests): the Timberborn adapter over dev-tests-core.

  python tbtest.py [--config <mod>/DevTests/devtests.json] run smoke [--map _Mini] [--hours H] [--speed S] [--timeout S] [--startup-timeout S] [--keep-open]
  python tbtest.py [--config ...] list | release-check [mod_dir]
  python tbtest.py restore | latest [--batch B] | timings [run] | prune [--keep N]

`run` builds the runner and installs it, with the mod's DevTests DLL (devtests.json "devBuild") and a request.json, into a
dev folder Documents/Timberborn/Mods/<modId>DevTests (Mods/TimberbornDevTests without --config); the mod's own folder is left
alone. It isolates mods through the game's own PlayerPrefs keys: the dev folder, the mod named by devtests.json ("modId") and
its transitive RequiredMods stay enabled, every other installed mod is disabled (all of them without --config). It launches
Timberborn through Steam with its log in the run folder, waits for report.json, then restores the PlayerPrefs key exactly,
removes the dev folder and checks the player's data was untouched. Each run starts a fresh game (D4). Run folders are under
work/runs.

The user runs `run` and `restore` from their own terminal: registry writes made from an agent's sandboxed session never
reach the game (SPEC D2). If a launcher was killed mid-run, the next `run` restores the key first; `restore` does it alone.

Exit codes: 0 pass, 1 failures or isolation breach, 2 timeout, crash or no report, 3 refusal (including the in-game probe
refusing a run whose isolation did not reach the game), 4 launcher error.
"""
import argparse
import base64
import ctypes
from dataclasses import dataclass
import hashlib
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
# Present only while a run has changed the player's environment (PlayerPrefs, the dev folder).
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

    def mod_folder(self, mod):
        return (self.mods if mod.source == "Local" else self.workshop) / mod.folder

    @property
    def error_reports(self):
        return self.user_data / "Error reports"

    @property
    def protected(self):
        return [self.user_data / name for name in PROTECTED_FOLDERS]

    @property
    def default_log(self):
        return Path(os.environ["USERPROFILE"]) / "AppData/LocalLow/Mechanistry/Timberborn/Player.log"


@dataclass
class Config:
    name: str
    mod_id: str  # the manifest Id of the mod under test
    root: Path  # the mod's checkout: <root>/DevTests/devtests.json
    dev_build: Path = None  # the built DevTests DLL ("devBuild", relative to root); None for an isolation-only config

    @property
    def fixtures(self):
        return self.root / "DevTests/Fixtures"


def load_config(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("modId"):
        raise ValueError(f'{path} needs "modId": the manifest Id of the mod under test')
    root = path.parent.parent
    return Config(name=data.get("name") or data["modId"], mod_id=data["modId"], root=root,
                  dev_build=(root / data["devBuild"]).resolve() if data.get("devBuild") else None)


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
    required: tuple = ()  # RequiredMods Ids from the manifest the game reads

    @property
    def enabled_key(self):
        return f"ModEnabled.{self.source}.{self.folder}.{self.mod_id}"


def version_tuple(text, game_version=GAME_VERSION):
    # ModRepository reads a bare "version-" folder as the running game's version.
    if not text:
        return tuple(game_version)
    parts = [int(p) for p in text.split(".") if p.isdigit()]
    return tuple(parts + [0] * (4 - len(parts)))


def read_manifest(folder, game_version=GAME_VERSION):
    """The manifest the game reads for a mod folder, from the highest version-* subfolder not above the game version.
    None when the game would skip the folder."""
    # Directory.GetDirectories("version-*") is case-insensitive on Windows; several mods ship "Version-1.1".
    versions = [d for d in folder.iterdir() if d.is_dir() and d.name.lower().startswith("version-")]
    if versions:
        def version(d):
            return version_tuple(d.name[len("version-"):], game_version)
        eligible = [d for d in versions if version(d) <= tuple(game_version)]
        if not eligible:
            return None
        folder = max(eligible, key=version)
    manifest = folder / "manifest.json"
    if not manifest.is_file():
        return None
    text = manifest.read_text(encoding="utf-8-sig", errors="replace")
    for candidate in (text, re.sub(r",\s*([}\]])", r"\1", text)):
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    else:
        # Some community manifests are not JSON at all (the game's reader is lenient); fall back to the Id field.
        match = re.search(r'"Id"\s*:\s*"([^"]+)"', text)
        return {"Id": match.group(1)} if match else None
    return data if isinstance(data, dict) else None


def manifest_id(folder, game_version=GAME_VERSION):
    manifest = read_manifest(folder, game_version)
    return manifest.get("Id") if manifest else None


def installed_mods(workshop, mods, game_version=GAME_VERSION):
    """Every mod the game would load besides the runner, Workshop first. The runner is any folder with its Id: the plain
    runner folder, or a mod's dev folder (Mods/<Mod>DevTests), which the launcher keeps enabled itself."""
    found = []
    for source, base in (("Steam Workshop", Path(workshop)), ("Local", Path(mods))):
        for folder in sorted(base.iterdir()) if base.is_dir() else []:
            if not folder.is_dir():
                continue
            manifest = read_manifest(folder, game_version)
            if manifest and manifest.get("Id") and manifest["Id"] != RUNNER_ID:
                required = tuple(r["Id"] for r in manifest.get("RequiredMods") or [] if isinstance(r, dict) and r.get("Id"))
                found.append(InstalledMod(source, folder.name, manifest["Id"], required))
    return found


def select_mods(mod_id, installed):
    """The mod under test plus its transitive RequiredMods, one installed folder per Id, and why the set cannot load.
    Ids match exactly, as the game compares them. OptionalMods stay out of the set."""
    by_id = {}
    for mod in installed:
        # A Local and a Workshop copy of one Id both load (the game only flags duplicates within a source), so keep one:
        # the Local copy, which is the developer's working build.
        if mod.mod_id not in by_id or (mod.source == "Local" and by_id[mod.mod_id].source != "Local"):
            by_id[mod.mod_id] = mod
    if mod_id not in by_id:
        return [], [f"the mod under test ({mod_id}) is not installed in Mods or the Workshop"]
    selected, problems, queue, seen = [], [], [mod_id], {mod_id}
    while queue:
        mod = by_id[queue.pop(0)]
        selected.append(mod)
        for dependency in mod.required:
            if dependency in seen:
                continue
            seen.add(dependency)
            if dependency in by_id:
                queue.append(dependency)
            else:
                problems.append(f"{mod.mod_id} requires {dependency}, which is not installed")
    return selected, problems


def disable_values(mods, keep=()):
    """Isolation (D3): a 1 for each kept mod's enable key, so a mod the player switched off still loads, and a 0 for
    every other installed mod."""
    return {unity_pref_name(mod.enabled_key): [4, 1 if mod in keep else 0] for mod in mods}  # 4 = REG_DWORD


# ModSorter orders mods by (sorted index - ModPriority), and ModCodeStarter runs the starters in that order. A priority above
# any index puts the runner's starter first, so its log hook sees every error the mod's starter logs. The game rewrites the
# value after sorting; the exact restore puts it back.
RUNNER_PRIORITY = 100000


def dev_folder_name(mod_id):
    """Mods/<Mod>DevTests: the folder that holds the runner and the mod's DevTests DLL for a run, beside the production
    folder, which a run never touches. A run without a mod under test uses the plain runner folder."""
    return re.sub(r"[^\w.-]", "", mod_id) + "DevTests" if mod_id else RUNNER_FOLDER


def dev_folder_keys(folder):
    """The raw PlayerPrefs keys a run writes for its dev folder: enabled, whatever the player's list says (a new folder
    loads by default, but isolation doesn't leave that to chance), and its starter first."""
    return {f"ModEnabled.Local.{folder}.{RUNNER_ID}": 1, f"ModPriority.Local.{folder}.{RUNNER_ID}": RUNNER_PRIORITY}


def prefs_left_changed(snapshot, current):
    """PlayerPrefs value names that still differ from the snapshot after a restore."""
    removals, writes = restore_plan(snapshot, current)
    return sorted(set(removals) | set(writes))


def mod_assemblies(folder):
    """Names of the assemblies in a mod folder: the game loads every *.dll under it. Their namespaces mark the mod's errors."""
    return sorted({p.stem for p in Path(folder).rglob("*.dll")})


# ---- Request, install and launch -------------------------------------------------------------------------------------------

def build_request(run_id, run_dir, batch, map_name, speed, hours, deadline_ms, probe_prefs=None, mod_name=None,
                  mod_assemblies=(), keep_open=False, fixture_dir=None):
    """probe_prefs maps each enable key the launcher wrote (raw, as PlayerPrefs.HasKey takes it) to the value written; the
    starter refuses the run if the game sees any of them missing or different. mod_name and mod_assemblies let the runner
    recognise errors naming the mod under test (its ErrorMarker falls back to mod_name). fixture_dir is where a batch's
    relative Fixture name is looked up before the run folder (the mod's DevTests/Fixtures)."""
    return {"RunId": run_id, "RunDir": str(run_dir), "Batch": batch, "Map": map_name,
            "FixtureDir": str(fixture_dir) if fixture_dir else None,
            "SettlementName": f"DevTests-{run_id}", "Speed": speed, "GameHours": hours, "DeadlineUtcMs": deadline_ms,
            "ProbePrefs": dict(probe_prefs or {}), "ModName": mod_name, "ModAssemblies": list(mod_assemblies),
            "KeepOpen": keep_open}


def request_text(request):
    """request.json as installed; launcher.json records its hash."""
    return json.dumps(request, indent=2)


def runner_manifest():
    return {"Name": "Timberborn Dev Tests (developer only)", "Version": "0.1.0", "Id": RUNNER_ID, "MinimumGameVersion": "1.1.0.0",
            "Description": "Developer test runner installed and removed by tbtest.py. Does nothing without request.json.",
            "RequiredMods": []}


def is_runner_folder(folder):
    """True for a folder this launcher may replace or delete: absent, empty, or holding the runner's manifest."""
    folder = Path(folder)
    if not folder.exists():
        return True
    if (folder / "manifest.json").is_file():
        return manifest_id(folder) == RUNNER_ID
    return not any(folder.iterdir())


def remove_runner_folder(folder):
    folder = Path(folder)
    if not is_runner_folder(folder):
        raise RuntimeError(f"{folder} is not a runner folder (its manifest Id is not {RUNNER_ID}); left alone")
    shutil.rmtree(folder, ignore_errors=True)


def install_runner(dlls, mods_dir, request, folder=RUNNER_FOLDER):
    """A fresh dev folder (Mods/<Mod>DevTests, or the plain runner folder): the runner's manifest, exactly the DLLs given
    (the runner and the mod's DevTests DLL) and the request. The game loads every DLL in it, so nothing else goes in. The
    manifest goes first, so a folder a crash left mid-install is still recognised as the runner's."""
    target = Path(mods_dir) / folder
    remove_runner_folder(target)
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(json.dumps(runner_manifest(), indent=2), encoding="utf-8")
    for dll in dlls:
        shutil.copy2(dll, target / Path(dll).name)
    (target / "request.json").write_text(request_text(request), encoding="utf-8")
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


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dev_problems(config, production_folder, dev_folder):
    """Why a run of this mod cannot install its dev folder, checked before anything changes."""
    problems = []
    if config.dev_build and not config.dev_build.is_file():
        problems.append(f"build DevTests first: {config.dev_build} is missing (devBuild in devtests.json)")
    # A DevTests DLL copied into the production folder by hand (the old route) would load twice beside the dev folder's.
    problems += [f"{p}; remove it from the production folder: the launcher installs the DevTests DLL into Mods/{Path(dev_folder).name}"
                 for dll in sorted(Path(production_folder).rglob("*.dll")) if (p := developer_dll_problem(dll))]
    if not is_runner_folder(dev_folder):
        problems.append(f"{dev_folder} already holds another mod; the launcher needs that folder for the dev DLLs")
    return problems


# ---- Summary ---------------------------------------------------------------------------------------------------------------

def case_lines(cases, batches):
    """One line per case, as the runner's Report.cs records it. A diagnostic case names the result it was meant to report; a
    case that didn't pass shows its steps and logged errors; gameplay skips are listed again under "Not covered"."""
    lines = []
    for case in cases:
        result, diagnostic = str(case.get("Result")), case.get("Diagnostic")
        coverage = f" [{case.get('CoverageReason') or 'unclassified'}]" if result == "skip" else ""
        intended = ""
        if diagnostic:
            mismatch = "" if result == case.get("ExpectedResult") else ", NOT AS INTENDED"
            intended = f" (intended {case.get('ExpectedResult')}{mismatch})"
        lines.append(f"  {result.upper()}{coverage} {case.get('Id')}{intended}" + (f": {case['Reason']}" if case.get("Reason") else ""))
        if case.get("Observed"):
            lines.append(f"    observed {json.dumps(case['Observed'])[:400]}")
        if result != "pass":
            lines += [f"      {step}" for step in case.get("Steps") or []]
        if case.get("LoggedErrors"):
            first = [e for e in case.get("Evidence") or [] if e.startswith("logged error:")][:3]
            lines.append(f"    {case['LoggedErrors']} logged error(s): " + "; ".join(first))
        if not diagnostic and case.get("FixedGaps"):
            lines.append(f"  KNOWN GAP NOW HOLDS in {case.get('Batch')}/{case.get('Id')}: {case['FixedGaps']} step(s) marked FIXED; make each a Step")
    for batch in batches:
        if batch.get("Status") != "complete":
            lines.append(f"  BATCH {batch.get('Id')} {batch.get('Status')}: {batch.get('Reason')}")
    checks = [c for c in cases if c.get("Diagnostic")]
    if checks:
        matched = sum(1 for c in checks if c.get("Result") == c.get("ExpectedResult"))
        lines.append(f"  diagnostic: {matched} of {len(checks)} reported as intended")
    # A skip is not coverage, even in a run reported as PASS.
    skipped = [c for c in cases if not c.get("Diagnostic") and c.get("Result") == "skip"]
    lines.append(f"  Not covered: {len(skipped)} skipped case(s)" if skipped else "  Not covered: none")
    lines += [f"    SKIP [{c.get('CoverageReason') or 'unclassified'}] {c.get('Batch')}/{c.get('Id')}: {c.get('Reason')}" for c in skipped]
    return lines


def mod_error_lines(report):
    """Errors naming the mod under test, as the runner's Report.cs records them: those logged while the game loaded (until the
    main menu) and those logged during the run. Under the mod's FailOnModErrors either kind fails the run."""
    marker = report.get("errorMarker")
    if not marker:
        return ["  Startup: not checked; no mod under test (run with --config)"]
    counted = " (FAILS the run)" if report.get("failOnModErrors") else " (not counted against the result)"
    startup = report.get("startupModErrors") or []
    if startup:
        lines = [f"  Startup: {len(startup)} error(s) naming '{marker}' while the game loaded{counted}"]
        lines += [f"    STARTUP ERROR {line}" for line in startup[:5]]
    else:
        lines = [f"  Startup: no errors naming '{marker}' while the game loaded"]
    logged, naming = report.get("loggedErrors") or 0, report.get("modErrors") or 0
    if logged:
        lines.append(f"  Logged errors: {logged} during the run, {naming} naming '{marker}'" + (counted if naming else ""))
    return lines


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
        lines += case_lines(report.get("cases") or [], report.get("batches") or [])
        lines += mod_error_lines(report)
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


# ---- Evidence and release ----------------------------------------------------------------------------------------------------

def developer_dll_problem(dll):
    """Why a DLL is developer-only (a DevTests DLL, or one that references the runner), or None for production code."""
    if "devtests" in dll.name.lower():
        return f"DevTests assembly present: {dll}"
    data = dll.read_bytes()
    if RUNNER_ID.encode() in data or RUNNER_ID.encode("utf-16-le") in data:
        return f"runner reference found in {dll}"
    return None


def release_problems(mod_dir):
    """Developer test files in a mod package: a DevTests DLL, a DLL that references the runner, or the runner's own files."""
    mod_dir = Path(mod_dir)
    problems = [p for dll in sorted(mod_dir.rglob("*.dll")) if (p := developer_dll_problem(dll))]
    problems += [f"runner request present: {p}" for p in sorted(mod_dir.rglob("request.json"))]
    for manifest in sorted(mod_dir.rglob("manifest.json")):
        try:
            runner = json.loads(manifest.read_text(encoding="utf-8-sig")).get("Id") == RUNNER_ID
        except ValueError:
            runner = False
        if runner:
            problems.append(f"runner manifest present: {manifest}")
    return problems


def mod_build(mod_dir):
    """What a run of the mod measured: the SHA-256 of each production DLL in its folder (relative path, lower case) and one
    hash over them. Developer DLLs are left out, so a package that still holds one is compared on its production code
    (release-check fails it for the developer DLL separately)."""
    mod_dir = Path(mod_dir)
    dlls = {p.relative_to(mod_dir).as_posix().lower(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(mod_dir.rglob("*.dll")) if not developer_dll_problem(p)}
    combined = hashlib.sha256("".join(f"{name}\0{dlls[name]}\n" for name in sorted(dlls)).encode("utf-8")).hexdigest()
    return {"hash": combined, "dlls": dlls}


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def mod_runs(evidence_root, mod_id):
    """Run folders whose launcher tested this mod (launcher.json "modUnderTest"; None for runs without --config), newest
    first. The runs folder is shared by every mod, so a case Id another mod also uses never counts, and a renamed mod keeps
    its runs."""
    return [folder for folder in reversed(core.run_dirs(evidence_root, RUN_FILES))
            if (read_json(folder / "launcher.json") or {}).get("modUnderTest") == mod_id]


def newest_batch_list(evidence_root, mod_id, dev_hash=None):
    """(run folder, batches.json) of the newest run of this mod that wrote a batch list, or None; with dev_hash, only a run
    of that DevTests build. The runner writes batches.json into each run folder when it reaches the main menu."""
    for folder in mod_runs(evidence_root, mod_id):
        listed = read_json(folder / "batches.json")
        if listed is not None and (dev_hash is None or (read_json(folder / "launcher.json") or {}).get("devBuildHash") == dev_hash):
            return folder, listed
    return None


def current_dev_hash(config):
    """The hash of the DevTests DLL in the working tree, or None when there is none to read."""
    return sha256(config.dev_build) if config and config.dev_build and config.dev_build.is_file() else None


def perf_problems(mod_dir, mod_id, evidence_root, dev_hash):
    """D8: the perf.* cases of the current DevTests build (from a run of that build's batch list, diagnostic batches left
    out) must have passed in their newest run, and that run must have measured the DLLs in this package. Mirrors
    rimtest.py's perf_problems, which reads its list the same way, without the shared Dubs batch, which Timberborn has no
    counterpart for. Returns (problems, passing summaries, warnings)."""
    if not mod_id:
        return [f"no manifest Id in {mod_dir}; pass --config so release-check knows which mod's perf runs to read"], [], []
    if dev_hash is None:
        return [f"no DevTests build to read {mod_id}'s perf.* cases from; pass --config with devBuild in devtests.json, "
                "and build DevTests"], [], []
    newest = newest_batch_list(evidence_root, mod_id, dev_hash)
    if newest is None:
        return [f"no batch list from the current DevTests build of {mod_id}; run any of its batches with --config first "
                "(the game writes the list)"], [], []
    wanted = {case: f"run {batch['id']}" for batch in newest[1].get("batches") or [] if not batch.get("diagnostic")
              for case in batch.get("cases") or [] if case.startswith("perf.")}
    if not wanted:
        return [], [], ["no perf.* cases; time the mod's costly paths with PerfTiming in a case whose Id starts with perf."]
    found = core.newest_cases(mod_runs(evidence_root, mod_id), wanted)
    shipped = mod_build(mod_dir)["hash"]
    problems, passed = [], []
    for case_id, command in wanted.items():
        if case_id not in found:
            problems.append(f"no run of {case_id}; {command}")
            continue
        folder, _, case = found[case_id]
        measured = ((read_json(folder / "launcher.json") or {}).get("modBuild") or {}).get("hash")
        if measured != shipped:
            problems.append(f"newest {case_id} run {folder.name} measured a different build of {mod_id}; {command}")
        elif case.get("Result") != "pass":
            problems.append(f"{case_id} in run {folder.name} did not pass ({case.get('Result')}): "
                            f"{case.get('Reason') or case.get('Evidence') or 'see report.json'}")
        else:
            passed.append(f"{case_id} in run {folder.name}")
    return problems, passed, []


def list_batches(evidence_root, mod_id, dev_hash=None):
    """The batches from the newest run of this mod (mod_id None: runs without --config). dev_hash is the working tree's
    DevTests build, to say when the list came from another one."""
    newest = newest_batch_list(evidence_root, mod_id)
    if newest:
        folder, listed = newest
        print(f"Batches from run {folder.name}:")
        if (read_json(folder / "launcher.json") or {}).get("devBuildHash") != dev_hash:
            print("Note: this list is from a different DevTests build than the one in the working tree.")
        for entry in listed.get("batches") or []:
            print(f"{entry['id']}: {len(entry.get('cases') or [])} cases" + (" (runner self-check)" if entry.get("diagnostic") else ""))
        if listed.get("runAll"):
            print("run-all order: " + ", ".join(listed["runAll"]))
        return core.PASS
    print("No batch list yet: the game writes it each time a run reaches the main menu, so it appears after the first run.")
    return core.NO_MATCH


# ---- Commands --------------------------------------------------------------------------------------------------------------

def release_check(mod_dir, config, paths, evidence_root=EVIDENCE):
    """D8: the package holds no developer test files, and the current DevTests build's perf.* cases passed against the
    DLLs it ships. The default package is the installed copy the run would load. The mod is the package's manifest Id, or
    --config's; the DevTests build is --config's devBuild."""
    if mod_dir is None:
        if config is None:
            print("REFUSED: name the mod folder to check, or pass --config")
            return core.REFUSED
        selected, problems = select_mods(config.mod_id, installed_mods(paths.workshop, paths.mods))
        if not selected:
            print("REFUSED:", problems[0])
            return core.REFUSED
        mod_dir = paths.mod_folder(selected[0])
    if not Path(mod_dir).is_dir():
        print(f"REFUSED: no mod folder at {mod_dir}")
        return core.REFUSED
    problems = release_problems(mod_dir)
    perf, measured, warnings = perf_problems(mod_dir, manifest_id(Path(mod_dir)) or (config and config.mod_id), evidence_root,
                                             current_dev_hash(config))
    for problem in problems + perf:
        print("FAIL:", problem)
    if not problems:
        print("PASS: no developer test runner in", mod_dir)
    for line in measured if not perf else []:
        print("PASS: perf", line)
    for warning in warnings:
        print("WARN:", warning)
    return core.FAILED if problems or perf else core.PASS


def recover(state_file, mods_dir, prefs):
    """Undo what a run left behind (its launcher was killed before its finally block): the PlayerPrefs key back to the
    run's snapshot exactly, and the run's dev folder removed. Call only while Timberborn is closed. None when nothing was
    left."""
    state_file = Path(state_file)
    if not state_file.is_file():
        return None
    state = json.loads(state_file.read_text(encoding="utf-8"))
    changed = prefs.restore(state["prefs"])
    # A state file written before dev folders existed means the plain runner folder.
    folder = Path(mods_dir) / state.get("devFolder", RUNNER_FOLDER)
    remove_runner_folder(folder)
    state_file.unlink()
    return f"Restored {changed} PlayerPrefs value(s) left by run {state.get('runId')}; removed {folder}."


def restore(paths, prefs):
    if core.pids(PROCESS):
        print("REFUSED: Timberborn is running; close it first (Unity writes PlayerPrefs on exit).")
        return core.REFUSED
    print(recover(STATE, paths.mods, prefs) or "Nothing to restore.")
    return core.PASS


def refusal(paths):
    if not core.pids("steam.exe"):
        return "Steam is not running; the game needs it"
    if not paths.game_dir.is_dir():
        return f"no Timberborn at {paths.game_dir}; set gameDir in {LOCAL_FILE.name} or TIMBERBORN_DIR"
    return None


RUNNING_REFUSAL = ("Timberborn is running; the launcher only drives a game it starts itself, and Steam allows one game at "
                   "a time")


def run(args, paths, prefs, config=None):
    if core.pids(PROCESS):
        print("REFUSED:", RUNNING_REFUSAL)
        return core.REFUSED
    # Restore at the next start (D3): a launcher killed mid-run left the player's mods disabled.
    recovered = recover(STATE, paths.mods, prefs)
    if recovered:
        print(recovered, flush=True)
    reason = refusal(paths)
    if reason:
        print("REFUSED:", reason)
        return core.REFUSED
    mods = installed_mods(paths.workshop, paths.mods)
    selected = []
    folder = dev_folder_name(config and config.mod_id)
    if config:
        selected, problems = select_mods(config.mod_id, mods)
        if problems:
            print(f"REFUSED: {config.name}'s mod set cannot load:\n  " + "\n  ".join(problems))
            return core.REFUSED
        problems = dev_problems(config, paths.mod_folder(selected[0]), paths.mods / folder)
        if problems:
            print("REFUSED: " + "\n  ".join(problems))
            return core.REFUSED
    dlls = build_runner() + ([config.dev_build] if config and config.dev_build else [])
    run_id = core.new_run_id(args.batch)
    run_dir = EVIDENCE / run_id
    started = time.monotonic()
    deadline = started + args.timeout
    # The dev folder is kept enabled and probed like every other key; its priority is not probed, because the game
    # rewrites it after sorting.
    probe = {m.enabled_key: 1 if m in selected else 0 for m in mods}
    probe.update({key: value for key, value in dev_folder_keys(folder).items() if key.startswith("ModEnabled.")})
    # selected[0] is the mod under test (select_mods starts from it).
    request = build_request(run_id, run_dir, args.batch, args.map, args.speed, args.hours, core.game_deadline(deadline),
                            probe, mod_name=config and config.name,
                            mod_assemblies=mod_assemblies(paths.mod_folder(selected[0])) if selected else (),
                            keep_open=args.keep_open, fixture_dir=config and config.fixtures)
    launcher = {"runId": run_id, "request": request, "problems": [], "modUnderTest": config and config.mod_id,
                "modsSelected": [m.enabled_key for m in selected], "modsDisabled": len(mods) - len(selected),
                "devFolder": str(paths.mods / folder),
                # The DLLs the game loads for the mod under test; release-check matches perf runs to a package by them.
                "modBuild": mod_build(paths.mod_folder(selected[0])) if selected else None,
                # What else the game loaded for this run: release-check reads the batch list only from runs of the
                # current DevTests build.
                "runnerHash": sha256(RUNNER_BUILD),
                "devBuildHash": sha256(config.dev_build) if config and config.dev_build else None,
                "requestHash": hashlib.sha256(request_text(request).encode("utf-8")).hexdigest()}
    if recovered:
        launcher["recovered"] = recovered
    # The build takes a while: a game the player started meanwhile must not be driven, or killed afterwards (D9).
    if core.pids(PROCESS):
        print("REFUSED:", RUNNING_REFUSAL)
        return core.REFUSED
    run_dir.mkdir(parents=True)
    snapshot = prefs.read()
    protected_before, reports_before = core.tree_snapshot(*paths.protected), core.tree_snapshot(paths.error_reports)
    timed_out = False
    print(f"Run {run_id}: evidence {run_dir}", flush=True)
    try:
        # Written first inside the try: from here on the finally block, or the next start, puts everything back.
        STATE.write_text(json.dumps({"runId": run_id, "prefs": snapshot, "devFolder": folder}), encoding="utf-8")
        timed_out = drive(args, paths, prefs, mods, selected, folder, dlls, request, run_dir, launcher, started, deadline)
    finally:
        launcher["wallSeconds"] = round(time.monotonic() - started, 1)
        # Only a game that appeared after the launch is the launcher's own.
        before = launcher.get("pidsBeforeLaunch")
        if before is not None:
            for pid in [p for p in core.pids(PROCESS) if p not in before]:
                subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, check=False)
        # Restore only with no game running at all: Unity writes PlayerPrefs on exit, so a game still open would undo it.
        if core.wait_for(lambda: not core.pids(PROCESS), 30):
            launcher["prefsRestored"] = prefs.restore(snapshot)
            remove_runner_folder(paths.mods / folder)
            STATE.unlink(missing_ok=True)
            left = prefs_left_changed(snapshot, prefs.read())
            if left:
                launcher["problems"].append(f"PlayerPrefs differ from the snapshot after the restore: {left[:5]}")
        else:
            launcher["problems"].append("Timberborn did not exit; close it, then run `python tbtest.py restore`")
            left = []
        launcher["errorReportsMoved"] = core.move_new_files(reports_before, paths.error_reports, run_dir)
        changes = core.snapshot_diff(protected_before, core.tree_snapshot(*paths.protected), ignore=IGNORED_CHANGES)
        launcher["protectedChanges"] = changes + [f"PlayerPrefs {name}" for name in left]
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


def drive(args, paths, prefs, mods, selected, folder, dlls, request, run_dir, launcher, started, deadline):
    """Isolate, install, launch and wait for the report. True when the run hit its time limit."""
    # Isolation only writes values; the finally block in run() restores the snapshot taken before this.
    dev_keys = {unity_pref_name(key): [4, value] for key, value in dev_folder_keys(folder).items()}  # 4 = REG_DWORD
    prefs.apply([], {**disable_values(mods, keep=selected), **dev_keys})
    install_runner(dlls, paths.mods, request, folder)
    command = launch_command(steam_exe(), run_dir / "Player.log")
    launcher["command"] = command
    before = core.pids(PROCESS)
    launcher["pidsBeforeLaunch"] = before
    subprocess.Popen(command)
    pid = core.wait_for(lambda: next((p for p in core.pids(PROCESS) if p not in before), None), args.startup_timeout)
    if not pid:
        launcher["problems"].append(f"Timberborn.exe did not start within {args.startup_timeout} s of steam -applaunch")
        return False
    launcher["pid"] = pid
    launcher["processSeenAfterSeconds"] = round(time.monotonic() - started, 1)
    print(f"Timberborn started (pid {pid}).", flush=True)
    process = core.GameProcess(pid)
    report_path = run_dir / "report.json"
    # The runner's starter writes a heartbeat within a second of activating, or the report if it refused at once.
    runner_seen = (run_dir / "heartbeat.json", report_path)
    startup_deadline = started + args.startup_timeout
    try:
        while process.alive() and not report_path.is_file() and time.monotonic() < deadline:
            if time.monotonic() >= startup_deadline and not any(p.is_file() for p in runner_seen):
                launcher["problems"].append(
                    f"STARTUP FAILED: the runner did not start in the game within {args.startup_timeout} s; see Player.log "
                    "(a large mod set may need a longer --startup-timeout)")
                print(launcher["problems"][-1], flush=True)
                process.kill()
                return False
            time.sleep(1)
        if report_path.is_file() and args.keep_open:
            print("Run finished; the game is left paused. Close Timberborn to finish cleanup.", flush=True)
            while not process.wait(3600):
                pass
        elif report_path.is_file() and not process.wait(60):
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
    parser.add_argument("--config", type=Path,
                        help="the mod's DevTests/devtests.json; run keeps that mod and its RequiredMods enabled (default: no mods)")
    commands = parser.add_subparsers(dest="command", required=True)
    launch = commands.add_parser("run", help="launch Timberborn and run a batch in a new game (user's terminal only)")
    launch.add_argument("batch", help="batch to run: smoke, diagnostic or one of the mod's")
    launch.add_argument("--map", help="built-in map for the new game, instead of the batch's own (_Mini by default)")
    launch.add_argument("--hours", type=float, default=2.0, help="game hours the smoke batch runs")
    launch.add_argument("--speed", type=float, default=30.0, help="game speed while it runs (dev speeds: 30, 99)")
    launch.add_argument("--timeout", type=int, default=600,
                        help=f"wall-clock seconds for the whole run; the game closes it {core.DEADLINE_GRACE} s before and is killed at it")
    launch.add_argument("--startup-timeout", type=int, default=120,
                        help="seconds a newly launched game has to start the runner, from steam -applaunch")
    launch.add_argument("--keep-open", action="store_true", help="leave the game paused after the run; close it to finish cleanup")
    commands.add_parser("restore", help="put back the PlayerPrefs key and remove the runner after an interrupted run")
    show = commands.add_parser("latest", help="print the latest run's summary, or that it has no report, without launching Timberborn")
    show.add_argument("--batch")
    timing = commands.add_parser("timings", help="per-batch wall clock of a run, slowest first, without launching Timberborn")
    timing.add_argument("run", nargs="?", help="run folder name or path (default: the latest run)")
    commands.add_parser("list", help="list the mod's batches from its newest run, without launching Timberborn")
    check = commands.add_parser("release-check", help="verify a mod folder contains no developer test runner or DevTests DLL, and its "
                                   "perf.* cases passed on the DLLs it ships")
    check.add_argument("mod_dir", nargs="?", type=Path, help="the package to check (default: the installed folder of --config's mod)")
    pruner = commands.add_parser("prune", help="delete old run folders")
    pruner.add_argument("--keep", type=int, default=20, help="newest run folders to keep")
    args = parser.parse_args(argv)
    if args.command == "latest":
        return core.latest(EVIDENCE, args.batch, run_files=RUN_FILES, unfinished_files=LAUNCHER_FILES)
    if args.command == "timings":
        return core.timings(EVIDENCE, args.run, run_files=RUN_FILES)
    if args.command == "prune":
        if args.keep < 1:
            parser.error("--keep must be at least 1")
        return core.prune(EVIDENCE, args.keep, run_files=RUN_FILES)
    config = load_config(args.config) if args.config else None
    if args.command == "list":
        if config:
            print("Mod under test: " + config.mod_id)
        return list_batches(EVIDENCE, config and config.mod_id, current_dev_hash(config))
    paths, prefs = resolve_paths(), RegistryPrefs()
    if args.command == "release-check":
        return release_check(args.mod_dir, config, paths)
    if args.command == "restore":
        return restore(paths, prefs)
    if args.timeout <= 0 or args.startup_timeout <= 0:
        parser.error("--timeout and --startup-timeout must be greater than zero")
    WORK.mkdir(parents=True, exist_ok=True)
    return run(args, paths, prefs, config)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    return core.guarded(run_command, argv)


if __name__ == "__main__":
    sys.exit(main())
