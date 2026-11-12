"""Browse project textures and recorded artwork candidates."""

import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageTk
from mask_review import clear_request, current_recipes, mark_review, read_reviews, relative as review_path, review_context

from editor_project import ROOT, settings



def words(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name.replace("_", " ").replace("-", " ")).strip()


def artwork_items(root=ROOT):
    registry_path = root / "artwork/objects.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {"objects": []}
    project = settings(root)
    labels, masters = {}, {}
    for obj in registry["objects"]:
        base = obj["texture"]
        for direction in obj.get("directions", []) or ["single"]:
            relative = base + ("_" + direction if direction != "single" else "") + ".png"
            labels[relative] = obj["label"] + (f" · {direction}" if direction != "single" else "")
        master = obj.get("approvedMaster", {})
        if master.get("path") and master.get("sha256"):
            masters[master["path"]] = master["sha256"]
    for folder in (root / "Defs", root / "Integrations"):
        for xml in folder.rglob("*.xml"):
            try:
                definitions = ET.parse(xml).getroot()
            except ET.ParseError:
                continue
            for definition in definitions:
                label = definition.findtext("label")
                texture = definition.findtext("graphicData/texPath")
                if label and texture:
                    labels.setdefault(texture + ".png", label)
                    for direction in ("north", "east", "south", "west"):
                        labels.setdefault(texture + "_" + direction + ".png", f"{label} · {direction}")
    items = []
    for folder in (root / "Textures",):
        for image in folder.rglob("*.png"):
            stem = image.stem
            if stem.endswith("_m") or re.search(r"_(north|east|south|west)m$", stem, re.I):
                continue
            relative = image.relative_to(root / "Textures").as_posix()
            if relative in project.get("supersededTextures", []):
                continue
            direction = re.search(r"_(north|east|south|west)$", stem, re.I)
            mask = image.with_name(stem + ("m.png" if direction else "_m.png"))
            label = labels.get(relative)
            if not label:
                parent = image.parent.name
                label = words(stem)
                if parent not in ("Misc", "Textures") and parent.lower() not in stem.lower():
                    label = words(parent) + " " + label
            expected = masters.get(relative)
            approved = bool(expected and hashlib.sha256(image.read_bytes()).hexdigest() == expected)
            items.append({"name": label, "group": "In mod", "detail": "Approved image" if approved else "Mod texture",
                          "image": image, "mask": mask if mask.is_file() else None})

    exports = {}
    for record in (root / "work").rglob("export.json"):
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
            manifest = Path(data["manifest"]).resolve()
            if not manifest.is_file() or hashlib.sha256(manifest.read_bytes()).hexdigest() != data["manifestSha256"]:
                continue
            sources = data["layers"] + [data[name] for name in ("paintedMask", "paintedColor") if name in data]
            if any(not (manifest.parent / source["path"]).is_file()
                   or hashlib.sha256((manifest.parent / source["path"]).read_bytes()).hexdigest() != source["sha256"]
                   for source in sources):
                continue
            color = record.parent / Path(data["color"]["path"]).name
            mask = record.parent / Path(data["mask"]["path"]).name
            if not color.is_file() or not mask.is_file():
                continue
            if hashlib.sha256(color.read_bytes()).hexdigest() != data["color"]["sha256"] or hashlib.sha256(mask.read_bytes()).hexdigest() != data["mask"]["sha256"]:
                continue
            old = exports.get(manifest)
            if old is None or record.stat().st_mtime > old[0]:
                exports[manifest] = (record.stat().st_mtime, color, mask)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    for manifest in (root / "artwork/design-sources").glob("*/master.json"):
        if manifest.parent.name in project.get("supersededDesigns", []):
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            exported = exports.get(manifest.resolve())
            image = exported[1] if exported else manifest.parent / data["layers"][0]["path"]
            if image.is_file():
                items.append({"name": words(manifest.parent.name), "group": "Designs",
                              "detail": "Recipe export" if exported else "Source layer · no current export",
                              "image": image, "mask": exported[2] if exported else None,
                              "recipe": manifest})
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
    for name in project.get("sourceCandidates", []):
        image = root / "artwork/design-sources" / name / "source.png"
        if image.is_file():
            mask = image.with_name("source_m.png")
            items.append({"name": words(name), "group": "Designs", "detail": "Accepted source",
                          "image": image, "mask": mask if mask.is_file() else None})
    reviews = read_reviews(root)
    current = current_recipes(root)
    shown = set()
    for item in items:
        keys = [review_path(item["image"], root)]
        if item.get("recipe"):
            keys.insert(0, review_path(item["recipe"], root))
        key = next((value for value in keys if value in reviews and reviews[value].get("status", "pending") == "pending"),
                   next((value for value in keys if value in reviews), None))
        if key:
            item["review_key"] = key
            item["review_note"] = reviews[key].get("note", "")
            item["review_status"] = reviews[key].get("status", "pending")
            item['review_context'] = review_context(key, current)
            shown.add(key)
            if reviews[key].get("mask"):
                item["mask"] = root / reviews[key]["mask"]
    for key, entry in reviews.items():
        if key in shown:
            continue
        path = root / key
        if path.parent.name in project.get("supersededDesigns", []) or key.removeprefix("Textures/") in project.get("supersededTextures", []):
            continue
        try:
            if entry["kind"] == "recipe":
                data = json.loads(path.read_text(encoding="utf-8"))
                image = path.parent / data["layers"][0]["path"]
                item = {"name": words(path.parent.name), "group": "Designs", "detail": "Recipe",
                        "image": image, "mask": None, "recipe": path}
            else:
                group = "Designs" if path.is_relative_to(root / "work") else "In mod"
                item = {"name": words(path.stem), "group": group, "detail": "Requested artwork",
                        "image": path, "mask": root / entry["mask"]}
            item.update(review_key=key, review_note=entry.get("note", ""),
                        review_status=entry.get("status", "pending"), review_context=review_context(key, current))
            items.append(item)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
    def modified(item):
        paths = [item.get("recipe"), item.get("mask")]
        if not item.get("recipe"):
            paths.append(item["image"])
        else:
            try:
                data = json.loads(item["recipe"].read_text(encoding="utf-8"))
                paths.extend(item["recipe"].parent / layer["path"] for layer in data["layers"])
                paths.extend(item["recipe"].parent / data[key] for key in ("paintedMask", "paintedColor") if key in data)
            except (OSError, ValueError, KeyError, TypeError):
                pass
        return max((path.stat().st_mtime for path in paths if path and path.is_file()), default=0)
    return sorted(items, key=lambda item: (item.get("review_status") != "pending", -modified(item),
                                           item["name"].casefold(), str(item["image"])))


class Gallery:
    def __init__(self, editor):
        self.editor = editor
        self.items = getattr(editor, "gallery_items", [])
        self.window = tk.Toplevel(editor.root)
        self.window.title("Artwork gallery")
        self.window.geometry("960x720")
        self.window.minsize(600, 400)
        self.query = tk.StringVar()
        self.group = tk.StringVar(value="All artwork")
        header = ttk.Frame(self.window, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="Artwork gallery", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(0, 18))
        ttk.Label(header, text="Search").pack(side="left", padx=(0, 5))
        entry = ttk.Entry(header, textvariable=self.query, width=24)
        entry.pack(side="left", padx=(0, 10))
        ttk.Combobox(header, textvariable=self.group, state="readonly", width=15,
                     values=("All artwork", "Current review", "For review", "Reviewed", "In mod", "Designs")).pack(side="left")
        self.count = tk.StringVar()
        ttk.Label(header, textvariable=self.count).pack(side="right")
        frame = ttk.Frame(self.window, padding=(12, 0, 12, 12))
        frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(frame, background="#dedfe1", highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.grid = ttk.Frame(self.canvas, padding=8)
        self.grid_window = self.canvas.create_window(0, 0, anchor="nw", window=self.grid)
        self.grid.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self.resize)
        self.canvas.bind("<MouseWheel>", self.wheel)
        self.grid.bind("<MouseWheel>", self.wheel)
        self.query.trace_add("write", lambda *_: self.refresh())
        self.group.trace_add("write", lambda *_: self.refresh())
        self.columns = 0
        self.photos = []
        self.thumbnails = getattr(editor, "gallery_thumbnails", {})
        editor.gallery_thumbnails = self.thumbnails
        self.refresh_id = 0
        self.load_id = 0
        self.loading = False
        if self.items:
            self.refresh()
        self.load_items()
        entry.focus_set()

    def load_items(self):
        self.load_id += 1
        load_id = self.load_id
        self.loading = True
        self.count.set("Loading artwork…")
        results = queue.Queue()

        def scan():
            try:
                results.put((artwork_items(), None))
            except (OSError, ValueError, KeyError, TypeError) as error:
                results.put((None, error))

        def complete():
            if load_id != self.load_id:
                return
            try:
                items, error = results.get_nowait()
            except queue.Empty:
                self.window.after(50, complete)
                return
            self.loading = False
            if error:
                self.count.set("Could not load artwork")
                messagebox.showerror("Cannot load artwork", str(error), parent=self.window)
                return
            self.items = items
            self.editor.gallery_items = items
            self.refresh()

        threading.Thread(target=scan, daemon=True).start()
        self.window.after(50, complete)

    def wheel(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def resize(self, event):
        self.canvas.itemconfigure(self.grid_window, width=event.width)
        columns = max(1, event.width // 200)
        if columns != self.columns:
            self.columns = columns
            self.refresh()

    def refresh(self):
        self.refresh_id += 1
        refresh_id = self.refresh_id
        for child in self.grid.winfo_children():
            child.destroy()
        self.photos = []
        query, group = self.query.get().casefold().strip(), self.group.get()
        matches = [item for item in self.items if (group == "All artwork" or item["group"] == group
                   or (group == 'Current review' and item.get('review_status') == 'pending'
                       and item.get('review_context') == 'current approved')
                   or (group == "For review" and item.get("review_status") == "pending")
                   or (group == "Reviewed" and item.get("review_status") == "reviewed"))
                   and query in (item["name"] + " " + str(item["image"])).casefold()]
        self.count.set("Loading artwork…" if self.loading else f"{len(matches)} items")
        columns = max(1, self.columns)
        for col in range(columns):
            self.grid.columnconfigure(col, weight=1, uniform="gallery")
        if not matches:
            message = "Loading artwork…" if self.loading else "No artwork matches your search."
            ttk.Label(self.grid, text=message, padding=20).grid(row=0, column=0, sticky="w")
        def add_card(index):
            item = matches[index]
            try:
                thumbnail_key = (item["image"], item["image"].stat().st_mtime_ns)
            except OSError:
                return
            photo = self.thumbnails.get(thumbnail_key)
            if photo is None:
                try:
                    with Image.open(item["image"]) as source:
                        image = source.convert("RGBA")
                    image.thumbnail((150, 150), Image.Resampling.LANCZOS)
                    background = Image.new("RGBA", (168, 168), "#b8b8b8")
                    draw = ImageDraw.Draw(background)
                    for y in range(0, 168, 12):
                        for x in range(0, 168, 12):
                            if (x // 12 + y // 12) % 2:
                                draw.rectangle((x, y, x + 11, y + 11), fill="#dedede")
                    background.alpha_composite(image, ((168 - image.width) // 2, (168 - image.height) // 2))
                    photo = ImageTk.PhotoImage(background, master=self.editor.root)
                except OSError:
                    return
                self.thumbnails[thumbnail_key] = photo
            self.photos.append(photo)
            name = textwrap.fill(item["name"], width=24) + "\n" + item["detail"] + (" · mask" if item["mask"] else " · recipe" if item.get("recipe") else " · no mask")
            if item.get("review_key"):
                name += "\nMASK REVIEWED" if item["review_status"] == "reviewed" else "\nFOR MASK REVIEW"
                name += '\n' + item['review_context']
                if item.get("review_note"):
                    name += "\n" + textwrap.fill(item["review_note"], width=24)
            card = ttk.Frame(self.grid)
            card.grid(row=index // columns, column=index % columns, padx=4, pady=5, sticky="n")
            button = ttk.Button(card, image=photo, text=name, compound="top", command=lambda chosen=item: self.open(chosen))
            button.pack()
            button.bind("<MouseWheel>", self.wheel)
            if item["mask"] or item.get("recipe"):
                action = "Clear request" if item.get("review_status") == "pending" else "Mark for review"
                control = ttk.Button(card, text=action, command=lambda chosen=item: self.toggle_review(chosen))
                control.pack(pady=(3, 0))
                control.bind("<MouseWheel>", self.wheel)

        def add_batch(start):
            if refresh_id != self.refresh_id:
                return
            for index in range(start, min(start + 8, len(matches))):
                add_card(index)
            if start + 8 < len(matches):
                self.window.after(1, lambda: add_batch(start + 8))

        add_batch(0)

    def toggle_review(self, item):
        try:
            if item.get("review_status") == "pending":
                clear_request(item["review_key"])
            else:
                mark_review(item.get("review_key") or item.get("recipe", item["image"]),
                            mask=None if item.get("recipe") else item["mask"])
            self.load_items()
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("Cannot update review", str(error), parent=self.window)

    def open(self, item):
        image, mask = item["image"], item["mask"]
        recipe = item.get("recipe")
        if recipe and mask is None:
            try:
                (ROOT / "work").mkdir(exist_ok=True)
                output = Path(tempfile.mkdtemp(prefix="mask-gallery-", dir=ROOT / "work"))
                subprocess.run([sys.executable, str(Path(__file__).with_name("export-layered-artwork.py")), str(recipe),
                                "--output", str(output)], capture_output=True, text=True, check=True)
                manifest = json.loads(recipe.read_text(encoding="utf-8"))
                image, mask = output / manifest["colorFilename"], output / manifest["maskFilename"]
            except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
                detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
                messagebox.showerror("Cannot open design", detail, parent=self.window)
                return
        if not self.editor.open_image(str(image), auto_mask=False):
            return
        if mask:
            if self.editor.open_mask(str(mask), recipe=recipe):
                self.editor.review_key = item.get("review_key")
        else:
            self.editor.new_mask()
            self.editor.dirty = False
        self.editor.gallery_input_after = time.monotonic() + 1
        self.window.destroy()
