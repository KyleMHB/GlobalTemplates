# Codex Personal Instructions

## Operating Style

- Be concise. No pleasantries, filler, or unnecessary narration.
- Prefer direct answers, clear assumptions, and practical implementation.
- Explain logic briefly only when it affects design, trade-offs, or user decisions.
- Use built-in APIs, platform standards, and existing project patterns before custom code.
- Make the smallest safe change that solves the actual problem.

## Planning and Clarification

Before writing or modifying code, make sure the intent, constraints, and success criteria are clear.

Ask clarifying questions before implementation when:
- Requirements are ambiguous or multiple valid approaches exist.
- The change affects architecture, data models, APIs, auth, state, deployment, or user-facing behavior.
- The task may require destructive changes, migrations, new dependencies, or production deployment.
- Existing project conventions conflict with the request.
- The intended solution cannot be explained clearly.

Ask about:
- Success criteria.
- The core problem being solved.
- Intended logic and behavior.
- Inputs, outputs, and edge cases.
- What should be avoided.
- Whether failures should throw, recover gracefully, or return a fallback.

If uncertainty is minor and the safe path is obvious, state the assumption and continue.

## Code Standards

- Maintainability: prefer existing utilities, native APIs, and official standards.
- Readability: prefer clear code over clever one-liners.
- DRY/SOLID: use small, focused, single-responsibility functions.
- Architecture: separate business logic, UI/presentation, persistence, and external integrations.
- Error handling: never silently swallow errors. Log, throw, or surface exceptions appropriately.
- Robustness: handle edge cases, null/undefined values, invalid inputs, async races, retries, and partial failures.
- State: do not introduce hidden global state or mutate shared state unexpectedly.
- Security: never hardcode secrets, API keys, tokens, credentials, or sensitive environment variables.
- Data safety: do not delete, overwrite, migrate, or destructively modify data without explicit approval.

## Naming and Comments

Follow existing project conventions first. Use these defaults only when no convention exists:

- `camelCase` for variables and functions.
- `PascalCase` for classes, types, interfaces, and components.
- `kebab-case` for file names.
- Comments should explain WHY, not WHAT.

## Editing and Refactoring

- Make targeted edits only.
- Do not rewrite unrelated code.
- Do not reformat unchanged files.
- Preserve existing file structure, public APIs, and behavior unless the task requires changing them.
- Do not remove existing functionality unless asked.
- Do not add abstractions unless they reduce real duplication or improve clarity.
- In the final response, summarize meaningful changes instead of pasting entire files.

## Dependencies and External APIs

- Do not add new production dependencies unless necessary.
- Prefer existing dependencies and native APIs first.
- If a new dependency is justified, explain why briefly.
- Do not introduce external services, network calls, telemetry, tracking, or data sharing without explicit approval.

## Build, Test, and Validation

After code changes:
- Run the most relevant build, lint, typecheck, or test command available.
- If no validation command exists, inspect project scripts/config and state that no obvious command was found.
- Report validation results based strictly on facts.
- Do not claim success unless the command actually passed.
- If validation fails, explain the failure and likely cause.

## Versioning and Releases

After successful implementation and validation, determine whether the completed change is release-worthy.

A change is release-worthy when it:
- Adds features or capabilities.
- Fixes bugs.
- Changes behavior, compatibility, public APIs, or user-facing functionality.
- Updates functionality that should be reflected in a published app/mod version.

Do not bump versions for:
- Docs-only changes.
- Formatting-only changes.
- Typo fixes.
- Failed or partial tasks.
- Exploratory work.
- Purely mechanical changes with no useful release value.

When a version bump is needed:
- Use Semantic Versioning where the project already uses SemVer.
- Use MAJOR for breaking changes.
- Use MINOR for new features or meaningful behavior additions.
- Use PATCH for bug fixes, compatibility fixes, refactors, and internal improvements.
- Preserve the project’s existing version format, such as `1.2.3` or `v1.2.3`.
- Update all existing recognized version fields in relevant project files.
- Do not create new manifest files or invent version fields unless explicitly asked.
- If the correct version bump is ambiguous, ask before changing versions.

Common version files to check when present:
- `package.json`
- `manifest.json`
- `About.xml`
- `package.xml`
- Any existing project-specific config or metadata file containing the current version.

Do not push, publish, upload, or deploy after a version bump unless explicitly instructed.

## Git Rules

- Check whether the current folder is a git repository before commit-related work.
- If it is not a git repository, do not run `git init` automatically.
- Ask for the project name and confirmation before initialising git.
- Do not push, publish, upload, or deploy unless explicitly instructed.
- Local commits are allowed after successful validated tasks when in a git repository, unless explicitly told not to commit.
- Only commit after:
  - The requested change is complete.
  - Relevant validation has passed, or failures are clearly reported.
  - Required markdown/template updates are complete when applicable.
  - Versioning has been considered and applied when needed.
- Commit functional changes, markdown updates, and version updates together unless explicitly asked to create a separate release commit.
- For explicit release or publish tasks, the version bump and changelog release entry may be committed separately.
- Use concise conventional commit messages.
- Example: `fix: prevent duplicate checkout submissions`
- Example release commit: `chore: bump version to 1.2.3`

## Markdown Files and Global Templates

Use the GlobalTemplates repository as the source of truth for reusable markdown templates:
- Repository: `https://github.com/KyleMHB/GlobalTemplates`
- Preferred local clone: `E:\Coding\Templates\GlobalTemplates`
- Fallback local path: `E:\Coding\Templates`

When creating or updating markdown documentation:
- Read and follow the relevant template instructions before writing the target file.
- Prefer the local template path when accessible.
- If local templates are unavailable, use the raw GitHub template URL when network access is available.
- If neither local nor remote templates are accessible, report that clearly and use the safest fallback structure only when appropriate.
- Do not edit global templates unless explicitly asked. Use them as source templates only.
- If the target markdown file already exists in the repo, update it instead of creating a duplicate.
- Do not overwrite useful project-specific content or markdown history unless explicitly asked.

Template mappings:
- README:
  - Target file: `README.md`
  - Template path: `Git/readme-template.md`
  - Remote fallback: `https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/Git/readme-template.md`
- Changelog:
  - Target file: `CHANGELOG.md`
  - Template path: `Git/change-log-template.md`
  - Remote fallback: `https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/Git/change-log-template.md`
- Steam Workshop description:
  - Target file: follow the filename required by the template.
  - Template path: `Steam/steam-description-template.md`
  - Remote fallback: `https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/Steam/steam-description-template.md`
- Wayward mod metadata:
  - Target file: `mod.json`
  - Template path: `Steam/wayward/wayward-mod-json-template.md`
  - Remote fallback: `https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/Steam/wayward/wayward-mod-json-template.md`
- RimWorld mod metadata:
  - Target file: `About/About.xml`
  - Template path: `Steam/rimworld/rimworld-about-xml-template.md`
  - Remote fallback: `https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/Steam/rimworld/rimworld-about-xml-template.md`

## Changelog Policy

After successful implementation and validation, check for `CHANGELOG.md`.

Use `change-log-template.md` from the GlobalTemplates repository when accessible.

The changelog must be a dated history of completed changes, with newest changes near the top.

Preferred heading format when a version bump is applied:
- `## VERSION - YYYY-MM-DD`
- Example: `## 1.2.3 - 2026-05-02`

If no version bump is needed, use a date-only heading:
- `## YYYY-MM-DD`

Rules:
- Update the existing `CHANGELOG.md` instead of creating a duplicate.
- If no `CHANGELOG.md` exists, create one from `changeLogTemplate.md`.
- Use the current local date in `YYYY-MM-DD` format.
- Add a new version/date or date-only section near the top.
- Append entries under the correct category.
- Preserve previous changelog history.
- Do not rewrite old entries unless fixing an obvious error or duplicate.
- Omit empty categories.
- Write concise entries focused on user-facing, maintainer-facing, or operational impact.
- Do not include commit hashes unless requested.
- Do not mention tests unless the change itself is test-related.
- Omit purely mechanical changes with no useful historical value.

Standard categories:
- `Added` for new features or capabilities.
- `Changed` for behavior, UX, API, workflow, or configuration changes.
- `Fixed` for bug fixes.
- `Removed` for deleted behavior, files, features, or APIs.
- `Internal` for refactors, dependency updates, build tooling, or non-user-facing work.

## Final Response Format

When finished, respond with:
- What changed.
- Why, briefly.
- Validation performed and result.
- Versioning status.
- Markdown/template status.
- Changelog status.
- Git status.
- Deploy/publish/upload status.
