"""A mod's translatable def text, as DefInjected entries, with XML inheritance (ParentName) resolved.

Keys use list indexes, such as KM_Glacite.tools.0.label or KM_Cooler.comps.4.effect, counted after inheritance as the
game counts them. An English DefInjected entry in a load folder overrides or adds to the text the defs carry.
"""
import copy
from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from modlayout import Mod, language_files, read_language_data

FIELDS = {"label", "description", "jobString", "effect", "labelNoun", "extraTooltip", "desc", "shortDescOverride", "verb",
          "gerund", "missingDesc", "labelAbstract", "deathMessage", "reportString", "ingestCommandString",
          "ingestReportString", "deathLetter", "deathLetterExtra", "letterLabel", "letterText", "labelShort",
          "outcomeDescription", "pawnLabel", "customLabel", "fixedName", "spectatorsLabel", "beginLetter",
          "ritualExplanation", "labelPlural", "labelFemale", "labelMale", "fuelLabel", "fuelGizmoLabel", "chargeNoun",
          "cooldownGerund", "baseInspectLine", "labelSocial", "skillLabel", "pawnsPlural", "labelTendedWell",
          "labelTendedWellInner", "labelSolidTendedWell", "destroyedLabel", "inspectString", "gizmoLabel", "gizmoDesc",
          "outOfFuelMessage", "successMessage"}


@dataclass
class DefText:
    folder: Path      # load folder whose Languages/<language>/DefInjected receives the translation
    def_type: str
    stem: str         # DefInjected file name, without .xml
    key: str
    english: str

    @property
    def ident(self):
        return f"DefInjected:{self.def_type}:{self.key}"


def merge(parent, child):
    out = copy.deepcopy(parent)
    out.attrib = dict(child.attrib)
    for c in child:
        if not isinstance(c.tag, str):
            continue
        existing = out.find(c.tag) if c.tag != "li" else None
        if c.tag == "li":
            out.append(copy.deepcopy(c))
        elif existing is not None and len(c) and c.get("Inherit", "").lower() != "false":
            out.remove(existing)
            out.append(merge(existing, c))
        else:
            if existing is not None:
                out.remove(existing)
            out.append(copy.deepcopy(c))
    return out


def walk(node, path, found):
    index = 0
    for c in node:
        if not isinstance(c.tag, str):
            continue
        if c.tag == "li":
            sub = f"{path}.{index}" if path else str(index)
            index += 1
        else:
            sub = f"{path}.{c.tag}" if path else c.tag
        if len(c):
            walk(c, sub, found)
        elif c.tag in FIELDS and (c.text or "").strip() and re.search("[A-Za-z]", c.text):
            found.append((sub, c.text.strip()))


def entries(mod):
    if not isinstance(mod, Mod):
        mod = Mod(mod)
    defs, named = [], {}
    for folder in mod.folders:
        base = folder / "Defs"
        for path in sorted(base.rglob("*.xml")) if base.is_dir() else []:
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError:
                continue
            for d in root:
                if not isinstance(d.tag, str):
                    continue
                defs.append((folder, path, d))
                if d.get("Name"):
                    named[d.get("Name")] = d
    resolved = {}

    def resolve(d):
        if id(d) not in resolved:
            parent = named.get(d.get("ParentName")) if d.get("ParentName") else None
            resolved[id(d)] = merge(resolve(parent), d) if parent is not None else d
        return resolved[id(d)]

    out, index = [], {}
    for folder, path, d in defs:
        if d.get("Abstract", "").lower() == "true":
            continue
        r = resolve(d)
        def_name = (r.findtext("defName") or "").strip()
        if not def_name:
            continue
        found = []
        walk(r, "", found)
        for key, text in found:
            if key == "defName":
                continue
            entry = DefText(folder, d.tag.split(".")[-1], path.stem, f"{def_name}.{key}", text)
            index[entry.ident] = entry
            out.append(entry)
    for folder, path in language_files(mod, "English", "DefInjected"):
        for key, text in read_language_data(path):
            entry = DefText(folder, path.parent.name, path.stem, key, text)
            if entry.ident in index:
                index[entry.ident].english = text
            else:
                index[entry.ident] = entry
                out.append(entry)
    return out


def def_names(mod):
    """(def type, defName) of every def the mod's own load folders define."""
    if not isinstance(mod, Mod):
        mod = Mod(mod)
    names = set()
    for folder in mod.folders:
        base = folder / "Defs"
        for path in sorted(base.rglob("*.xml")) if base.is_dir() else []:
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError:
                continue
            names |= {(d.tag.split(".")[-1], (d.findtext("defName") or "").strip()) for d in root if isinstance(d.tag, str)}
    return names


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for e in entries(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()):
        print(f"{e.folder.name}\t{e.def_type}\t{e.stem}\t{e.key}\t{e.english}")
