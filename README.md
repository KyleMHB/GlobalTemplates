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

## Usage

When template-backed work is requested:

- Read only the relevant template.
- Inspect the target project and existing document before writing.
- Update existing files instead of creating duplicates.
- Preserve useful project-specific content and confirmed identifiers.
- Write the target file and return a concise change and validation summary.
- Do not edit this source repository unless template maintenance is explicitly requested.

Templates marked as public copy run their reader-facing prose through the installed `unslop` skill and its core validation gates before delivery. For `mod.json`, this covers `name` and `description`; for `About/About.xml`, it covers `<name>` and `<description>`. When the skill or its scripts are unavailable, the agent applies the repository writing rules manually and reports that automated Unslop validation was unavailable.

Automatic work follows the triggers in `AGENTS.md`. A `CHANGELOG.md` may be created or updated after a completed change with useful user, maintainer, or operational impact. An existing `TESTING.md` may be updated when its repeatable procedures, expectations, or evidence materially change; create it only on explicit request.

## Adding or changing templates

1. Use a descriptive kebab-case filename ending in `-template.md`.
2. Include exactly one `## Use when`, `## Evidence`, `## Update rules`, `## Validation`, and `## Delivery` heading. Public-facing templates also require exactly one `## Public copy` heading. Name the target file under `Use when`.
3. Keep project-specific detail only in narrow platform templates.
4. Update `templates.json`, this catalog, and the mapping in `AGENTS.md`.
5. Run the repository validator.

~~~powershell
pwsh -NoProfile -File scripts/validate-templates.ps1
~~~

## Contributing

Contributions, issues, and feature requests are welcome.

## Links

[![Support me on Ko-fi](https://img.shields.io/badge/Support_me_on_Ko--fi-72a4f2?style=for-the-badge&logo=kofi&logoColor=white)](https://ko-fi.com/I7L525WMJ6)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/KyleMHB/GlobalTemplates)

## License

Released under the **GNU General Public License v3.0**. See [`LICENSE`](LICENSE) for details.

Copyright (C) 2026 KyleMHB.

Commercial use is allowed under GPLv3. Distributed modified versions must remain under GPLv3 and make corresponding source available as required by the license.
