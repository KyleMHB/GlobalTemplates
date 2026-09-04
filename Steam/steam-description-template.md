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

## Default section order

Use this reader-first order and omit only the sections marked as conditional:

1. Description
2. Features
3. How to Use
4. Settings and Configuration, when applicable
5. Requirements and Dependencies, when applicable
6. Compatibility, Load Order, Multiplayer, and Save Safety, when applicable
7. Fork History, required for forks
8. Credits, when applicable
9. License and Forking Policy
10. Links, when present

Description, Features, and How to Use must remain the first three content sections. Dependencies must appear after How to Use. Fork History, Credits, and License and Forking Policy must remain below the player-facing sections. When present, Links must be the final section.

## Section guidance

### Description

Use a clear hook and concise summary of what the mod changes and why it is useful.

### Features

Use a scannable BBCode list of confirmed player-facing features.

### How to Use

Explain how players enable, configure, and use the mod in-game. Include relevant menus, controls, hotkeys, setup steps, or automatic behavior. Keep the instructions concise and evidence-based.

### Settings and Configuration

Include only when players can configure meaningful behavior. Explain where settings are found and what the important options change.

### Requirements and Dependencies

Include only when the mod requires a game expansion, framework, library, companion mod, or special setup. Keep this section below How to Use even when the dependency is mandatory.

### Compatibility, Load Order, Multiplayer, and Save Safety

Include only confirmed and useful compatibility information. Cover required load order, known conflicts, multiplayer behavior, and whether the mod is safe to add or remove from existing saves when applicable.

### Fork History

For a fork, name the original mod and author, explain why the fork exists, and describe the meaningful differences from the upstream mod. Omit this section for original mods.

### Credits

Include confirmed authors, contributors, asset creators, and upstream projects when credit is useful. Keep detailed provenance below the player-facing sections.

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

## Applicability

Description, Features, How to Use, and License and Forking Policy are required. Settings and Configuration, Requirements and Dependencies, Compatibility, Load Order, Multiplayer, and Save Safety, Credits, and Links are conditional. Fork History is required only for forks. Links is conditional. Include it only when at least one confirmed and permitted link remains, and put all additional reference links there. Do not add empty sections or placeholder links.

## Update rules

Update an existing `steam-description.md` without discarding useful content. Preserve confirmed links, credits, compatibility notes, and formatting. Do not copy README or changelog text wholesale.

## Validation

Confirm BBCode tags are balanced, Markdown formatting is absent, required sections are present, the reader-first order is preserved, How to Use gives actionable instructions, dependencies follow How to Use, fork history explains both purpose and differences when applicable, Links is last, badge destinations use confirmed values, links are confirmed, and compatibility and license claims match project evidence.

## Delivery

Write the result to `steam-description.md`. Return a concise summary and validation result. Do not reproduce the full description in chat unless requested.
