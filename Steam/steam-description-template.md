# Steam Workshop Description Template

## Use when

Use this template only when the user explicitly requests a template-backed Steam Workshop description. Create or update `steam-description.md` in the project root.

## Evidence

Inspect the mod and user-provided notes. Use only confirmed features, game versions, dependencies, compatibility, multiplayer behavior, save safety, authors, links, and license information.

## Brief

Before drafting, write a short internal brief. Keep it out of `steam-description.md`.

- **Reader:** a player skimming the Workshop who decides from the opening lines whether to scroll on. Note what they are likely to doubt, such as balance, performance or save safety.
- **Messages:** at most three things the reader should remember. Other details belong in Features or later sections.
- **Their words:** the in-game names players see, not internal defNames or codenames.
- **Hook:** one sentence of about 15 words that says, in "you" terms, what the player's game becomes with the mod. Use no figures or version numbers.
- **No-go list:** spoilers, unconfirmed claims, and content that only appears with a DLC or option the reader may not have.

Check the finished description against the brief.

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

Steam limits a description to 8,000 characters, and BBCode tags count toward that limit. Aim for well under it so later updates have room. `preview-workshop.py` reports the length and warns when it is over.

Keep release notes out of the description. Put them in Steam's Change Notes for each update.

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
9. License
10. AI disclosure, when the author provides one
11. Links, when present

A status line, when it applies, sits above Description and is not a section. Description, Features, and How to Use must remain the first three content sections. Dependencies must appear after How to Use. Fork History, Credits, and License must remain below the player-facing sections. When present, Links must be the final section.

## Section guidance

### Status line

Add one bold line above the Description heading only when the page's status would change a player's decision to subscribe:

- **Fork or continuation:** name the original mod with a link and its author, state the supported game versions, and say where to report problems so players do not contact the original author.
- **Obsolete or superseded:** say what replaced the mod, such as a base-game update or another mod, and link the replacement when one exists.
- **Discontinued or up for adoption:** say that updates have stopped and the last supported game version.

Keep it to one or two sentences. Leave the detail to Fork History or Description. Omit the line for an actively maintained original mod.

```text
[b]Unofficial continuation of [url={original-url}]{original-name}[/url] by {original-author} for RimWorld {game-versions}. Please report problems here, not to the original author.[/b]
```

Use confirmed values only. If a value cannot be confirmed, leave that clause out instead of adding a placeholder.

### Description

State what the mod changes and how that affects the player. Keep the summary concise and evidence-based.

Open with the brief's hook so the player benefit comes first. Lore, background or a fair statement of a likely doubt can follow it. When a likely doubt matters, state it the way the reader would, then answer it with mechanics.

Keep the Description to the brief's messages. Limit any list here to about five items. Move longer supporting lists, such as balance details, into Features as their own subsection, so the version declaration and Features stay near the top.

After the summary, include one small version declaration within the Description section:

```text
[b]Mod version:[/b] {mod-version}
```

Replace `{mod-version}` with the mod release version from authoritative project release metadata for the artifact being published, such as `mod.json.version` for Wayward. Preserve the complete version, including any prerelease suffix. Keep supported game versions separately labeled.

Refresh this declaration whenever the release version changes, and keep exactly one `Mod version` line. If the mod version cannot be established from authoritative evidence, omit the declaration and report the missing evidence; never leave a placeholder or infer the mod version from a game version or update date.

### Features

Use a scannable BBCode list of confirmed player-facing features. Pair each claim with the mechanic or number that supports it.

### How to Use

Explain how players enable, configure, and use the mod in-game. Include relevant menus, controls, hotkeys, setup steps, or automatic behavior. Keep the instructions concise and evidence-based.

### Settings and Configuration

Include this section only when settings change player-visible behavior. State where players find each documented setting and what it changes.

### Requirements and Dependencies

Include only when the mod requires a game expansion, framework, library, companion mod, or special setup. Keep this section below How to Use even when the dependency is mandatory.

State whether each expansion is required or only adds optional content. Also link every required Workshop item in the item's Required Items sidebar, because mod managers and Workshop indexers read that list rather than the description.

### Compatibility, Load Order, Multiplayer, and Save Safety

Include only details confirmed by project evidence. Cover any confirmed load-order requirements, conflicts, multiplayer behavior, and effects of adding or removing the mod from an existing save.

Answer the questions players ask most often, when the evidence supports an answer:

- Can it be added to an existing save, and does anything need doing afterwards, such as allowing new items in stockpile or bill filters?
- Can it be removed from an existing save, and what breaks if it is?
- For RimWorld, does it work with Combat Extended: patched in the mod, handled elsewhere, or not relevant because it does not touch combat?
- Does it work in multiplayer?

Leave a question out when its answer is unknown rather than guessing.

### Fork History

For a fork, name the original mod and author, explain why the fork exists, and describe the meaningful differences from the upstream mod. Omit this section for original mods.

### Credits

Credit confirmed third-party contributors and upstream projects, preserving required license attribution. Omit self-credit for the page owner and credits for tools or vendors, including OpenAI. Keep production-tool provenance in internal artwork records rather than the public Workshop description.

### License

For a fork, state that it inherits the original mod's license. Do not relicense it without authorization from the relevant copyright holders.

For an original mod, use its existing confirmed license. If no license can be confirmed, report the gap instead of inventing one.

For an original GPLv3 mod, state that commercial use is allowed and distributed modified versions must remain under GPLv3 with corresponding source available as required by the license. Do not claim GPLv3 unless the repository contains the official GPLv3 text or adding it is part of the request.

### AI disclosure

When the author profile named in the user's or project's agent instructions has an `ai-disclosure`, add its BBCode block immediately before Links, or last when Links is absent. Copy it verbatim. Omit the section when no profile is named or it has no disclosure. Never use a profile that was not named. This is an author disclosure, separate from tool credits and internal production records.

### Links

For mods the author owns or maintains, include these linked badges in the Links section. Replace `{repository-url}` with the confirmed project repository URL. If no repository URL is confirmed, omit the GitHub badge instead of adding a placeholder to `steam-description.md`.

Replace `{kofi-url}` with the `kofi-url` from the author profile named in the user's or project's agent instructions; when none is set, omit the Ko-fi badge and its introduction. Introduce the badges with: `Support me on Ko-fi.`

[url={kofi-url}][img]https://img.shields.io/badge/Support_me_on_Ko--fi-72a4f2?style=for-the-badge&logo=kofi&logoColor=white[/img][/url]
[url={repository-url}][img]https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white[/img][/url]

For a fork the author maintains, introduce the badges with: `Support me on Ko-fi. This does not imply endorsement by the original authors.` Inspect the inherited license and upstream project terms, and omit the Ko-fi badge when support links or monetization are explicitly prohibited. Keep upstream attribution clear.

Do not embed scripts or replace the badges with raw widget code.

When the project has a confirmed place for bug reports, such as GitHub Issues or a pinned Workshop discussion, link it here and say what to include. For RimWorld, ask for the game's `Player.log` file and the mod list or load order.

## Applicability

Description, Features, How to Use, and License are required. Settings and Configuration, Requirements and Dependencies, Compatibility, Load Order, Multiplayer, and Save Safety, and Credits are conditional. Fork History is required only for forks. The status line is required for forks and for obsolete or discontinued mods. AI disclosure is included only when the author provides one. Links is conditional. Include it only when at least one confirmed and permitted link remains, and put all additional reference links there. Do not add empty sections or placeholder links.

## Update rules

Update an existing `steam-description.md` without discarding useful content. Preserve confirmed links, credits, compatibility notes, and formatting. Do not copy README or changelog text wholesale.

## Author voice and image text

Describe media positively and accurately, such as an illustrated motion preview. Omit stock disclaimers such as "it is not recorded gameplay" from public Workshop copy. Keep capture and verification notes in internal records; label illustrations accurately rather than claiming they are gameplay captures.

Write as the mod's owner. Use first person when describing personal work or decisions; describe the mod directly elsewhere. Omit third-person references to the owner's name and self-credit. Preserve required third-party attribution.

Make each section readable on its own, because players jump between sections. Name the thing instead of pointing to it with "below", "above" or "as mentioned earlier".

Keep headings to a short noun phrase of about 40 characters or fewer.

Use native Steam BBCode for section headings, group introductions and explanatory notes. When the page is illustrated, follow `workshop-page-guide.md` for image composition and preview checks.

## Public copy

Run the installed `unslop` skill on all reader-facing prose after drafting and before delivery. Preserve facts, names, identifiers, links, image URLs, and BBCode structure.

If `unslop` is unavailable, apply the rules in `writing-copy.md` manually and state in the delivery summary that `unslop` was unavailable.

Whichever route you take, also remove these patterns:

- Softeners: really, just, simply, actually, genuinely, honestly, truly.
- Exclamation marks and hype superlatives such as "best" or "ultimate".
- Emphasis crutches such as "Full stop" or "Let that sink in".
- A neat moral or summary line at the end of every section. Stop when the point is made.

Then score the draft from 1 to 10 for directness, rhythm, trust in the reader, sounding like a specific author, and density. Revise any draft that scores below 35 out of 50. Keep the score out of the description and the delivery summary.

## Validation

Confirm BBCode tags are balanced, Markdown formatting is absent, the description is within Steam's 8,000-character limit and contains no release notes, required sections are present, the reader-first order is preserved, the Description opens with the hook and covers no more than the brief's messages, How to Use gives actionable instructions, dependencies follow How to Use, a fork, obsolete, or discontinued mod opens with one status line above Description, fork history explains both purpose and differences when applicable, Links is last, badge destinations use confirmed values, links are confirmed, and compatibility and license claims match project evidence.

When a mod release version is available, confirm that exactly one Mod version declaration appears in Description, its value matches the authoritative release metadata, and no version placeholder remains. Otherwise, confirm that the delivery reports the missing version evidence.

## Delivery

Write the result to `steam-description.md`. Return a concise summary and validation result. Do not reproduce the full description in chat unless requested.
