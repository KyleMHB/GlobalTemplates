"""Paint the red construction-tint channel of an opaque RimWorld mask."""

if __name__ == "__main__":
    import argparse
    import os
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="target mod root; defaults to the current directory")
    parser.add_argument("--gallery", action="store_true")
    parser.add_argument("image", nargs="?")
    parser.add_argument("mask", nargs="?")
    args = parser.parse_args()
    if not args.project.is_dir():
        parser.error("--project must be an existing directory")
    os.environ["RIMWORLD_ART_PROJECT"] = str(args.project.resolve())

import tkinter as tk
import sys
import time
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageTk
import mask_review

from editor_project import ROOT, settings



def matching_mask(image):
    image = Path(image)
    suffix = "m.png" if re.search(r"_(north|east|south|west)$", image.stem, re.I) else "_m.png"
    return image.with_name(image.stem + suffix)


def production_recipe(image):
    image = Path(image).resolve()
    for texture, recipe in settings().get("recipeOverrides", {}).items():
        if (ROOT / texture).resolve() == image:
            return ROOT / recipe
    registry_path = ROOT / "artwork/objects.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {"objects": []}
    for obj in registry["objects"]:
        for direction, recipe in obj.get("recipes", {}).items():
            suffix = "" if direction == "single" else "_" + direction
            if (ROOT / "Textures" / (obj["texture"] + suffix + ".png")).resolve() == image:
                return ROOT / recipe
    return None


@lru_cache(maxsize=32)
def brush_tip(size, hardness, opacity, shape):
    tip = Image.new("L", (size, size))
    center = (size - 1) / 2
    radius = max(1, size / 2 - (1 if size % 2 == 0 else 0.5))
    hard = hardness / 100
    pixels = []
    for y in range(size):
        for x in range(size):
            adjustment = 0.5 if size % 2 == 0 else 0
            dx = max(0, abs(x - center) - adjustment) / radius
            dy = max(0, abs(y - center) - adjustment) / radius
            distance = max(dx, dy) if shape == "square" else math.hypot(dx, dy)
            if distance > 1:
                strength = 0
            elif distance <= hard or hard == 1:
                strength = 1
            else:
                strength = (1 - distance) / (1 - hard)
            pixels.append(round(255 * opacity / 100 * strength))
    tip.putdata(pixels)
    return tip


class MaskEditor:
    def __init__(self, root):
        self.root = root
        self.gallery_input_after = 0
        root.title(f"RimWorld mask editor — {ROOT.name}")
        self.image = self.image_path = self.mask = self.mask_path = None
        self.saved_image = None
        self.line_start = None
        self.mask_recipe = None
        self.review_key = None
        self.undo = []
        self.redo = []
        self.dirty = False
        self.last = None
        self.points = []
        self.selection_closed = False
        self.selection_mask = None
        self.selection_inverted = False
        self.selection_base = None
        self.selection_operation = "replace"
        self.selecting = False
        self.zoom = tk.IntVar(value=2)
        self.brush = tk.IntVar(value=8)
        self.brush_opacity = tk.IntVar(value=100)
        self.brush_hardness = tk.IntVar(value=100)
        self.brush_shape = tk.StringVar(value="round")
        self.mode = tk.StringVar(value="paint")
        self.tool = tk.StringVar(value="brush")
        self.overlay = tk.BooleanVar(value=True)
        self.preview_mode = "mask"
        bar = ttk.Frame(root, padding=5)
        bar.pack(fill="x")
        for label, command in [("Open image", self.open_image), ("Open mask", self.open_mask),
                               ("New mask", self.new_mask), ("Save", self.save_current), ("Save as", self.save),
                               ("Undo", self.undo_stroke), ("Redo", self.redo_stroke)]:
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)
        ttk.Radiobutton(bar, text="Paint", variable=self.mode, value="paint").pack(side="left", padx=4)
        ttk.Radiobutton(bar, text="Erase", variable=self.mode, value="erase").pack(side="left")
        ttk.Label(bar, text="Brush px").pack(side="left", padx=(8, 2))
        ttk.Spinbox(bar, from_=1, to=128, width=4, textvariable=self.brush).pack(side="left")
        ttk.Combobox(bar, textvariable=self.brush_shape, values=("round", "square"),
                     state="readonly", width=6).pack(side="left", padx=4)
        ttk.Label(bar, text="Zoom").pack(side="left", padx=(8, 2))
        ttk.Spinbox(bar, from_=1, to=8, width=3, textvariable=self.zoom, command=self.render).pack(side="left")
        ttk.Checkbutton(bar, text="Show mask", variable=self.overlay, command=self.render).pack(side="left", padx=8)
        selection_bar = ttk.Frame(root, padding=(5, 0, 5, 5))
        selection_bar.pack(fill="x")
        for label, value in [("Mask brush", "brush"), ("Outline brush", "outline_brush"), ("Outline line", "outline_line"), ("Line selection", "polygon"), ("Pen selection", "freehand")]:
            ttk.Radiobutton(selection_bar, text=label, variable=self.tool, value=value).pack(side="left", padx=4)
        ttk.Button(selection_bar, text="Close selection", command=self.close_selection).pack(side="left", padx=4)
        ttk.Button(selection_bar, text="Fill selection", command=lambda: self.fill_selection(255)).pack(side="left", padx=4)
        ttk.Button(selection_bar, text="Erase selection", command=self.delete_selection).pack(side="left", padx=4)
        ttk.Button(selection_bar, text="Clear selection", command=self.clear_selection).pack(side="left", padx=4)
        self.preview_label = tk.StringVar(value="View: mask")
        ttk.Label(selection_bar, textvariable=self.preview_label).pack(side="left", padx=8)
        ttk.Label(selection_bar, text="Line: click points, then the first point to close. Pen: drag. Delete clears mask.").pack(side="left", padx=8)
        brush_bar = ttk.Frame(root, padding=(5, 0, 5, 5))
        brush_bar.pack(fill="x")
        ttk.Button(brush_bar, text="Artwork gallery", command=self.open_gallery).pack(side="left", padx=(0, 10))
        for label, variable in (("Opacity %", self.brush_opacity), ("Hardness %", self.brush_hardness)):
            ttk.Label(brush_bar, text=label).pack(side="left", padx=(4, 2))
            ttk.Spinbox(brush_bar, from_=0, to=100, width=5, textvariable=variable).pack(side="left")
        frame = ttk.Frame(root)
        frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(frame, background="#383838", highlightthickness=0)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.canvas.xview)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.status = tk.StringVar(value="Open a colour image, then open or create its mask.")
        ttk.Label(root, textvariable=self.status, padding=5).pack(fill="x")
        self.canvas.bind("<ButtonPress-1>", self.start_stroke)
        self.canvas.bind("<B1-Motion>", self.stroke)
        self.canvas.bind("<ButtonRelease-1>", self.end_stroke)
        self.canvas.bind("<Motion>", self.show_brush)
        self.canvas.bind("<Leave>", lambda event: self.canvas.delete("brush"))
        self.canvas.bind("<MouseWheel>", self.wheel_zoom)
        self.canvas.bind("<ButtonPress-2>", lambda event: self.canvas.scan_mark(event.x, event.y))
        self.canvas.bind("<B2-Motion>", self.pan)
        self.canvas.bind("<Configure>", lambda event: self.update_scrollregion())
        root.bind("<Control-z>", lambda event: self.undo_stroke())
        root.bind("<Control-s>", lambda event: self.save_current())
        root.bind("<Control-i>", lambda event: self.invert_selection())
        root.bind("<Control-Shift-Z>", lambda event: self.redo_stroke())
        root.bind("<Control-Shift-z>", lambda event: self.redo_stroke())
        root.bind("<Return>", lambda event: self.close_selection())
        root.bind("<Delete>", lambda event: self.delete_selection())
        root.bind("<Escape>", lambda event: self.clear_selection())
        root.bind("<KeyPress-p>", self.preview_key)
        root.bind("<KeyPress-P>", self.preview_key)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.geometry("1100x800")

    def discard(self):
        return not self.dirty or messagebox.askyesno("Unsaved changes", "Discard unsaved artwork and mask changes?")

    def open_gallery(self):
        from mask_gallery import Gallery
        Gallery(self)

    def open_image(self, path=None, auto_mask=True):
        if not self.discard():
            return
        path = path or filedialog.askopenfilename(title="Open colour image", filetypes=[("PNG images", "*.png")])
        if not path:
            return
        try:
            with Image.open(path) as source:
                self.image = source.convert("RGBA")
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot open image", str(error))
            return
        self.mask = self.mask_path = None
        self.mask_recipe = None
        self.review_key = None
        self.points = []
        self.selection_closed = False
        self.selection_mask = None
        self.selection_inverted = False
        self.image_path = Path(path).resolve()
        self.saved_image = self.image.copy()
        self.background = Image.new("RGBA", self.image.size, "#b8b8b8")
        draw = ImageDraw.Draw(self.background)
        for y in range(0, self.image.height, 8):
            for x in range(0, self.image.width, 8):
                if (x // 8 + y // 8) % 2:
                    draw.rectangle((x, y, x + 7, y + 7), fill="#dedede")
        self.checkerboard = self.background.copy()
        self.background.alpha_composite(self.image)
        self.undo.clear()
        self.redo.clear()
        self.dirty = False
        self.status.set(f"{path} | Open or create a mask")
        self.render()
        mask = matching_mask(path)
        if auto_mask and mask.is_file():
            self.open_mask(str(mask), recipe=production_recipe(path))
        elif auto_mask:
            self.new_mask()
            self.dirty = False
        return True

    def open_mask(self, path=None, recipe=None):
        if self.image is None or not self.discard():
            return
        path = path or filedialog.askopenfilename(title="Open mask", filetypes=[("PNG images", "*.png")])
        if not path:
            return
        try:
            with Image.open(path) as source:
                mask = source.convert("RGBA")
            if mask.size != self.image.size:
                raise ValueError("The mask and colour image must have the same dimensions.")
            r, g, b, a = mask.split()
            if g.getextrema() != (0, 0) or b.getextrema() != (0, 0) or a.getextrema() != (255, 255):
                raise ValueError("This is not an opaque-red mask. Inspect its encoding before editing it.")
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot open mask", str(error))
            return
        self.mask, self.mask_path = r, Path(path)
        if recipe is None and self.image_path and Path(path).resolve() == matching_mask(self.image_path).resolve():
            recipe = production_recipe(self.image_path)
        self.mask_recipe = Path(recipe) if recipe else None
        self.review_key = None
        self.overlay.set(True)
        self.preview_mode = "mask"
        self.preview_label.set("View: mask")
        self.points = []
        self.selection_closed = False
        self.selection_mask = None
        self.selection_inverted = False
        self.undo.clear()
        self.redo.clear()
        self.dirty = False
        self.status.set(f"Mask: {path} | Red overlay shows construction tint")
        self.render()
        return True

    def new_mask(self):
        if self.image is None or not self.discard():
            return
        self.mask = Image.new("L", self.image.size, 0)
        self.points = []
        self.selection_closed = False
        self.selection_mask = None
        self.selection_inverted = False
        self.mask_path = None
        self.mask_recipe = None
        self.review_key = None
        self.undo.clear()
        self.redo.clear()
        self.dirty = True
        self.status.set("New mask | Red overlay shows construction tint")
        self.render()

    def render(self):
        if self.image is None:
            return
        try:
            zoom = max(1, min(8, self.zoom.get()))
        except tk.TclError:
            return
        if self.mask is not None and self.preview_mode != "mask":
            background = self.tint_view((0, 0, *self.image.size))
        else:
            background = self.background.copy()
        if self.mask is not None and self.preview_mode == "mask" and self.overlay.get():
            red = Image.new("RGBA", self.image.size, (255, 30, 30, 0))
            red.putalpha(self.mask.point(lambda value: value * 110 // 255))
            background.alpha_composite(red)
        self.photo = ImageTk.PhotoImage(background.resize((self.image.width * zoom, self.image.height * zoom), Image.Resampling.NEAREST))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.update_scrollregion()
        self.draw_selection()

    def preview_key(self, event):
        if self.mask is None or isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, ttk.Combobox, ttk.Spinbox)):
            return
        modes = ("mask", "light", "dark", "wood")
        if event.state & 0x0001:
            self.preview_mode = modes[(modes.index(self.preview_mode) + 1) % len(modes)]
        else:
            self.preview_mode = "light" if self.preview_mode == "mask" else "mask"
        self.preview_label.set(f"View: {self.preview_mode}")
        self.render()
        return "break"

    def tint_view(self, box):
        colors = {"light": (1.0, 0.95, 0.83), "dark": (0.2, 0.2, 0.2), "wood": (0.55, 0.35, 0.2)}
        color = self.image.crop(box)
        coverage = self.mask.crop(box)
        channels = color.split()
        result = []
        for channel, tint in zip(channels[:3], colors[self.preview_mode]):
            tinted = channel.point(lambda value: round(value * tint))
            result.append(Image.composite(tinted, channel, coverage))
        background = self.checkerboard.crop(box)
        background.alpha_composite(Image.merge("RGBA", (*result, channels[3])))
        return background

    def update_scrollregion(self):
        if self.image is None:
            return
        try:
            zoom = max(1, min(8, self.zoom.get()))
        except tk.TclError:
            return
        padx = max(1, self.canvas.winfo_width() // 2)
        pady = max(1, self.canvas.winfo_height() // 2)
        self.canvas.configure(scrollregion=(-padx, -pady, self.image.width * zoom + padx, self.image.height * zoom + pady))

    def render_brush_area(self, start, end, size):
        if self.preview_mode == "mask" and not self.overlay.get():
            return
        zoom = max(1, min(8, self.zoom.get()))
        padding = size + 2
        left = max(0, min(start[0], end[0]) - padding)
        top = max(0, min(start[1], end[1]) - padding)
        right = min(self.image.width, max(start[0], end[0]) + padding + 1)
        bottom = min(self.image.height, max(start[1], end[1]) + padding + 1)
        if left >= right or top >= bottom:
            return
        box = (left, top, right, bottom)
        if self.preview_mode == "mask":
            background = self.background.crop(box)
            red = Image.new("RGBA", background.size, (255, 30, 30, 0))
            red.putalpha(self.mask.crop(box).point(lambda value: value * 110 // 255))
            background.alpha_composite(red)
        else:
            background = self.tint_view(box)
        patch = ImageTk.PhotoImage(background.resize((background.width * zoom, background.height * zoom), Image.Resampling.NEAREST))
        self.photo.tk.call(str(self.photo), "copy", str(patch), "-to", left * zoom, top * zoom)

    def draw_selection(self, preview=None):
        self.canvas.delete("selection")
        if not self.points:
            return
        zoom = max(1, min(8, self.zoom.get()))
        if self.selection_closed:
            padded = ImageOps.expand(self.selection_mask, border=1, fill=0)
            box = (1, 1, self.image.width + 1, self.image.height + 1)
            expanded = padded.filter(ImageFilter.MaxFilter(3)).crop(box)
            contracted = padded.filter(ImageFilter.MinFilter(3)).crop(box)
            boundary = ImageChops.subtract(expanded, contracted)
            outline = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
            outline.putalpha(boundary)
            inner = ImageChops.subtract(self.selection_mask, contracted)
            white = Image.new("RGBA", self.image.size, (255, 255, 255, 0))
            white.putalpha(inner)
            outline.alpha_composite(white)
            self.selection_photo = ImageTk.PhotoImage(outline.resize((self.image.width * zoom, self.image.height * zoom), Image.Resampling.NEAREST))
            self.canvas.create_image(0, 0, image=self.selection_photo, anchor="nw", tags="selection")
            return
        points = self.points + ([self.points[0]] if self.selection_closed else ([preview] if preview else []))
        coords = [(value + 0.5) * zoom for point in points for value in point]
        if len(coords) >= 4:
            self.canvas.create_line(*coords, fill="black", width=3, tags="selection")
            self.canvas.create_line(*coords, fill="white", width=1, dash=(4, 3), tags="selection")
        for x, y in self.points if self.tool.get() == "polygon" and not self.selection_closed else []:
            x, y = (x + 0.5) * zoom, (y + 0.5) * zoom
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill="white", outline="black", tags="selection")

    def close_selection(self):
        if len(self.points) >= 3:
            self.selection_closed = True
            region = Image.new("L", self.mask.size)
            ImageDraw.Draw(region).polygon(self.points, fill=255)
            if self.selection_base is not None and self.selection_operation == "add":
                self.selection_mask = ImageChops.lighter(self.selection_base, region)
            elif self.selection_base is not None and self.selection_operation == "subtract":
                self.selection_mask = ImageChops.subtract(self.selection_base, region)
            else:
                self.selection_mask = region
            self.selection_base = None
            self.selection_inverted = False
            self.selecting = False
            self.draw_selection()
            self.status.set("Selection closed | Press Delete to clear mask coverage, or Escape to deselect")

    def clear_selection(self):
        self.points = []
        self.selection_mask = None
        self.selection_base = None
        self.selection_inverted = False
        self.selection_closed = self.selecting = False
        self.canvas.delete("selection")

    def delete_selection(self):
        self.fill_selection(0)

    def invert_selection(self):
        if self.selection_closed:
            self.selection_mask = ImageOps.invert(self.selection_mask)
            self.selection_inverted = not self.selection_inverted
            self.draw_selection()
            self.status.set("Selection inverted | Press Escape to deselect")

    def fill_selection(self, value):
        if self.mask is None or not self.selection_closed:
            return
        self.undo.append((self.mask.copy(), self.image.copy()))
        self.redo.clear()
        if len(self.undo) > 100:
            self.undo.pop(0)
        self.mask.paste(value, mask=self.selection_mask)
        self.dirty = True
        self.render()

    def position(self, event):
        zoom = max(1, min(8, self.zoom.get()))
        return (int(self.canvas.canvasx(event.x) / zoom), int(self.canvas.canvasy(event.y) / zoom))

    def show_brush(self, event):
        self.canvas.delete("brush")
        if self.mask is None:
            return
        if self.tool.get() not in ("brush", "outline_brush", "outline_line"):
            if self.tool.get() == "polygon" and not self.selection_closed:
                self.draw_selection(self.position(event))
            return
        try:
            zoom = max(1, min(8, self.zoom.get()))
            size = max(1, min(128, self.brush.get())) * zoom
            x, y = self.position(event)
        except tk.TclError:
            return
        x, y = (x + 0.5) * zoom, (y + 0.5) * zoom
        radius = size / 2
        bounds = (x - radius, y - radius, x + radius, y + radius)
        outline = self.canvas.create_rectangle if self.brush_shape.get() == "square" else self.canvas.create_oval
        outline(*bounds, outline="black", width=3, tags="brush")
        outline(*bounds, outline="white", width=1, tags="brush")

    def wheel_zoom(self, event):
        if self.image is None:
            return
        if event.state & 0x0004:  # Tk's Control modifier bit
            try:
                size = max(1, min(128, self.brush.get() + (1 if event.delta > 0 else -1)))
            except tk.TclError:
                return
            self.brush.set(size)
            self.show_brush(event)
            return "break"
        old = max(1, min(8, self.zoom.get()))
        new = max(1, min(8, old + (1 if event.delta > 0 else -1)))
        if new == old:
            return
        x = self.canvas.canvasx(event.x) / old
        y = self.canvas.canvasy(event.y) / old
        self.zoom.set(new)
        self.render()
        left, top, right, bottom = map(float, self.canvas.cget("scrollregion").split())
        self.canvas.xview_moveto((x * new - event.x - left) / (right - left))
        self.canvas.yview_moveto((y * new - event.y - top) / (bottom - top))
        self.show_brush(event)

    def pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.show_brush(event)

    def start_stroke(self, event):
        if self.mask is None or time.monotonic() < self.gallery_input_after:
            return
        if self.tool.get() == "outline_line":
            self.line_start = self.position(event)
            return
        if self.tool.get() not in ("brush", "outline_brush"):
            point = self.position(event)
            if (self.tool.get() == "polygon" and not self.selection_closed and len(self.points) >= 3
                    and (point[0] - self.points[0][0]) ** 2 + (point[1] - self.points[0][1]) ** 2
                    <= (max(1, 8 / max(1, min(8, self.zoom.get())))) ** 2):
                self.close_selection()
                return
            if self.selection_closed or self.tool.get() == "freehand":
                self.selection_base = self.selection_mask if self.selection_closed else None
                if event.state & (0x0008 | 0x20000):
                    self.selection_operation = "subtract"
                elif event.state & 0x0001:
                    self.selection_operation = "add"
                else:
                    self.selection_operation = "replace"
                self.points = []
                self.selection_closed = False
                self.selection_mask = None
                self.selection_inverted = False
            self.points.append(point)
            self.selecting = self.tool.get() == "freehand"
            self.draw_selection()
            return
        self.undo.append((self.mask.copy(), self.image.copy()))
        self.redo.clear()
        if len(self.undo) > 100:
            self.undo.pop(0)
        self.last = self.position(event)
        self.stroke_base = self.image.copy() if self.tool.get() == "outline_brush" else self.mask.copy()
        self.stroke_strength = Image.new("L", self.mask.size)
        self.stroke_paint = None
        self.stroke(event)

    def stroke(self, event):
        if self.line_start is not None:
            zoom = max(1, min(8, self.zoom.get()))
            point = self.position(event)
            self.canvas.delete("line_preview")
            coords = [(v + .5) * zoom for p in (self.line_start, point) for v in p]
            self.canvas.create_line(*coords, fill="white", width=1, dash=(4, 3), tags="line_preview")
            return
        if self.selecting:
            point = self.position(event)
            if point != self.points[-1]:
                self.points.append(point)
                self.draw_selection()
            return
        if self.mask is None or self.last is None:
            return
        try:
            size = max(1, min(128, self.brush.get()))
            opacity = max(0, min(100, self.brush_opacity.get()))
            hardness = max(0, min(100, self.brush_hardness.get()))
            point = self.position(event)
        except tk.TclError:
            return
        paint = self.mode.get() == "paint"
        if event.state & 0x0001:  # Tk's Shift modifier bit
            paint = not paint
        outline = self.tool.get() in ("outline_brush", "outline_line")
        if not outline and self.stroke_paint is not None and self.stroke_paint != paint:
            self.stroke_base = self.mask.copy()
            self.stroke_strength = Image.new("L", self.mask.size)
        self.stroke_paint = paint
        dx, dy = point[0] - self.last[0], point[1] - self.last[1]
        padding = size + 2
        box = (max(0, min(self.last[0], point[0]) - padding), max(0, min(self.last[1], point[1]) - padding),
               min(self.mask.width, max(self.last[0], point[0]) + padding + 1),
               min(self.mask.height, max(self.last[1], point[1]) + padding + 1))
        if box[0] >= box[2] or box[1] >= box[3]:
            return
        if outline:
            # Sample the outline between image pixels before reducing it, so even
            # thin diagonal strokes have partial edge coverage.
            scale = 4
            tip = brush_tip(size * scale, hardness, opacity, self.brush_shape.get())
            segment = Image.new("L", ((box[2] - box[0]) * scale, (box[3] - box[1]) * scale))
            steps = max(1, math.ceil(math.hypot(dx, dy) / max(.5, size / 8)))
            for step in range(steps + 1):
                x = round((self.last[0] + dx * step / steps - box[0] + .5) * scale - tip.width / 2)
                y = round((self.last[1] + dy * step / steps - box[1] + .5) * scale - tip.height / 2)
                area = (x, y, x + tip.width, y + tip.height)
                segment.paste(ImageChops.lighter(segment.crop(area), tip), area)
            segment = segment.resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
            self.stroke_strength.paste(ImageChops.lighter(self.stroke_strength.crop(box), segment), box)
        else:
            tip = brush_tip(size, hardness, opacity, self.brush_shape.get())
            steps = max(1, math.ceil(math.hypot(dx, dy) / max(1, size / 4)))
            for step in range(steps + 1):
                x = round(self.last[0] + dx * step / steps) - size // 2
                y = round(self.last[1] + dy * step / steps) - size // 2
                left, top = max(0, x), max(0, y)
                right, bottom = min(self.mask.width, x + size), min(self.mask.height, y + size)
                if left >= right or top >= bottom:
                    continue
                area = (left, top, right, bottom)
                stamp = tip.crop((left - x, top - y, right - x, bottom - y))
                self.stroke_strength.paste(ImageChops.lighter(self.stroke_strength.crop(area), stamp), area)
        strength = self.stroke_strength.crop(box)
        if self.selection_closed:
            strength = ImageChops.multiply(strength, self.selection_mask.crop(box))
        if outline:
            target = Image.new("RGBA", strength.size, (0, 0, 0, 255))
            self.image.paste(Image.composite(target, self.stroke_base.crop(box), strength), box)
            self.background = self.checkerboard.copy()
            self.background.alpha_composite(self.image)
        else:
            target = Image.new("L", strength.size, 255 if paint else 0)
            self.mask.paste(Image.composite(target, self.stroke_base.crop(box), strength), box)
        start = self.last
        self.last = point
        self.dirty = True
        if outline and self.preview_mode == "mask" and not self.overlay.get():
            self.render()
        else:
            self.render_brush_area(start, point, size)
        self.show_brush(event)

    def end_stroke(self, event):
        if self.line_start is not None:
            start = self.line_start
            self.line_start = None
            self.canvas.delete("line_preview")
            self.undo.append((self.mask.copy(), self.image.copy()))
            self.undo = self.undo[-100:]
            self.redo.clear()
            self.last = start
            self.stroke_base = self.image.copy()
            self.stroke_strength = Image.new("L", self.mask.size)
            self.stroke_paint = None
            self.stroke(event)
        self.last = None
        if self.selecting:
            if len(self.points) >= 3:
                self.close_selection()
            else:
                self.selection_mask = self.selection_base
                self.selection_closed = self.selection_mask is not None
                self.selection_base = None
                self.selecting = False
                self.draw_selection()

    def undo_stroke(self):
        if self.undo:
            self.redo.append((self.mask.copy(), self.image.copy()))
            if len(self.redo) > 100:
                self.redo.pop(0)
            self.mask, self.image = self.undo.pop()
            self.background = self.checkerboard.copy()
            self.background.alpha_composite(self.image)
            self.dirty = True
            self.render()

    def redo_stroke(self):
        if self.redo:
            self.undo.append((self.mask.copy(), self.image.copy()))
            if len(self.undo) > 100:
                self.undo.pop(0)
            self.mask, self.image = self.redo.pop()
            self.background = self.checkerboard.copy()
            self.background.alpha_composite(self.image)
            self.dirty = True
            self.render()

    def save(self):
        if self.mask is None:
            return
        options = {"title": "Save mask", "defaultextension": ".png", "filetypes": [("PNG images", "*.png")]}
        if self.mask_path:
            options.update(initialdir=str(self.mask_path.parent), initialfile=self.mask_path.name)
        elif self.image_path:
            suggested = matching_mask(self.image_path)
            options.update(initialdir=str(suggested.parent), initialfile=suggested.name)
        path = filedialog.asksaveasfilename(**options)
        if not path:
            return
        self.write_mask(path)

    def save_current(self):
        if self.mask_path is None:
            self.save()
        else:
            self.write_mask(self.mask_path)

    def write_mask(self, path):
        if Path(path).resolve() == self.image_path:
            messagebox.showerror("Cannot save mask", "Choose a different file from the colour image.")
            return
        try:
            previous = self.mask_path if self.mask_path and self.mask_path.is_file() else None
            before_bytes = previous.read_bytes() if previous else None
            changed_pixels = None
            if previous:
                with Image.open(previous) as old:
                    if old.size == self.mask.size:
                        difference = ImageChops.difference(old.convert("RGBA").getchannel("R"), self.mask)
                        changed_pixels = self.mask.width * self.mask.height - difference.histogram()[0]
            zero = Image.new("L", self.mask.size, 0)
            opaque = Image.new("L", self.mask.size, 255)
            result = Image.merge("RGBA", (self.mask, zero, zero, opaque))
            recipe_path = self.mask_recipe if self.mask_path and Path(path).resolve() == self.mask_path.resolve() else None
            color_changed = self.saved_image is not None and self.image.tobytes() != self.saved_image.tobytes()
            color_recipe = self.mask_recipe if color_changed else None
            active_recipe = recipe_path or color_recipe
            if active_recipe:
                recipe = json.loads(active_recipe.read_text(encoding="utf-8"))
            if recipe_path:
                if "paintedMask" not in recipe:
                    filename = "painted-mask.png"
                    number = 2
                    while (recipe_path.parent / filename).exists():
                        filename = f"painted-mask-{number}.png"
                        number += 1
                    recipe["paintedMask"] = filename
                result.save(recipe_path.parent / recipe["paintedMask"])
            if color_recipe:
                if "paintedColor" not in recipe:
                    filename = "painted-color.png"
                    number = 2
                    while (color_recipe.parent / filename).exists():
                        filename = f"painted-color-{number}.png"
                        number += 1
                    recipe["paintedColor"] = filename
                self.image.save(color_recipe.parent / recipe["paintedColor"])
            if active_recipe:
                active_recipe.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
            if color_changed:
                self.image.save(self.image_path)
            result.save(path)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("Cannot save mask", str(error))
            return
        self.mask_path = Path(path)
        self.saved_image = self.image.copy()
        self.dirty = False
        suffix = " | Recipe mask updated" if recipe_path else ""
        if color_changed:
            suffix += " | Artwork saved" + (" and recipe updated" if color_recipe else "")
        try:
            self.review_key = mask_review.record_reviewed(self.image_path, self.mask_path, recipe=recipe_path,
                                                         key=self.review_key, before_bytes=before_bytes,
                                                         changed_pixels=changed_pixels)
            suffix += " | Mask reviewed"
        except (OSError, ValueError, KeyError) as error:
            messagebox.showwarning("Review status not saved", f"The mask was saved, but its review status could not be recorded: {error}")
        self.status.set(f"Saved: {path}{suffix}")

    def close(self):
        if self.discard():
            self.root.destroy()


if __name__ == "__main__":
    editor = MaskEditor(tk.Tk())
    paths = [str(path if (path := Path(value)).is_absolute() else ROOT / path) for value in (args.image, args.mask) if value]
    if paths:
        editor.open_image(paths[0], auto_mask=len(paths) < 2)
    if len(paths) > 1:
        editor.open_mask(paths[1])
    if args.gallery:
        editor.open_gallery()
    editor.root.mainloop()
