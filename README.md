# GlobalTemplates

Reusable, opt-in templates for repository documentation, Steam Workshop descriptions, and game mod metadata.

## Purpose

This repository keeps shared templates in one version-controlled location so documentation and metadata rules stay consistent across projects. Ordinary templates are inspected or applied only when explicitly requested. Project-memory and changelog templates may also activate when their file-specific materiality trigger is satisfied.

The canonical template catalog is [`templates.json`](templates.json). Local paths are resolved from this repository. Cloud environments can use this raw GitHub base URL when local files are unavailable and network access is allowed:

~~~text
https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/
~~~

## Template catalog

| Document | Template | Format |
| --- | --- | --- |
| `README.md` | `Git/readme-template.md` | GFM |
| `CHANGELOG.md` | `Git/change-log-template.md` | GFM |
| `PROJECT.md` | `Git/project-template.md` | GFM |
| `HISTORY.md` | `Git/history-template.md` | GFM |
| `DECISIONS.md` | `Git/decisions-template.md` | GFM |
| `TESTING.md` | `Git/testing-template.md` | GFM |
| `steam-description.md` | `Steam/steam-description-template.md` | BBCode |
| `mod.json` | `Steam/wayward/wayward-mod-json-template.md` | JSON |
| `About/About.xml` | `Steam/rimworld/rimworld-about-xml-template.md` | XML |

## Usage

When template-backed work is requested:

- Read only the relevant template.
- Inspect the target project and existing document before writing.
- Update existing files instead of creating duplicates.
- Preserve useful project-specific content and confirmed identifiers.
- Write the target file and return a concise change and validation summary.
- Do not edit this source repository unless template maintenance is explicitly requested.

Automatic project-memory and changelog work follows the triggers in `AGENTS.md`. Only the triggered document is created or updated.

## Project memory

The project-memory templates have separate responsibilities:

- `PROJECT.md`: current scope, architecture, validated state, risks, and next steps.
- `HISTORY.md`: chronological engineering evidence, corrections, and lessons.
- `DECISIONS.md`: stable technical decisions and consequences.
- `TESTING.md`: repeatable procedures and observed validation.
- `CHANGELOG.md`: concise release-oriented history.

Use only the documents that provide ongoing value. Read headings and the newest relevant sections instead of preloading full history.

Automatic creation or maintenance is limited to:

- `PROJECT.md` after a material change to an iterative project's current state.
- `HISTORY.md` for durable implementation evidence, root causes, rejected approaches, incidents, or lessons.
- `DECISIONS.md` when a choice constrains future technical work.
- `TESTING.md` when repeatable procedures, expectations, or evidence materially change.
- `CHANGELOG.md` after a completed change with useful user, maintainer, or operational impact.

## Adding or changing templates

1. Use a descriptive kebab-case filename ending in `-template.md`.
2. Include exactly one `## Use when`, `## Evidence`, `## Update rules`, `## Validation`, and `## Delivery` heading. Name the target file under `Use when`.
3. Keep project-specific detail only in narrow platform templates.
4. Update `templates.json`, this catalog, and the mapping in `AGENTS.md`.
5. Run the repository validator.

~~~powershell
pwsh -NoProfile -File scripts/validate-templates.ps1
~~~

## Contributing and Forking Policy

Contributions, issues, and feature requests are welcome.

**Forking Policy:** If your fork primarily consists of bug fixes or feature additions that align with the core vision of this repository, I reserve the right to request that your changes be submitted as a pull request to this existing codebase rather than being published as a separate standalone release.

This is a project request, not an additional GPLv3 restriction.

## Links

[![Support me on Ko-fi](https://img.shields.io/badge/Support_me_on_Ko--fi-72a4f2?style=for-the-badge&logo=kofi&logoColor=white)](https://ko-fi.com/I7L525WMJ6)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/KyleMHB/GlobalTemplates)

## License

Released under the **GNU General Public License v3.0**. See [`LICENSE`](LICENSE) for details.

Copyright (C) 2026 KyleMHB.

Commercial use is allowed under GPLv3. Distributed modified versions must remain under GPLv3 and make corresponding source available as required by the license.
