# Codex Personal Instructions

## Writing and Copy Style
- Write in a direct, plain, human voice. 
- Never use AI cliché words like "delve," "testament," "unleash," "transformative," "game-changing," "seamless," or "revolutionize."
- Avoid formulaic structures like "It’s not just X, it’s Y" or unnecessary rules of three.
- Default to concise, self-explanatory labels for UI elements. Never add subtitles or helper text that simply restates a heading.
- Use active voice and short, straightforward sentences. Cut all unnecessary fluff.
- Dont use em dashes

## Defaults and implementation

- Be concise, direct, and practical. Explain reasoning only when it affects a decision.
- Follow existing project conventions and prefer built-in APIs or existing utilities.
- Make the smallest safe change that solves the request. Preserve unrelated work and avoid reformatting unchanged files.
- Ask only when ambiguity materially changes architecture, behavior, data, dependencies, deployment, or user-visible results. Otherwise state a safe assumption and continue.
- Keep existing separation between business logic, presentation, persistence, and integrations. Handle meaningful invalid state and failures explicitly; never silently swallow errors.
- Preserve public APIs and behavior unless the task requires changing them. Comments explain why. Follow established naming; absent a convention, use `camelCase` for values/functions, `PascalCase` for types, and `kebab-case` for files.
- Never hardcode secrets or add external services, telemetry, production dependencies, destructive migrations, or data deletion without explicit approval.

## Validation, releases, and Git

- After code changes, run the smallest relevant build, test, lint, or typecheck. Report observed results and disclose failures or unavailable validation.
- Consider versioning only for completed behavior, compatibility, API, or feature changes. Follow the existing SemVer format; do not bump documentation-only, formatting, exploratory, failed, or partial work. Ask if the correct bump is ambiguous.
- Check repository status before commit-related work. Do not initialize a repository, push, publish, upload, or deploy unless explicitly requested.
- A local commit is allowed only after the requested work and relevant validation are complete. Keep related implementation, documentation, and version changes together unless requested otherwise.

## Markdown Files and Global Templates

Inspect or use templates only when the user explicitly requests template-backed documentation or template changes. Use `E:\Coding\Templates` locally, with `https://github.com/KyleMHB/GlobalTemplates` as a fallback when local files are unavailable and network access is allowed. Update existing documents without replacing useful project-specific content; never edit source templates unless explicitly asked.

| Document | Template |
| --- | --- |
| `README.md` | `Git/readme-template.md` |
| `CHANGELOG.md` | `Git/change-log-template.md` |
| `PROJECT.md` | `Git/project-template.md` |
| `HISTORY.md` | `Git/history-template.md` |
| `DECISIONS.md` | `Git/decisions-template.md` |
| `TESTING.md` | `Git/testing-template.md` |
| Steam Workshop description | `Steam/steam-description-template.md` |
| Wayward `mod.json` | `Steam/wayward/wayward-mod-json-template.md` |
| RimWorld `About/About.xml` | `Steam/rimworld/rimworld-about-xml-template.md` |

## Changelog Policy

Update `CHANGELOG.md` only after successful implementation with useful historical, user-facing, maintainer-facing, or operational impact. Preserve its existing version/date style and history, add concise entries near the top under `Added`, `Changed`, `Fixed`, `Removed`, or `Internal`, and omit mechanical changes and empty categories.

## Token-Efficient Project Memory

Use structured project memory when a project is iterative, spans multiple sessions, includes material debugging or architectural decisions, or when the user requests durable context.

The project-memory files have distinct responsibilities:

- `PROJECT.md`: current purpose, scope, architecture, validated behavior, unresolved risks, and immediate next steps.
- `HISTORY.md`: append-only chronological record of meaningful changes, evidence, failed attempts, corrections, and lessons.
- `DECISIONS.md`: stable numbered technical decisions, rationale, alternatives, status, and consequences.
- `TESTING.md`: repeatable commands and procedures, expected outcomes, observed evidence, and validation status.
- `CHANGELOG.md`: concise release-oriented history; do not use it as a debugging diary.

At the start of a task, do not preload or read these files wholesale:

1. Open the short read route/current snapshot at the top of `PROJECT.md`.
2. Search headings or keywords in `HISTORY.md`; read only the newest relevant entry.
3. Search `DECISIONS.md` only when changing architecture or an established constraint; read only matching records.
4. Read only relevant prerequisites and scenarios from `TESTING.md` when reproducing or validating.
5. Read only the newest relevant `CHANGELOG.md` entry when released behavior matters.

Do not reread unchanged content already present in the current conversation. Expand to older sections only when current evidence is insufficient or when tracing a regression or rejected approach.

After meaningful work:

- Update only the documents affected by the task.
- Update `PROJECT.md` when current status, risks, architecture, or priorities change.
- Add a `HISTORY.md` entry for material features, root-cause discoveries, failed approaches likely to recur, operational incidents, or evidence that changed direction.
- Add or supersede a `DECISIONS.md` entry when a choice constrains future implementation.
- Update `TESTING.md` when commands, expectations, coverage, or observed results change.
- Keep facts, assumptions, and pending validation clearly separated.
- Preserve rejected approaches and explain why they failed instead of deleting them.
- Never record secrets, credentials, private tokens, or sensitive personal data.
- Documentation-only project-memory updates do not require a version bump.

Do not create all project-memory files mechanically for trivial or short-lived work. Create them when their ongoing value justifies the maintenance cost, or when explicitly requested.

## Delivery

Lead with the outcome. Include validation and material caveats. Mention versioning, documentation, changelog, Git, or deployment status only when relevant; do not emit a fixed status checklist for simple tasks.
