"""A mod's translation layout: its translation.json, the folders the game loads, and LanguageData files."""
import json
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

CONFIG = "translation.json"
DEFAULT_GAME_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\RimWorld"
LOCAL_CONFIG = Path(__file__).resolve().parent / "rwtranslate.local.json"


def local_game_dir():
    """gameDir from the untracked rwtranslate.local.json next to this tool, if present."""
    if LOCAL_CONFIG.is_file():
        return json.loads(LOCAL_CONFIG.read_text(encoding="utf-8")).get("gameDir")
    return None
VERSION_DIR = re.compile(r"^v?(\d+)\.(\d+)$")


class Mod:
    """Settings come from <mod>/translation.json; every field is optional (see README.md)."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        path = self.root / CONFIG
        config = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        self.has_config = path.is_file()
        self.key_prefix = config.get("keyPrefix")
        self.sources = [self.root / s for s in config.get("source", ["Source"]) if (self.root / s).is_dir()]
        self.skip_files = set(config.get("skipFiles", []))
        self.languages = config.get("languages", [])
        self.hardcoded_check = config.get("hardcodedCheck", False)
        self.record_dir = self.root / config.get("record", "translation")
        self.work_dir = self.root / config.get("work", "work/translation")
        self.folders = load_folders(self.root)
        game = config.get("gameDir") or os.environ.get("RIMWORLD_DIR") or local_game_dir() or DEFAULT_GAME_DIR
        self.game_dir = Path(game) if Path(game).is_dir() else None

    @property
    def glossary(self):
        return self.record_dir / "glossary.md"

    def record_path(self, language):
        return self.record_dir / "record" / f"{language}.json"

    @property
    def keyed_home(self):
        """Where new English Keyed files go: the first load folder that already has them, else the first load folder."""
        for folder in self.folders:
            if (folder / "Languages/English/Keyed").is_dir():
                return folder
        return self.folders[0]

    def rel(self, path):
        return Path(path).relative_to(self.root).as_posix()


def version_key(tag):
    match = VERSION_DIR.match(tag)
    return (int(match.group(1)), int(match.group(2))) if match else (-1, -1)


def load_folders(root):
    """The folders the newest game version loads, in load order, with conditional folders included."""
    root = Path(root)
    path = root / "LoadFolders.xml"
    folders = []
    if path.is_file():
        blocks = [b for b in ET.parse(path).getroot() if isinstance(b.tag, str)]
        if blocks:
            newest = max(blocks, key=lambda b: version_key(b.tag))
            for li in newest:
                text = (li.text or "").strip().strip("/")
                folders.append(root / text if text else root)
    else:
        folders.append(root)
        if (root / "Common").is_dir():
            folders.append(root / "Common")
        versions = [p for p in root.iterdir() if p.is_dir() and VERSION_DIR.match(p.name)]
        if versions:
            folders.append(max(versions, key=lambda p: version_key(p.name)))
    unique = []
    for folder in folders:
        if folder.is_dir() and folder.resolve() not in [u.resolve() for u in unique]:
            unique.append(folder)
    return unique or [root]


def read_language_data(path, problems=None, rel=None):
    """(key, text) pairs of one LanguageData file, in file order."""
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root = ET.parse(path, parser=parser).getroot()
    except ET.ParseError as error:
        if problems is not None:
            problems.append(f"{rel or path}: malformed XML: {error}")
        return []
    if root.tag != "LanguageData" and problems is not None:
        problems.append(f"{rel or path}: root element must be LanguageData")
    return [(e.tag, e.text or "") for e in root if isinstance(e.tag, str)]


def write_language_data(path, updates):
    """Sets keys in a LanguageData file as a text edit, so the diff shows only what changed.

    An existing key's value is replaced where it stands; new keys go before </LanguageData> with the file's own
    indentation and line endings. Blank lines, comments, a byte order mark and untouched entries stay byte for byte.
    """
    path = Path(path)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        body = ['<?xml version="1.0" encoding="utf-8"?>', "<LanguageData>"]
        body += [f"\t<{k}>{escape(v)}</{k}>" for k, v in updates.items()] + ["</LanguageData>"]
        path.write_bytes(("\n".join(body) + "\n").encode("utf-8"))
        return
    raw = path.read_bytes().decode("utf-8")
    bom = "﻿" if raw.startswith("﻿") else ""
    text = raw[len(bom):]
    newline = "\r\n" if "\r\n" in text else "\n"
    indent_match = re.search(r"^([ \t]+)<", text, re.M)
    indent = indent_match.group(1) if indent_match else "\t"
    current = dict(read_language_data(path))
    added = []
    for key, value in updates.items():
        if key not in current:
            added.append(f"{indent}<{key}>{escape(value)}</{key}>")
        elif current[key] != value:
            pattern = re.compile(r"<" + re.escape(key) + r">.*?</" + re.escape(key) + r">|<" + re.escape(key) + r"\s*/>", re.S)
            text = pattern.sub(lambda _: f"<{key}>{escape(value)}</{key}>", text, count=1)
    if added:
        close = text.rindex("</LanguageData>")
        head = text[:close].rstrip(" \t")
        if not head.endswith(("\n", "\r")):
            head += newline
        text = head + newline.join(added) + newline + text[close:]
    path.write_bytes((bom + text).encode("utf-8"))


def language_files(mod, language, kind):
    """(load folder, path) of every <folder>/Languages/<language>/<kind>/**/*.xml."""
    out = []
    for folder in mod.folders:
        base = folder / "Languages" / language / kind
        if base.is_dir():
            out += [(folder, p) for p in sorted(base.rglob("*.xml"))]
    return out


PLACEHOLDER = re.compile(r"\{(\w+?)(?:_\w+)?\}|(?<![A-Za-z])(Target[ABC])(?![A-Za-z])")


def stray_line_break(text, english):
    """A real line break where the English has none: RimWorld text marks breaks with a literal \\n."""
    return "\n" in text.strip() and "\n" not in english.strip()


def placeholders(text):
    """{0}, {PAWN} (from {PAWN_labelShort} and friends) and TargetA/B/C job tokens."""
    return {a or b for a, b in PLACEHOLDER.findall(text)}
