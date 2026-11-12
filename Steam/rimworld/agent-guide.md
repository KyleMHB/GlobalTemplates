# RimWorld agent read route

Use only the branch relevant to the task. Project instructions own design choices, expected values, run/deployment permissions and acceptance.

| Task | Start here | Read next only as needed |
| --- | --- | --- |
| Write test cases, change the harness, triage results | [Harness agent guide](../../tools/rimworld-dev-tests/AGENTS.md), or `python tools/rimworld-dev-tests/rimtest.py guide` from the Templates root | `guide authoring`; `guide recording` for capture; `guide recipes`, then a matching topic such as `beds` or `placement` |
| Paint masks, browse a mod gallery or queue reviews | [Mask editor guide](mask-editor-guide.md) | [Mask editor agent guide](../../tools/rimworld-mask-editor/AGENTS.md) |
| Generate/edit sprites, directional variants, masks, icons, effects or drawing settings | [Artwork guide](rimworld-art-guide.md#read-route) | Relevant sections plus the target mod's art requirements and approved references |
| Change About.xml metadata | [About.xml template](rimworld-about-xml-template.md) when template-backed metadata work is requested | Existing About.xml, LoadFolders.xml and package evidence |
| Establish game behavior or version-sensitive facts | Project configuration and installed game sources | [Harness game facts](../../tools/rimworld-dev-tests/docs/game-facts.md), or a project's own game reference; search relevant types or headings |

The test harness, **RimWorld Dev Tests**, is bundled in `tools/rimworld-dev-tests`. Each mod supplies its adapter and cases and points its build and wrapper at that folder. Its short guide routes to setup pitfalls, evidence and a workflow for retaining discoveries. Read that guide instead of loading every source or recipe.

Before a first build or run, set the machine's game paths as its README's "Local paths" describes. Keep mod-specific rules and evidence in their owning repository. Add reusable artwork guidance here and reusable testing discoveries to the harness recipes, with version scope, evidence and limits.
