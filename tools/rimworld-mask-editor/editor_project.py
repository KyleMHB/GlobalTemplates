"""The selected mod owns all artwork, recipes and review records."""
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("RIMWORLD_ART_PROJECT", Path.cwd())).resolve()

def settings(root=ROOT):
    path = root / "artwork/mask-editor.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
