# RimWorld Translate

Shared translation tooling for Kyle's RimWorld mods: a checker for Keyed and DefInjected files, a lister of translatable
def text, export/import of translation chunks, and an applier for C# string-extraction batches.

```
python rwtranslate.py --mod "<mod root>" check | status | defs
python rwtranslate.py --mod "<mod root>" export <Language> | import <Language> | baseline <Language>
python rwtranslate.py --mod "<mod root>" extract <batch.py> [...]
```

`python rwtranslate.py --help` describes each command. Run the tests with `python -m unittest discover -s tests`.

## Per-mod settings: `<mod root>/translation.json`

Every field is optional; a mod without the file is still checked with these defaults.

| Field | Default | Meaning |
| --- | --- | --- |
| `keyPrefix` | none | Prefix of the mod's own Keyed keys, such as `MyMod_`. Enables the unused-key check and run-time key prefixes. |
| `source` | `["Source"]` | Folders searched for C#. |
| `skipFiles` | `[]` | C# file names to skip, such as pure-logic files compiled into tests without RimWorld. |
| `hardcodedCheck` | `false` | Fail on player-facing English literals in C#. Turn on once a mod's strings are extracted. |
| `languages` | `[]` | Languages the mod maintains; `status` and `check` also pick up any folder under `Languages/`. |
| `record` | `translation` | Folder holding `glossary.md` and `record/<Language>.json`. Commit it; it is not shipped. |
| `work` | `work/translation` | Where `export` writes chunks. Keep it ignored by git. |
| `gameDir` | `RIMWORLD_DIR`, then `gameDir` in the untracked `rwtranslate.local.json` next to this README, then Steam's standard `C:\Program Files (x86)\Steam\steamapps\common\RimWorld` | Vanilla Keyed keys come from here, so translating vanilla keys is not reported as missing. Prefer the local file over committing a machine path to a mod. |

## Layout the tool assumes

Load folders come from `LoadFolders.xml` (the newest version block, conditional folders included), or else the root,
`Common` and the newest version folder. English Keyed files and def text are read from every load folder, and a
translation is written into the same load folder as its English, so DLC-conditional text loads only with its folder.
DefInjected keys use list indexes after `ParentName` inheritance, such as `KM_Cooler.comps.4.effect`; the game's own
translations use the same numeric form (`Bear_Grizzly.lifeStages.0.label`).

## Record and outdated translations

`import` and `baseline` store the English each translation was made from in `record/<Language>.json`. When the English
later changes, `status` and `check` count the translation as outdated and `export` includes it with the previous
translation beside it. A language with no record never reports outdated texts; run `baseline` to start tracking.
