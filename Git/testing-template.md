# Testing Guide Template

## Use when

Use this template when the user explicitly requests template-backed testing documentation, or when an existing `TESTING.md` has procedures, expectations, or evidence that materially change. Create `TESTING.md` in the project root only on explicit request.

## Evidence

List test headings and read only prerequisites and scenarios affected by the task. Keep `Agent read route` compact with a heading-search command, a pointer to the test tiers table, and major feature-to-scenario mappings.

For RimWorld test-case or harness changes, follow the testing branch of the [RimWorld agent read route](../Steam/rimworld/agent-guide.md). It locates the shared harness and searchable setup recipes.

## Recommended structure

~~~md
# [Project] Testing

Updated through: [version or milestone] on YYYY-MM-DD

## Agent read route

## Test prerequisites

## Test tiers

## [Feature or risk] test

## Lifecycle test

## Performance and soak test

## Result recording
~~~

`Test tiers` maps each kind of change to what it runs, so an agent picks checks without reading every scenario. Size the tiers by what the suite costs to run:

~~~md
| Tier | When | Runs |
| --- | --- | --- |
| Quick | Every code change, each ticket and fix-up | Unit tests, plus the batches or scenarios that cover the changed area. When the whole suite takes a minute or two, Quick can be the whole suite. |
| Visual | Art or drawing changes | Screenshots or clips narrowed to what changed |
| Full | Seams: a feature branch merging to main, a dependency or game update, a release | The whole suite, plus every variant it leaves out (other mod sets, optional integrations), each under its own configuration |

| Area (source folder or feature) | Covering batches or scenarios |
| --- | --- |
~~~

Every scenario or batch belongs to a tier. One that no tier runs never runs.

Include only applicable scenarios. A RimWorld mod always includes a performance test: the harness `perf` batch (`run perf --mods perf`) with its recorded ms/tick, which release requires, and the mod's `perf.*` cases with each path's scale, budget and measured cost. Each procedure should state preconditions, exact commands or actions, expected result, current status, caveats, and cleanup.

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

## Update rules

- Separate expected and observed behavior.
- Never mark an unrun test as passed because code compiles.
- Count only behaviour checks as passes. Report evidence-only cases (a screenshot was written), skips and variants not run separately, as evidence or as not covered.
- Keep a list of what the tests do not cover. Include any passing check that is narrower than its name suggests, and say what it would miss.
- Date any case count or run time written into instructions, or name where it is measured.
- Record environment, configuration, permissions, and version differences when relevant.
- Label destructive, production, billing, and externally visible tests as approval-gated.
- Update changed procedures while preserving useful historical results.

## Validation

Confirm commands are reproducible and statuses match recorded evidence.

## Delivery

Write the result to `TESTING.md`. Return a concise summary and validation result. Do not reproduce the full document in chat unless requested.
