# Codex Personal Instructions

## Writing and Copy for User Facing Documents

- Write in a direct, plain, human voice with active sentences and concise labels.
- Avoid AI cliché words such as "delve," "testament," "unleash," "transformative," "game-changing," "seamless," and "revolutionize."
- Avoid formulaic contrasts, unnecessary rules of three, redundant subtitles, helper text that repeats headings, and em dashes.
- Use the `unslop` skill (for `README.md`, `CHANGELOG.md` and `steam-description.md`) with its default crisp-human preset on reader-facing prose before delivery. Follow its core preservation and validation gates; a blocking result means the document is incomplete. Preserve facts, names, identifiers, commands, links, code, markup, and data structure. In `mod.json`, process only `name` and `description`; in `About/About.xml`, process only `<name>` and `<description>`. If `unslop` or its validation scripts are unavailable, apply the Writing and copy rules manually and state in the delivery summary that automated Unslop validation was unavailable.

## Implementation

- Follow existing project conventions and prefer built-in APIs or existing utilities.
- Keep business logic, presentation, persistence, and integrations separated. Handle meaningful invalid state and failures explicitly.
- Preserve public APIs and behavior unless the task requires changing them. Comments explain why. Follow established naming; absent a convention, use `camelCase` for values and functions, `PascalCase` for types, and `kebab-case` for files.
- Never hardcode secrets or add external services, telemetry, production dependencies, destructive migrations, or data deletion without explicit approval.

## Template routing

Use `E:\Coding\Templates` locally, with `https://github.com/KyleMHB/GlobalTemplates` as a fallback when local files are unavailable and network access is allowed. Update existing documents without replacing useful project-specific content. Edit source templates only when explicitly requested.

Ordinary templates are explicit opt-in. A changelog template may be inspected and applied automatically only when the matching trigger below is satisfied. An existing `TESTING.md` may be updated automatically when its procedures, expectations, or evidence materially change; creating one requires an explicit request.

| Target | Template | Activation | Public copy |
| --- | --- | --- | --- |
| `README.md` | `Git/readme-template.md` | Explicit template-backed request | Yes |
| `CHANGELOG.md` | `Git/change-log-template.md` | Explicit request, or a completed change with useful user, maintainer, or operational impact | Yes |
| `TESTING.md` | `Git/testing-template.md` | Explicit request to create, or material changes to an existing file's procedures, expectations, or evidence | No |
| `steam-description.md` | `Steam/steam-description-template.md` | Explicit template-backed request | Yes |
| `mod.json` | `Steam/wayward/wayward-mod-json-template.md` | Explicit template-backed request | Yes |
| `About/About.xml` | `Steam/rimworld/rimworld-about-xml-template.md` | Explicit template-backed request | Yes |

## Delivery

Lead with the outcome. Include validation and material caveats. Mention versioning, documentation, changelog, Git, or deployment status only when relevant.
