---
name: rimworld-translate
description: "Translate a RimWorld mod: make its C# text translatable, add a language, or update translations after English text changed."
---

Translating runs on the tool in `tools/rimworld-translate` of the Templates repository that bundles this skill (two folders above this skill's folder, or the Templates root the user's instructions name). Below, `rwt` means `python <templates-root>/tools/rimworld-translate/rwtranslate.py --mod "<mod root>"`. Its README lists the commands and `translation.json` fields; [the localisation facts](../../../tools/rimworld-translate/docs/localisation.md) hold the game facts. Every step ends on its criterion; finish it before starting the next.

## 1. Orient

Read the mod's `AGENTS.md`, `LoadFolders.xml` and `translation.json`. If it has no `translation.json`, create one with `keyPrefix` (the prefix its own Keyed keys use, or a new one such as `Mod_`) and `languages`. Run `rwt status` and `rwt check`.

Done when: you know the key prefix, the target languages, and whether the C# still holds English text (step 2) or only the translations need work (skip to step 3).

## 2. Extract C# text

Set `"hardcodedCheck": true`; `rwt check` then lists player-facing English literals. Convert them in **batches** of a few files, written as batch files in the format `extract.py` documents, applied with `rwt extract <batch.py>`, and followed by a build.

- One key per whole sentence, with `{0}` slots or `pawn.Named("PAWN")` for values. Pass a list or plural through separate keys (`...One` / `...Many`).
- Keep identifiers and display text apart: a name used in saved keys, signals or lookups keeps its English, and gets a translated label beside it.
- Translate when text is shown, never in static initialisers.
- Mark developer-only text (dev gizmos, config errors, logs) with `// not translated`.
- English output stays byte-identical; tests that compare English text keep passing.

Done when: the mod builds, `rwt check` passes with `hardcodedCheck` on, and the project's tests pass.

## 3. Glossary

Before translating, write or extend `<mod>/translation/glossary.md`: a table of every recurring proper noun and system term with its rendering in each target language, plus per-language style notes such as formality and how to render in-game names.

Done when: every term that appears in three or more English texts has a row for every target language.

## 4. Translate

For each language, `rwt export <Language>` writes `chunk-NN.json` files under the work folder. Each chunk carries the rules, the glossary, the texts by id, and the previous translation where the English changed. For each chunk, write `chunk-NN.done.json` with the Write tool: a JSON object mapping every id to its translation. (A shell heredoc turns the literal `\n` RimWorld uses into real line breaks.) Chunks are independent: dispatch one subagent per chunk, giving it the chunk's path and this paragraph.

Done when: every chunk has a done file covering every id it holds.

## 5. Import and verify

Run `rwt import <Language>`. It writes nothing until every translation keeps its placeholders; fix the ids it names and import again. Then run `rwt status`, `rwt check` and the mod's build.

Done when: status shows 0 untranslated and 0 outdated for each language, check passes, and the build passes.

## 6. Wire

- The mod's deploy step copies `Languages` and any load folder's `Languages`.
- Its commit hook or CI runs `rwt check`.
- Its `AGENTS.md` names the check command and this skill.

Done when: each holds, or the user has been told which do not.
