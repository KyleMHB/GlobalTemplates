# Codex Personal Instructions

## Writing and copy

- Write in a direct, plain, human voice with active sentences and concise labels.
- Avoid AI cliché words such as "delve," "testament," "unleash," "transformative," "game-changing," "seamless," and "revolutionize."
- Avoid formulaic contrasts, unnecessary rules of three, redundant subtitles, helper text that repeats headings, and em dashes.

## Implementation

- Follow existing project conventions and prefer built-in APIs or existing utilities.
- Make the smallest safe change that solves the request. Preserve unrelated work and avoid reformatting unchanged files.
- Ask only when ambiguity materially changes architecture, behavior, data, dependencies, deployment, or user-visible results. Otherwise state a safe assumption and continue.
- Keep business logic, presentation, persistence, and integrations separated. Handle meaningful invalid state and failures explicitly.
- Preserve public APIs and behavior unless the task requires changing them. Comments explain why. Follow established naming; absent a convention, use `camelCase` for values and functions, `PascalCase` for types, and `kebab-case` for files.
- Never hardcode secrets or add external services, telemetry, production dependencies, destructive migrations, or data deletion without explicit approval.

## Validation, versions, and Git

- After code changes, run the smallest relevant build, test, lint, or typecheck. Report observed results and unavailable validation.
- Change versions only for completed behavior, compatibility, API, or feature changes. Follow the existing SemVer format and ask when the correct bump is ambiguous.
- Check repository status before commit-related work. One coherent local commit may follow successful relevant validation when the user has not prohibited commits and no unrelated changes would be included.
- Never initialize a repository, push, publish, upload, or deploy unless explicitly requested.

## Template routing

Use `E:\Coding\Templates` locally, with `https://github.com/KyleMHB/GlobalTemplates` as a fallback when local files are unavailable and network access is allowed. Update existing documents without replacing useful project-specific content. Edit source templates only when explicitly requested.

Ordinary templates are explicit opt-in. Project-memory and changelog templates may be inspected and applied automatically only when the matching trigger below is satisfied.

| Target | Template | Activation | Public copy |
| --- | --- | --- | --- |
| `README.md` | `Git/readme-template.md` | Explicit template-backed request | Yes |
| `CHANGELOG.md` | `Git/change-log-template.md` | Explicit request, or a completed change with useful user, maintainer, or operational impact | Yes |
| `PROJECT.md` | `Git/project-template.md` | Explicit request, or a material change to an iterative project's current state | No |
| `HISTORY.md` | `Git/history-template.md` | Explicit request, or durable implementation evidence, root causes, rejected approaches, incidents, or lessons | No |
| `DECISIONS.md` | `Git/decisions-template.md` | Explicit request, or a choice that constrains future technical work | No |
| `TESTING.md` | `Git/testing-template.md` | Explicit request, or a material change to repeatable procedures, expectations, or evidence | No |
| `steam-description.md` | `Steam/steam-description-template.md` | Explicit template-backed request | Yes |
| `mod.json` | `Steam/wayward/wayward-mod-json-template.md` | Explicit template-backed request | Yes |
| `About/About.xml` | `Steam/rimworld/rimworld-about-xml-template.md` | Explicit template-backed request | Yes |

For each template marked as public copy, run the installed `unslop` skill with its default crisp-human preset on reader-facing prose before delivery. Follow its core preservation and validation gates; a blocking result means the document is incomplete. Preserve facts, names, identifiers, commands, links, code, markup, and data structure. In `mod.json`, process only `name` and `description`; in `About/About.xml`, process only `<name>` and `<description>`. If `unslop` or its validation scripts are unavailable, apply the Writing and copy rules manually and state in the delivery summary that automated Unslop validation was unavailable.

Create or update only the triggered documents. Keep facts, assumptions, and pending validation distinct. Preserve prior history, rejected approaches, stable decisions, and useful project-specific content. Never record secrets, credentials, private tokens, or sensitive personal data.

## Delivery

Lead with the outcome. Include validation and material caveats. Mention versioning, documentation, changelog, Git, or deployment status only when relevant.
