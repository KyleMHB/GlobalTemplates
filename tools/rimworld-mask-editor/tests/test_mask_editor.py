import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parents[1]))
import mask_gallery
import mask_review


spec = importlib.util.spec_from_file_location("mask_editor", Path(__file__).parents[1] / "mask-editor.py")
editor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editor_module)


class MaskPromotionTests(unittest.TestCase):
    def test_promotes_reviewed_mask_and_refuses_unrelated_changes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / 'work') as folder:
            root = Path(folder)
            recipe_dir = root / 'artwork/design-sources/test'
            recipe_dir.mkdir(parents=True)
            (root / 'tools').mkdir()
            (root / 'work').mkdir()
            shutil.copyfile(Path(__file__).parents[1] / 'export-layered-artwork.py', root / 'tools/export-layered-artwork.py')
            Image.new('RGBA', (8, 8), (160, 0, 0, 255)).save(recipe_dir / 'source.png')
            Image.new('RGBA', (8, 8), (255, 0, 0, 255)).save(recipe_dir / 'painted-mask.png')
            recipe = recipe_dir / 'master.json'
            recipe.write_text(json.dumps({'sourceSize': [8, 8], 'crop': [0, 0, 8, 8], 'canvas': [8, 8],
                'targetBox': [0, 0, 8, 8], 'colorFilename': 'Color.png', 'maskFilename': 'Color_m.png',
                'sourceRepair': 'none', 'alphaHandling': 'preserve',
                'layers': [{'path': 'source.png', 'constructionTint': False}], 'paintedMask': 'painted-mask.png'}))
            output = root / 'work/export'
            subprocess.run([sys.executable, str(root / 'tools/export-layered-artwork.py'), str(recipe),
                            '--output', str(output)], capture_output=True, check=True)
            texture = root / 'Textures/Things/Test.png'
            texture.parent.mkdir(parents=True)
            shutil.copyfile(output / 'Color.png', texture)
            mask = texture.with_name('Test_m.png')
            Image.new('RGBA', (8, 8), (0, 0, 0, 255)).save(mask)
            import hashlib
            (root / 'artwork/objects.json').write_text(json.dumps({'objects': [{'label': 'Test',
                'texture': 'Things/Test', 'approvedMaster': {'path': 'Things/Test.png',
                'sha256': hashlib.sha256(texture.read_bytes()).hexdigest()},
                'recipes': {'single': 'artwork/design-sources/test/master.json'}}]}))
            mask_review.mark_review(recipe, root=root)
            mask_review.record_reviewed(output / 'Color.png', output / 'Color_m.png', recipe=recipe,
                                        before_bytes=mask.read_bytes(), root=root)
            plan = mask_review.promote_review(recipe, root=root)
            self.assertNotEqual(plan[0]['beforeSha256'], plan[0]['afterSha256'])
            mask_review.promote_review(recipe, apply=True, root=root)
            self.assertEqual(mask.read_bytes(), (recipe_dir / 'painted-mask.png').read_bytes())
            Image.new('RGBA', (8, 8), (40, 0, 0, 255)).save(mask)
            with self.assertRaisesRegex(ValueError, 'unrelated changes'):
                mask_review.promote_review(recipe, apply=True, root=root)


class CrossModGalleryTests(unittest.TestCase):
    def test_plain_mods_have_independent_galleries_reviews_and_exclusions(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / "work") as folder:
            roots = [Path(folder) / name for name in ("ModA", "ModB")]
            for root in roots:
                texture = root / "Textures/Custom/Object.png"
                texture.parent.mkdir(parents=True)
                Image.new("RGBA", (4, 4), (120, 120, 120, 255)).save(texture)
                Image.new("RGBA", (4, 4), (0, 0, 0, 255)).save(texture.with_name("Object_m.png"))
                self.assertEqual(len(mask_gallery.artwork_items(root)), 1)
            first, second = roots
            mask_review.mark_review(first / "Textures/Custom/Object.png", root=first)
            self.assertEqual(mask_gallery.artwork_items(first)[0]["review_status"], "pending")
            self.assertNotIn("review_status", mask_gallery.artwork_items(second)[0])
            (first / "artwork/mask-editor.json").write_text(json.dumps({"supersededTextures": ["Custom/Object.png"]}))
            self.assertEqual(mask_gallery.artwork_items(first), [])
            self.assertEqual(len(mask_gallery.artwork_items(second)), 1)
            self.assertEqual(mask_review.read_reviews(second), {})


class MaskEditorRedrawTests(unittest.TestCase):
    def test_outline_line_softens_diagonal_edges(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = editor_module.MaskEditor(root)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / "work") as folder:
            image = Path(folder) / "image.png"
            mask = Path(folder) / "image_m.png"
            Image.new("RGBA", (24, 24), "white").save(image)
            Image.new("RGBA", (24, 24), (0, 0, 0, 255)).save(mask)
            editor.open_image(str(image))
            editor.zoom.set(1)
            editor.brush.set(1)
            editor.brush_hardness.set(50)
            editor.tool.set("outline_line")
            event = lambda x, y: SimpleNamespace(x=x, y=y, state=0)
            editor.start_stroke(event(2, 3))
            editor.end_stroke(event(20, 13))
            values = set(editor.image.getchannel("R").tobytes())
            self.assertTrue(any(0 < value < 255 for value in values), values)

    def test_mask_review_persists_and_sorts_first_until_cleared(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / "work") as folder:
            root = Path(folder)
            (root / "artwork/design-sources").mkdir(parents=True)
            (root / "artwork/objects.json").write_text('{"objects": []}')
            (root / "work").mkdir()
            textures = root / "Textures/Things/Building/Misc"
            textures.mkdir(parents=True)
            (root / "Textures/Extra").mkdir()
            for name in ("First", "Second"):
                Image.new("RGBA", (4, 4), "white").save(textures / f"{name}.png")
                Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(textures / f"{name}_m.png")
            key = mask_review.mark_review(textures / "Second.png", "Inspect rim", root=root)
            items = mask_gallery.artwork_items(root)
            self.assertEqual(items[0]["review_key"], key)
            self.assertEqual(items[0]["review_note"], "Inspect rim")
            self.assertEqual(mask_review.read_reviews(root)[key]["kind"], "image")
            mask_review.record_reviewed(textures / "Second.png", textures / "Second_m.png", root=root)
            self.assertEqual(mask_review.read_reviews(root)[key]["status"], "reviewed")
            reviewed = next(item for item in mask_gallery.artwork_items(root) if item.get("review_key") == key)
            self.assertEqual(reviewed["review_status"], "reviewed")
            mask_review.mark_review(textures / "Second.png", "Review again", root=root)
            self.assertEqual(mask_review.read_reviews(root)[key]["status"], "pending")
            self.assertEqual(len(mask_review.read_reviews(root)[key]["saves"]), 1)
            mask_review.clear_request(key, root=root)
            self.assertEqual(mask_review.read_reviews(root)[key]["status"], "reviewed")
            self.assertEqual(len(mask_review.read_reviews(root)[key]["saves"]), 1)
            mask_review.clear_review(key, root=root)
            self.assertFalse(mask_review.read_reviews(root))
            self.assertFalse(any(item.get("review_key") for item in mask_gallery.artwork_items(root)))
            design = root / "artwork/design-sources/new-fixture"
            design.mkdir()
            Image.new("RGBA", (4, 4), "white").save(design / "source.png")
            manifest = design / "master.json"
            manifest.write_text(json.dumps({"layers": [{"path": "source.png"}],
                                            "colorFilename": "color.png", "maskFilename": "color_m.png"}))
            key = mask_review.mark_review(manifest, "Check crystal boundary", root=root)
            item = mask_gallery.artwork_items(root)[0]
            self.assertEqual(item["review_key"], key)
            self.assertEqual(item["recipe"], manifest)
            mask_review.clear_review(key, root=root)
            candidate = root / "work/candidate.png"
            Image.new("RGBA", (4, 4), "white").save(candidate)
            Image.new("RGBA", (4, 4), (0, 0, 0, 255)).save(root / "work/candidate_m.png")
            key = mask_review.mark_review(candidate, "Check base", root=root)
            self.assertEqual(mask_gallery.artwork_items(root)[0]["review_key"], key)

    def test_open_image_loads_adjacent_mask(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = editor_module.MaskEditor(root)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / "work") as folder:
            image = Path(folder) / "Cluster.png"
            mask = Path(folder) / "Cluster_m.png"
            Image.new("RGBA", (8, 8), "white").save(image)
            Image.new("RGBA", (8, 8), (90, 0, 0, 255)).save(mask)
            editor.open_image(str(image))
            self.assertEqual(editor.mask_path, mask)
            self.assertEqual(editor.mask.getpixel((1, 1)), 90)

    def test_gallery_opens_recipe_export_mask(self):
        spec = importlib.util.spec_from_file_location("mask_gallery", Path(__file__).parents[1] / "mask_gallery.py")
        gallery_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gallery_module)
        calls = []
        gallery = gallery_module.Gallery.__new__(gallery_module.Gallery)
        gallery.editor = SimpleNamespace(open_image=lambda path, auto_mask: True,
                                         open_mask=lambda path, recipe=None: calls.append((path, recipe)),
                                         status=SimpleNamespace(set=lambda text: None))
        gallery.window = SimpleNamespace(destroy=lambda: None)
        gallery.open({"image": Path("candidate.png"), "mask": Path("candidate_m.png"), "recipe": Path("master.json")})
        self.assertEqual(calls, [("candidate_m.png", Path("master.json"))])

    def test_saving_recipe_mask_preserves_reproducible_input(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = editor_module.MaskEditor(root)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / "work") as folder:
            folder = Path(folder)
            image, mask, recipe = folder / "color.png", folder / "color_m.png", folder / "master.json"
            Image.new("RGBA", (8, 8), "white").save(image)
            Image.new("RGBA", (8, 8), (90, 0, 0, 255)).save(mask)
            recipe.write_text(json.dumps({"layers": [], "colorFilename": "color.png", "maskFilename": "color_m.png"}), encoding="utf-8")
            editor.open_image(str(image), auto_mask=False)
            editor.open_mask(str(mask), recipe=recipe)
            key = mask_review.mark_review(recipe, "Inspect the edge", root=folder)
            editor.mask.putpixel((1, 1), 200)
            record = mask_review.record_reviewed
            with patch.object(mask_review, "record_reviewed", side_effect=lambda *a, **kw: record(*a, root=folder, **kw)):
                editor.save_current()
                editor.mask.putpixel((2, 2), 150)
                with patch.object(editor_module.filedialog, "asksaveasfilename", return_value=str(mask)):
                    editor.save()
            input_path = recipe.parent / json.loads(recipe.read_text())["paintedMask"]
            with Image.open(input_path) as saved, Image.open(mask) as exported:
                self.assertEqual(saved.getpixel((1, 1)), (200, 0, 0, 255))
                self.assertEqual(saved.tobytes(), exported.tobytes())
            review = mask_review.read_reviews(folder)[key]
            self.assertEqual(review["status"], "reviewed")
            self.assertEqual(review["note"], "Inspect the edge")
            self.assertEqual([save["changedPixels"] for save in review["saves"]], [1, 1])
            self.assertTrue(all(save["recipeUpdated"] for save in review["saves"]))
            for save in review["saves"]:
                self.assertTrue((folder / save["previousSnapshot"]).is_file())
                self.assertTrue((folder / save["savedSnapshot"]).is_file())

    def test_scroll_region_extends_past_image(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = editor_module.MaskEditor(root)
        editor.image = Image.new("RGBA", (512, 512), "white")
        editor.update_scrollregion()
        left, top, right, bottom = map(int, editor.canvas.cget("scrollregion").split())
        self.assertLess(left, 0)
        self.assertLess(top, 0)
        self.assertGreater(right, 512 * editor.zoom.get())
        self.assertGreater(bottom, 512 * editor.zoom.get())

    def test_brush_redraw_updates_only_affected_area(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = editor_module.MaskEditor(root)
        editor.image = Image.new("RGBA", (512, 512), "white")
        editor.background = editor.image.copy()
        editor.mask = Image.new("L", editor.image.size)
        editor.zoom.set(8)
        editor.render()
        ImageDraw.Draw(editor.mask).line((10, 10, 20, 20), fill=255, width=8)
        original = editor_module.ImageTk.PhotoImage
        with patch.object(editor_module.ImageTk, "PhotoImage", wraps=original) as photo:
            editor.render_brush_area((10, 10), (20, 20), 8)
            self.assertLess(photo.call_args.args[0].width, editor.image.width * 8)
        updated = editor.photo.tk.call(str(editor.photo), "get", 120, 120)
        editor.render()
        self.assertEqual(updated, editor.photo.tk.call(str(editor.photo), "get", 120, 120))


if __name__ == "__main__":
    unittest.main()
