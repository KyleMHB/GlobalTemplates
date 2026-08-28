# System Instructions: Repeatable Testing Guide

## Role

Create or update `TESTING.md` with repeatable validation procedures, expected outcomes, current evidence, and a durable result-recording format.

## Required behavior

- Prefer commands and steps another person can reproduce without chat context.
- Before updating, list test headings and read only prerequisites plus scenarios affected by the task.
- Separate expected behavior from observed behavior.
- Mark tests as Passed, Failed, Blocked, Pending, or Partially passed.
- Include environment, version, configuration differences, and required permissions where relevant.
- Never convert an unrun test into a pass because the code compiles.
- Keep destructive, production, billing, or externally visible tests clearly labeled and approval-gated.

## Recommended structure

```md
# [Project] Testing

Updated through: [version or milestone] on YYYY-MM-DD

## Agent read route

## Test prerequisites

## Fast smoke test

## [Feature or risk] test

## Lifecycle test

## Performance and soak test

## Result recording
```

Each test should contain:

- Preconditions.
- Exact commands or actions.
- Expected result.
- Current status.
- Known caveats or cleanup steps.

Keep `Agent read route` compact: provide the heading-search command, identify the smoke test, and map major feature areas to their scenario headings.

## Result entry format

```md
## YYYY-MM-DD — [Test name]

- Version/environment:
- Configuration differences:
- Actions:
- Expected:
- Observed:
- Evidence:
- Status: Passed | Failed | Blocked | Pending | Partially passed
- Follow-up:
```

## File management

Write the result to `TESTING.md` in the project root. Update existing procedures when behavior changes and preserve useful historical result entries.
