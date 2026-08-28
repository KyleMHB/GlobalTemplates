# Steam Workshop Description Template

## Use when

Use this template only when the user explicitly requests a template-backed Steam Workshop description. Create or update `steam-description.md` in the project root.

## Evidence

Inspect the mod and user-provided notes. Use only confirmed features, game versions, dependencies, compatibility, multiplayer behavior, save safety, authors, links, and license information.

## Format

Write Steam BBCode, not Markdown:

- Headers: `[h1]Heading[/h1]` or `[h2]Heading[/h2]`
- Bold: `[b]text[/b]`
- Italic: `[i]text[/i]`
- Lists: `[list][*]First item[*]Second item[/list]`
- Links: `[url=https://example.com]Link text[/url]`
- Images: `[img]https://example.com/image.png[/img]`
- Linked images: `[url=https://example.com][img]https://example.com/image.png[/img][/url]`
- Divider: `[hr][/hr]`

Keep the order natural for the mod instead of forcing every possible section.

## Required content

### Description

Use a clear hook and concise summary of what the mod changes and why it is useful.

### Features

Use a scannable BBCode list of confirmed player-facing features.

### How to Use

Explain how players enable, configure, and use the mod in-game. Include relevant menus, controls, hotkeys, setup steps, or automatic behavior. Keep the instructions concise and evidence-based.

### Fork History

For a fork, name the original mod and author, explain why the fork exists, and describe the meaningful differences from the upstream mod. Omit this section for original mods.

### License and Forking Policy

For a fork, state that it inherits the original mod's license. Do not relicense it without authorization from the relevant copyright holders.

For an original GPLv3 mod, state that commercial use is allowed and distributed modified versions must remain under GPLv3 with corresponding source available as required by the license.

Include this non-binding project policy:

> If your fork primarily consists of bug fixes or feature additions that align with the core vision of this mod, I reserve the right to request that your changes be submitted as a Pull Request to my existing codebase rather than being published as a completely separate standalone release.

Make clear that this is a request, not an additional GPLv3 restriction.

### Links

For mods I own or maintain, include these linked badges in the Links section. Replace `{repository-url}` with the confirmed project repository URL. If no repository URL is confirmed, omit the GitHub badge instead of adding a placeholder to `steam-description.md`.

Introduce the badges with: `Support me on Ko-fi.`

[url=https://ko-fi.com/I7L525WMJ6][img]https://img.shields.io/badge/Support_me_on_Ko--fi-72a4f2?style=for-the-badge&logo=kofi&logoColor=white[/img][/url]
[url={repository-url}][img]https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white[/img][/url]

For a fork I maintain, introduce the badges with: `Support me on Ko-fi. This does not imply endorsement by the original authors.` Inspect the inherited license and upstream project terms, and omit the Ko-fi badge when support links or monetization are explicitly prohibited. Keep upstream attribution clear.

Do not embed scripts or replace the badges with raw widget code.

## Conditional content

Include only when supported and useful:

- Compatibility, load order, multiplayer behavior, and save safety
- Settings or setup
- Credits
- Additional reference links

Do not add empty sections or placeholder links.

## Update rules

Update an existing `steam-description.md` without discarding useful content. Preserve confirmed links, credits, compatibility notes, and formatting. Do not copy README or changelog text wholesale.

## Validation

Confirm BBCode tags are balanced, Markdown formatting is absent, required sections are present, How to Use gives actionable instructions, fork history explains both purpose and differences when applicable, badge destinations use confirmed values, links are confirmed, and compatibility and license claims match project evidence.

## Delivery

Write the result to `steam-description.md`. Return a concise summary and validation result. Do not reproduce the full description in chat unless requested.
