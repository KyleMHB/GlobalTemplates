import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_workshop_update.py"
if not SCRIPT.exists():
    SCRIPT = Path(__file__).with_name("prepare_workshop_update.py")
spec = importlib.util.spec_from_file_location("prepare_workshop_update", SCRIPT)
workshop_update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workshop_update)


class PrepareUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "mod.json").write_text(json.dumps({"publishedFileId": "12345"}), encoding="utf-8")
        (self.root / "steam-description.md").write_text('[b]Mod[/b]\nA "quoted" path C:\\Mods.\n', encoding="utf-8")

    def test_description_only_fields_and_literal_multiline_text(self):
        result = workshop_update.prepare(self.root, "379210")
        self.assertIn('"publishedfileid" "12345"', result)
        self.assertIn('[b]Mod[/b]\nA \\"quoted\\" path C:\\\\Mods.\n', result)
        for field in ["contentfolder", "previewfile", "title", "visibility", "changenote"]:
            self.assertNotIn(f'"{field}"', result)

    def test_rejects_conflicting_or_new_item_ids(self):
        for item_id in ["0", "12x", "99999"]:
            with self.assertRaises(ValueError):
                workshop_update.prepare(self.root, "379210", item_id=item_id)
        (self.root / "mod.json").unlink()
        with self.assertRaises(ValueError):
            workshop_update.prepare(self.root, "379210")
        self.assertIn('"publishedfileid" "12345"', workshop_update.prepare(self.root, "379210", item_id="12345"))

    def test_rejects_empty_description_and_control_characters(self):
        for description in [" \n", "hello\0world"]:
            (self.root / "steam-description.md").write_text(description, encoding="utf-8")
            with self.assertRaises(ValueError):
                workshop_update.prepare(self.root, "379210")


if __name__ == "__main__":
    unittest.main()
