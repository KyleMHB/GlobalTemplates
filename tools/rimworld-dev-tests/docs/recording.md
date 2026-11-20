# Recording a test run

The common runner and `recording.py` provide recording for any mod adapter. Mod-specific batches, camera tours and showcase blueprints stay in the owning mod. Recording uses a fresh process; ordinary runs still reuse an idle session.

From the mod root, for example:

```powershell
python tools/mymod_test.py run mymod-batch --seed 1 --record --show-ui --ffmpeg <path-to>/ffmpeg.exe
```

Use an installed FFmpeg build with the Windows `gfxcapture` filter. The launcher checks support before launch. Search order is an explicit `--ffmpeg`, PATH, the current project's `work/ffmpeg/ffmpeg.exe`, then the shared harness's `work/ffmpeg/ffmpeg.exe`. No download is automatic.

This machine's shared copy is `work/ffmpeg/ffmpeg.exe` (with `ffprobe.exe`), FFmpeg 9.0.2 essentials from gyan.dev (`https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip`, sha256 checked, installed 2026-11-16); `work/` is ignored, so reinstall it there on another machine.

The game pauses setup until the recorder confirms its first captured frame. `capture-*.json` markers coordinate readiness, failures and completion. The launcher retries capture start up to three times; failure stops the run rather than silently producing gameplay evidence without a recording. Inspect `recording.log`, `recording.json`, `build.mp4` and the normal report in the run directory. Recoverable raw footage remains when final conversion fails. Recording adds real CPU/GPU overhead; video duration is not an unrecorded regression runtime.

To look at a recording, take stills rather than writing an FFmpeg pipeline: `run ... --record --frames 6` saves six evenly spaced stills and a contact sheet into the run's `frames/` folder, and `frames [run] --at 3,8,14` (or `--count N`) does the same for an earlier recording without launching the game. Both find FFmpeg the same way recording does (`--ffmpeg`, then PATH, then `work/ffmpeg/ffmpeg.exe`) and print each still's path and time. Read `frames/frames.png` first; open single stills only where the sheet is too small.

`--show-ui` keeps the normal HUD visible; without it the recording hides that HUD in the runner-owned colony. The test progress panel remains a separate runner overlay. Escape cancels while the normal menu shortcut is hidden. `--keep-open` leaves the game paused after recording; close it to finish cleanup. Live game capture is version/platform dependent; passing recorder unit tests does not establish a successful recording on a different installation.

A mod's wrapper can add its own showcase, recording and triage commands while importing the same `recording.py`. Shared C# `RunRecording` handles both regular batches and showcase recorder waits. New showcase batches may use `Batch.Prepare`/`Archive`, `Wait.Seconds`/`Recorder`, and the runner's save-export checks; their layouts and gameplay assertions belong to the mod.
