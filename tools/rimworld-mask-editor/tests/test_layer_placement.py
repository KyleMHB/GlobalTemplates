import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image


spec = importlib.util.spec_from_file_location(
    "layered_export", Path(__file__).resolve().parents[1] / "export-layered-artwork.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class PlacementTests(unittest.TestCase):
    def test_scaled_fixed_layer_occludes_tint_at_offset(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "work") as directory:
            root = Path(directory)
            Image.new("RGBA", (8, 8), (180, 180, 180, 255)).save(root / "bowl.png")
            Image.new("RGBA", (4, 4), (240, 150, 180, 255)).save(root / "crystal.png")
            manifest = dict(sourceSize=[8, 8], crop=[0, 0, 8, 8], canvas=[8, 8],
                            targetBox=[0, 0, 8, 8], sourceRepair="none", alphaHandling="preserve",
                            colorFilename="color.png", maskFilename="mask.png", layers=[
                                dict(path="bowl.png", constructionTint=True),
                                dict(path="crystal.png", constructionTint=False,
                                     scale=0.5, offset=[3, 2])])
            path = root / "master.json"
            path.write_text(json.dumps(manifest))
            with contextlib.redirect_stdout(io.StringIO()):
                exporter.export(path, root / "out")
            color = Image.open(root / "out/color.png")
            mask = Image.open(root / "out/mask.png")
            self.assertEqual(color.getpixel((3, 2)), (240, 150, 180, 255))
            self.assertEqual(mask.getpixel((3, 2)), (0, 0, 0, 255))
            self.assertEqual(mask.getpixel((2, 2)), (255, 0, 0, 255))
            self.assertEqual(mask.getpixel((5, 4)), (255, 0, 0, 255))
            # A half-transparent fixed point must remove only half the housing contribution.
            Image.new("RGBA", (4, 4), (240, 150, 180, 128)).save(root / "crystal.png")
            with contextlib.redirect_stdout(io.StringIO()):
                exporter.export(path, root / "partial")
            with Image.open(root / "partial/color.png") as partial:
                pixel = partial.getpixel((3, 2))
                # Pillow's premultiplied Lanczos resize can round RGB down by one.
                self.assertTrue(all(abs(actual - expected) <= 1
                                    for actual, expected in zip(pixel[:3], (210, 165, 180))))
                self.assertEqual(pixel[3], 255)
                self.assertEqual(partial.getpixel((2, 2)), (180, 180, 180, 255))
            with Image.open(root / "partial/mask.png") as partial:
                self.assertEqual(partial.getpixel((3, 2)), (127, 0, 0, 255))
            # Explicit identity placement must preserve the legacy export bytes.
            manifest["layers"] = manifest["layers"][:1]
            path.write_text(json.dumps(manifest))
            with contextlib.redirect_stdout(io.StringIO()):
                exporter.export(path, root / "legacy")
                manifest["layers"][0].update(scale=1, offset=[0, 0])
                path.write_text(json.dumps(manifest))
                exporter.export(path, root / "identity")
            for name in ("color.png", "mask.png"):
                self.assertEqual((root / "legacy" / name).read_bytes(),
                                 (root / "identity" / name).read_bytes())
