"""Render a comparison contact sheet: one or more items across their versions, with arrows.

See README.md beside this file for the commands.
"""
import argparse
import colorsys
import io
import re
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

SS = 2  # the shapes are drawn at this scale and reduced, which smooths their edges

sheetColour = (30, 31, 34)
textColour = (242, 243, 245)
mutedColour = (165, 170, 180)
fallbackAccent = (88, 101, 242)

pad = 36
arrowGap = 84
rowGap = 20
captionHeight = 30
headerHeight = 40


def font(size, bold=True):
    names = ["seguisb.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else [
        "segoeui.ttf", "DejaVuSans.ttf", "arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def git(args, cwd, text=True):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=text)
    if result.returncode != 0:
        error = result.stderr if text else result.stderr.decode(errors="replace")
        sys.exit(f"git {' '.join(args)} failed: {error.strip()}")
    return result.stdout


def resolve(source):
    """A file path, a bare name tracked by git (`SunstoneArray`), or `REV:path`."""
    path = Path(source)
    if path.is_file():
        return path
    tracked = git(["ls-files"], ".").splitlines()
    wanted = source if source.lower().endswith(".png") else source + ".png"
    matches = [p for p in tracked if Path(p).name.lower() == wanted.lower()]
    if len(matches) > 1:
        # A mod keeps old copies beside its design sources; the shipped one wins.
        shipped = [p for p in matches if p.startswith("Textures/")]
        matches = shipped if len(shipped) == 1 else matches
    if len(matches) == 1:
        root = git(["rev-parse", "--show-cdup"], ".").strip()
        return Path(root) / matches[0]
    if matches:
        sys.exit(f"'{source}' matches several files; pass a path:\n  " + "\n  ".join(matches))
    return None


def load(source):
    path = resolve(source)
    if path is not None:
        data = path.read_bytes()
    elif ":" in source:
        data = git(["show", source], ".", text=False)
    else:
        sys.exit(f"Can't find '{source}' as a file, a tracked image name or REV:path.")
    return data


def history(source, count):
    """The last `count` distinct versions of a file, oldest first, as (caption, bytes)."""
    path = resolve(source)
    if path is None:
        sys.exit(f"Can't find '{source}' for --history.")
    folder = path.parent
    tracked = git(["ls-files", "--full-name", "--", path.name], folder).strip()
    versions = [("Current", path.read_bytes())]
    log = git(["log", "--format=%h|%ad", "--date=format:%d %b", "--", path.name], folder)
    for line in log.splitlines():
        if len(versions) > count:
            break
        commit, date = line.split("|")
        blob = git(["show", f"{commit}:{tracked}"], folder, text=False)
        if blob == versions[-1][1]:
            # This commit introduced the version already listed; date it unless it is the current one.
            if versions[-1][0] != "Current":
                versions[-1] = (date.lstrip("0"), blob)
            continue
        versions.append((date.lstrip("0"), blob))
    return list(reversed(versions[:count]))


def accentOf(image):
    """The item's own colour: the average of its saturated, opaque pixels."""
    small = image.convert("RGBA").resize((48, 48))
    total, n = [0, 0, 0], 0
    raw = small.tobytes()
    for i in range(0, len(raw), 4):
        r, g, b, a = raw[i:i + 4]
        if a < 200:
            continue
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s > 0.4 and v > 0.45:
            total[0] += r; total[1] += g; total[2] += b; n += 1
    if n < 20:
        return fallbackAccent
    h, s, v = colorsys.rgb_to_hsv(*(c / n / 255 for c in total))
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, min(s, 0.8), max(v, 0.9)))


def hexColour(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def tile(size, backdrop):
    """A rounded square that is lighter in the middle, so dark outlines stay readable."""
    edge = tuple(round(c * 0.8) for c in backdrop)
    glow = Image.radial_gradient("L").resize((size, size))
    square = Image.composite(Image.new("RGB", (size, size), edge), Image.new("RGB", (size, size), backdrop), glow)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 14, fill=255)
    square.putalpha(mask)
    return square


def arrow(draw, x, y, width, colour):
    head = 19 * SS
    draw.line((x, y, x + width - head, y), fill=colour, width=9 * SS)
    draw.ellipse((x - 4.5 * SS, y - 4.5 * SS, x + 4.5 * SS, y + 4.5 * SS), fill=colour)
    draw.polygon([(x + width, y), (x + width - head * 1.15, y - head), (x + width - head * 1.15, y + head)], fill=colour)


def equals(draw, x, y, width, colour):
    for offset in (-8 * SS, 8 * SS):
        draw.line((x + width * 0.2, y + offset, x + width * 0.8, y + offset), fill=colour, width=7 * SS)


def render(items, labels, title, subtitle, footer, cell, backdrop, accent):
    """`items` is a list of (label, [(caption, bytes), ...])."""
    columns = max(len(versions) for _, versions in items)
    captions = labels is None and any(caption for _, versions in items for caption, _ in versions)
    titleFont, subtitleFont = font(34), font(18, bold=False)
    labelFont, captionFont, footerFont = font(21), font(17), font(15, bold=False)

    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    gutter = max((measure.textlength(label, font=labelFont) for label, _ in items if label), default=0)
    gutter = round(gutter) + 26 if gutter else 0

    top = pad
    if title:
        top += 46
    if subtitle:
        top += 28
    if title or subtitle:
        top += 14
    if labels:
        top += headerHeight
    rowHeight = cell + (captionHeight if captions else 0)
    width = pad * 2 + gutter + columns * cell + (columns - 1) * arrowGap
    height = top + len(items) * rowHeight + (len(items) - 1) * rowGap + pad + (26 if footer else 0)

    shapes = Image.new("RGBA", (width * SS, height * SS), sheetColour + (255,))
    draw = ImageDraw.Draw(shapes)
    square = tile(cell * SS, backdrop)
    placed = []  # (image, x, y) pasted after the shapes are reduced, so the art is resized only once
    texts = []   # (xy, text, font, colour, anchor)

    left = pad + gutter
    rows = []
    for index, (label, versions) in enumerate(items):
        images = [Image.open(io.BytesIO(data)).convert("RGBA") for _, data in versions]
        rowAccent = accent or accentOf(images[-1])
        rows.append(rowAccent)
        y = top + index * (rowHeight + rowGap)
        if label:
            texts.append(((pad, y + cell / 2), label, labelFont, textColour, "lm"))
        # Rows with fewer versions sit to the right, so the current version always lines up.
        first = columns - len(versions)
        for step, (image, (caption, data)) in enumerate(zip(images, versions)):
            column = first + step
            x = left + column * (cell + arrowGap)
            last = step == len(versions) - 1
            shapes.alpha_composite(square, (x * SS, y * SS))
            if last and len(versions) > 1:
                draw.rounded_rectangle((x * SS, y * SS, (x + cell) * SS - 1, (y + cell) * SS - 1),
                                       radius=cell * SS // 14, outline=rowAccent, width=3 * SS)
            inner = round(cell * 0.92)
            fitted = image.copy()
            scale = min(inner / image.width, inner / image.height)
            fitted = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
            placed.append((fitted, x + (cell - fitted.width) // 2, y + (cell - fitted.height) // 2))
            same = step > 0 and data == versions[step - 1][1]
            if step > 0:
                ax = (x - arrowGap + 16) * SS
                mark = equals if same else arrow
                mark(draw, ax, (y + cell // 2) * SS, (arrowGap - 32) * SS, mutedColour if same else rowAccent)
            if same:
                texts.append(((x + cell / 2, y + cell - 16), "unchanged", captionFont, textColour, "mm"))
            if captions and caption:
                texts.append(((x + cell / 2, y + cell + captionHeight / 2 + 2), caption, captionFont,
                              textColour if last else mutedColour, "mm"))

    if title or subtitle:
        barBottom = pad + (42 if title else 0) + (28 if subtitle else 0)
        draw.rounded_rectangle((pad * SS, (pad + 4) * SS, (pad + 6) * SS, barBottom * SS), radius=3 * SS, fill=rows[0])
    sheet = shapes.resize((width, height), Image.LANCZOS)
    for image, x, y in placed:
        sheet.alpha_composite(image, (x, y))

    draw = ImageDraw.Draw(sheet)
    y = pad
    if title:
        draw.text((pad + 20, y + 22), title, font=titleFont, fill=textColour, anchor="lm")
        y += 46
    if subtitle:
        draw.text((pad + 20, y + 12), subtitle, font=subtitleFont, fill=mutedColour, anchor="lm")
    if labels:
        for column, text in enumerate(labels):
            x = left + column * (cell + arrowGap) + cell / 2
            draw.text((x, top - headerHeight / 2 - 2), text, font=captionFont,
                      fill=textColour if column == columns - 1 else mutedColour, anchor="mm")
    for xy, text, textFont, colour, anchor in texts:
        draw.text(xy, text, font=textFont, fill=colour, anchor=anchor)
    if footer:
        draw.text((width - pad, height - pad / 2 - 6), footer, font=footerFont, fill=mutedColour, anchor="rm")
    return sheet.convert("RGB")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--item", action="append", nargs="+", default=[], metavar=("LABEL", "IMAGE"),
                        help="a row: its label, then its images oldest first (a path, a tracked image name, or REV:path)")
    parser.add_argument("--history", nargs="+", metavar=("COUNT", "IMAGE"),
                        help="a row per image, showing its last COUNT distinct versions from git")
    parser.add_argument("--labels", nargs="+", help="column headings, oldest first")
    parser.add_argument("--title")
    parser.add_argument("--subtitle")
    parser.add_argument("--footer")
    parser.add_argument("--cell", type=int, help="tile size in pixels; chosen from the column count by default")
    parser.add_argument("--backdrop", default="#77736b", help="tile colour behind the art")
    parser.add_argument("--accent", help="arrow and highlight colour; taken from each row's art by default")
    args = parser.parse_args()

    items = []
    for label, *sources in args.item:
        if not sources:
            parser.error(f"--item {label} needs at least one image")
        items.append((label, [(None, load(source)) for source in sources]))
    if args.history:
        count, *sources = args.history
        if not count.isdigit() or not sources:
            parser.error("--history takes a count, then one or more images")
        for source in sources:
            name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", Path(source).stem)  # SunstoneVessel -> Sunstone Vessel
            items.append((name, history(source, int(count))))
    if not items:
        parser.error("give at least one --item or --history")

    columns = max(len(versions) for _, versions in items)
    if args.labels and len(args.labels) != columns:
        parser.error(f"--labels has {len(args.labels)} headings for {columns} columns")
    if len(items) == 1 and not args.title:
        # One row needs no row label beside it; its name reads better as the heading.
        args.title, items = items[0][0], [("", items[0][1])]
    cell = args.cell or {1: 420, 2: 380, 3: 340}.get(columns, 300)
    sheet = render(items, args.labels, args.title, args.subtitle, args.footer, cell,
                   hexColour(args.backdrop), hexColour(args.accent) if args.accent else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"{args.output} ({sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
