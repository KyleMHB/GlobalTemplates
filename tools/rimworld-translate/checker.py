"""Checks a mod's translations: Keyed text against the C# that uses it, and every language against English.

Fails on malformed LanguageData, a key defined twice, a key the code translates that English lacks, an English key
nothing uses (when keyPrefix is set), a placeholder index the call site does not pass, a translation whose placeholders
differ from English, a DefInjected key that matches no translatable def field, and player-facing text still hardcoded in
the C#. Untranslated and outdated texts are only counted, since the game shows English in their place.
"""
import json
import re

import def_text
from modlayout import language_files, placeholders, read_language_data, stray_line_break

NOT_TRANSLATED = "// not translated"
NOT_TEXT_PREFIXES = ("KM_", "DV_", "UI/", "DEV:")
# Places a string literal reaches the player. Display fields and calls: a single capitalised word there counts as text.
UI_CALL = re.compile(
    r'\b(?:defaultLabel|defaultDesc|toolTip|label|count|reason|description|note)\s*=\s*"([^"]*)"'
    r'|(?:Messages\.Message|\.Label|CheckboxLabeled|ButtonText|new FloatMenuOption|\.AppendLine|\.Append|\.Disable'
    r'|ReceiveLetter|TooltipHandler\.TipRegion|\.In)\s*\(\s*"([^"]*)"'
    r'|\.Add\(\s*(?:"[^"]*"|[\w.]+(?:\s*\+\s*"[^"]*")?)\s*,\s*"([^"]*)"')
# Returned or chosen literals are often keys or ids, so only sentence-like text counts.
UI_VALUE = re.compile(r'\breturn\s+"([^"]*)"|[?:]\s*"([^"]*)"')
# A literal followed by .Translate( is a key; an interpolated string's holes are code.
KEY_CALL = re.compile(r'"[^"]*"\s*\.\s*Translate\s*\(')
INTERPOLATED = re.compile(r'\$@?"(?:[^"{]|\{[^}]*\})*"')


def reads_as_text(literal, prefix, single_word):
    """English words, rather than a key, defName, path or format string."""
    if not literal or literal.startswith(NOT_TEXT_PREFIXES) or (prefix and literal.startswith(prefix)):
        return False
    if re.search(r"[A-Za-z]{2,}[ ,][A-Za-z(]|[a-z][.!?)]$", literal):
        return True
    return single_word and bool(re.fullmatch(r"[A-Z][a-z]+", literal))


def hardcoded_text(line, prefix):
    code = INTERPOLATED.sub('""', KEY_CALL.sub("_(", line))
    first = lambda m: next(g for g in m.groups() if g is not None)  # noqa: E731
    return (any(reads_as_text(first(m), prefix, True) for m in UI_CALL.finditer(code))
            or any(reads_as_text(first(m), prefix, False) for m in UI_VALUE.finditer(code)))


def call_arguments(text, start):
    """The number of top-level arguments in the call whose "(" ends at start."""
    depth, count, quote, i, seen = 1, 0, None, start, False
    while i < len(text) and depth:
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote, seen = c, True
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 1:
            count += 1
        elif not c.isspace():
            seen = True
        i += 1
    return count + 1 if seen else 0


def source_files(mod):
    return [p for s in mod.sources for p in sorted(s.rglob("*.cs"))
            if p.name not in mod.skip_files and "obj" not in p.parts and "bin" not in p.parts]


def code_usage(mod):
    """Literal keys, run-time key prefixes, each Translate call's argument counts, and hardcoded UI text."""
    prefix = mod.key_prefix
    key_literal = re.compile(r'"(' + re.escape(prefix) + r'[A-Za-z0-9_]*)"') if prefix else None
    translate = re.compile(r'"([A-Za-z][A-Za-z0-9_.]*)"\s*\.\s*Translate\s*\(')
    keys, prefixes, calls, hardcoded = set(), set(), {}, []
    for path in source_files(mod):
        text = path.read_text(encoding="utf-8")
        if key_literal:
            for m in key_literal.finditer(text):
                (prefixes if m.group(1).endswith("_") else keys).add(m.group(1))
        for m in translate.finditer(text):
            keys.add(m.group(1))
            calls.setdefault(m.group(1), set()).add(call_arguments(text, m.end()))
        if not mod.hardcoded_check:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or NOT_TRANSLATED in line or "Log." in line or "Exception(" in line:
                continue
            if hardcoded_text(line, prefix):
                hardcoded.append(f"{mod.rel(path)}:{number}: hardcoded UI text: {stripped[:120]}")
    return keys, prefixes, calls, hardcoded


def load_keyed(mod, language, problems):
    entries = {}
    for _, path in language_files(mod, language, "Keyed"):
        for key, text in read_language_data(path, problems, mod.rel(path)):
            if key in entries:
                problems.append(f"{mod.rel(path)}: {key} is defined more than once")
            entries[key] = text
    return entries


def load_def_injected(mod, language, problems):
    entries = {}
    for _, path in language_files(mod, language, "DefInjected"):
        for key, text in read_language_data(path, problems, mod.rel(path)):
            ident = f"DefInjected:{path.parent.name}:{key}"
            if ident in entries:
                problems.append(f"{mod.rel(path)}: {key} is defined more than once")
            entries[ident] = text
    return entries


def vanilla_keys(mod):
    """The game's own English Keyed keys, which mods may translate without defining."""
    keys = set()
    data = mod.game_dir / "Data" if mod.game_dir else None
    for path in sorted(data.glob("*/Languages/English/Keyed/*.xml")) if data and data.is_dir() else []:
        keys |= {k for k, _ in read_language_data(path)}
    return keys


def translated_languages(mod):
    names = set(mod.languages)
    for folder in mod.folders:
        base = folder / "Languages"
        if base.is_dir():
            names |= {p.name for p in base.iterdir() if p.is_dir()}
    return sorted(names - {"English"})


def check(mod, notes=None):
    """Problems that fail the check. With notes, untranslated and outdated counts are added there."""
    problems = []
    english = load_keyed(mod, "English", problems)
    keys, prefixes, calls, hardcoded = code_usage(mod)
    problems += hardcoded
    prefix = mod.key_prefix
    vanilla = vanilla_keys(mod)
    for key in sorted(keys - english.keys() - vanilla):
        if not prefix or key.startswith(prefix):
            problems.append(f"{key} is used in the source but missing from Languages/English/Keyed")
    if prefix:
        for key in sorted(english.keys() - keys):
            if key.startswith(prefix) and not any(key.startswith(p) for p in prefixes):
                problems.append(f"{key} is defined in Languages/English/Keyed but never used")
    for key, counts in sorted(calls.items()):
        if key not in english:
            continue
        indexes = [int(p) for p in placeholders(english[key]) if p.isdigit()]
        if indexes and max(indexes) >= min(counts):
            problems.append(f"{key} uses {{{max(indexes)}}} but a call passes {min(counts)} argument(s)")
    defs = {e.ident: e.english for e in def_text.entries(mod)}
    own_defs = def_text.def_names(mod) | {(i.split(":")[1], i.split(":")[2].split(".")[0]) for i in defs}
    keyed_english = {f"Keyed:{k}": v for k, v in english.items()}
    for language in translated_languages(mod):
        keyed = {f"Keyed:{k}": v for k, v in load_keyed(mod, language, problems).items()}
        injected = load_def_injected(mod, language, problems)
        for ident, text in sorted(keyed.items()):
            if ident not in keyed_english:
                problems.append(f"{language}: Keyed {ident[6:]} is not an English key")
            elif placeholders(text) != placeholders(keyed_english[ident]):
                problems.append(f"{language}: Keyed {ident[6:]} placeholders differ from English")
            elif stray_line_break(text, keyed_english[ident]):
                problems.append(f"{language}: Keyed {ident[6:]} has a real line break where English uses \\n")
        for ident, text in sorted(injected.items()):
            _, def_type, key = ident.split(":", 2)
            if ident not in defs:
                # Translations of other mods' or vanilla defs cannot be checked here.
                if (def_type, key.split(".")[0]) in own_defs:
                    problems.append(f"{language}: DefInjected/{def_type} {key} matches no translatable def field")
            elif placeholders(text) != placeholders(defs[ident]):
                problems.append(f"{language}: DefInjected/{def_type} {key} placeholders differ from English")
        if notes is not None:
            sources = {**keyed_english, **defs}
            done = {**keyed, **injected}
            missing = len(sources.keys() - done.keys())
            record_path = mod.record_path(language)
            record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {}
            outdated = sum(1 for i, e in sources.items() if i in done and i in record and record[i] != e)
            if missing or outdated:
                notes.append(f"{language}: {missing} untranslated, {outdated} outdated (English changed since translation)")
    return problems
