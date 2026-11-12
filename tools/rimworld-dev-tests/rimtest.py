"""Shared launcher for the RimWorld developer test harness (RimWorldDevTests).

Configured per mod by a devtests.json file:

  python rimtest.py --config <mod>/DevTests/devtests.json run <batch|run-all> [--mods SET] [--seed N] [--timeout S] [--quit-on-finish] [--keep-open]
  python rimtest.py --config ... close-session | latest [--batch B] | release-check [mod_dir] | install-dev | remove-dev

`run` reuses an idle launcher-owned RimWorld session at the main menu, or launches one, and sends the batch to it. The game
window stays open with the progress panel; finish with close-session, which also removes the DevTests DLL.
--quit-on-finish and --keep-open use a single fresh process instead.

Mod lists: the game runs with -savedatafolder=work/userdata/<argPrefix>, so the player's ModsConfig, Prefs, mod settings
and saves are never written. Each launch writes that folder's ModsConfig from a named set in devtests.json ("modSets",
"batchModSets"): a batch uses its mapped set or "default", run-all the union of "default" and every mapped set, and
--mods any set. The reserved set "full" copies the player's active list and mod settings, adding the mod under test if
missing. Sets are validated (installed, dependencies, load order) before launch, and an idle session with a different set
is closed and relaunched. Optional per-set mod settings: <mod>/DevTests/modsettings/<set>/Mod_*.xml.

Every run refuses while an unrelated RimWorld is open or while the installed mod differs from the working tree, enforces a
wall-clock limit, and checks that no user save, autosave setting or the player's ModsConfig changed and the loaded build matches.
Exit codes: 0 pass, 1 failures or isolation breach, 2 timeout or no report, 3 refusal.
Agent entry point: python rimtest.py guide [topic] (no config required).
Window recording is shared; showcase content and triage stay in each mod.
"""
import argparse
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

HARNESS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_ROOT))
from recording import Recording, find_ffmpeg

DEFAULT_GAME_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\RimWorld")


def resolve_game_dir():
    """RIMWORLD_DIR, then gameDir in the untracked rimtest.local.json, then the default Steam location."""
    if os.environ.get("RIMWORLD_DIR"):
        return Path(os.environ["RIMWORLD_DIR"])
    local = HARNESS_ROOT / "rimtest.local.json"
    if local.exists():
        game_dir = json.loads(local.read_text(encoding="utf-8")).get("gameDir")
        if game_dir:
            return Path(game_dir)
    return DEFAULT_GAME_DIR


GAME_DIR = resolve_game_dir()
GAME_VERSION = "1.7"
WORKSHOP_DIR = GAME_DIR.parents[1] / "workshop/content/294100"
SAVE_DATA = Path.home() / "AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios"
USER_MODS_CONFIG = SAVE_DATA / "Config/ModsConfig.xml"
AUTOSAVE_PREFS = ("autosaveIntervalDays", "autosavesCount")
LOG_TAIL_LINES = 40
DEFAULT_SET, FULL_SET, RUN_ALL = "default", "full", "run-all"


@dataclass
class Config:
    name: str
    arg_prefix: str
    root: Path
    mod_dir: Path
    # The working-tree folder laid out like the installed mod: the repo root, or a built package ("runtimeRoot").
    runtime_root: Path
    production_dll: Path
    # Where the developer DLLs go: the installed folder holding the production DLL (load folders such as v1.6/Assemblies).
    dev_assemblies: Path
    dev_build: Path
    dev_project: Path
    evidence_root: Path
    runtime_folders: tuple
    runtime_files: tuple
    game_command: list
    userdata: Path
    package_id: str
    mod_sets: dict
    batch_mod_sets: dict
    process_name: str = "RimWorld.exe"
    # The player's real data: never written by a run, and checked afterwards to prove it.
    saves_dir: Path = SAVE_DATA / "Saves"
    prefs_path: Path = SAVE_DATA / "Config/Prefs.xml"
    # 1.7's engine always logs here, ignoring -savedatafolder and Unity's -logFile (observed 2026-11-09, 1.7.5000).
    player_log: Path = SAVE_DATA / "Logs/Player.log"

    def launch_command(self):
        return self.game_command + [f"-savedatafolder={self.userdata}"]

    @property
    def dev_dll(self):
        return self.dev_build.name

    @property
    def harness_build(self):
        return self.dev_build.with_name("RimWorldDevTests.dll")

    @property
    def developer_builds(self):
        return (self.dev_build, self.harness_build)

    @property
    def save_prefix(self):
        return self.arg_prefix.upper() + "Test-"

    def arg(self, name, value):
        return f"-{self.arg_prefix}{name}={value}"


def load_config(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent.parent  # <mod>/DevTests/devtests.json
    userdata = HARNESS_ROOT / "work/userdata" / data["argPrefix"]
    about = read_about(root)
    return Config(name=data["name"], arg_prefix=data["argPrefix"], root=root, mod_dir=Path(data["modDir"]),
                  runtime_root=root / data.get("runtimeRoot", "."), production_dll=root / data.get("runtimeRoot", ".") / data["productionDll"], dev_assemblies=Path(data["modDir"]) / Path(data["productionDll"]).parent, dev_build=root / data["devBuild"],
                  dev_project=root / data.get("devProject", "DevTests"),
                  evidence_root=userdata / data["evidenceFolder"], runtime_folders=tuple(data["runtimeFolders"]),
                  runtime_files=tuple(data.get("runtimeFiles", ["LoadFolders.xml"])),
                  game_command=[str(GAME_DIR / "RimWorld.exe")], userdata=userdata,
                  package_id=about.package_id if about else "",
                  mod_sets={name: [i.lower() for i in ids] for name, ids in data.get("modSets", {}).items()},
                  batch_mod_sets=data.get("batchModSets", {}))


# ---- Mod sets ----------------------------------------------------------------------------------------------------------

@dataclass
class ModInfo:
    package_id: str
    name: str
    dependencies: list  # each entry lists the acceptable ids (packageId plus alternativePackageIds)
    load_after: set
    load_before: set


def _ids(element):
    return [li.text.strip().lower() for li in (element if element is not None else []) if li.text and li.text.strip()]


def _for_version(root, tag):
    """RimWorld uses <tagByVersion><v1.7> when it has an entry for the running version, else <tag>."""
    versioned = root.find(f"{tag}ByVersion/v{GAME_VERSION}")
    return versioned if versioned is not None else root.find(tag)


def read_about(folder):
    try:
        root = ET.parse(Path(folder) / "About/About.xml").getroot()
    except (OSError, ET.ParseError):
        return None
    package_id = (root.findtext("packageId") or "").strip().lower()
    if not package_id:
        return None
    dependencies = []
    dependency_list = _for_version(root, "modDependencies")
    for li in dependency_list if dependency_list is not None else []:
        options = [(li.findtext("packageId") or "").strip().lower()] + _ids(li.find("alternativePackageIds"))
        if options[0]:
            dependencies.append(options)
    return ModInfo(package_id, (root.findtext("name") or package_id).strip(), dependencies,
                   set(_ids(_for_version(root, "loadAfter")) + _ids(root.find("forceLoadAfter"))),
                   set(_ids(_for_version(root, "loadBefore")) + _ids(root.find("forceLoadBefore"))))


def mod_index():
    """Installed mods by packageId. Core/DLC first, then local Mods (the mod under test), then Workshop copies."""
    index = {}
    for base in (GAME_DIR / "Data", GAME_DIR / "Mods", WORKSHOP_DIR):
        for folder in sorted(base.iterdir()) if base.is_dir() else []:
            info = read_about(folder)
            if info and info.package_id not in index:
                index[info.package_id] = info
    return index


def active_mods(path):
    return _ids(ET.parse(path).getroot().find("activeMods"))


def merge_sets(lists):
    """Union that keeps each set's relative order: a missing id goes right after its predecessor in its own set."""
    merged = []
    for ids in lists:
        anchor = -1
        for package_id in ids:
            if package_id in merged:
                anchor = merged.index(package_id)
            else:
                anchor += 1
                merged.insert(anchor, package_id)
    return merged


@dataclass
class ModSelection:
    name: str
    mods: list
    settings_dirs: list

    def identity(self):
        settings = {p.name: sha256(p) for d in self.settings_dirs for p in sorted(d.glob("Mod_*.xml"))}
        return {"set": self.name, "mods": self.mods, "settings": settings}


def select_mods(config, batch, override=None):
    if DEFAULT_SET not in config.mod_sets:
        raise RuntimeError('devtests.json needs "modSets" with a "default" set; the runner no longer uses the player\'s mod list')
    if FULL_SET in config.mod_sets:
        raise RuntimeError(f'"{FULL_SET}" is reserved for the player\'s own mod list; rename that set in devtests.json')
    settings_root = config.root / "DevTests/modsettings"
    name = override or (None if batch == RUN_ALL else config.batch_mod_sets.get(batch, DEFAULT_SET))
    if name == FULL_SET:
        mods = active_mods(USER_MODS_CONFIG)
        if config.package_id not in mods:
            mods.append(config.package_id)
        return ModSelection(FULL_SET, mods, [SAVE_DATA / "Config"])
    if name is None:
        # Sets no batch maps to (optional integrations) are --mods variants, not run-all needs.
        names = [n for n in config.mod_sets if n == DEFAULT_SET or n in config.batch_mod_sets.values()]
        # Mod settings are process-wide: one launch cannot give each batch its own settings files.
        with_settings = [n for n in names if (settings_root / n).is_dir()]
        if with_settings and len(names) > 1:
            raise RuntimeError(f"run-all would merge mod sets with their own settings ({', '.join(with_settings)}) into one launch; "
                               "run each batch separately")
        return ModSelection("run-all union of " + ", ".join(names), merge_sets(config.mod_sets[n] for n in names),
                            [settings_root / n for n in names if (settings_root / n).is_dir()])
    if name not in config.mod_sets:
        raise RuntimeError(f"unknown mod set {name!r}; known: {', '.join(list(config.mod_sets) + [FULL_SET])}")
    return ModSelection(name, list(config.mod_sets[name]), [settings_root / name] if (settings_root / name).is_dir() else [])


def mod_problems(config, mods, index):
    problems, position = [], {}
    for i, package_id in enumerate(mods):
        if package_id in position:
            problems.append(f"{package_id} is listed twice")
        position.setdefault(package_id, i)
    if config.package_id not in position:
        problems.append(f"the mod under test ({config.package_id}) is not in the set")
    for package_id in position:
        info = index.get(package_id)
        if info is None:
            problems.append(f"{package_id} is not installed (Data, Mods or Workshop)")
            continue
        for options in info.dependencies:
            if not any(o in position for o in options):
                problems.append(f"{info.name} ({package_id}) requires {' or '.join(options)}")
        problems += [f"{package_id} must load after {o}" for o in sorted(info.load_after) if position.get(o, -1) > position[package_id]]
        problems += [f"{package_id} must load before {o}" for o in sorted(info.load_before) if -1 < position.get(o, -1) < position[package_id]]
    return problems


def prepare_userdata(config, selection):
    """Write the isolated save-data folder for this launch. The player's own Config is only read."""
    problems = mod_problems(config, selection.mods, index := mod_index())
    if problems:
        raise RuntimeError(f"mod set {selection.name!r} is not loadable:\n  " + "\n  ".join(problems))
    folder = config.userdata / "Config"
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / "Prefs.xml").is_file() and config.prefs_path.is_file():
        shutil.copy2(config.prefs_path, folder / "Prefs.xml")  # once; the harness owns this copy afterwards
    version = ET.parse(USER_MODS_CONFIG).getroot().findtext("version") if USER_MODS_CONFIG.is_file() else None
    # Every installed DLC must be "known", or RimWorld treats it as new and may enable it or open a dialog.
    expansions = [i for i in index if i.startswith("ludeon.rimworld.")]
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<ModsConfigData>"]
    lines += [f"  <version>{version}</version>"] if version else []
    lines += ["  <activeMods>"] + [f"    <li>{i}</li>" for i in selection.mods] + ["  </activeMods>"]
    lines += ["  <knownExpansions>"] + [f"    <li>{i}</li>" for i in expansions] + ["  </knownExpansions>", "</ModsConfigData>"]
    (folder / "ModsConfig.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for old in folder.glob("Mod_*.xml"):
        old.unlink()
    for source in selection.settings_dirs:
        for path in source.glob("Mod_*.xml"):
            shutil.copy2(path, folder / path.name)
    print(f"Mod set {selection.name!r}: {len(selection.mods)} mods, {len(list(folder.glob('Mod_*.xml')))} settings files; save data {config.userdata}")


def session_mods(config):
    path = config.evidence_root / "session-mods.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def restart_hint(config):
    if process_running(config.process_name):
        print("RimWorld relaunched itself while loading (a mod such as Load Them Last rewrote the load order). Close that "
              "game, fix the set's order in devtests.json, and run again.")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_manifest(config, root):
    root = Path(root)
    files = [p for name in config.runtime_folders for p in (root / name).rglob("*") if p.is_file()]
    files += [root / name for name in config.runtime_files if (root / name).is_file()]
    return {p.relative_to(root).as_posix().lower(): sha256(p) for p in files
            if p.suffix.lower() != ".pdb" and p.name not in (config.dev_dll, "RimWorldDevTests.dll")}


def manifest_hash(files):
    return hashlib.sha256("".join(f"{name}\0{files[name]}\n" for name in sorted(files)).encode("utf-8")).hexdigest()


def preflight(config):
    candidate, installed = runtime_manifest(config, config.runtime_root), runtime_manifest(config, config.mod_dir)
    differences = [n for n in sorted(candidate.keys() | installed.keys()) if candidate.get(n) != installed.get(n)]
    if differences:
        raise RuntimeError("installed mod differs from the working tree; review and deploy first:\n  " + "\n  ".join(differences))
    if not all(p.is_file() for p in config.developer_builds):
        raise RuntimeError(f"build DevTests first: dotnet build {config.dev_project} -c Release")
    return {"schema": 1, "runtimeHash": manifest_hash(candidate), "files": candidate, "developerHash": sha256(config.dev_build), "harnessHash": sha256(config.harness_build)}


def process_running(name):
    listing = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"], capture_output=True, text=True, check=False).stdout
    return name.lower() in listing.lower()


def snapshot_saves(saves_dir):
    return {p.name: sha256(p) for p in Path(saves_dir).iterdir() if p.is_file()} if Path(saves_dir).is_dir() else {}


def autosave_prefs(prefs_path):
    text = Path(prefs_path).read_text(encoding="utf-8", errors="replace") if Path(prefs_path).is_file() else ""
    return {k: (m.group(1) if (m := re.search(f"<{k}>(.*?)</{k}>", text)) else None) for k in AUTOSAVE_PREFS}


def user_config(config):
    return {**autosave_prefs(config.prefs_path), "ModsConfig.xml": sha256(USER_MODS_CONFIG) if USER_MODS_CONFIG.is_file() else None}


def snapshot(config):
    return preflight(config), snapshot_saves(config.saves_dir), user_config(config)


def run_problems(config, manifest, report, saves_before, prefs_before):
    problems = []
    saves_after, prefs_after = snapshot_saves(config.saves_dir), user_config(config)
    for name in sorted(set(saves_before) | set(saves_after)):
        if name.startswith(config.save_prefix) or saves_before.get(name) == saves_after.get(name):
            continue
        change = "added" if name not in saves_before else "removed" if name not in saves_after else "modified"
        problems.append(f"user save {change}: {name}")
    for key in AUTOSAVE_PREFS:
        if prefs_before[key] != prefs_after[key]:
            problems.append(f"autosave setting changed: {key} {prefs_before[key]} -> {prefs_after[key]}")
    if prefs_before["ModsConfig.xml"] != prefs_after["ModsConfig.xml"]:
        # The runner only writes its own save-data folder, so this points at another game or tool, not the harness.
        problems.append("the player's ModsConfig.xml changed during the run; check for another RimWorld or mod manager")
    if manifest_hash(runtime_manifest(config, config.mod_dir)) != manifest["runtimeHash"]:
        problems.append("installed runtime files changed during the run")
    environment = (report or {}).get("environment") or {}
    if report and report.get("status") != "refused" and environment:
        if environment.get("runtimeHash") != manifest["runtimeHash"]:
            problems.append("report runtime manifest does not match preflight")
        if (environment.get("modBuild") or {}).get("sha256") != sha256(config.production_dll):
            problems.append("report's loaded production DLL is not the candidate build")
    if environment:
        for key in ("developerHash", "harnessHash"):
            if environment.get(key) != manifest[key]:
                problems.append(f"report {key} does not match preflight")
    for problem in problems:
        print("ISOLATION FAIL:", problem)
    return problems


def tail(path, lines=LOG_TAIL_LINES):
    return "\n".join(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]) if Path(path).is_file() else f"(missing: {path})"


def print_summary(run_dir, manifest):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "deployment.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summary = run_dir / "summary.txt"
    if summary.is_file():
        print(f"Summary: {summary}")
        print(summary.read_text(encoding="utf-8"))


def print_diagnostics(config, run_dir):
    print(f"Progress file {run_dir / 'progress.json'}:\n{tail(run_dir / 'progress.json')}")
    print(f"Last {LOG_TAIL_LINES} lines of {config.player_log}:\n{tail(config.player_log)}")


def new_run_id(batch, seed):
    return f"{datetime.now():%Y%m%d-%H%M%S}-{re.sub(r'[^a-z0-9-]', '-', batch.lower())}-s{seed}"


# ---- Reusable session (session.json heartbeat + session-request.json inbox) ----------------------

@contextmanager
def session_lock(config):
    import msvcrt
    config.evidence_root.mkdir(parents=True, exist_ok=True)
    with (config.evidence_root / "session.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError("another launcher command is using the runner session") from error
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


class SessionProcess:
    """Hold the exact Windows process so timeout cleanup cannot target a reused PID."""

    def __init__(self, pid):
        from ctypes import wintypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.TerminateProcess.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.OpenProcess(0x100000 | 0x1000 | 0x0001, False, pid)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "could not open runner process")

    def alive(self):
        return self.api.WaitForSingleObject(self.handle, 0) == 258

    def kill(self):
        if self.alive():
            if not self.api.TerminateProcess(self.handle, 1):
                raise OSError(ctypes.get_last_error(), "could not stop timed-out runner process")
            self.api.WaitForSingleObject(self.handle, 5000)

    def close(self):
        self.api.CloseHandle(self.handle)


def session_status(config):
    path = config.evidence_root / "session.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return None


def send_session_request(config, session, command, **fields):
    path = config.evidence_root / "session-request.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"Session": session, "Command": command, **fields}), encoding="utf-8")
    temp.replace(path)


def clear_session(config):
    for build in config.developer_builds:
        (config.dev_assemblies / build.name).unlink(missing_ok=True)
    for name in ("session.json", "session-request.json", "session-mods.json"):
        (config.evidence_root / name).unlink(missing_ok=True)


def wait_session(config, process, token, deadline, after=0):
    while process.alive():
        status = session_status(config)
        if status and status["session"] == token and status["heartbeat"] > after:
            if status["state"] == "idle":
                return status
            if status["state"] == "unrelated-colony":
                raise RuntimeError("runner session has an unrelated colony open; it cannot accept a batch")
        if time.monotonic() >= deadline:
            raise TimeoutError("runner did not return to the main menu before the timeout")
        time.sleep(0.1)
    raise RuntimeError("runner process exited before reaching the main menu")


def run_session(config, batch, seed, timeout, mod_set=None):
    try:
        with session_lock(config):
            return _run_session(config, batch, seed, timeout, mod_set)
    except (OSError, ValueError, RuntimeError, ET.ParseError) as error:
        print("REFUSED:", error)
        return 3


def _run_session(config, batch, seed, timeout, mod_set):
    manifest, saves_before, prefs_before = snapshot(config)
    selection = select_mods(config, batch, mod_set)
    production_hash, developer_hash = sha256(config.production_dll), manifest["developerHash"]
    deadline = time.monotonic() + timeout
    reuse = False
    if process_running(config.process_name):
        status = session_status(config)
        if not status or time.time() * 1000 - status["heartbeat"] > 10000:
            raise RuntimeError("RimWorld is open without a responsive launcher session; leave that game untouched and close it before running batches")
        if status["productionHash"] != production_hash or status["developerHash"] != developer_hash or status.get("harnessHash") != manifest["harnessHash"]:
            raise RuntimeError("the open session loaded different DLLs; use close-session, then run the batch again")
        if status.get("runtimeHash") != manifest["runtimeHash"]:
            raise RuntimeError("the open session loaded different runtime files; close-session before running again")
        if (config.evidence_root / "session-request.json").exists():
            raise RuntimeError("the session already has a pending command; wait for it to finish")
        loaded = session_mods(config)
        # Compare what was loaded, not the set's name: run-all and a single batch often resolve to the same mods.
        if loaded and {k: loaded.get(k) for k in ("mods", "settings")} == {k: selection.identity()[k] for k in ("mods", "settings")}:
            reuse = True
            token = status["session"]
            process = SessionProcess(status["pid"])
            print(f"Reusing the open RimWorld runner session (mod set {selection.name!r}).")
        else:
            print(f"The open session loaded mod set {(loaded or {}).get('set', 'unknown')!r}; relaunching with {selection.name!r}.")
            _close_session(config)
    if not reuse:
        prepare_userdata(config, selection)
        clear_session(config)
        for build in config.developer_builds:
            shutil.copy2(build, config.dev_assemblies / build.name)
        token = uuid.uuid4().hex
        (config.evidence_root / "session-mods.json").write_text(json.dumps(selection.identity(), indent=2), encoding="utf-8")
        try:
            launched = subprocess.Popen(config.launch_command() + [config.arg("Session", token)])
            process = SessionProcess(launched.pid)
        except OSError:
            if not process_running(config.process_name):
                clear_session(config)
            raise
        print("Launched a reusable RimWorld runner session.")
    run_id = new_run_id(batch, seed) + "-" + uuid.uuid4().hex[:8]
    run_dir = config.evidence_root / run_id
    report_path, summary_path = run_dir / "report.json", run_dir / "summary.txt"
    timed_out, report, ready = False, None, False
    try:
        wait_session(config, process, token, deadline)
        print(f"Run {run_id}: evidence {run_dir}", flush=True)
        send_session_request(config, token, "run", RunId=run_id, Batch=batch, Seed=seed)
        while process.alive():
            if summary_path.is_file():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                # Completion is published before the scene change finishes; wait for a newer idle heartbeat so the next
                # command can submit at once.
                wait_session(config, process, token, deadline, after=summary_path.stat().st_mtime * 1000)
                ready = True
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("batch exceeded its wall-clock limit")
            time.sleep(0.1)
    except TimeoutError as error:
        timed_out = True
        print(f"Game timed out after {timeout} s: {error}; stopping runner session.")
        process.kill()
    except RuntimeError:
        if process.alive():
            raise
        print("Runner process exited before the command completed.")
        restart_hint(config)
    finally:
        if not process.alive():
            clear_session(config)
        process.close()
    print_summary(run_dir, manifest)
    problems = run_problems(config, manifest, report, saves_before, prefs_before)
    if timed_out or report is None or not ready:
        print_diagnostics(config, run_dir)
        return 2
    print("RimWorld is at the main menu, ready for the next batch. Use close-session when finished.")
    if report.get("status") == "refused":
        return 3
    return 0 if report.get("overallPass") and not problems else 1


def close_session(config):
    try:
        with session_lock(config):
            if not process_running(config.process_name):
                clear_session(config)
                print("RimWorld is closed; removed DevTests and stale session files.")
                return 0
            _close_session(config)
            print("Closed the runner session and removed DevTests.")
            return 0
    except (OSError, ValueError, RuntimeError) as error:
        print("REFUSED:", error)
        return 3


def _close_session(config):
    """Close the idle launcher session; the caller holds session_lock."""
    status = session_status(config)
    if not status or time.time() * 1000 - status["heartbeat"] > 10000 or status["state"] != "idle":
        raise RuntimeError("only an idle launcher session at the main menu can be closed")
    process = SessionProcess(status["pid"])
    try:
        send_session_request(config, status["session"], "close")
        deadline = time.monotonic() + 30
        while process.alive():
            if time.monotonic() >= deadline:
                raise RuntimeError("runner did not close; DevTests remains installed")
            time.sleep(0.1)
        clear_session(config)
    finally:
        process.close()


# ---- Single fresh process -----------------------------------------------------------------------------------------------

def run_once(config, batch, seed, timeout, keep_open=False, record=False, ffmpeg=None, show_ui=False, mod_set=None):
    if process_running(config.process_name):
        print(f"REFUSED: {config.process_name} is already running. Close it, or use run without --quit-on-finish to reuse a runner session.")
        return 3
    try:
        manifest, saves_before, prefs_before = snapshot(config)
        prepare_userdata(config, select_mods(config, batch, mod_set))
        clear_session(config)  # a fresh process shares the folder; drop any stale session files
        if record:
            ffmpeg = find_ffmpeg(ffmpeg)
    except (OSError, ValueError, RuntimeError, ET.ParseError, subprocess.SubprocessError) as error:
        print("REFUSED:", error)
        return 3
    run_id = new_run_id(batch, seed)
    run_dir = config.evidence_root / run_id
    installed_dev = config.dev_assemblies / config.dev_dll
    recording = Recording(ffmpeg, run_dir, timeout, hide_ui=not show_ui) if record else None
    print(f"Run {run_id}: evidence {run_dir}", flush=True)
    for build in config.developer_builds:
        shutil.copy2(build, config.dev_assemblies / build.name)
    timed_out = False
    try:
        process = subprocess.Popen(config.launch_command() + [config.arg("Test", batch), config.arg("Seed", seed), config.arg("RunId", run_id)]
                                   + ([config.arg("KeepOpen", "true")] if keep_open else [])
                                   + ([config.arg("Record", "true")] if record else [])
                                   + ([config.arg("ShowUI", "true")] if show_ui else []))
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if recording:
                recording.poll()
            if keep_open and (run_dir / "summary.txt").is_file() and (not recording or recording.done):
                print("Run finished; the game is left paused. Close RimWorld to finish cleanup.", flush=True)
                process.wait()
                break
            if time.monotonic() >= deadline:
                timed_out = True
                process.kill()
                process.wait()
                break
            time.sleep(0.25)
    finally:
        if recording:
            recording.close()
        for build in config.developer_builds:
            (config.dev_assemblies / build.name).unlink(missing_ok=True)
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    print_summary(run_dir, manifest)
    if timed_out or report is None:
        print(f"Game {'timed out after ' + str(timeout) + ' s and was killed' if timed_out else 'exited without a report'}.")
        print_diagnostics(config, run_dir)
        restart_hint(config)
    problems = run_problems(config, manifest, report, saves_before, prefs_before)
    if timed_out or report is None:
        return 2
    if report.get("status") == "refused":
        return 3
    return 0 if report.get("overallPass") and not problems and not (recording and recording.error) else 1


def release_problems(config, mod_dir):
    problems = []
    marker = f"{config.arg_prefix}Test"
    for dll in Path(mod_dir).rglob("*.dll"):
        if "devtests" in dll.name.lower():
            problems.append(f"DevTests assembly present: {dll}")
            continue
        data = dll.read_bytes()
        if marker.encode() in data or marker.encode("utf-16-le") in data:
            problems.append(f"runner entry point found in {dll}")
    return problems


def latest(config, batch=None):
    for path in sorted(config.evidence_root.glob("*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        request = json.loads(path.read_text(encoding="utf-8")).get("request", {})
        if batch and request.get("Batch") != batch:
            continue
        print(path.parent / "summary.txt")
        print((path.parent / "summary.txt").read_text(encoding="utf-8"))
        return 0
    print("No matching completed report found.")
    return 1


GUIDE_TOPICS = {
    "index": "AGENTS.md",
    "authoring": "docs/authoring.md",
    "recipes": "docs/recipes/index.md",
    "placement": "docs/recipes/placement.md",
    "beds": "docs/recipes/beds.md",
    "measurements": "docs/recipes/measurements.md",
    "environment": "docs/recipes/environment.md",
    "maintaining": "docs/maintaining.md",
    "recording": "docs/recording.md",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, help="the mod's DevTests/devtests.json (required except for guide)")
    commands = parser.add_subparsers(dest="command", required=True)
    guide = commands.add_parser("guide", help="agent instructions and searchable setup recipes; no game or config needed")
    guide.add_argument("topic", nargs="?", default="index", choices=GUIDE_TOPICS, help="read only the relevant topic")
    launch = commands.add_parser("run", help="run a batch, or run-all; reuse the runner session or launch one")
    launch.add_argument("batch")
    launch.add_argument("--mods", metavar="SET", help="mod set from devtests.json, or full for the player's list (default: the batch's set)")
    launch.add_argument("--seed", type=int, default=1)
    launch.add_argument("--timeout", type=int, default=900, help="wall-clock seconds before the game is killed")
    launch.add_argument("--quit-on-finish", action="store_true", help="use a fresh process and close it after the run")
    launch.add_argument("--record", action="store_true", help="record the game window to build.mp4 in a fresh process")
    launch.add_argument("--ffmpeg", type=Path, help="FFmpeg build with gfxcapture support")
    launch.add_argument("--show-ui", action="store_true", help="keep the normal game HUD visible in recordings")
    launch.add_argument("--keep-open", action="store_true", help="fresh process, left paused after the run; close it to finish cleanup")
    check = commands.add_parser("release-check", help="verify a mod folder contains no developer test runner")
    check.add_argument("mod_dir", nargs="?", type=Path)
    commands.add_parser("close-session", help="close the idle runner session and remove the developer DLL")
    show = commands.add_parser("latest", help="print the latest summary without launching RimWorld")
    show.add_argument("--batch")
    commands.add_parser("install-dev", help="install the DevTests DLL for the developer-menu path")
    commands.add_parser("remove-dev", help="remove the DevTests DLL from the installed mod")
    args = parser.parse_args(argv)
    if args.command == "guide":
        path = Path(__file__).resolve().parent / GUIDE_TOPICS[args.topic]
        print(f"Source: {path}\n")
        print(path.read_text(encoding="utf-8"))
        return 0
    if args.config is None:
        parser.error("--config is required for " + args.command)
    config = load_config(args.config)
    if args.command == "run":
        if args.timeout <= 0:
            parser.error("--timeout must be greater than zero")
        if args.keep_open and args.quit_on_finish:
            parser.error("--keep-open and --quit-on-finish cannot be combined")
        if args.keep_open or args.quit_on_finish or args.record:
            return run_once(config, args.batch, args.seed, args.timeout, args.keep_open, args.record, args.ffmpeg, args.show_ui, args.mods)
        return run_session(config, args.batch, args.seed, args.timeout, args.mods)
    if args.command == "close-session":
        return close_session(config)
    if args.command == "latest":
        return latest(config, args.batch)
    if args.command == "release-check":
        problems = release_problems(config, args.mod_dir or config.mod_dir)
        for problem in problems:
            print("FAIL:", problem)
        if not problems:
            print("PASS: no developer test runner in", args.mod_dir or config.mod_dir)
        return 1 if problems else 0
    target = config.dev_assemblies / config.dev_dll
    if args.command == "install-dev":
        for build in config.developer_builds:
            shutil.copy2(build, target.with_name(build.name))
        print("Installed", target, "- run remove-dev before publishing.")
    else:
        for build in config.developer_builds:
            target.with_name(build.name).unlink(missing_ok=True)
        print("Removed", target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
