"""Join two or more video clips into one labelled side-by-side comparison.

See README.md beside this file for the commands.
"""
import argparse
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FPS = 30
BAR = 60  # the label strip above each panel
GAP = 2
barColour = "0x1e1f22"
oldColour = "0xe0a868"
midColour = "0xa5aab4"
newColour = "0x7fd6a0"
uploadLimit = 10 * 1024 * 1024  # Discord's upload limit without Nitro


def find_ffmpeg(explicit):
    """An explicit path, then PATH, then the RimWorld test harness's shared copy beside this tool."""
    shared = Path(__file__).resolve().parent.parent / "rimworld-dev-tests" / "work" / "ffmpeg"
    candidates = [explicit, shutil.which("ffmpeg"), shared / "ffmpeg.exe", shared / "ffmpeg"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    sys.exit("ffmpeg not found: pass --ffmpeg, or put it on PATH")


def find_font():
    names = ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
    return next((name for name in names if Path(name).is_file()), None)


def escape(path):
    """Quotes a file path for use inside a quoted ffmpeg filter option."""
    return str(path).replace("\\", "/").replace(":", "\\:")


def run(command):
    result = subprocess.run([str(c) for c in command], capture_output=True, text=True, errors="replace")
    # ffmpeg builds without a fontconfig file print this on every drawtext; the font is given by path, so it is noise.
    errors = [line for line in result.stderr.splitlines() if line.strip() and "Fontconfig" not in line]
    if result.returncode != 0:
        sys.exit("ffmpeg failed:\n" + "\n".join(errors))
    return result.stdout


def duration(ffmpeg, path):
    probe = ffmpeg.with_name("ffprobe" + ffmpeg.suffix)
    if not probe.is_file():
        sys.exit(f"give {path.name} a LENGTH: ffprobe is not beside ffmpeg to measure it")
    return float(run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def parse_clip(ffmpeg, values):
    if not 2 <= len(values) <= 5:
        sys.exit("--clip takes LABEL FILE [START [LENGTH [ZOOM]]]")
    path = Path(values[1])
    if not path.is_file():
        sys.exit(f"no such clip: {path}")
    try:
        numbers = [float(v) for v in values[2:]]
    except ValueError:
        sys.exit(f"START, LENGTH and ZOOM must be numbers: {' '.join(values[2:])}")
    start = numbers[0] if numbers else 0.0
    length = numbers[1] if len(numbers) > 1 else duration(ffmpeg, path) - start
    zoom = numbers[2] if len(numbers) > 2 else 1.0
    if length <= 0 or zoom < 1:
        sys.exit(f"{values[0]}: LENGTH must be above 0 and ZOOM at least 1")
    return {"label": values[0], "path": path, "start": start, "length": length, "zoom": zoom}


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", required=True, type=Path, help="the MP4 to write")
    parser.add_argument("--clip", action="append", nargs="+", required=True, metavar="VALUE",
                        help="LABEL FILE [START [LENGTH [ZOOM]]], oldest first; repeat for each clip")
    parser.add_argument("--length", type=float, help="seconds of output (default: the longest clip); shorter clips loop")
    parser.add_argument("--panel", default="960x540", help="size of each clip's panel (default: 960x540)")
    parser.add_argument("--layout", choices=["row", "stack", "feature"], default="row",
                        help="row: side by side (default); stack: above each other; "
                             "feature: the older clips in a row, the newest large beneath them")
    parser.add_argument("--still", type=float, metavar="SECONDS", help="also write a PNG of the frame at this time")
    parser.add_argument("--ffmpeg", help="path to ffmpeg")
    args = parser.parse_args(argv)

    ffmpeg = find_ffmpeg(args.ffmpeg)
    clips = [parse_clip(ffmpeg, values) for values in args.clip]
    if len(clips) < 2:
        sys.exit("give at least two --clip entries")
    try:
        width, height = (int(n) for n in args.panel.lower().split("x"))
    except ValueError:
        sys.exit("--panel is WIDTHxHEIGHT, such as 960x540")
    total = args.length or max(clip["length"] for clip in clips)
    font = find_font()
    fontOption = f"fontfile='{escape(font)}':" if font else ""

    # Labels reach drawtext through files, so their punctuation needs no filter escaping.
    labels = Path(tempfile.mkdtemp(prefix="clip-compare-"))
    command = [ffmpeg, "-v", "error", "-y"]
    chains = []
    for index, clip in enumerate(clips):
        labelFile = labels / f"{index}.txt"
        labelFile.write_text(clip["label"], encoding="utf-8")
        command += ["-ss", f"{clip['start']:.3f}", "-t", f"{clip['length']:.3f}", "-i", clip["path"]]
        colour = newColour if index == len(clips) - 1 else oldColour if index == 0 else midColour
        frames = min(math.ceil(clip["length"] * FPS), 32767)
        # In the feature layout the newest clip spans the row of older ones above it.
        span = len(clips) - 1 if args.layout == "feature" and index == len(clips) - 1 else 1
        panelWidth, panelHeight = width * span, height * span
        innerWidth, innerHeight = panelWidth - 2 * GAP, panelHeight - GAP
        chains.append(
            f"[{index}:v]fps={FPS},crop=iw/{clip['zoom']}:ih/{clip['zoom']},"
            # A clip shorter than the output repeats, so the newest version can run on while an older one loops.
            f"loop=loop=-1:size={frames}:start=0,trim=duration={total:.3f},setpts=N/{FPS}/TB,"
            f"scale={innerWidth}:{innerHeight}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={innerWidth}:{innerHeight}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"pad={panelWidth}:{panelHeight + BAR}:{GAP}:{BAR}:color={barColour},"
            f"drawtext={fontOption}textfile='{escape(labelFile)}':expansion=none:fontcolor={colour}:fontsize=30:x=20:y=14[v{index}]")
    joined = "".join(f"[v{index}]" for index in range(len(clips)))
    if args.layout == "feature" and len(clips) > 2:
        older = len(clips) - 1
        chains.append(f"{joined[:-len(f'[v{older}]')]}hstack=inputs={older}[top]")
        chains.append(f"[top][v{older}]vstack=inputs=2")
    elif args.layout == "feature":
        chains.append(f"{joined}vstack=inputs=2")
    else:
        chains.append(f"{joined}{'vstack' if args.layout == 'stack' else 'hstack'}=inputs={len(clips)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    command += ["-filter_complex", ";".join(chains), "-an", "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "23",
                "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.output]
    run(command)
    shutil.rmtree(labels, ignore_errors=True)
    size = args.output.stat().st_size
    print(f"{args.output} ({total:.1f} s, {size / 1048576:.1f} MB)")
    if size > uploadLimit:
        print("Warning: over 10 MB, Discord's upload limit without Nitro. Shorten the clip or use a smaller --panel.")
    if args.still is not None:
        still = args.output.with_suffix(".png")
        run([ffmpeg, "-v", "error", "-y", "-ss", f"{args.still:.3f}", "-i", args.output, "-frames:v", "1", still])
        print(still)


if __name__ == "__main__":
    main(sys.argv[1:])
