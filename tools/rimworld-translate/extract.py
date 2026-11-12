"""Applies extraction batches: exact replacements in C# files, plus the English Keyed entries they introduce.

A batch is a Python file defining SPECS, a list of dicts:
  FILE  C# file, relative to the mod root or the name of a file under a source folder
  R     list of (old, new) or (old, new, count): old must occur exactly count times (default 1)
  K     {key: English}: written to <keyed home>/Languages/English/Keyed/<XML>.xml
  XML   Keyed file name without .xml (default: the C# file's stem)
Every replacement is checked before anything is written, so a failing batch changes nothing. Line endings and a byte
order mark are kept. A file changed by someone else between reading and writing is left alone and reported.
"""
import hashlib
import runpy
from pathlib import Path

from modlayout import read_language_data, write_language_data

BOM = "﻿"


class Source:
    def __init__(self, path):
        self.path = path
        self.raw = path.read_bytes()
        text = self.raw.decode("utf-8")
        self.crlf, self.bom = "\r\n" in text, text.startswith(BOM)
        self.text = text.lstrip(BOM).replace("\r\n", "\n")

    def save(self):
        if hashlib.sha256(self.path.read_bytes()).digest() != hashlib.sha256(self.raw).digest():
            raise RuntimeError(f"{self.path} changed while the batch ran; nothing was written to it")
        out = self.text.replace("\n", "\r\n") if self.crlf else self.text
        self.path.write_bytes(((BOM if self.bom else "") + out).encode("utf-8"))


def find_source(mod, name):
    direct = mod.root / name
    if direct.is_file():
        return direct
    matches = [p for s in mod.sources for p in s.rglob(Path(name).name)]
    if len(matches) != 1:
        raise SystemExit(f"{name}: expected one matching source file, found {len(matches)}")
    return matches[0]


def apply(mod, batch_paths, out=print):
    sources, keyed = {}, {}
    keyed_dir = mod.keyed_home / "Languages/English/Keyed"
    for batch in batch_paths:
        module = runpy.run_path(str(batch))
        for spec in module.get("SPECS") or [module]:
            path = find_source(mod, spec["FILE"])
            src = sources.setdefault(path, Source(path))
            for item in spec.get("R", []):
                old, new = item[0], item[1]
                want = item[2] if len(item) > 2 else 1
                found = src.text.count(old)
                if found != want:
                    raise SystemExit(f"{spec['FILE']}: expected {want} of {old!r}, found {found}. Nothing written.")
                src.text = src.text.replace(old, new)
            stem = spec.get("XML", path.stem)
            entries = keyed.setdefault(stem, dict(read_language_data(keyed_dir / f"{stem}.xml"))
                                       if (keyed_dir / f"{stem}.xml").is_file() else {})
            for key, text in spec.get("K", {}).items():
                if key in entries and entries[key] != text:
                    raise SystemExit(f"{key} is already defined with different text. Nothing written.")
                entries[key] = text
            out(f"{spec['FILE']}: {len(spec.get('R', []))} replacements, {len(spec.get('K', {}))} keys")
    for src in sources.values():
        src.save()
    for stem, entries in keyed.items():
        write_language_data(keyed_dir / f"{stem}.xml", entries)
