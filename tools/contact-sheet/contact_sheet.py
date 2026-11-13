"""Render a comparison contact sheet: one or more items across their versions, with arrows.

See README.md beside this file for the commands.
"""
import argparse
import colorsys
import io
import math
from pathlib import Path
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 2  # the shapes are drawn at this scale and reduced, which smooths their edges

sheetColour = (30, 31, 34)
textColour = (242, 243, 245)
mutedColour = (165, 170, 180)
fallbackAccent = (88, 101, 242)

pad = 36
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


def tileImage(size, colour):
    """A rounded square that is lighter in the middle, so dark outlines stay readable."""
    edge = tuple(round(c * 0.8) for c in colour)
    glow = Image.radial_gradient("L").resize((size, size))
    square = Image.composite(Image.new("RGB", (size, size), edge), Image.new("RGB", (size, size), colour), glow)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 14, fill=255)
    square.putalpha(mask)
    return square


class Canvas:
    """Collects tiles, marks and text in sheet pixels, then draws them once the sheet's size is known."""

    def __init__(self, backdrop):
        self.backdrop = backdrop
        self.tiles, self.marks, self.art, self.texts = [], [], [], []

    def tile(self, x, y, size, image, shade=1.0, ring=None, glow=False):
        """`shade` darkens or lifts the tile; `ring` is an outline colour; `glow` adds a halo in that colour."""
        self.tiles.append((x, y, size, shade, ring, glow))
        inner = round(size * 0.92)
        scale = min(inner / image.width, inner / image.height)
        fitted = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
        self.art.append((fitted, x + (size - fitted.width) // 2, y + (size - fitted.height) // 2))

    def arrow(self, start, end, colour, weight=1.0):
        self.marks.append(("arrow", start, end, colour, weight))

    def equals(self, centre, colour, weight=1.0):
        self.marks.append(("equals", centre, None, colour, weight))

    def bar(self, box, colour):
        self.marks.append(("bar", box, None, colour, 1.0))

    def text(self, xy, text, textFont, colour, anchor="mm", outlined=False):
        self.texts.append((xy, text, textFont, colour, anchor, outlined))

    def step(self, start, end, same, colour, weight=1.0):
        """The mark between two versions: an arrow, or an equals sign when nothing changed."""
        if same:
            self.equals(((start[0] + end[0]) / 2, (start[1] + end[1]) / 2), mutedColour, weight)
        else:
            self.arrow(start, end, colour, weight)

    def render(self, width, height):
        shapes = Image.new("RGBA", (width * SS, height * SS), sheetColour + (255,))
        halo = Image.new("RGBA", shapes.size, (0, 0, 0, 0))
        haloDraw = ImageDraw.Draw(halo)
        for x, y, size, shade, ring, glow in self.tiles:
            if glow:
                haloDraw.rounded_rectangle(((x - 3) * SS, (y - 3) * SS, (x + size + 3) * SS, (y + size + 3) * SS),
                                           radius=size * SS // 14, fill=ring + (170,))
        shapes.alpha_composite(halo.filter(ImageFilter.GaussianBlur(14 * SS)))
        draw = ImageDraw.Draw(shapes)
        squares = {}
        for x, y, size, shade, ring, glow in self.tiles:
            key = (size, shade)
            if key not in squares:
                squares[key] = tileImage(size * SS, tuple(min(255, round(c * shade)) for c in self.backdrop))
            shapes.alpha_composite(squares[key], (x * SS, y * SS))
            if ring:
                draw.rounded_rectangle((x * SS, y * SS, (x + size) * SS - 1, (y + size) * SS - 1),
                                       radius=size * SS // 14, outline=ring, width=3 * SS)
        for kind, a, b, colour, weight in self.marks:
            if kind == "bar":
                draw.rounded_rectangle(tuple(v * SS for v in a), radius=3 * SS, fill=colour)
            elif kind == "equals":
                half, offset = 13 * weight * SS, 8 * weight * SS
                for dy in (-offset, offset):
                    draw.line((a[0] * SS - half, a[1] * SS + dy, a[0] * SS + half, a[1] * SS + dy),
                              fill=colour, width=round(7 * weight * SS))
            else:
                x0, y0, x1, y1 = a[0] * SS, a[1] * SS, b[0] * SS, b[1] * SS
                length = math.hypot(x1 - x0, y1 - y0)
                ux, uy = (x1 - x0) / length, (y1 - y0) / length
                head = 19 * weight * SS
                bx, by = x1 - ux * head * 1.15, y1 - uy * head * 1.15
                draw.line((x0, y0, bx + ux, by + uy), fill=colour, width=round(9 * weight * SS))
                r = 4.5 * weight * SS
                draw.ellipse((x0 - r, y0 - r, x0 + r, y0 + r), fill=colour)
                draw.polygon([(x1, y1), (bx - uy * head, by + ux * head), (bx + uy * head, by - ux * head)], fill=colour)

        # The art goes on after the shapes are reduced, so it is resized only once.
        sheet = shapes.resize((width, height), Image.LANCZOS)
        for image, x, y in self.art:
            sheet.alpha_composite(image, (x, y))
        draw = ImageDraw.Draw(sheet)
        for xy, text, textFont, colour, anchor, outlined in self.texts:
            draw.text(xy, text, font=textFont, fill=colour, anchor=anchor,
                      stroke_width=2 if outlined else 0, stroke_fill=sheetColour)
        return sheet.convert("RGB")


labelFont, captionFont, smallFont = font(21), font(17), font(13)


def rowsLayout(canvas, rows, labels, top, cell, hero):
    """One row per item. With `hero`, earlier versions shrink and darken so the current one leads."""
    columns = max(len(versions) for _, versions, _ in rows)
    captions = labels is None and any(caption for _, versions, _ in rows for caption, _, _ in versions)
    small = round(cell * 0.56) if hero else cell
    gap = 66 if hero else 84
    margin = 13 if hero else 16
    weight = 0.85 if hero else 1.0

    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    gutter = max((measure.textlength(label, font=labelFont) for label, _, _ in rows if label), default=0)
    left = pad + (round(gutter) + 26 if gutter else 0)
    if labels:
        top += headerHeight
    rowHeight = cell + (captionHeight if captions else 0)

    for index, (label, versions, accent) in enumerate(rows):
        y = top + index * (rowHeight + rowGap)
        if label:
            canvas.text((pad, y + cell / 2), label, labelFont, textColour, "lm")
        # Rows with fewer versions sit to the right, so the current version always lines up.
        first = columns - len(versions)
        for step, (caption, data, image) in enumerate(versions):
            column = first + step
            last = step == len(versions) - 1
            lead = last and len(versions) > 1
            size = cell if last else small
            x = left + column * (small + gap)
            ty = y + (cell - size) // 2
            shade = (1.08 if last else 0.7) if hero else 1.0
            canvas.tile(x, ty, size, image, shade, accent if lead else None, hero and lead)
            same = step > 0 and data == versions[step - 1][1]
            if step > 0:
                canvas.step((x - gap + margin, y + cell / 2), (x - margin, y + cell / 2), same, accent, weight)
            if same:
                canvas.text((x + size / 2, ty + size - 16), "unchanged", captionFont, textColour, outlined=True)
            if captions and caption:
                canvas.text((x + size / 2, ty + size + captionHeight / 2 + 2), caption, captionFont,
                            textColour if last else mutedColour)
            if labels and index == 0:
                canvas.text((x + size / 2, ty - headerHeight / 2 - 2), labels[column], captionFont,
                            textColour if last else mutedColour)
    width = left + (columns - 1) * (small + gap) + cell
    return width, top + len(rows) * rowHeight + (len(rows) - 1) * rowGap


def cardsLayout(canvas, rows, labels, top, cell):
    """A card per item: the current version large, its earlier versions stacked small beside it."""
    columns = max(len(versions) for _, versions, _ in rows)
    earlier = columns - 1
    stackGap, gap, cardGap = 38, 62, 44
    thumb = min(round(cell * 0.42), (cell - (earlier - 1) * stackGap) // earlier) if earlier else 0
    lead = thumb + gap if earlier else 0
    named = any(label for label, _, _ in rows)
    captioned = labels is not None or any(caption for _, versions, _ in rows for caption, _, _ in versions)
    heading = 42 if named else 0
    cardWidth = lead + cell
    cardHeight = heading + cell + (captionHeight if captioned else 0)
    across = 1 if len(rows) == 1 else 2 if len(rows) <= 4 else 3

    for index, (label, versions, accent) in enumerate(rows):
        cx = pad + (index % across) * (cardWidth + cardGap)
        cy = top + (index // across) * (cardHeight + 26)
        if label:
            canvas.bar((cx, cy + 6, cx + 5, cy + 30), accent)
            canvas.text((cx + 16, cy + 18), label, labelFont, textColour, "lm")
        ty = cy + heading
        names = [labels[columns - len(versions) + i] if labels else caption for i, (caption, _, _) in enumerate(versions)]
        before = versions[:-1]
        block = len(before) * thumb + (len(before) - 1) * stackGap
        by = ty + (cell - block) // 2
        for step, (caption, data, image) in enumerate(before):
            y = by + step * (thumb + stackGap)
            canvas.tile(cx, y, thumb, image, 0.7)
            if step > 0:
                same = data == before[step - 1][1]
                canvas.step((cx + thumb / 2, y - stackGap + 8), (cx + thumb / 2, y - 8), same, accent, 0.6)
            if names[step]:
                canvas.text((cx + thumb / 2, y + thumb - 13), names[step], smallFont, textColour, outlined=True)
        caption, data, image = versions[-1]
        hx = cx + lead
        canvas.tile(hx, ty, cell, image, 1.08, accent if before else None, bool(before))
        if before:
            # The arrow leaves the newest of the earlier versions, at the foot of the stack.
            ay = by + block - thumb / 2
            same = data == before[-1][1]
            canvas.step((cx + thumb + 13, ay), (hx - 13, ay), same, accent, 0.85)
            if same:
                canvas.text((hx + cell / 2, ty + cell - 16), "unchanged", captionFont, textColour, outlined=True)
        if names[-1]:
            canvas.text((hx + cell / 2, ty + cell + captionHeight / 2 + 2), names[-1], captionFont, textColour)
    used = min(across, len(rows))
    down = math.ceil(len(rows) / across)
    return pad + used * cardWidth + (used - 1) * cardGap, top + down * cardHeight + (down - 1) * 26


def render(items, labels, title, subtitle, footer, cell, backdrop, accent, layout):
    """`items` is a list of (label, [(caption, bytes), ...])."""
    rows = []
    for label, versions in items:
        loaded = [(caption, data, Image.open(io.BytesIO(data)).convert("RGBA")) for caption, data in versions]
        rows.append((label, loaded, accent or accentOf(loaded[-1][2])))
    canvas = Canvas(backdrop)

    top = pad
    if title:
        canvas.text((pad + 20, top + 22), title, font(34), textColour, "lm")
        top += 46
    if subtitle:
        canvas.text((pad + 20, top + 12), subtitle, font(18, bold=False), mutedColour, "lm")
        top += 28
    if title or subtitle:
        canvas.bar((pad, pad + 4, pad + 6, top - 4), rows[0][2])
        top += 14

    if layout == "cards":
        right, bottom = cardsLayout(canvas, rows, labels, top, cell)
    else:
        right, bottom = rowsLayout(canvas, rows, labels, top, cell, hero=layout == "hero")
    width, height = right + pad, bottom + pad + (26 if footer else 0)
    if footer:
        canvas.text((width - pad, height - pad / 2 - 6), footer, font(15, bold=False), mutedColour, "rm")
    return canvas.render(width, height)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--item", action="append", nargs="+", default=[], metavar=("LABEL", "IMAGE"),
                        help="a row: its label, then its images oldest first (a path, a tracked image name, or REV:path)")
    parser.add_argument("--history", nargs="+", metavar=("COUNT", "IMAGE"),
                        help="a row per image, showing its last COUNT distinct versions from git")
    parser.add_argument("--labels", nargs="+", help="column headings, oldest first")
    parser.add_argument("--layout", choices=["cards", "hero", "grid"], default="cards",
                        help="cards: one card per item with earlier versions stacked beside the current one; "
                             "hero: a row per item, earlier versions small and current large; grid: equal tiles")
    parser.add_argument("--title")
    parser.add_argument("--subtitle")
    parser.add_argument("--footer")
    parser.add_argument("--cell", type=int, help="size of the current version's tile in pixels")
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
    if args.layout == "grid":
        cell = args.cell or {1: 420, 2: 380, 3: 340}.get(columns, 300)
    else:
        cell = args.cell or (420 if len(items) == 1 else 360)
    sheet = render(items, args.labels, args.title, args.subtitle, args.footer, cell,
                   hexColour(args.backdrop), hexColour(args.accent) if args.accent else None, args.layout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"{args.output} ({sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
