# README Template

## Use when

Use this template only when the user explicitly requests template-backed README work. Create or update `README.md` in the project root.

## Evidence

Inspect the repository and user-provided notes before writing. Infer the project type from source files, manifests, build scripts, package metadata, and existing documentation.

- Use only evidence-backed names, commands, links, compatibility claims, and features.
- Preserve useful project-specific content when updating an existing README.
- Mark important unresolved details for confirmation or omit them when they are not needed.
- Identify forks early and preserve their inherited license.

## Content

Start with the project name and a concise summary. Use plain headings and include only applicable sections.

Common sections:

- Features
- Installation
- Usage
- Configuration
- Building from source
- Credits
- Contributing
- License
- Links, always last

Use commands found in project files or confirmed notes. Do not invent package names, installation paths, download locations, or configuration behavior. Leave out test results and validation status. On the subject of testing, cover only build and install instructions.

### Contributing section

Include this section when the project accepts outside contributions, using:

> Contributions, issues, and feature requests are welcome.

### License section

Always include this section. If no license can be confirmed, omit the license claim and report the gap in the delivery summary.

For a fork, state that it inherits the original project's license and link to the original license or project when available. Do not relicense a fork without authorization from the relevant copyright holders.

For an original project, use its existing confirmed license. When GPLv3 is requested and the repository contains the official license text, use:

> Released under the **GNU General Public License v3.0**. See [`LICENSE`](LICENSE) for the complete terms.
>
> Commercial use is allowed. Distributed modified versions must remain under GPLv3 and make corresponding source available as required by the license.

Do not claim GPLv3 unless the repository contains the official GPLv3 text or adding it is part of the request.

### AI disclosure

When the author profile named in the user's or project's agent instructions has an `ai-disclosure`, add its Markdown block as its own section immediately before Links, or last when Links is absent. Copy it verbatim, keeping its wording and emphasis. Omit the section when no profile is named or it has no disclosure. Never use a profile that was not named.

### Links section

For projects the author owns or maintains, include these linked badges in the Links section. Replace `{repository-url}` with the confirmed project repository URL. If no repository URL is confirmed, omit the GitHub badge instead of adding a placeholder to `README.md`.

Replace `{kofi-url}` with the `kofi-url` from the author profile named in the user's or project's agent instructions; when none is set, omit the Ko-fi badge and its introduction. Introduce the badges with: `Support me on Ko-fi.`

[![Support me on Ko-fi](https://img.shields.io/badge/Support_me_on_Ko--fi-72a4f2?style=for-the-badge&logo=kofi&logoColor=white)]({kofi-url})
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white)]({repository-url})

For a fork the author maintains, introduce the badges with: `Support me on Ko-fi. This does not imply endorsement by the original authors.` Inspect the inherited license and upstream project terms, and omit the Ko-fi badge when support links or monetization are explicitly prohibited. Keep upstream attribution clear.

Do not embed scripts or replace the badges with raw widget code.

## Update rules

- Update the existing `README.md` instead of creating a duplicate.
- Keep the existing structure when it is already clear and useful.
- Remove sections only when they are obsolete, incorrect, duplicated, or explicitly requested.
- Use GitHub Flavored Markdown.
- Do not add placeholder links or empty sections.

## Public copy

Run the installed `unslop` skill on all reader-facing prose after drafting and before delivery. Preserve facts, names, identifiers, commands, links, code, and Markdown structure.

If `unslop` is unavailable, apply the rules in `writing-copy.md` manually and state in the delivery summary that `unslop` was unavailable.

## Validation

Confirm that commands match project scripts, relative links resolve, badge destinations use confirmed values, required policy and license text are accurate, and no unsupported claims, scripts, or placeholders remain.

## Delivery

Write the result to `README.md`. Return a concise summary of changes and validation. Do not reproduce the full README in chat unless requested.
