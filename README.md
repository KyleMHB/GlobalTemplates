# GlobalTemplates

Reusable, opt-in templates for repository documentation, Steam Workshop descriptions, and game mod metadata.

## Purpose

This repository keeps shared templates in one version-controlled location so documentation and metadata rules stay consistent across projects. Templates are inspected or applied only when explicitly requested, except for eligible changelog updates and material updates to an existing testing guide.

The canonical template catalog is [`templates.json`](templates.json). Local paths are resolved from this repository. Cloud environments can use this raw GitHub base URL when local files are unavailable and network access is allowed:

~~~text
https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/
~~~

## Template catalog

| Document | Template | Format | Public copy |
| --- | --- | --- | --- |
| `README.md` | `Git/readme-template.md` | GFM | Yes |
| `CHANGELOG.md` | `Git/change-log-template.md` | GFM | Yes |
| `TESTING.md` | `Git/testing-template.md` | GFM | No |
| `steam-description.md` | `Steam/steam-description-template.md` | BBCode | Yes |
| `mod.json` | `Steam/wayward/wayward-mod-json-template.md` | JSON | Yes |
| `About/About.xml` | `Steam/rimworld/rimworld-about-xml-template.md` | XML | Yes |

## Supporting files

- [RimWorld agent read route](Steam/rimworld/agent-guide.md) locates the shared test harness and task-specific artwork guidance.
- [RimWorld mask editor guide](Steam/rimworld/mask-editor-guide.md) explains cross-mod gallery, painting, review and recipe workflows.
- [RimWorld artwork guide](Steam/rimworld/rimworld-art-guide.md) covers sprites, directions, masks and native rendering.
- `Steam/workshop-page-guide.md` explains how to build an illustrated Workshop page.
- `Steam/preview-workshop.py` renders a `steam-description.md` file to a local HTML preview. It needs Python 3.9 or newer.
- `Git/matt-pocock-workflow.md` shows which engineering skill to use for each kind of work.
- `tools/rimworld-dev-tests` is a shared C# runner and Python launcher for in-game RimWorld mod tests. Start with its `AGENTS.md`.
- `tools/rimworld-mask-editor` is a mask painter, artwork gallery and recipe exporter for RimWorld mods. Start with its `README.md`.
- `profiles/` holds author profiles; see [Author details](#author-details).

## Install

Clone this repository anywhere. Below, `<templates-root>` means that folder.

1. **Load the shared rules in every project.** Add one line to your user-level agent instructions. Keep shared rules in `AGENTS.md` rather than copying them into each file.
   - Codex, `~/.codex/AGENTS.md`: `Read and apply <templates-root>/AGENTS.md.`
   - Claude Code, `~/.claude/CLAUDE.md`: `@<templates-root>/AGENTS.md`
   - Other agents: the equivalent user-level instruction file.
2. **Register the bundled skills.** Link each folder in `.agents/skills` into the skill folder your agent reads: `~/.agents/skills` or `~/.codex/skills` for Codex, and `~/.claude/skills` for Claude Code. A link keeps the skill current when you pull.

   ~~~powershell
   # Windows: a directory junction needs no admin rights
   cmd /c mklink /J "%USERPROFILE%\.claude\skills\steam-workshop-utils" "<templates-root>\.agents\skills\steam-workshop-utils"
   ~~~

   ~~~bash
   # macOS and Linux
   ln -s "<templates-root>/.agents/skills/steam-workshop-utils" ~/.claude/skills/steam-workshop-utils
   ~~~

   Repeat for `review-mod` and for `~/.agents/skills`. Optional `agents/openai.yaml` files are Codex metadata; other agents use `SKILL.md` alone. See [skill lookup](skill-lookup.md) for discovery and fallback rules.
3. **Install the engineering skills** (optional). `AGENTS.md` routes planning and implementation to the Matt Pocock skills, verified at v1.3.1; see [the workflow guide](Git/matt-pocock-workflow.md). Install that version for each agent you use. Without them, agents do the same work directly.
4. **Name your author profile** (optional). See [Author details](#author-details).
5. **Set local game paths** for the RimWorld test harness, if you use it. See its README's "Local paths".

## Usage

When template-backed work is requested:

- Read the relevant template and any file it points to.
- Inspect the target project and existing document before writing.
- Update existing files instead of creating duplicates.
- Preserve useful project-specific content and confirmed identifiers.
- Write the target file and return a concise change and validation summary.
- Do not edit this source repository unless template maintenance is explicitly requested.

Templates marked as public copy run their reader-facing prose through the installed `unslop` skill before delivery. For `mod.json`, this covers `description`; for `About/About.xml`, it covers `<description>`. When the skill is unavailable, the agent applies the repository writing rules manually and reports that `unslop` was unavailable.

Automatic work follows the triggers in `template-routing.md`. A `CHANGELOG.md` may be created or updated after a completed change with useful user, maintainer, or operational impact. An existing `TESTING.md` may be updated when its repeatable procedures, expectations, or evidence materially change; create it only on explicit request.

## Author details

The README and Steam description templates have two author-specific parts: a Ko-fi badge (`{kofi-url}`) and an AI disclosure section. Both come from an author profile:

1. Copy `profiles/example.md` to `profiles/<your-name>.md` and fill it in. Keep or delete each section.
2. Name it in the same user-level file as the shared rules: `Author profile: <templates-root>/profiles/<your-name>.md`.

Agents use only the profile your instructions name, never another file in `profiles/`. With no profile named, they leave out the Ko-fi badge and the AI disclosure instead of publishing a placeholder.

## Adding or changing templates

1. Use a descriptive kebab-case filename ending in `-template.md`.
2. Include exactly one `## Use when`, `## Evidence`, `## Update rules`, `## Validation`, and `## Delivery` heading. Public-facing templates also require exactly one `## Public copy` heading. Name the target file under `Use when`.
3. Keep project-specific detail only in narrow platform templates.
4. Update `templates.json`, this catalog, and the mapping in `template-routing.md`.
5. Run the repository validator and its failure tests. They need PowerShell 7 (`pwsh`), or Windows PowerShell 5.1 on Windows. The Python preview tool and bundled scripts do not require PowerShell.

~~~powershell
pwsh -NoProfile -File scripts/validate-templates.ps1
pwsh -NoProfile -File scripts/test-validator.ps1
~~~

With Windows PowerShell 5.1, run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate-templates.ps1` instead, since its default policy blocks unsigned scripts.

## Contributing

Contributions, issues, and feature requests are welcome.

## License

Released under the **GNU General Public License v3.0**. See [`LICENSE`](LICENSE) for details.

Copyright (C) 2026 KyleMHB.

Commercial use is allowed under GPLv3. Distributed modified versions must remain under GPLv3 and make corresponding source available as required by the license.

## Links

Support me on Ko-fi.

[![Support me on Ko-fi](https://img.shields.io/badge/Support_me_on_Ko--fi-72a4f2?style=for-the-badge&logo=kofi&logoColor=white)](https://ko-fi.com/I7L525WMJ6)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/KyleMHB/GlobalTemplates)
