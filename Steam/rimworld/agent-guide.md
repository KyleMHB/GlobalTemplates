# RimWorld agent read route

Use only the branch relevant to the task. Project instructions own design choices, expected values, run/deployment permissions and acceptance.

| Task | Start here | Read next only as needed |
| --- | --- | --- |
| Write test cases, change the harness, triage results | [Harness agent guide](../../tools/rimworld-dev-tests/AGENTS.md), or `python tools/rimworld-dev-tests/rimtest.py guide` from the Templates root | `guide authoring`; `guide recording` for capture; `guide recipes`, then a matching topic such as `beds` or `placement` |
| Paint masks, browse a mod gallery or queue reviews | [Mask editor guide](mask-editor-guide.md) | [Mask editor agent guide](../../tools/rimworld-mask-editor/AGENTS.md) |
| Generate/edit sprites, directional variants, masks, icons, effects or drawing settings | [Artwork guide](rimworld-art-guide.md#read-route) | Relevant sections plus the target mod's art requirements and approved references |
| Write C# for a new mod | [Translatable by default](#translatable-by-default) | [Localisation facts](../../tools/rimworld-translate/docs/localisation.md) |
| Translate a mod, add a language, or update translations after English changed | The `rimworld-translate` skill (`.agents/skills/rimworld-translate/SKILL.md`) | [Translate tool agent guide](../../tools/rimworld-translate/AGENTS.md); [localisation facts](../../tools/rimworld-translate/docs/localisation.md) |
| Change About.xml metadata | [About.xml template](rimworld-about-xml-template.md) when template-backed metadata work is requested | Existing About.xml, LoadFolders.xml and package evidence |
| Establish game behavior or version-sensitive facts | Project configuration and installed game sources | [Harness game facts](../../tools/rimworld-dev-tests/docs/game-facts.md), or a project's own game reference; search relevant types or headings |

The test harness, **RimWorld Dev Tests**, is bundled in `tools/rimworld-dev-tests`. Each mod supplies its adapter and cases and points its build and wrapper at that folder. Its short guide routes to setup pitfalls, evidence and a workflow for retaining discoveries. Read that guide instead of loading every source or recipe.

Before a first build or run, set the machine's game paths as its README's "Local paths" describes. Keep mod-specific rules and evidence in their owning repository. Add reusable artwork guidance here and reusable testing discoveries to the harness recipes, with version scope, evidence and limits.

## Translatable by default

A new mod ships English only but keeps every player-facing text translatable, so others can publish translation mods without code changes. Def XML is translatable as written; the rules cover C#.

- With the first C# file, add `translation.json` with a per-mod `keyPrefix` (such as `MyMod_`) and `"hardcodedCheck": true`, and put English text in `Languages/English/Keyed/<Mod>.xml`. Every Keyed key starts with the prefix, because Keyed keys are global across mods.
- Player-facing text, including settings labels, tooltips, letters and messages, goes through `"Key".Translate()`. Use one key per whole sentence, with `{0}` slots or `pawn.Named("PAWN")` for values; never join translated fragments.
- Developer-only text (dev-mode gizmos, `Log.*` messages, config errors) stays English and is marked `// not translated`.
- The mod's build or commit hook runs `python <templates-root>/tools/rimworld-translate/rwtranslate.py --mod "<mod root>" check` (see the [tool README](../../tools/rimworld-translate/README.md)) and fails on a hardcoded English literal.

The [localisation facts](../../tools/rimworld-translate/docs/localisation.md) cover when `Translate()` is safe to call and the `TaggedString` conditional pitfall. Existing mods adopt these rules when next worked on, through step 2 of the `rimworld-translate` skill.
