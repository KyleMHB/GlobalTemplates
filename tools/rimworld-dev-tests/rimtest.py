"""Shared launcher for the RimWorld developer test harness (RimWorldDevTests).

Configured per mod by a devtests.json file:

  python rimtest.py --config <mod>/DevTests/devtests.json run <batch...|run-all> [--mods SET] [--language NAME] [--seed N] [--timeout S] [--startup-timeout S] [--quit-on-finish] [--keep-open] [--record [--frames N]]
  python rimtest.py --config ... close-session | latest [--batch B] | timings [run] | list | self-check | prune [--keep N] | release-check [mod_dir] | install-dev | remove-dev
  python rimtest.py --config ... status | lease take|release [--purpose P] | frames [run] [--at 3,8,14 | --count N]

Install lease: run, self-check, install-dev and a mod's deploy script (via `lease take`) claim the installed mod folder for the
checkout (%LOCALAPPDATA%/RimWorldDevTests/leases); close-session releases it. Another checkout of the same mod is refused until
then, or until the lease sits unused for 30 minutes with that mod's game closed. Different mods hold different leases.

Parallel games: several mods' tests run at once, each in its own game. A per-user registry (%LOCALAPPDATA%/RimWorldDevTests/
games.json) records every game a launcher started; up to maxGames (rimtest.local.json, default 3) run at once, and a run waits
for a free slot until its --timeout. Idle sessions keep their slot until close-session. Two games never load each other's mod,
since both harness DLLs would load in one process. Games load one at a time: a launch waits until any other test game
reaches the main menu, since every game writes the shared Player.log and reads mod folders while loading. The perf batch and recorded runs wait until no other game is running a batch,
and other runs wait while one of those runs. `status` shows this mod's lease and game and every other test game.

`run` reuses an idle launcher-owned RimWorld session at the main menu, or launches one, and sends the batch to it. The game
window stays open with the progress panel; finish with close-session, which also removes the DevTests DLL. Several batches
run in one command, grouped by mod set so batches that share a set share one launch.
--quit-on-finish and --keep-open use a single fresh process instead.

Mod lists: the game runs with -savedatafolder=work/userdata/<argPrefix>, so the player's ModsConfig, Prefs, mod settings
and saves are never written. Each launch writes that folder's ModsConfig from a named set in devtests.json ("modSets",
"batchModSets"): a batch uses its mapped set or "default", run-all the union of "default" and every mapped set, and
--mods any set. The reserved set "full" copies the player's active list and mod settings, adding the mod under test if
missing. Sets are validated (installed, dependencies, load order) before launch, and an idle session with a different set
is closed and relaunched. Optional per-set mod settings: <mod>/DevTests/modsettings/<set>/Mod_*.xml.
Every launch runs in English unless run is given --language (Russian, ChineseSimplified, ...); an idle session in another
language is relaunched, and a run whose game loaded a different language fails.

Every run refuses while a RimWorld the launcher did not start is open or while the installed mod differs from the working tree, enforces a
wall-clock limit, and checks that no user save, autosave setting or the player's ModsConfig changed and the loaded build matches.
The game is told the limit and closes the run with a report shortly before it; a game that does not respond is killed.
Exit codes: 0 pass, 1 failures or isolation breach, 2 timeout, interrupted run, failed startup or no report, 3 refusal,
4 launcher error (bad config, missing file, bug).
Agent entry point: python rimtest.py guide [topic] (no config required).
Window recording is shared; showcase content and triage stay in each mod.
"""
import argparse
from fnmatch import fnmatchcase
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback
import uuid
import xml.etree.ElementTree as ET

HARNESS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_ROOT))
from recording import Recording, extract_frames, find_ffmpeg, locate_ffmpeg

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
LOG_KEEP_BYTES = 20 * 1024 * 1024
# The game closes its run this long before the launcher's limit, so the report is written before the kill.
DEADLINE_GRACE = 15
# The harness's copy of Prefs.xml keeps the player's display settings but not these, so runs behave the same on every machine.
# --language replaces langFolderName for one run.
DEFAULT_LANGUAGE = "English"
PINNED_PREFS = {"autosaveIntervalDays": "1", "langFolderName": DEFAULT_LANGUAGE}
# Vanilla ships English as a folder and every other language as <folder>.tar, which the game reads as a folder of that name.
LANGUAGES_DIR = GAME_DIR / "Data/Core/Languages"
MANUAL_MARKER = "RimWorldDevTests.manual"  # DevTestsStartup.ManualMarker
STARTUP_ERROR_ARG = "RimWorldDevTestsStartupError"  # DevTestsStartup.StartupErrorArg
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
    # Mod sets that break a loadAfter/loadBefore rule on purpose ("looseOrderSets"): players load mods in the wrong order too.
    loose_order_sets: tuple = ()
    process_name: str = "RimWorld.exe"
    # The player's real data: never written by a run, and checked afterwards to prove it.
    saves_dir: Path = SAVE_DATA / "Saves"
    prefs_path: Path = SAVE_DATA / "Config/Prefs.xml"
    # 1.7's engine always logs here, ignoring -savedatafolder and Unity's -logFile (observed 2026-11-09, 1.7.5000).
    player_log: Path = SAVE_DATA / "Logs/Player.log"
    # File names HarnessSettings.ExtraRuntimeExclusions leaves out of the runtime hash ("runtimeExclusions").
    runtime_exclusions: tuple = ()
    last_run_dir: Path = None
    # Patterns from --case; empty runs every case.
    cases: list = None
    # The game's folder name for --language, as Prefs.xml stores it (Russian (Русский)).
    language: str = DEFAULT_LANGUAGE

    @property
    def startup_error(self):
        return self.evidence_root / "startup-error.json"

    def launch_command(self):
        return self.game_command + [f"-savedatafolder={self.userdata}", f"-{STARTUP_ERROR_ARG}={self.startup_error}"]

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
                  batch_mod_sets=data.get("batchModSets", {}),
                  loose_order_sets=tuple(data.get("looseOrderSets", [])),
                  runtime_exclusions=tuple(data.get("runtimeExclusions", [])))


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


def mod_problems(config, mods, index, order_notes=None):
    """Why a mod list cannot load. With order_notes (a list), load-order violations go there instead: the set breaks them on
    purpose, and the game only warns about them."""
    problems, position = [], {}
    order = problems if order_notes is None else order_notes
    for i, package_id in enumerate(mods):
        if package_id in position:
            problems.append(f"{package_id} is listed twice")
        position.setdefault(package_id, i)
    # Earlier game versions list a Workshop copy that duplicates a local mod as <id>_steam (not rechecked on 1.7). It is
    # the same mod for installation, dependencies and order.
    listed = list(position)
    for package_id in listed:
        if package_id.endswith("_steam"):
            position.setdefault(package_id.removesuffix("_steam"), position[package_id])
    if config.package_id not in position:
        problems.append(f"the mod under test ({config.package_id}) is not in the set")
    for package_id in listed:
        info = index.get(package_id) or index.get(package_id.removesuffix("_steam"))
        if info is None:
            problems.append(f"{package_id} is not installed (Data, Mods or Workshop)")
            continue
        for options in info.dependencies:
            if not any(o in position for o in options):
                problems.append(f"{info.name} ({package_id}) requires {' or '.join(options)}")
        order += [f"{package_id} must load after {o}" for o in sorted(info.load_after) if position.get(o, -1) > position[package_id]]
        order += [f"{package_id} must load before {o}" for o in sorted(info.load_before) if -1 < position.get(o, -1) < position[package_id]]
    return problems


def prepare_userdata(config, selection):
    """Write the isolated save-data folder for this launch. The player's own Config is only read."""
    order_notes = [] if selection.name in config.loose_order_sets else None
    problems = mod_problems(config, selection.mods, index := mod_index(), order_notes)
    if problems:
        raise RuntimeError(f"mod set {selection.name!r} is not loadable:\n  " + "\n  ".join(problems))
    for note in order_notes or []:
        print(f"NOTE: mod set {selection.name!r} breaks a load-order rule on purpose (looseOrderSets): {note}")
    folder = config.userdata / "Config"
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / "Prefs.xml").is_file() and config.prefs_path.is_file():
        shutil.copy2(config.prefs_path, folder / "Prefs.xml")  # once; the harness owns this copy afterwards
    pin_prefs(folder / "Prefs.xml", config.language)
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
    print(f"Mod set {selection.name!r}: {len(selection.mods)} mods, {len(list(folder.glob('Mod_*.xml')))} settings files; "
          f"language {config.language}; save data {config.userdata}")


def pin_prefs(path, language=DEFAULT_LANGUAGE):
    if not path.is_file():
        return
    text = pinned = path.read_text(encoding="utf-8", errors="replace")
    for key, value in {**PINNED_PREFS, "langFolderName": language}.items():
        pinned = re.sub(f"<{key}>.*?</{key}>", lambda _, key=key, value=value: f"<{key}>{value}</{key}>", pinned)
    if pinned != text:
        path.write_text(pinned, encoding="utf-8")


def legacy_language_name(folder_name):
    """The short name the game also matches for a mod's Languages folder (LoadedLanguage's constructor), but not in Prefs."""
    return folder_name[:folder_name.index("(")].strip() if "(" in folder_name else folder_name.strip()


def installed_languages(folder=None):
    folder = Path(folder or LANGUAGES_DIR)
    if not folder.is_dir():
        raise RuntimeError(f"no language folder at {folder}; check the game directory")
    return sorted({p.name.removesuffix(".tar") for p in folder.iterdir() if p.is_dir() or p.suffix == ".tar"})


def resolve_language(name, installed=None):
    """The folder name to write into Prefs.xml for a --language value. The game selects a language only when Prefs holds its
    full folder name (Russian (Русский)); a short name falls back to English without an error (1.7.5014 source)."""
    wanted = name.strip().lower()
    if wanted == DEFAULT_LANGUAGE.lower():
        return DEFAULT_LANGUAGE
    installed = installed_languages() if installed is None else installed
    for folder in installed:
        if wanted in (folder.lower(), legacy_language_name(folder).lower()):
            return folder
    raise RuntimeError(f"unknown language {name!r}; installed: {', '.join(legacy_language_name(f) for f in installed)}")


def session_identity(config, selection):
    """What an idle session must have loaded to be reused."""
    return {**selection.identity(), "language": config.language}


def session_mods(config):
    path = config.evidence_root / "session-mods.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def restart_hint(config):
    with registry_lock():
        unrelated = unrelated_games(read_registry())
    if unrelated:
        print("RimWorld relaunched itself while loading (a mod such as Load Them Last rewrote the load order). Close that "
              "game, fix the set's order in devtests.json, and run again.")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_manifest(config, root):
    root = Path(root)
    files = [p for name in config.runtime_folders for p in (root / name).rglob("*") if p.is_file()]
    files += [root / name for name in config.runtime_files if (root / name).is_file()]
    return {p.relative_to(root).as_posix().lower(): sha256(p) for p in files
            if p.suffix.lower() != ".pdb" and p.name not in (config.dev_dll, "RimWorldDevTests.dll", *config.runtime_exclusions)}


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


def snapshot_saves(saves_dir):
    """Size and modification time of each of the player's saves. Runs write to their own save-data folder, so this only has
    to notice a change; hashing a large save folder twice for every run was slow."""
    if not Path(saves_dir).is_dir():
        return {}
    return {p.name: (s.st_size, s.st_mtime_ns) for p in Path(saves_dir).iterdir() if p.is_file() and (s := p.stat())}


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
        if environment.get("language") not in (None, config.language):
            problems.append(f"the game loaded language {environment['language']!r}, not the requested {config.language!r}")
        if environment.get("runtimeHash") != manifest["runtimeHash"]:
            problems.append("report runtime manifest does not match preflight" + runtime_config_difference(config, environment))
        if (environment.get("modBuild") or {}).get("sha256") != sha256(config.production_dll):
            problems.append("report's loaded production DLL is not the candidate build")
    if environment:
        for key in ("developerHash", "harnessHash"):
            if environment.get(key) != manifest[key]:
                problems.append(f"report {key} does not match preflight")
    for problem in problems:
        print("ISOLATION FAIL:", problem)
    return problems


def runtime_config_difference(config, environment):
    """Names the devtests.json entry that disagrees with the mod's HarnessSettings, the usual cause of a hash mismatch."""
    theirs = environment.get("runtimeConfig") or {}
    mine = {"folders": config.runtime_folders, "files": config.runtime_files, "exclusions": config.runtime_exclusions}
    keys = {"folders": "runtimeFolders", "files": "runtimeFiles", "exclusions": "runtimeExclusions"}
    differences = [f'devtests.json "{keys[k]}" {sorted(mine[k])} differs from HarnessSettings {sorted(theirs[k] or [])}'
                   for k in mine if k in theirs and sorted(x.lower() for x in mine[k]) != sorted(x.lower() for x in theirs[k] or [])]
    return ": " + "; ".join(differences) if differences else ""


def tail(path, lines=LOG_TAIL_LINES):
    return "\n".join(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]) if Path(path).is_file() else f"(missing: {path})"


def print_summary(run_dir, manifest):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "deployment.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summary = run_dir / "summary.txt"
    if summary.is_file():
        print(f"Summary: {summary}")
        print(summary.read_text(encoding="utf-8"))


def player_log_owner(config):
    """The -savedatafolder on Player.log's Command line. Every game on the machine writes the one file and replaces it at launch,
    so with several test games running it belongs to whichever launched last (observed 2026-11-22, 1.7.5014)."""
    try:
        with config.player_log.open("r", encoding="utf-8", errors="replace") as log:
            head = log.read(8192)
    except OSError:
        return None
    match = re.search(r"^Command:.*?-savedatafolder=(.+?)(?:\s+-\w|$)", head, re.MULTILINE)
    return match.group(1).strip().strip('"') if match else None


def owns_player_log(config):
    owner = player_log_owner(config)
    return owner is not None and same_path(owner, config.userdata)


def keep_player_log(config, run_dir):
    """Keep this game's Player.log (its tail when huge), but not one that another game has since replaced."""
    if not owns_player_log(config):
        note = f"Player.log was not copied: another game launched after this one and replaced it (now {player_log_owner(config)})."
        print(note)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "Player.log.txt").write_text(note + "\n", encoding="utf-8")
        return
    try:
        with config.player_log.open("rb") as source:
            source.seek(max(0, config.player_log.stat().st_size - LOG_KEEP_BYTES))
            (run_dir / "Player.log").write_bytes(source.read())
    except OSError as error:
        print(f"Player.log was not copied: {error}")


def known_batches(config, developer_hash):
    """The batch list the game wrote at its last launcher start, or None when it is missing or from another build."""
    try:
        listed = json.loads((config.evidence_root / "batches.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return listed if listed.get("developerHash") == developer_hash else None


def check_batch(config, batch, manifest):
    listed = known_batches(config, manifest["developerHash"])
    known = [b["id"] for b in listed["batches"]] + [RUN_ALL] if listed else None
    if known and batch not in known:
        raise RuntimeError(f"unknown batch {batch!r}; known: {', '.join(known)}")


def game_deadline(deadline, graceful=True):
    """UTC milliseconds at which the game should close its run, or 0 when the limit is too short to leave a margin."""
    remaining = deadline - time.monotonic()
    return int((time.time() + remaining - DEADLINE_GRACE) * 1000) if graceful and remaining > 2 * DEADLINE_GRACE else 0


class StartupFailure(Exception):
    pass


def check_startup(config):
    if config.startup_error.is_file():
        try:
            error = json.loads(config.startup_error.read_text(encoding="utf-8")).get("error")
        except (OSError, ValueError):
            error = "unreadable startup error file"
        raise StartupFailure(f"the developer test runner failed to start in the game: {error} (details: {config.startup_error})")


def startup_hint(config):
    return (f"Check Player.log. devtests.json argPrefix and evidenceFolder must match the mod's HarnessSettings "
            f"(expected session files in {config.evidence_root}). A large mod set may need a longer --startup-timeout.")


def print_diagnostics(config, run_dir):
    print(f"Progress file {run_dir / 'progress.json'}:\n{tail(run_dir / 'progress.json')}")
    if owns_player_log(config):
        print(f"Last {LOG_TAIL_LINES} lines of {config.player_log}:\n{tail(config.player_log)}")
    else:
        print(f"{config.player_log} belongs to another game launched since ({player_log_owner(config)}), so its lines are not this run's.")


def new_run_id(batch, seed, cases=None):
    """A run filtered by --case says so in its id, so its folder is never mistaken for a full batch run."""
    return f"{datetime.now():%Y%m%d-%H%M%S}-{re.sub(r'[^a-z0-9-]', '-', batch.lower())}-s{seed}" + ("-cases" if cases else "")


def select_case_batches(config, batches, cases):
    """Checks --case patterns against the batch list the game last wrote and keeps only the batches they select. Raises on a
    pattern that matches no planned case. Without a current list (first launch after a DevTests build) the game checks instead:
    it refuses a request whose filter selects nothing."""
    listed = known_batches(config, sha256(config.dev_build)) if config.dev_build.is_file() else None
    if not listed or RUN_ALL in batches:
        return batches
    plans = {b["id"]: b.get("cases") or [] for b in listed.get("batches") or []}
    def selected(batch):
        return [c for c in plans.get(batch, []) if any(fnmatchcase(c.lower(), p.lower()) for p in cases)]
    unmatched = [p for p in cases if not any(fnmatchcase(c.lower(), p.lower()) for b in batches for c in plans.get(b, []))]
    if unmatched:
        raise RuntimeError(f"--case {' '.join(unmatched)} matches no planned case in {', '.join(batches)}; "
                           "case ids are listed in each batch's report.json and summary")
    kept = [b for b in batches if b not in plans or selected(b)]
    for batch in batches:
        if batch in plans:
            print(f"--case selects {len(selected(batch))} of {len(plans[batch])} cases in {batch}" if selected(batch) else
                  f"--case selects nothing in {batch}; not running it")
    return kept


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


def remove_developer_files(config):
    for name in [build.name for build in config.developer_builds] + [MANUAL_MARKER]:
        (config.dev_assemblies / name).unlink(missing_ok=True)


def clear_session(config):
    remove_developer_files(config)
    for name in ("session.json", "session-request.json", "session-mods.json", "startup-error.json"):
        (config.evidence_root / name).unlink(missing_ok=True)


def wait_session(config, process, token, deadline, after=0, startup_limit=0):
    """Wait for an idle heartbeat. startup_limit (seconds) marks the first wait after a launch, which has its own limit."""
    startup_deadline = time.monotonic() + startup_limit if startup_limit else None
    while process.alive():
        check_startup(config)
        status = session_status(config)
        if status and status["session"] == token and status["heartbeat"] > after:
            if status["state"] == "idle":
                return status
            if status["state"] == "unrelated-colony":
                raise RuntimeError("runner session has an unrelated colony open; it cannot accept a batch")
        if startup_deadline and time.monotonic() >= startup_deadline:
            raise StartupFailure(f"the game did not reach the main menu with the runner loaded within {startup_limit} s. " + startup_hint(config))
        if time.monotonic() >= deadline:
            raise TimeoutError("runner did not return to the main menu before the timeout")
        time.sleep(0.1)
    check_startup(config)
    raise RuntimeError("runner process exited before reaching the main menu")


def run_session(config, batch, seed, timeout, mod_set=None, startup_timeout=300, graceful=True):
    try:
        with session_lock(config):
            return _run_session(config, batch, seed, timeout, mod_set, startup_timeout, graceful)
    except (OSError, ValueError, RuntimeError, ET.ParseError) as error:
        print("REFUSED:", error)
        return 3


def run_batches(config, batches, seed, timeout, mod_set=None, startup_timeout=300):
    """Run batches in the reusable session, grouped by mod set so each set launches once. Keeps going after test failures
    (exit 1); stops at a refusal, timeout or launcher fault, since later batches would hit the same problem."""
    order = list(dict.fromkeys(mod_set or config.batch_mod_sets.get(b, DEFAULT_SET) for b in batches))
    queue = sorted(dict.fromkeys(batches), key=lambda b: order.index(mod_set or config.batch_mod_sets.get(b, DEFAULT_SET)))
    results = []
    for batch in queue:
        print(f"\n=== {batch} (mod set {mod_set or config.batch_mod_sets.get(batch, DEFAULT_SET)})", flush=True)
        code = run_session(config, batch, seed, timeout, mod_set, startup_timeout)
        results.append((batch, code))
        if code >= 2:
            break
    print("\nBatches:")
    for batch, code in results:
        print(f"  {batch}: {'PASS' if code == 0 else 'FAIL' if code == 1 else f'stopped (exit {code})'}")
    for batch in queue[len(results):]:
        print(f"  {batch}: not run")
    return max(code for _, code in results)


def _run_session(config, batch, seed, timeout, mod_set, startup_timeout=300, graceful=True):
    manifest, saves_before, prefs_before = snapshot(config)
    check_batch(config, batch, manifest)
    selection = select_mods(config, batch, mod_set)
    production_hash, developer_hash = sha256(config.production_dll), manifest["developerHash"]
    deadline = time.monotonic() + timeout
    exclusive = batch == "perf" or selection.name in EXCLUSIVE_SETS
    reuse = False
    if own_game_open(config):
        status = session_status(config)
        if not status or time.time() * 1000 - status["heartbeat"] > 10000:
            raise RuntimeError("RimWorld is open without a responsive launcher session; leave that game untouched and close it before running batches")
        if status["productionHash"] != production_hash or status["developerHash"] != developer_hash or status.get("harnessHash") != manifest["harnessHash"]:
            raise RuntimeError("the open session loaded different DLLs; use close-session, then run the batch again")
        if status.get("runtimeHash") != manifest["runtimeHash"]:
            raise RuntimeError("the open session loaded different runtime files; close-session before running again")
        if (config.evidence_root / "session-request.json").exists():
            raise RuntimeError("the session already has a pending command; wait for it to finish")
        loaded, wanted = session_mods(config), session_identity(config, selection)
        if loaded:
            loaded.setdefault("language", DEFAULT_LANGUAGE)  # written before --language existed
        # Compare what was loaded, not the set's name: run-all and a single batch often resolve to the same mods.
        keys = ("mods", "settings", "language")
        if loaded and {k: loaded.get(k) for k in keys} == {k: wanted[k] for k in keys}:
            reuse = True
            token = status["session"]
            process = SessionProcess(status["pid"])
            print(f"Reusing the open RimWorld runner session (mod set {selection.name!r}, language {config.language}).")
        else:
            print(f"The open session loaded mod set {(loaded or {}).get('set', 'unknown')!r} in {(loaded or {}).get('language', 'an unknown language')}; "
                  f"relaunching with {selection.name!r} in {config.language}.")
            _close_session(config)
    concurrent = claim_game(config, selection.mods, exclusive, launching=not reuse, deadline=deadline)
    try:
        return _run_claimed(config, batch, seed, timeout, startup_timeout, graceful, manifest, saves_before, prefs_before, selection,
                            deadline, reuse, token if reuse else None, process if reuse else None, concurrent)
    finally:
        release_game(config)


def _run_claimed(config, batch, seed, timeout, startup_timeout, graceful, manifest, saves_before, prefs_before, selection, deadline,
                 reuse, token, process, concurrent):
    if not reuse:
        prepare_userdata(config, selection)
        clear_session(config)
        for build in config.developer_builds:
            shutil.copy2(build, config.dev_assemblies / build.name)
        token = uuid.uuid4().hex
        (config.evidence_root / "session-mods.json").write_text(json.dumps(session_identity(config, selection), indent=2), encoding="utf-8")
        try:
            launched = subprocess.Popen(config.launch_command() + [config.arg("Session", token)])
            register_launch(config, launched.pid)
            process = SessionProcess(launched.pid)
        except OSError:
            clear_session(config)
            raise
        print("Launched a reusable RimWorld runner session.")
    run_id = new_run_id(batch, seed, config.cases) + "-" + uuid.uuid4().hex[:8]
    run_dir = config.last_run_dir = config.evidence_root / run_id
    report_path, summary_path = run_dir / "report.json", run_dir / "summary.txt"
    timed_out, report, ready, failure = False, None, False, None
    try:
        wait_session(config, process, token, deadline, startup_limit=0 if reuse else startup_timeout)
        if not reuse:
            mark_loaded(config)
        print(f"Run {run_id}: evidence {run_dir}", flush=True)
        send_session_request(config, token, "run", RunId=run_id, Batch=batch, Seed=seed, DeadlineUtcMs=game_deadline(deadline, graceful),
                             Cases=config.cases, ConcurrentGames=concurrent)
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
    except StartupFailure as error:
        failure = str(error)
        process.kill()
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
    keep_player_log(config, run_dir)
    problems = run_problems(config, manifest, report, saves_before, prefs_before)
    if failure:
        print("STARTUP FAILED:", failure)
    if failure or timed_out or report is None or not ready:
        print_diagnostics(config, run_dir)
        return 2
    print("RimWorld is at the main menu, ready for the next batch. Leave it open; close-session only before rebuilding or release-check.")
    return result_code(report, problems)


def result_code(report, problems, recording_error=None):
    if report.get("status") == "refused":
        return 3
    if report.get("status") == "interrupted":
        print("Run interrupted:", report.get("reason"))
        return 2
    return 0 if report.get("overallPass") and not problems and not recording_error else 1


def close_session(config):
    try:
        with session_lock(config):
            if not own_game_open(config):
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


# ---- Game registry: the harness games running on this machine -----------------------------------------------------------
# Several mods' tests can run at once, each in its own game with its own -savedatafolder. The registry records every game a
# launcher started, so a RimWorld that is not in it (the player's own) still refuses a run: an autosave there would read as an
# isolation breach, and it may hold the mod's DLLs. It lives per user, outside any checkout, so worktrees share it. Each entry
# also says whether a launcher command is using that game right now ("busy"), which the slot limit and exclusive runs read.

STATE_ROOT = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "RimWorldDevTests"
REGISTRY_PATH = STATE_ROOT / "games.json"
LEASE_DIR = STATE_ROOT / "leases"
DEFAULT_MAX_GAMES = 3
# Runs that time things or capture the window: other games' load skews them, so they wait until no other game is busy.
EXCLUSIVE_SETS = ("perf",)
RESERVATION_SECONDS = 120  # a slot reserved for a launch that never registered is freed after this
# Games load one at a time. Every game writes the shared Player.log (renaming the last one to Player-prev.log) and reads the mod
# folders while it loads, so two startups at once could race for a locked file. A game still loading after this stops holding
# the others back.
STARTUP_HOLD_SECONDS = 600


def max_games():
    """maxGames in rimtest.local.json, else DEFAULT_MAX_GAMES."""
    local = HARNESS_ROOT / "rimtest.local.json"
    if local.exists():
        value = json.loads(local.read_text(encoding="utf-8")).get("maxGames")
        if isinstance(value, int) and value >= 1:
            return value
    return DEFAULT_MAX_GAMES


def process_created(pid):
    """The process's creation time, or None when it has exited; with the pid it names one process even after pid reuse."""
    from ctypes import wintypes
    if not pid:
        return None
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x1000 | 0x100000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
    if not handle:
        return None
    try:
        if api.WaitForSingleObject(handle, 0) != 258:  # signalled: exited
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not api.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            return None
        return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    finally:
        api.CloseHandle(handle)


def rimworld_pids():
    listing = subprocess.run(["tasklist", "/FI", "IMAGENAME eq RimWorld.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, check=False).stdout
    return [int(row[1]) for row in (line.split('","') for line in listing.splitlines()) if len(row) > 1 and row[1].isdigit()]


def same_path(a, b):
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


@contextmanager
def registry_lock():
    import msvcrt
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    # Byte 0 is locked whether or not the file holds it, so the file stays empty: reading a byte another process has locked fails
    # with EACCES on Windows.
    with (STATE_ROOT / "games.lock").open("a+b") as lock:
        deadline = time.monotonic() + 30
        while True:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"another launcher held {STATE_ROOT / 'games.lock'} for 30 s")
                time.sleep(0.05)
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def live(entry):
    """Drop exited games and abandoned reservations; clear a busy mark whose launcher has exited."""
    if entry.get("pid"):
        if process_created(entry["pid"]) != entry.get("created"):
            return None
    elif time.time() - entry.get("reserved", 0) > RESERVATION_SECONDS or process_created(entry.get("launcher")) != entry.get("launcherCreated"):
        return None
    if entry.get("busy") and process_created(entry["busy"]) != entry.get("busyCreated"):
        entry.update(busy=None, busyCreated=None, exclusive=False, loading=None)
    if entry.get("loading") and time.time() - entry["loading"] > STARTUP_HOLD_SECONDS:
        entry["loading"] = None
    return entry


def read_registry():
    """Live entries; the caller holds registry_lock."""
    try:
        entries = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        entries = []
    return [e for e in (live(e) for e in entries) if e]


def write_registry(entries):
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    temp = REGISTRY_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    temp.replace(REGISTRY_PATH)


def own_entry(config, entries):
    return next((e for e in entries if same_path(e["userdata"], config.userdata)), None)


def adopt_session(config, entries):
    """Register this mod's open session when an older launcher started it, so it is not taken for an unrelated game."""
    if own_entry(config, entries):
        return
    status = session_status(config)
    created = process_created(status.get("pid")) if status else None
    if created:
        entries.append({"pid": status["pid"], "created": created, "mod": config.name, "checkout": str(config.root.resolve()),
                        "userdata": str(config.userdata), "packageId": config.package_id, "mods": session_mods(config) and
                        session_mods(config).get("mods") or [], "busy": None, "busyCreated": None, "exclusive": False})


def unrelated_games(entries):
    known = {e["pid"] for e in entries if e.get("pid")}
    return [pid for pid in rimworld_pids() if pid not in known]


def own_game_open(config):
    with registry_lock():
        entries = read_registry()
        adopt_session(config, entries)
        write_registry(entries)
        entry = own_entry(config, entries)
        return bool(entry and entry.get("pid"))


def describe_game(entry):
    state = ("loading" if entry.get("loading") else "busy" + (", exclusive" if entry.get("exclusive") else "") if entry.get("busy")
             else "idle" if entry.get("pid") else "starting")
    return f"{entry['mod']} ({state}, {entry['checkout']})"


def blockers(config, entries, mods, exclusive, launching):
    others = [e for e in entries if not same_path(e["userdata"], config.userdata)]
    found = []
    if launching and len(others) >= max_games():
        found.append(f"all {max_games()} test game slots are in use (maxGames in rimtest.local.json): "
                     + "; ".join(describe_game(e) for e in others) + ". Idle sessions keep their slot until their checkout runs close-session")
    if launching:
        found += [f"{describe_game(e)} is still loading; test games start one at a time so their startups don't race for shared files"
                  for e in others if e.get("loading") or not e.get("pid")]
    package = config.package_id.lower()
    for e in others:
        if package and package in [m.lower() for m in e.get("mods", [])] or e.get("packageId", "").lower() in [m.lower() for m in mods]:
            found.append(f"{describe_game(e)} loads this mod, or this run loads that one; two harness DLLs cannot share a game")
    if exclusive:
        found += [f"{describe_game(e)} is running a batch; perf and recorded runs wait for other games to finish" for e in others if e.get("busy")]
    else:
        found += [f"{describe_game(e)} is running a perf or recorded batch, which needs the machine to itself" for e in others if e.get("exclusive")]
    return found


def claim_game(config, mods, exclusive, launching, deadline):
    """Wait until this command may use (or launch) its game, then mark it busy, or reserve a slot for the launch. Returns the
    number of other harness games running. RuntimeError for an unrelated RimWorld, or when the wait outlives the deadline."""
    me, my_created = os.getpid(), process_created(os.getpid())
    shown = None
    while True:
        with registry_lock():
            entries = read_registry()
            adopt_session(config, entries)
            unrelated = unrelated_games(entries)
            if unrelated:
                write_registry(entries)
                raise RuntimeError(f"RimWorld is open outside the test launcher (pid {', '.join(map(str, unrelated))}); leave that game "
                                   "untouched and close it before running batches")
            found = blockers(config, entries, mods, exclusive, launching)
            if not found:
                entry = own_entry(config, entries)
                if entry is None or launching:
                    entries = [e for e in entries if e is not entry]
                    entry = {"pid": None, "created": None, "reserved": time.time(), "loading": time.time(), "launcher": me, "launcherCreated": my_created,
                             "mod": config.name, "checkout": str(config.root.resolve()), "userdata": str(config.userdata),
                             "packageId": config.package_id}
                    entries.append(entry)
                entry.update(mods=list(mods), busy=me, busyCreated=my_created, exclusive=exclusive)
                write_registry(entries)
                return len(entries) - 1
            write_registry(entries)
        if time.monotonic() >= deadline:
            raise RuntimeError("waited for a test game until the timeout: " + " | ".join(found))
        if found != shown:
            print("Waiting: " + " | ".join(found), flush=True)
            shown = found
        time.sleep(2)


def register_launch(config, pid):
    with registry_lock():
        entries = read_registry()
        entry = own_entry(config, entries)
        if entry is None:
            raise RuntimeError("the reserved game slot expired before the game started")
        entry.update(pid=pid, created=process_created(pid), reserved=None)
        write_registry(entries)


def mark_loaded(config):
    """The game reached the main menu with the runner ready, so the next game may start loading."""
    with registry_lock():
        entries = read_registry()
        entry = own_entry(config, entries)
        if entry and entry.get("loading"):
            entry["loading"] = None
            write_registry(entries)


def games_loading_mod(config):
    """Other test games that load this mod and are still loading: they read its files, so a deploy waits for them."""
    package = config.package_id.lower()
    with registry_lock():
        return [e for e in read_registry() if not same_path(e["userdata"], config.userdata) and e.get("loading")
                and package in [m.lower() for m in e.get("mods", [])]]


def release_game(config):
    """End this command's use of its game: an open session stays registered as idle; a reservation or exited game is dropped."""
    with registry_lock():
        entries = read_registry()
        entry = own_entry(config, entries)
        if entry and not entry.get("pid"):
            entries.remove(entry)
        elif entry:
            entry.update(busy=None, busyCreated=None, exclusive=False, loading=None)
        write_registry(entries)


def other_games(config):
    with registry_lock():
        return [e for e in read_registry() if not same_path(e["userdata"], config.userdata)]


# ---- Install lease: one checkout at a time owns an installed mod ----------------------------------------------------------
# session_lock covers a single launcher command. The lease covers the whole loop (deploy, runs, close-session), so another
# checkout or worktree of the same mod cannot deploy over a tree under test or launch between two of its runs. Leases are per
# installed mod folder: different mods run side by side. It names the holder's checkout so a refused agent knows whom it is
# waiting for, instead of polling processes and messaging other sessions.

LEASE_IDLE_MINUTES = 30  # an untouched lease whose mod has no game open is abandoned


def lease_path(config):
    key = re.sub(r"[^a-z0-9]+", "-", os.path.normcase(os.path.normpath(str(config.mod_dir))).lower()).strip("-")
    return LEASE_DIR / f"{key}.json"


def read_lease(config):
    try:
        return json.loads(lease_path(config).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def lease_stale(lease):
    if not Path(lease["holder"]).is_dir():
        return True
    if time.time() - lease.get("touched", 0) <= LEASE_IDLE_MINUTES * 60:
        return False
    with registry_lock():
        return not any(e.get("pid") and same_path(e["userdata"], lease.get("userdata", "")) for e in read_registry())


def describe_lease(lease):
    minutes = (time.time() - lease.get("touched", 0)) / 60
    return (f"{lease['holder']} ({lease.get('mod', '?')}, {lease.get('purpose', '?')}), last used {minutes:.0f} min ago")


def take_lease(config, purpose):
    """Claim or refresh the lease for this checkout; RuntimeError names the other holder."""
    holder = str(config.root.resolve())
    lease = read_lease(config)
    if lease and lease["holder"] != holder and not lease_stale(lease):
        raise RuntimeError(f"the installed {config.name} is leased to {describe_lease(lease)}. Wait until that checkout runs "
                           f"close-session, or until it sits unused for {LEASE_IDLE_MINUTES} min with its game closed. "
                           "`status` shows the holder.")
    now = time.time()
    since = lease["since"] if lease and lease["holder"] == holder else now
    path = lease_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"holder": holder, "mod": config.name, "modDir": str(config.mod_dir), "userdata": str(config.userdata),
                                "purpose": purpose, "since": since, "touched": now}), encoding="utf-8")
    temp.replace(path)


def release_lease(config):
    lease = read_lease(config)
    if lease and lease["holder"] == str(config.root.resolve()):
        lease_path(config).unlink(missing_ok=True)
        return True
    return False


def lease_command(config, action, purpose):
    if action == "release":
        print("Released the install lease." if release_lease(config) else "This checkout holds no lease.")
        return 0
    try:
        take_lease(config, purpose)
        # A deploy script takes the lease before copying files: wait until no other test game is loading this mod's files.
        deadline, shown = time.monotonic() + STARTUP_HOLD_SECONDS, None
        while loading := games_loading_mod(config):
            if time.monotonic() >= deadline:
                raise RuntimeError("these test games are still loading this mod: " + "; ".join(describe_game(e) for e in loading))
            names = "; ".join(describe_game(e) for e in loading)
            if names != shown:
                print(f"Waiting: {names} loads this mod and is still starting; deploying now could race its file reads.", flush=True)
                shown = names
            time.sleep(2)
    except RuntimeError as error:
        print("REFUSED:", error)
        return 3
    print(f"This checkout holds the install lease for {config.name} ({purpose}).")
    return 0


def status(config):
    lease = read_lease(config)
    if not lease:
        print(f"Lease ({config.name}): free.")
    else:
        mine = lease["holder"] == str(config.root.resolve())
        state = "this checkout" if mine else "stale, free to take" if lease_stale(lease) else "another checkout"
        print(f"Lease ({config.name}): {state}: {describe_lease(lease)}")
    with registry_lock():
        entries = read_registry()
        adopt_session(config, entries)
        write_registry(entries)
        unrelated = unrelated_games(entries)
    mine = own_entry(config, entries)
    print(f"RimWorld ({config.name}): {'running' if mine and mine.get('pid') else 'closed'}.")
    others = [e for e in entries if e is not mine]
    print(f"Other test games: {'none' if not others else '; '.join(describe_game(e) for e in others)} (limit {max_games()}).")
    if unrelated:
        print(f"RimWorld outside the launcher: pid {', '.join(map(str, unrelated))}; runs refuse until it closes.")
    session = session_status(config)
    if session:
        age = time.time() - session.get("heartbeat", 0) / 1000
        print(f"Runner session ({config.name}): {session.get('state')}, heartbeat {age:.0f} s ago.")
    candidate, installed = runtime_manifest(config, config.runtime_root), runtime_manifest(config, config.mod_dir)
    differences = [n for n in candidate.keys() | installed.keys() if candidate.get(n) != installed.get(n)]
    print("Installed mod: matches this checkout." if not differences
          else f"Installed mod: differs from this checkout in {len(differences)} file(s); deploy before running.")
    return 0


# ---- Recorded runs: stills for looking at art ----------------------------------------------------------------------------

def recorded_run(config, run=None):
    if run:
        folder = Path(run) if Path(run).is_dir() else config.evidence_root / run
    else:
        folder = next((d for d in reversed(run_dirs(config)) if (d / "build.mp4").is_file()), None)
    if not folder or not (folder / "build.mp4").is_file():
        raise ValueError(f"no build.mp4 in {folder or 'any run'}; record a run with run --record")
    return folder / "build.mp4"


def frames(config, run=None, at=None, count=6, ffmpeg=None):
    try:
        video = recorded_run(config, run)
        stills, sheet = extract_frames(locate_ffmpeg(ffmpeg), video, at, count)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("REFUSED:", error)
        return 3
    for seconds, still in stills:
        print(f"{seconds:6.2f} s  {still}")
    print("Sheet:", sheet)
    return 0


# ---- Single fresh process -----------------------------------------------------------------------------------------------

def run_once(config, batch, seed, timeout, keep_open=False, record=False, ffmpeg=None, show_ui=False, mod_set=None, startup_timeout=300):
    try:
        if own_game_open(config):
            print(f"REFUSED: this mod's runner session is open. Use close-session first, or run without --quit-on-finish to reuse it.")
            return 3
        manifest, saves_before, prefs_before = snapshot(config)
        check_batch(config, batch, manifest)
        selection = select_mods(config, batch, mod_set)
        concurrent = claim_game(config, selection.mods, record or batch == "perf" or selection.name in EXCLUSIVE_SETS, launching=True,
                                deadline=time.monotonic() + timeout)
    except (OSError, ValueError, RuntimeError, ET.ParseError) as error:
        print("REFUSED:", error)
        return 3
    try:
        return _run_once_claimed(config, batch, seed, timeout, keep_open, record, ffmpeg, show_ui, startup_timeout, manifest,
                                 saves_before, prefs_before, selection, concurrent)
    finally:
        release_game(config)


def _run_once_claimed(config, batch, seed, timeout, keep_open, record, ffmpeg, show_ui, startup_timeout, manifest, saves_before,
                      prefs_before, selection, concurrent):
    try:
        prepare_userdata(config, selection)
        clear_session(config)  # a fresh process shares the folder; drop any stale session files
        if record:
            ffmpeg = find_ffmpeg(ffmpeg)
        for build in config.developer_builds:
            shutil.copy2(build, config.dev_assemblies / build.name)
    except (OSError, ValueError, RuntimeError, ET.ParseError, subprocess.SubprocessError) as error:
        print("REFUSED:", error)
        return 3
    run_id = new_run_id(batch, seed, config.cases)
    run_dir = config.last_run_dir = config.evidence_root / run_id
    recording = Recording(ffmpeg, run_dir, timeout, hide_ui=not show_ui) if record else None
    print(f"Run {run_id}: evidence {run_dir}", flush=True)
    timed_out, failure, loaded = False, None, False
    try:
        deadline = time.monotonic() + timeout
        startup_deadline = time.monotonic() + startup_timeout
        process = subprocess.Popen(config.launch_command() + [config.arg("Test", batch), config.arg("Seed", seed), config.arg("RunId", run_id),
                                                              config.arg("Deadline", game_deadline(deadline))]
                                   + ([config.arg("Cases", ",".join(config.cases))] if config.cases else [])
                                   + ([config.arg("KeepOpen", "true")] if keep_open else [])
                                   + ([config.arg("Record", "true")] if record else [])
                                   + ([config.arg("ShowUI", "true")] if show_ui else [])
                                   + ([config.arg("ConcurrentGames", concurrent)] if concurrent else []))
        register_launch(config, process.pid)
        while process.poll() is None:
            if recording:
                recording.poll()
            try:
                check_startup(config)
                # The run folder appears when the game accepts or refuses the request.
                if run_dir.is_dir() and not loaded:
                    loaded = True
                    mark_loaded(config)
                if not run_dir.is_dir() and time.monotonic() >= startup_deadline:
                    failure = f"the game did not start the run within {startup_timeout} s. " + startup_hint(config)
            except StartupFailure as error:
                failure = str(error)
            if failure:
                process.kill()
                process.wait()
                break
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
        try:
            remove_developer_files(config)
        except OSError as error:
            print(f"Developer DLLs are still installed ({error}); close RimWorld, then run remove-dev.")
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    print_summary(run_dir, manifest)
    keep_player_log(config, run_dir)
    if failure:
        print("STARTUP FAILED:", failure)
    elif timed_out or report is None:
        print(f"Game {'timed out after ' + str(timeout) + ' s and was killed' if timed_out else 'exited without a report'}.")
    if failure or timed_out or report is None:
        print_diagnostics(config, run_dir)
        restart_hint(config)
    problems = run_problems(config, manifest, report, saves_before, prefs_before)
    config.startup_error.unlink(missing_ok=True)
    if failure or timed_out or report is None:
        return 2
    return result_code(report, problems, recording and recording.error)


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
    problems += [f"developer-menu marker present: {p}" for p in Path(mod_dir).rglob(MANUAL_MARKER)]
    return problems


PREVIEW_LIMIT = 1024 * 1024


GAME_NAMESPACES = ("RimWorld", "Verse", "LudeonTK", "UnityEngine", "System")


def static_problems(config, mod_dir):
    """Mistakes in the mod's files that the game loads without an error and no case is sure to reach.
    Returns (problems, warnings): a class name is matched against the DLL's bytes, which can't prove a type is missing."""
    mod_dir, problems, warnings = Path(mod_dir), [], []
    preview = mod_dir / "About/Preview.png"
    # Steam rejects a larger Workshop preview mid-upload with a bare result code; the game does not check.
    if preview.is_file() and preview.stat().st_size > PREVIEW_LIMIT:
        problems.append(f"About/Preview.png is {preview.stat().st_size:,} bytes; Steam takes at most {PREVIEW_LIMIT:,}")
    shipped = mod_dir / config.production_dll.relative_to(config.runtime_root)
    dll = shipped.read_bytes() if shipped.is_file() else b""

    def in_dll(name):
        # Metadata keeps namespaces and type names as separate zero-terminated UTF-8 strings, and stores a name that ends
        # another (MendingStand, IMendingStand) once, so only the end of the string can be matched.
        return name.encode() + b"\0" in dll

    # Only the folders the mod ships: a working tree can hold other mods' files under its work folders.
    for path in sorted(p for folder in config.runtime_folders for p in (mod_dir / folder).rglob("*.xml")):
        folders = path.relative_to(mod_dir).parts[:-1]
        if "Defs" not in folders and "Patches" not in folders:
            continue
        shown = path.relative_to(mod_dir).as_posix()
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as error:
            problems.append(f"{shown} is not well-formed XML: {error}")
            continue
        # The game reads only <Patch>; any other root discards every operation in the file without a word.
        if "Patches" in folders and root.tag != "Patch":
            problems.append(f"{shown} has root <{root.tag}>, not <Patch>, so the game ignores every operation in it")
        names = set()
        for element in root.iter():
            names.add(element.get("Class"))
            if isinstance(element.tag, str) and element.tag.endswith("Class") and len(element) == 0:
                names.add((element.text or "").strip())
        for name in sorted(n for n in names if n and "." in n):
            namespace, _, type_name = name.rpartition(".")
            # A renamed class leaves the XML pointing at nothing, and the comp or worker silently never attaches. The DLL
            # also holds the namespaces of types it only uses, so a class of another mod that the code never names can be
            # reported here: a warning, to be checked by hand.
            if namespace.split(".")[0] in GAME_NAMESPACES or not dll or not in_dll(namespace):
                continue
            if not in_dll(type_name.split("+")[0]):
                warnings.append(f"{shown} names {name}, but {shipped.name} holds no type name {type_name}; renamed or removed?")
    return problems, warnings


PERF_BATCH, PERF_CASE, DUBS_ID ="perf", "perf.mod-tick", "dubwise.dubsperformanceanalyzer.steam"


def perf_problems(config, mod_dir):
    """Every mod must pass the shared perf batch and its own perf.* cases on the DLL it ships.
    Returns (problems, passing summaries, warnings)."""
    command = f"run {PERF_BATCH} --mods {PERF_BATCH}"
    if DUBS_ID not in config.mod_sets.get(PERF_BATCH, []):
        return [f"no '{PERF_BATCH}' mod set with Dubs Performance Analyzer ({DUBS_ID}) in devtests.json; add one (guide perf), then {command}"], [], []
    shipped = Path(mod_dir) / config.production_dll.relative_to(config.runtime_root)
    if not shipped.is_file():
        return [f"production DLL missing: {shipped}"], [], []
    listed = known_batches(config, sha256(config.dev_build)) if config.dev_build.is_file() else None
    if listed is None:
        return [f"no batch list from the current DevTests build; build DevTests, then {command} (it writes the list)"], [], []
    targeted = {case: batch["id"] for batch in listed.get("batches") or [] if batch.get("id") != PERF_BATCH
                for case in batch.get("cases") or [] if case.startswith("perf.") and case != PERF_CASE}
    wanted = {PERF_CASE: command, **{case: f"run {batch}" for case, batch in targeted.items()}}
    found, shipped_hash = {}, sha256(shipped)
    for folder in reversed(run_dirs(config)):
        if len(found) == len(wanted):
            break
        try:
            report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for case in report.get("cases") or []:
            # A --case run that left the case out did not measure it; an older full run may have.
            if case.get("CoverageReason") == "not-selected":
                continue
            if case.get("Id") in wanted and case.get("Id") not in found:
                found[case["Id"]] = (folder.name, report, case)
    problems, passed = [], []
    for case_id, run in wanted.items():
        if case_id not in found:
            problems.append(f"no run of {case_id}; {run}")
            continue
        name, report, case = found[case_id]
        if (report.get("modBuild") or {}).get("sha256") != shipped_hash:
            problems.append(f"newest {case_id} run {name} measured a different {shipped.name}; {run}")
        elif case.get("Result") != "pass":
            problems.append(f"{case_id} in run {name} did not pass ({case.get('Result')}): {case.get('Reason') or case.get('Evidence') or 'see report.json'}")
        elif case_id == PERF_CASE:
            passed.append(f"{case_id} {(case.get('Observed') or {}).get('modMsPerTick', '?')} ms/tick in run {name}")
        else:
            passed.append(f"{case_id} in run {name}")
    warnings = [] if targeted else ["no targeted perf.* cases; time the mod's patched and event-driven paths with PerfTiming (guide perf)"]
    return problems, passed, warnings


# ---- Evidence -----------------------------------------------------------------------------------------------------------

RUN_FILES = ("report.json", "progress.json", "deployment.json")


def run_dirs(config):
    """Run folders under the evidence root, oldest first by their latest report, progress or deployment file."""
    def stamp(folder):
        return max((p.stat().st_mtime for name in RUN_FILES if (p := folder / name).is_file()), default=None)
    folders = [(stamp(d), d) for d in config.evidence_root.iterdir() if d.is_dir()] if config.evidence_root.is_dir() else []
    return [d for when, d in sorted((f for f in folders if f[0] is not None), key=lambda f: f[0])]


def latest(config, batch=None):
    for folder in reversed(run_dirs(config)):
        report_path, progress_path = folder / "report.json", folder / "progress.json"
        if report_path.is_file():
            request = json.loads(report_path.read_text(encoding="utf-8")).get("request") or {}
        elif progress_path.is_file():
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            request = progress.get("Request") or {}
        else:
            continue
        if batch and request.get("Batch") != batch and batch not in (request.get("Batches") or []):
            continue
        if report_path.is_file():
            print(folder / "summary.txt")
            print((folder / "summary.txt").read_text(encoding="utf-8"))
            return 0
        # Never show an older run as the latest: a killed or crashed run has no report until the next run recovers it.
        finished = sum(1 for c in progress.get("Cases") or [] if c.get("Result") != "running")
        print(f"Run {folder.name} has no report: it is still running, or the game was killed or crashed before it finished.")
        print(f"Request: {', '.join(request.get('Batches') or [request.get('Batch', '?')])} seed {request.get('Seed')}; "
              f"stage {progress.get('Stage')}, batch {progress.get('BatchIndex', 0) + 1}, {finished} case(s) finished.")
        print(f"The next run closes it as interrupted and writes its report. Progress: {progress_path}")
        return 2
    print("No matching run found.")
    return 1


def timings(config, run=None):
    """Per-batch wall clock from a run's events.jsonl, slowest first. A batch runs from its first event to the next batch's
    first event; the last one ends at the run's final event."""
    if run:
        folder = Path(run) if Path(run).is_dir() else config.evidence_root / run
    else:
        folder = next((d for d in reversed(run_dirs(config)) if (d / "events.jsonl").is_file()), None)
    path = folder / "events.jsonl" if folder else None
    if not path or not path.is_file():
        print(f"No events.jsonl in {folder}." if folder else "No run with events.jsonl found.")
        return 1
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    starts = []
    for event in events:
        if event.get("batch") and (not starts or starts[-1][0] != event["batch"]):
            starts.append((event["batch"], event["monotonicSeconds"]))
    if not starts:
        print(f"No batch events in {path}.")
        return 1
    end = events[-1]["monotonicSeconds"]
    rows = [(batch, (starts[i + 1][1] if i + 1 < len(starts) else end) - start) for i, (batch, start) in enumerate(starts)]
    total = end - events[0]["monotonicSeconds"]
    width = max(len(batch) for batch, _ in rows)
    print(f"Run {folder.name}")
    for batch, seconds in sorted(rows, key=lambda row: -row[1]):
        print(f"  {batch:<{width}}  {seconds:8.1f} s  {100 * seconds / total if total else 0:5.1f}%")
    print(f"  {'total':<{width}}  {total:8.1f} s")
    return 0


def list_batches(config):
    print("Mod sets: " + ", ".join(list(config.mod_sets) + [FULL_SET]))
    try:
        listed = json.loads((config.evidence_root / "batches.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("No batch list yet: the game writes it each time it starts under the launcher, so it appears after the first run.")
        return 1
    if not config.dev_build.is_file() or listed.get("developerHash") != sha256(config.dev_build):
        print("Note: this list is from a different DevTests build than the one in the working tree.")
    for entry in listed["batches"]:
        tags = [t for t, on in (("runner self-check", entry.get("diagnostic")), ("showcase", entry.get("showcase"))) if on]
        tags += [f"mod set {config.batch_mod_sets[entry['id']]}"] if entry["id"] in config.batch_mod_sets else []
        print(f"{entry['id']}: {len(entry['cases'])} cases" + (f" ({', '.join(tags)})" if tags else ""))
    print(f"{RUN_ALL}: " + ", ".join(listed["runAll"]))
    return 0


def prune(config, keep):
    """Delete all but the newest run folders. Only this command removes evidence."""
    try:
        with session_lock(config):
            old = run_dirs(config)[:-keep]
            freed = 0
            for folder in old:
                freed += sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
                shutil.rmtree(folder)
                print("Removed", folder.name)
            print(f"Removed {len(old)} run folder(s), {freed / 1e6:.0f} MB, from {config.evidence_root}; kept the newest {keep}.")
            return 0
    except (OSError, RuntimeError) as error:
        print("REFUSED:", error)
        return 3


def self_check(config, seed=1):
    """Run the runner's own diagnostic batches and check what an exit code cannot show: cancellation, a clean stop at the
    time limit, and recovery of a run whose game was killed."""
    problems = []

    def run(batch, timeout, graceful=True):
        print(f"\n=== self-check: {batch}" + ("" if graceful else " (game killed at the limit)"), flush=True)
        config.last_run_dir = None
        return run_session(config, batch, seed, timeout, graceful=graceful), config.last_run_dir

    def read(run_dir):
        path = run_dir / "report.json" if run_dir else None
        report = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
        return report, {c["Id"]: c["Result"] for c in report.get("cases") or []}

    def expect(held, what):
        if not held:
            problems.append(what)

    code, _ = run("diagnostic", 900)
    expect(code == 0, f"diagnostic: exit code {code}, expected 0")
    code, _ = run("diagnostic-autosave", 1800)
    expect(code == 0, f"diagnostic-autosave: exit code {code}, expected 0")
    code, run_dir = run("diagnostic-cancel", 900)
    report, cases = read(run_dir)
    expect(report.get("status") == "cancelled", f"diagnostic-cancel: status {report.get('status')}, expected cancelled")
    expect(cases == {"diag-cancel.before": "pass", "diag-cancel.during": "error"},
           f"diagnostic-cancel: cases {cases}, expected before=pass, during=error and after never started")
    code, run_dir = run("diagnostic-stall", 120)
    report, cases = read(run_dir)
    expect(code == 2 and report.get("status") == "interrupted",
           f"diagnostic-stall: exit code {code}, status {report.get('status')}; expected 2 and a report closed as interrupted before the kill")
    expect(cases.get("diag-stall.forever") == "error", f"diagnostic-stall: cases {cases}, expected the stalled case in error")
    code, killed = run("diagnostic-stall", 90, graceful=False)
    expect(code == 2 and killed is not None and not (killed / "report.json").is_file(),
           f"diagnostic-stall (killed): exit code {code}, expected 2 and no report")
    code, _ = run("diagnostic", 900)
    expect(code == 0, f"diagnostic after a killed run: exit code {code}, expected 0")
    report, cases = read(killed)
    expect(report.get("status") == "interrupted" and cases.get("diag-stall.forever") == "error",
           f"recovery: the killed run has status {report.get('status')}, cases {cases}; expected interrupted with the stalled case in error")
    close_session(config)
    print()
    for problem in problems:
        print("SELF-CHECK FAIL:", problem)
    if not problems:
        print("SELF-CHECK PASS: diagnostics, cancellation, time-limit stop and recovery behaved as declared.")
    return 1 if problems else 0


GUIDE_TOPICS = {
    "index": "AGENTS.md",
    "authoring": "docs/authoring.md",
    "recipes": "docs/recipes/index.md",
    "placement": "docs/recipes/placement.md",
    "beds": "docs/recipes/beds.md",
    "measurements": "docs/recipes/measurements.md",
    "environment": "docs/recipes/environment.md",
    "perf": "docs/recipes/perf.md",
    "patches": "docs/recipes/patches.md",
    "maintaining": "docs/maintaining.md",
    "recording": "docs/recording.md",
}


def main(argv=None):
    # A language's folder name (Russian (Русский)) must not crash a launcher whose output is piped through a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    try:
        return run_command(argv)
    except Exception:  # any launcher fault gets its own exit code, so it is never read as a test failure (1)
        traceback.print_exc()
        print("LAUNCHER ERROR: the launcher itself failed; this is not a test result.")
        return 4


def run_command(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, help="the mod's DevTests/devtests.json (required except for guide)")
    commands = parser.add_subparsers(dest="command", required=True)
    guide = commands.add_parser("guide", help="agent instructions and searchable setup recipes; no game or config needed")
    guide.add_argument("topic", nargs="?", default="index", choices=GUIDE_TOPICS, help="read only the relevant topic")
    launch = commands.add_parser("run", help="run batches, or run-all; reuse the runner session or launch one")
    launch.add_argument("batch", nargs="+", help="one or more batches, run grouped by mod set; or run-all")
    launch.add_argument("--mods", metavar="SET", help="mod set from devtests.json, or full for the player's list (default: the batch's set)")
    launch.add_argument("--language", metavar="NAME", help="run in this installed game language, by short or full folder name "
                        "(Russian, ChineseSimplified); default English. An idle session in another language is relaunched")
    launch.add_argument("--seed", type=int, default=1)
    launch.add_argument("--case", action="append", default=[], metavar="ID",
                        help="run only cases whose full id matches (glob with * and ?; repeatable). The others are reported as "
                             "not-selected skips; batches save time only where their code checks ctx.Selected. A pattern matching no "
                             "planned case is refused. Not for release or seam runs")
    launch.add_argument("--timeout", type=int, default=900,
                        help="wall-clock seconds for the whole command, game startup included; the game closes the run with a report "
                             f"{DEADLINE_GRACE} s before it and is killed at it. With several batches it applies to each one. Raise it for run-all: each batch may take up to its own limit (15 minutes by default)")
    launch.add_argument("--startup-timeout", type=int, default=300, help="seconds a newly launched game has to load with the runner ready")
    launch.add_argument("--quit-on-finish", action="store_true", help="use a fresh process and close it after the run")
    launch.add_argument("--record", action="store_true", help="record the game window to build.mp4 in a fresh process")
    launch.add_argument("--ffmpeg", type=Path, help="FFmpeg build with gfxcapture support")
    launch.add_argument("--show-ui", action="store_true", help="keep the normal game HUD visible in recordings")
    launch.add_argument("--keep-open", action="store_true", help="fresh process, left paused after the run; close it to finish cleanup")
    launch.add_argument("--frames", type=int, metavar="N", help="with --record: save N evenly spaced stills and a contact sheet "
                                                               "from build.mp4 into the run's frames/ folder")
    commands.add_parser("status", help="who holds the install lease, whether RimWorld runs, and whether the installed mod matches this checkout")
    leaser = commands.add_parser("lease", help="take or release the install lease; a deploy script takes it before copying the mod")
    leaser.add_argument("action", choices=("take", "release"))
    leaser.add_argument("--purpose", default="deploy", help="shown to a checkout the lease refuses")
    stills = commands.add_parser("frames", help="stills and a contact sheet from a recorded run's build.mp4, without launching RimWorld")
    stills.add_argument("run", nargs="?", help="run folder name or path (default: the latest recorded run)")
    stills.add_argument("--at", help="comma-separated seconds, e.g. 3,8,14 (default: --count evenly spaced stills)")
    stills.add_argument("--count", type=int, default=6)
    stills.add_argument("--ffmpeg", type=Path)
    check = commands.add_parser("release-check", help="verify a mod folder contains no developer test runner and its DLL passed the perf batch and its perf.* cases")
    check.add_argument("mod_dir", nargs="?", type=Path)
    commands.add_parser("close-session", help="close the idle runner session and remove the developer DLL")
    show = commands.add_parser("latest", help="print the latest run's summary, or that it has no report, without launching RimWorld")
    show.add_argument("--batch")
    timing = commands.add_parser("timings", help="per-batch wall clock of a run, slowest first, without launching RimWorld")
    timing.add_argument("run", nargs="?", help="run folder name or path (default: the latest run)")
    commands.add_parser("list", help="list batches and mod sets without launching RimWorld")
    checker = commands.add_parser("self-check", help="run the runner's diagnostic batches and verify cancellation, time limits and recovery")
    checker.add_argument("--seed", type=int, default=1)
    pruner = commands.add_parser("prune", help="delete old run folders (reports, archived saves, videos)")
    pruner.add_argument("--keep", type=int, default=20, help="newest run folders to keep")
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
        if args.timeout <= 0 or args.startup_timeout <= 0:
            parser.error("--timeout and --startup-timeout must be greater than zero")
        if args.keep_open and args.quit_on_finish:
            parser.error("--keep-open and --quit-on-finish cannot be combined")
        if (args.ffmpeg or args.show_ui or args.frames) and not args.record:
            parser.error("--ffmpeg, --show-ui and --frames only apply with --record")
        if args.frames is not None and args.frames < 1:
            parser.error("--frames must be at least 1")
        try:
            config.language = resolve_language(args.language) if args.language else DEFAULT_LANGUAGE
        except RuntimeError as error:
            print("REFUSED:", error)
            return 3
        try:
            take_lease(config, "run")
        except RuntimeError as error:
            print("REFUSED:", error)
            return 3
        config.cases = [c for c in args.case if c.strip()]
        if any("," in c for c in config.cases):
            parser.error("--case takes one pattern each; repeat it for several")
        if config.cases:
            try:
                args.batch = select_case_batches(config, args.batch, config.cases)
            except (OSError, ValueError, RuntimeError) as error:
                print("REFUSED:", error)
                return 3
        if len(args.batch) > 1 and (RUN_ALL in args.batch or args.keep_open or args.quit_on_finish or args.record):
            parser.error("several batches run only in the reusable session, without run-all, --keep-open, --quit-on-finish or --record")
        if len(args.batch) > 1:
            return run_batches(config, args.batch, args.seed, args.timeout, args.mods, args.startup_timeout)
        args.batch = args.batch[0]
        if args.keep_open or args.quit_on_finish or args.record:
            code = run_once(config, args.batch, args.seed, args.timeout, args.keep_open, args.record, args.ffmpeg, args.show_ui, args.mods,
                            args.startup_timeout)
            take_lease(config, "run")  # refresh: a long recording should not read as idle
            if args.frames and config.last_run_dir and (config.last_run_dir / "build.mp4").is_file():
                frames(config, str(config.last_run_dir), count=args.frames, ffmpeg=args.ffmpeg)
            return code
        code = run_session(config, args.batch, args.seed, args.timeout, args.mods, args.startup_timeout)
        take_lease(config, "run")
        return code
    if args.command == "close-session":
        code = close_session(config)
        if code == 0 and release_lease(config):
            print("Released the install lease.")
        return code
    if args.command == "status":
        return status(config)
    if args.command == "lease":
        return lease_command(config, args.action, args.purpose)
    if args.command == "frames":
        at = [float(t) for t in args.at.split(",") if t.strip()] if args.at else None
        return frames(config, args.run, at, args.count, args.ffmpeg)
    if args.command == "latest":
        return latest(config, args.batch)
    if args.command == "timings":
        return timings(config, args.run)
    if args.command == "list":
        return list_batches(config)
    if args.command in ("self-check", "install-dev"):
        try:
            take_lease(config, args.command)
        except RuntimeError as error:
            print("REFUSED:", error)
            return 3
    if args.command == "self-check":
        return self_check(config, args.seed)
    if args.command == "prune":
        if args.keep < 1:
            parser.error("--keep must be at least 1")
        return prune(config, args.keep)
    if args.command == "release-check":
        mod_dir = args.mod_dir or config.mod_dir
        problems = release_problems(config, mod_dir)
        static, static_warnings = static_problems(config, mod_dir)
        perf, measured, warnings = perf_problems(config, mod_dir)
        warnings = static_warnings + warnings
        for problem in problems + static + perf:
            print("FAIL:", problem)
        if not problems:
            print("PASS: no developer test runner in", mod_dir)
        if not static:
            print("PASS: patch roots and preview size in", mod_dir)
        problems += static
        for line in measured if not perf else []:
            print("PASS: perf", line)
        for warning in warnings:
            print("WARN:", warning)
        return 1 if problems or perf else 0
    if args.command == "install-dev":
        missing = [str(build) for build in config.developer_builds if not build.is_file()]
        if missing:
            print(f"REFUSED: build DevTests first (dotnet build {config.dev_project} -c Release); missing {', '.join(missing)}")
            return 3
        for build in config.developer_builds:
            shutil.copy2(build, config.dev_assemblies / build.name)
        # Without launcher arguments the DLLs stay inactive unless this marker sits beside them.
        (config.dev_assemblies / MANUAL_MARKER).write_text("install-dev: developer-menu tests enabled\n", encoding="utf-8")
        print("Installed DevTests in", config.dev_assemblies, "- run remove-dev before publishing.")
    else:
        remove_developer_files(config)
        print("Removed DevTests from", config.dev_assemblies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
