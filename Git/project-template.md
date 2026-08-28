# System Instructions: Project Overview

## Role

Create or update `PROJECT.md` as the concise source of truth for the project's current state. It is an orientation document, not a chronological diary.

## Required behavior

- Inspect headings and code metadata first, then read only documentation sections relevant to the current state; do not preload whole history, decision, testing, or changelog files.
- Update an existing `PROJECT.md` instead of replacing useful content.
- State facts separately from assumptions and unvalidated expectations.
- Keep current status here; move chronological detail to `HISTORY.md`.
- Add an `Updated through` version/date line and refresh it whenever material status changes.
- Do not claim behavior is working unless evidence exists.

## Required structure

```md
# [Project] Project

Updated through: [version or milestone] on YYYY-MM-DD

## Current snapshot

## Agent read route

## Purpose

## Current scope

## Architecture

## Current validated behavior

## Unresolved validation and risks

## Immediate next steps

## Project memory
```

## Writing rules

- Describe the project at the level needed for a new maintainer or future agent session.
- Keep architecture focused on ownership, data flow, boundaries, and important constraints.
- List only evidence-backed behavior under validated status.
- Put known defects, unverified fixes, and technical debt under unresolved risks.
- Make next steps ordered, concrete, and testable.
- Link to `HISTORY.md`, `DECISIONS.md`, `TESTING.md`, `CHANGELOG.md`, and roadmap files when present.
- Keep `Current snapshot` to a few bullets covering the current version/milestone, strongest validation evidence, main pending evidence, and immediate action.
- Keep `Agent read route` short and tell future agents which current sections to read first and when linked memory files are relevant.

## File management

Write the result to `PROJECT.md` in the project root. Do not create a duplicate with a different name.
