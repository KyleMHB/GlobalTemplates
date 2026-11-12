"""Real-time capture of the runner's RimWorld window, coordinated by immutable marker files."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time

# Capture-start attempts before the first frame. Spaced 0, 2 and 4 seconds apart, inside the game's 30-second wait.
START_ATTEMPTS, RETRY_DELAY = 3, 2


def find_ffmpeg(explicit=None):
    candidates = (Path.cwd() / "work/ffmpeg/ffmpeg.exe", Path(__file__).resolve().parent / "work/ffmpeg/ffmpeg.exe")
    local = next((str(path) for path in candidates if path.is_file()), None)
    executable = str(explicit) if explicit else shutil.which("ffmpeg") or local
    if not executable:
        raise ValueError("FFmpeg is missing. Put a Windows build in work/ffmpeg/ or pass --ffmpeg PATH.")
    help_result = subprocess.run([executable, "-hide_banner", "-h", "filter=gfxcapture"],
                                 capture_output=True, text=True, timeout=15)
    if "window_exe" not in help_result.stdout + help_result.stderr:
        raise ValueError("This FFmpeg build lacks gfxcapture window capture. Use a recent Windows build with that filter.")
    return executable


class Recording:
    def __init__(self, executable, run_dir, timeout, hide_ui=True):
        self.executable, self.run_dir, self.timeout = executable, run_dir, timeout
        self.hide_ui = hide_ui
        self.process = self.log = None
        self.first_frame = threading.Event()
        self.started_at = self.tail_until = None
        self.frames = 0
        self.video_origin = None
        self.error = None
        self.done = self.acknowledged = False
        self.attempts, self.retry_at = 0, None
        self.output = run_dir / "build.mp4"
        self.raw_output = run_dir / "build-raw.mp4"

    def marker(self, name):
        return self.run_dir / f"capture-{name}.json"

    def write(self, name, value):
        target = self.marker(name)
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(value), encoding="utf-8")
        temp.replace(target)

    def start(self):
        self.attempts += 1
        if self.log:
            self.log.close()
        self.log = (self.run_dir / "recording.log").open("w" if self.attempts == 1 else "a", encoding="utf-8")
        self.log.write(f"--- capture attempt {self.attempts} of {START_ATTEMPTS}\n")
        self.log.flush()
        # Capture only the game window; a capture failure must never expose the desktop.
        source = "gfxcapture=window_exe='RimWorld[.]exe':capture_cursor=0:capture_border=0:display_border=0:max_framerate=60:width=-2:height=-2"
        args = [self.executable, "-hide_banner", "-loglevel", "warning", "-n", "-stats_period", "0.1",
                "-progress", "pipe:1", "-f", "lavfi", "-i", source,
                "-vf", "hwdownload,format=bgra,format=yuv420p", "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "18", "-r", "60", "-fps_mode", "cfr", "-movflags", "+frag_keyframe+empty_moov+default_base_moof",
                "-t", str(self.timeout), str(self.raw_output)]
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                        text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.started_at = time.monotonic()
        self.progress_thread = threading.Thread(target=self.read_progress, daemon=True)
        self.progress_thread.start()

    def read_progress(self):
        for line in self.process.stdout:
            if line.startswith("frame="):
                self.frames = int(line.split("=", 1)[1])
                if self.frames > 0:
                    if self.video_origin is None:
                        self.video_origin = time.perf_counter() - self.frames / 60
                    self.first_frame.set()

    def poll(self):
        if self.done:
            return
        try:
            if self.process is None and self.marker("ready").is_file() and (self.retry_at is None or time.monotonic() >= self.retry_at):
                self.start()
            if self.process is not None:
                if self.process.poll() is not None:
                    # gfxcapture can fail to open the window just after the game reports ready. The game waits for the
                    # first frame before testing, so a restart before then loses nothing.
                    if not self.acknowledged and self.attempts < START_ATTEMPTS:
                        self.progress_thread.join(timeout=2)
                        self.process.stdin.close()
                        self.process.stdout.close()
                        self.process = None
                        self.retry_at = time.monotonic() + RETRY_DELAY * self.attempts
                        return
                    raise RuntimeError(f"FFmpeg ended before capture completion (attempt {self.attempts} of {START_ATTEMPTS}); see recording.log")
                if not self.acknowledged:
                    if self.first_frame.is_set():
                        self.write("started", {"utc": datetime.now(timezone.utc).isoformat(), "fps": 60,
                                               "videoOriginMonotonicSeconds": self.video_origin})
                        self.acknowledged = True
                        print(f"Recording: {self.output}", flush=True)
                    elif time.monotonic() - self.started_at > 20:
                        raise RuntimeError("FFmpeg did not capture a frame within 20 seconds; see recording.log")
            if self.marker("complete").is_file():
                if self.tail_until is None:
                    self.tail_until = time.monotonic() + 2
                if time.monotonic() >= self.tail_until:
                    self.close()
        except (OSError, RuntimeError) as error:
            self.error = str(error)
            self.write("failed", {"error": self.error})
            self.close()

    def close(self):
        if self.done:
            return
        self.done = True
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    self.process.stdin.write("q\n")
                    self.process.stdin.flush()
                self.process.wait(timeout=15)
            except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                if self.process.poll() is None:
                    self.process.kill()
                    self.process.wait()
            finally:
                self.progress_thread.join(timeout=2)
                self.process.stdin.close()
                self.process.stdout.close()
                self.log.close()
            if self.process.returncode != 0:
                self.error = self.error or "FFmpeg capture failed; see recording.log"
            # Keep recoverable raw footage unless conversion completes successfully.
            if self.raw_output.is_file() and self.raw_output.stat().st_size > 0:
                remux_cmd = [self.executable, "-hide_banner", "-loglevel", "error", "-y", "-i", str(self.raw_output),
                             "-c", "copy", "-movflags", "+faststart", str(self.output)]
                try:
                    with (self.run_dir / "recording.log").open("a", encoding="utf-8") as log:
                        result = subprocess.run(remux_cmd, stdout=subprocess.DEVNULL, stderr=log, timeout=60)
                    if result.returncode != 0:
                        self.error = self.error or "FFmpeg conversion failed; raw video retained; see recording.log"
                    elif self.output.is_file() and self.output.stat().st_size > 0:
                        self.raw_output.unlink()
                except (OSError, subprocess.TimeoutExpired) as error:
                    self.error = self.error or f"FFmpeg conversion failed; raw video retained: {error}"
            if not self.output.is_file() or self.output.stat().st_size == 0:
                self.error = self.error or "FFmpeg did not produce a complete video; see recording.log"
        else:
            self.error = self.error or "The showcase ended before capture started"
        if self.run_dir.is_dir():
            metadata = {"video": self.output.name, "fps": 60, "frames": self.frames, "gameUIHidden": self.hide_ui,
                        "backend": "FFmpeg gfxcapture / Windows Graphics Capture", "audio": False,
                        "realTime": True, "success": self.error is None, "error": self.error,
                        "rawDurationSeconds": self.frames / 60,
                        "videoOriginMonotonicSeconds": self.video_origin,
                        "alignment": "Approximate QPC alignment from first FFmpeg progress; includes encoder/reporting latency, not frame-exact",
                        "note": "Build timings include recording overhead; video includes a two-second final hold."}
            (self.run_dir / "recording.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            self.write("stopped", {"success": self.error is None, "error": self.error})
        if self.error:
            print("RECORDING FAIL:", self.error, flush=True)
        else:
            print(f"Video saved: {self.output}", flush=True)
