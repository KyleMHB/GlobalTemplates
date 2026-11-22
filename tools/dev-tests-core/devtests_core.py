"""Game-agnostic parts of the developer test launchers (RimWorld Dev Tests, Timberborn Dev Tests).

A game adapter imports this module and keeps everything that knows about one game: install paths, mod lists, the launch
command and the in-game runner. Functions here take explicit paths instead of an adapter's config object, so each adapter
keeps its own config shape.

Exit codes shared by every adapter: 0 pass, 1 failures or isolation breach, 2 timeout, interrupted run, crash or no report,
3 refusal, 4 launcher error (bad config, missing file, bug).
"""
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import traceback

PASS, FAILED, NO_REPORT, REFUSED, LAUNCHER_ERROR = 0, 1, 2, 3, 4
# The game closes its run this long before the launcher's limit, so the report is written before the kill.
DEADLINE_GRACE = 15
LOG_TAIL_LINES = 40
LOG_KEEP_BYTES = 20 * 1024 * 1024
# Files whose newest modification time orders run folders. An adapter adds its own launcher-side files.
RUN_FILES = ("report.json", "progress.json", "deployment.json")


# ---- Local configuration -------------------------------------------------------------------------------------------------

def local_value(local_file, key, default=None):
    """A value from an adapter's untracked <tool>.local.json, else the default."""
    local_file = Path(local_file)
    if local_file.is_file():
        value = json.loads(local_file.read_text(encoding="utf-8")).get(key)
        if value is not None:
            return value
    return default


def local_path(env_name, local_file, key, default):
    """The environment variable, then the key in the local file, then the default."""
    if os.environ.get(env_name):
        return Path(os.environ[env_name])
    return Path(local_value(local_file, key, default))


# ---- Runs, results and deadlines ---------------------------------------------------------------------------------------

def new_run_id(batch, seed=None, cases=None):
    """A run filtered by --case says so in its id, so its folder is never mistaken for a full batch run. A game without a
    seed (Timberborn never seeds its randomness) leaves the seed out."""
    seed_part = f"-s{seed}" if seed is not None else ""
    return f"{datetime.now():%Y%m%d-%H%M%S}-{re.sub(r'[^a-z0-9-]', '-', batch.lower())}{seed_part}" + ("-cases" if cases else "")


def game_deadline(deadline, graceful=True):
    """UTC milliseconds at which the game should close its run, or 0 when the limit is too short to leave a margin."""
    remaining = deadline - time.monotonic()
    return int((time.time() + remaining - DEADLINE_GRACE) * 1000) if graceful and remaining > 2 * DEADLINE_GRACE else 0


def result_code(report, problems, recording_error=None):
    if report is None:
        return NO_REPORT
    if report.get("status") == "refused":
        return REFUSED
    if report.get("status") == "interrupted":
        print("Run interrupted:", report.get("reason"))
        return NO_REPORT
    return PASS if report.get("overallPass") and not problems and not recording_error else FAILED


def guarded(command, argv):
    """Run a launcher command; any launcher fault gets its own exit code, so it is never read as a test failure (1)."""
    try:
        return command(argv)
    except Exception:
        traceback.print_exc()
        print("LAUNCHER ERROR: the launcher itself failed; this is not a test result.")
        return LAUNCHER_ERROR


# ---- Processes -----------------------------------------------------------------------------------------------------------

def pids(image):
    """Process ids of every running process with this image name (Windows)."""
    listing = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, check=False).stdout
    return [int(row[1]) for row in (line.split('","') for line in listing.splitlines()) if len(row) > 1 and row[1].isdigit()]


def wait_for(predicate, seconds, step=0.5):
    """The predicate's first truthy value within the time, else None."""
    end = time.monotonic() + seconds
    while True:
        value = predicate()
        if value or time.monotonic() >= end:
            return value or None
        time.sleep(step)


class GameProcess:
    """Hold the exact Windows process so timeout cleanup cannot target a reused PID."""

    def __init__(self, pid):
        from ctypes import wintypes
        self.pid = pid
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.TerminateProcess.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        # PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
        self.handle = self.api.OpenProcess(0x100000 | 0x1000 | 0x0001, False, pid)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "could not open the game process")

    def alive(self):
        return self.api.WaitForSingleObject(self.handle, 0) == 258  # WAIT_TIMEOUT

    def wait(self, seconds):
        """True when the process exited within the time."""
        self.api.WaitForSingleObject(self.handle, int(seconds * 1000))
        return not self.alive()

    def kill(self):
        if self.alive():
            if not self.api.TerminateProcess(self.handle, 1):
                raise OSError(ctypes.get_last_error(), "could not stop the timed-out game")
            self.api.WaitForSingleObject(self.handle, 5000)

    def close(self):
        self.api.CloseHandle(self.handle)


# ---- Evidence: run folders, latest, timings, prune ------------------------------------------------------------------------

def run_dirs(evidence_root, run_files=RUN_FILES):
    """Run folders under the evidence root, oldest first by their newest run file."""
    def stamp(folder):
        return max((p.stat().st_mtime for name in run_files if (p := folder / name).is_file()), default=None)
    evidence_root = Path(evidence_root)
    folders = [(stamp(d), d) for d in evidence_root.iterdir() if d.is_dir()] if evidence_root.is_dir() else []
    return [d for when, d in sorted((f for f in folders if f[0] is not None), key=lambda f: f[0])]


def latest(evidence_root, batch=None, run_files=RUN_FILES, unfinished_files=()):
    """Print the newest run's summary. A newer run without a report (still running, killed or crashed) is shown as such,
    never hidden behind an older report. unfinished_files names launcher-side files that mark a started run on their own."""
    for folder in reversed(run_dirs(evidence_root, run_files)):
        report_path, progress_path = folder / "report.json", folder / "progress.json"
        progress = {}
        if report_path.is_file():
            request = json.loads(report_path.read_text(encoding="utf-8")).get("request") or {}
        elif progress_path.is_file():
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            request = progress.get("Request") or {}
        elif any((folder / name).is_file() for name in unfinished_files):
            request = {}
        else:
            continue
        if batch and request.get("Batch") != batch and batch not in (request.get("Batches") or []):
            continue
        if report_path.is_file():
            summary = folder / "summary.txt"
            print(summary)
            print(summary.read_text(encoding="utf-8") if summary.is_file() else f"(no summary.txt; see {report_path})")
            return 0
        # Never show an older run as the latest: a killed or crashed run has no report until the next run recovers it.
        finished = sum(1 for c in progress.get("Cases") or [] if c.get("Result") != "running")
        print(f"Run {folder.name} has no report: it is still running, or the game was killed or crashed before it finished.")
        if progress:
            print(f"Request: {', '.join(request.get('Batches') or [request.get('Batch', '?')])} seed {request.get('Seed')}; "
                  f"stage {progress.get('Stage')}, batch {progress.get('BatchIndex', 0) + 1}, {finished} case(s) finished.")
            print(f"The next run closes it as interrupted and writes its report. Progress: {progress_path}")
        return 2
    print("No matching run found.")
    return 1


def timings(evidence_root, run=None, run_files=RUN_FILES):
    """Per-batch wall clock from a run's events.jsonl, slowest first. A batch runs from its first event to the next batch's
    first event; the last one ends at the run's final event."""
    evidence_root = Path(evidence_root)
    if run:
        folder = Path(run) if Path(run).is_dir() else evidence_root / run
    else:
        folder = next((d for d in reversed(run_dirs(evidence_root, run_files)) if (d / "events.jsonl").is_file()), None)
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


def prune(evidence_root, keep, run_files=RUN_FILES):
    """Delete all but the newest run folders. Only this command removes evidence. The adapter holds its own lock."""
    try:
        old = run_dirs(evidence_root, run_files)[:-keep]
        freed = 0
        for folder in old:
            freed += sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
            shutil.rmtree(folder)
            print("Removed", folder.name)
        print(f"Removed {len(old)} run folder(s), {freed / 1e6:.0f} MB, from {evidence_root}; kept the newest {keep}.")
        return 0
    except OSError as error:
        print("REFUSED:", error)
        return 3


# ---- Protected data: prove the player's files were not touched -------------------------------------------------------------

def tree_snapshot(*folders):
    """Size and modification time of every file under the folders; a missing folder is empty."""
    files = {}
    for folder in folders:
        folder = Path(folder)
        if folder.is_dir():
            for path in folder.rglob("*"):
                if path.is_file():
                    stat = path.stat()
                    files[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return files


def snapshot_diff(before, after, ignore=()):
    """Paths added, removed or changed between two snapshots, except files named in ignore."""
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p) and Path(p).name not in ignore)


def move_new_files(before, folder, destination):
    """Move files that appeared directly in folder since the snapshot (crash reports the game writes) into destination."""
    moved = []
    for path in snapshot_diff(before, tree_snapshot(folder)):
        path = Path(path)
        if str(path) not in before and path.is_file() and path.parent == Path(folder):
            Path(destination).mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(Path(destination) / path.name))
            moved.append(path.name)
    return moved


# ---- Logs ------------------------------------------------------------------------------------------------------------------

EXCEPTION_LINE = re.compile(r"^[\w.`]*Exception\b(:|$)")
ERROR_LINE = re.compile(r"^\[?(Error|ERROR)\]?[: ]")


def tail(path, lines=LOG_TAIL_LINES):
    path = Path(path)
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]) if path.is_file() else f"(missing: {path})"


def keep_log(source, run_dir, keep_bytes=LOG_KEEP_BYTES, name="Player.log"):
    """Copy a log into the run folder (its tail when huge). False when there is no log to copy."""
    source = Path(source)
    try:
        with source.open("rb") as log:
            log.seek(max(0, source.stat().st_size - keep_bytes))
            Path(run_dir).mkdir(parents=True, exist_ok=True)
            (Path(run_dir) / name).write_bytes(log.read())
        return True
    except OSError:
        return False


def log_errors(path, crash_markers=("First uncaught exception",), keep=10):
    """Exception and error lines in a Unity player log, whether a crash marker appeared, and the first few lines found.
    A launcher-side count for runs whose game never wrote a report; the in-game runner counts errors itself."""
    counts = {"exceptions": 0, "errors": 0, "crashed": False, "first": []}
    path = Path(path)
    if not path.is_file():
        return counts
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if any(marker in line for marker in crash_markers):
            counts["crashed"] = True
        kind = "exceptions" if EXCEPTION_LINE.match(line) else "errors" if ERROR_LINE.match(line) else None
        if kind:
            counts[kind] += 1
            if len(counts["first"]) < keep:
                counts["first"].append(line.strip())
    return counts
