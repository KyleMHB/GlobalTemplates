# Codex Project Instructions

## Operating Style

- Be concise and practical.
- Prefer built-in APIs, platform standards, and existing project patterns before custom code.
- Make the smallest safe change that solves the actual problem.
- Do not add dependencies unless they are necessary and justified.

## Code Standards

- Use clear Python standard-library code where practical.
- Keep business logic, storage, external requests, and reporting concerns separated.
- Never hardcode secrets, API keys, tokens, credentials, or sensitive environment variables.
- Do not silently swallow errors. Record per-item sync failures and report them.
- Avoid broad disk scans for game modlists; inspect documented or user-provided paths only.

## Documentation Workflow

Use `E:\Coding\Templates` as the source of truth for reusable documentation templates.

- README target: `README.md`, from `Git/readme-template.md`.
- Changelog target: `CHANGELOG.md`, from `Git/change-log-template.md`.
- Preserve existing project-specific content when updating docs.
- Do not edit global templates unless explicitly asked.

## Validation

After code changes:

- Run `python -m py_compile scripts/sync_workshop.py scripts/report_workshop.py`.
- Run the skill validator from `C:\Users\kylem\.codex\skills\.system\skill-creator\scripts\quick_validate.py`.
- If network behavior changes, test with a small controlled live sample only when network access is approved.

## Git Rules

- Do not initialize git unless explicitly confirmed.
- Do not push, publish, upload, or deploy unless explicitly instructed.
- If git exists, commit only after implementation and validation are complete.

## Release Notes

Update `CHANGELOG.md` for useful user-facing, maintainer-facing, or operational changes. Use dated headings and concise entries.
