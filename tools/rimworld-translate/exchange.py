"""Export what a language still needs as numbered chunks, and import translated chunks into LanguageData files.

A text needs translating when the language lacks it, or when its English changed since it was translated. The record,
<record>/record/<language>.json, keeps the English each translation was made from; import and baseline write it.

Work folder <work>/<language>/:
  index.json        every exported text: id, English, previous translation, targets
  chunk-NN.json     {"language", "glossary", "rules", "texts": {id: English}, "previous": {id: old translation}}
  chunk-NN.done.json  written by the translator: {id: translation}
"""
from dataclasses import dataclass
import json
from pathlib import Path
import shutil

import def_text
from modlayout import language_files, placeholders, read_language_data, stray_line_break, write_language_data

RULES = ("Translate every text in 'texts' into the language. Write chunk-NN.done.json beside this file as a JSON object "
         "of id -> translation. Keep every {placeholder}, TargetA/TargetB token and literal \\n exactly; you may move "
         "them. Use the glossary's terms. Where 'previous' has an entry, the English changed: update that translation. "
         "Match the game's register: short labels lowercase unless English capitalises them.")


@dataclass
class Target:
    ident: str     # Keyed:<key> or DefInjected:<type>:<key>
    key: str
    path: Path     # the language file it belongs in, with LANGUAGE standing for the folder name
    english: str

    def file(self, language):
        return Path(str(self.path).replace("{LANGUAGE}", language))


def targets(mod):
    out = []
    for folder, path in language_files(mod, "English", "Keyed"):
        rel = path.relative_to(folder / "Languages/English")
        for key, text in read_language_data(path):
            out.append(Target(f"Keyed:{key}", key, folder / "Languages/{LANGUAGE}" / rel, text))
    for e in def_text.entries(mod):
        out.append(Target(e.ident, e.key, e.folder / "Languages/{LANGUAGE}/DefInjected" / e.def_type / f"{e.stem}.xml", e.english))
    return out


def current(mod, language):
    done = {}
    for kind in ("Keyed", "DefInjected"):
        for _, path in language_files(mod, language, kind):
            for key, text in read_language_data(path):
                done[f"Keyed:{key}" if kind == "Keyed" else f"DefInjected:{path.parent.name}:{key}"] = text
    return done


def load_record(mod, language):
    path = mod.record_path(language)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def save_record(mod, language, record):
    path = mod.record_path(language)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(record.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def status(mod, language):
    """(missing targets, outdated targets) for one language."""
    done, record = current(mod, language), load_record(mod, language)
    missing, outdated = [], []
    for t in targets(mod):
        if t.ident not in done:
            missing.append(t)
        elif t.ident in record and record[t.ident] != t.english:
            outdated.append(t)
    return missing, outdated


def export(mod, language, chunk_chars=6000, include_all=False):
    """Writes the chunks and returns how many texts and chunks were written."""
    done = current(mod, language)
    if include_all:
        needed = targets(mod)
    else:
        missing, outdated = status(mod, language)
        needed = missing + outdated
    texts = {}
    for t in needed:
        entry = texts.setdefault(t.english, {"english": t.english, "previous": done.get(t.ident), "targets": []})
        entry["targets"].append(t.ident)
    items = [dict(id=i, **v) for i, v in enumerate(texts.values())]
    work = mod.work_dir / language
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / "index.json").write_text(json.dumps({"language": language, "texts": items}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    glossary = mod.glossary.read_text(encoding="utf-8") if mod.glossary.is_file() else ""
    chunks, chunk, size = [], [], 0
    for item in items:
        chunk.append(item)
        size += len(item["english"])
        if size >= chunk_chars:
            chunks.append(chunk)
            chunk, size = [], 0
    if chunk:
        chunks.append(chunk)
    for n, chunk in enumerate(chunks):
        body = {"language": language, "rules": RULES, "glossary": glossary,
                "texts": {str(i["id"]): i["english"] for i in chunk},
                "previous": {str(i["id"]): i["previous"] for i in chunk if i["previous"]}}
        (work / f"chunk-{n:02}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(items), len(chunks)


def import_(mod, language):
    """Validates the done chunks and writes them. Returns (written texts, problems, ids still untranslated)."""
    work = mod.work_dir / language
    index = {str(i["id"]): i for i in json.loads((work / "index.json").read_text(encoding="utf-8"))["texts"]}
    translations, problems = {}, []
    for path in sorted(work.glob("chunk-*.done.json")):
        for tid, text in json.loads(path.read_text(encoding="utf-8")).items():
            if tid not in index:
                problems.append(f"{path.name}: id {tid} is not in index.json")
            elif placeholders(text) != placeholders(index[tid]["english"]):
                problems.append(f"{path.name}: id {tid} placeholders differ: {index[tid]['english'][:60]!r}")
            elif not text.strip():
                problems.append(f"{path.name}: id {tid} is empty")
            elif stray_line_break(text, index[tid]["english"]):
                problems.append(f"{path.name}: id {tid} has a real line break; write \\n as the two characters")
            else:
                translations[tid] = text
    if problems:
        return 0, problems, []
    by_ident = {ident: translations[tid] for tid, item in index.items() if tid in translations for ident in item["targets"]}
    files, record = {}, load_record(mod, language)
    for t in targets(mod):
        if t.ident in by_ident:
            files.setdefault(t.file(language), {})[t.key] = by_ident[t.ident]
            record[t.ident] = t.english
    for path, updates in files.items():
        write_language_data(path, updates)
    save_record(mod, language, record)
    return len(translations), [], sorted(set(index) - set(translations), key=int)


def baseline(mod, language):
    """Records the current English for every text the language already has, accepting those translations as current."""
    done, record = current(mod, language), load_record(mod, language)
    for t in targets(mod):
        if t.ident in done:
            record[t.ident] = t.english
    save_record(mod, language, record)
    return len(record)
