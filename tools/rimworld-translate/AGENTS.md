# RimWorld Translate: agent entry point

Keep reusable translation tooling here. Keep each mod's translations, glossary, record and `translation.json` in that mod.

| Task | Read |
| --- | --- |
| Translate a mod, add a language, or update translations after English changed | the [`rimworld-translate` skill](../../.agents/skills/rimworld-translate/SKILL.md) |
| Commands and `translation.json` fields | README.md; `python rwtranslate.py --help` |
| Game facts about Keyed, DefInjected and language folders | [Localisation facts](docs/localisation.md) |
| Change behaviour | `checker.py` (check), `def_text.py` (translatable def fields), `exchange.py` (export, import, record), `extract.py` (C# batches), `modlayout.py` (settings, load folders, LanguageData files) |

After code changes run `python -m unittest discover -s tests`, then `python rwtranslate.py --mod "<a translated mod>" check` on any mod with a `translation.json`, which must still pass.
