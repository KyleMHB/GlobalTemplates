# Testing Guide Template

## Use when

Use this template only when the user explicitly requests template-backed testing documentation or repeatable validation procedures materially change. Create or update `TESTING.md` in the project root.

## Read route

List test headings and read only prerequisites and scenarios affected by the task. Keep `Agent read route` compact with a heading-search command, the smoke test, and major feature-to-scenario mappings.

## Recommended structure

~~~md
# [Project] Testing

Updated through: [version or milestone] on YYYY-MM-DD

## Agent read route

## Test prerequisites

## Fast smoke test

## [Feature or risk] test

## Lifecycle test

## Performance and soak test

## Result recording
~~~

Include only applicable scenarios. Each procedure should state preconditions, exact commands or actions, expected result, current status, caveats, and cleanup.

## Result format

~~~md
## YYYY-MM-DD - [Test name]

- Version/environment:
- Configuration differences:
- Actions:
- Expected:
- Observed:
- Evidence:
- Status: Passed | Failed | Blocked | Pending | Partially passed
- Follow-up:
~~~

## Update and validation

- Separate expected and observed behavior.
- Never mark an unrun test as passed because code compiles.
- Record environment, configuration, permissions, and version differences when relevant.
- Label destructive, production, billing, and externally visible tests as approval-gated.
- Update changed procedures while preserving useful historical results.
- Confirm commands are reproducible and statuses match recorded evidence.

## Delivery

Write the result to `TESTING.md`. Return a concise summary and validation result. Do not reproduce the full document in chat unless requested.
