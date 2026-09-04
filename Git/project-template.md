# Project Overview Template

## Use when

Use this template only when the user explicitly requests template-backed project memory or when an iterative project's current state materially changes. Create or update `PROJECT.md` in the project root.

## Evidence

Inspect the current snapshot and headings first. Read only documentation, metadata, and evidence relevant to the current state. Do not preload full history, decision, testing, or changelog files.

## Structure

~~~md
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
~~~

## Content rules

- Keep `Current snapshot` to a few bullets covering the milestone, strongest validation evidence, main pending evidence, and immediate action.
- Keep `Agent read route` short and identify when linked memory files matter.
- Describe architecture through ownership, data flow, boundaries, and important constraints.
- Separate facts, assumptions, and unvalidated expectations.
- Put defects, unverified fixes, and technical debt under unresolved risks.
- Make next steps ordered, concrete, and testable.
- Link to `HISTORY.md`, `DECISIONS.md`, `TESTING.md`, `CHANGELOG.md`, and roadmap files only when present.
- Keep chronological detail in `HISTORY.md`.

## Update rules

Update the existing file without replacing useful project-specific content. Create it automatically only after a material change to an iterative project's current state. Refresh the `Updated through` line after a material status change.

## Validation

Confirm every validated-behavior claim has evidence, every referenced file exists, and facts, assumptions, and pending validation remain distinct.

## Delivery

Write the result to `PROJECT.md`. Return a concise summary and validation result. Do not reproduce the full document in chat unless requested.
