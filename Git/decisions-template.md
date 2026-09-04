# Technical Decision Log Template

## Use when

Use this template only when the user explicitly requests template-backed decisions or a choice constrains architecture, compatibility, data ownership, persistence, security, dependencies, public APIs, deployment, or long-term maintenance. Create or update `DECISIONS.md` in the project root.

## Evidence

List decision headings and search for the affected topic. Read only matching records. Keep a short `Agent read route` below the introduction that maps major topics to decision IDs.

## Decision structure

~~~md
## D-001 - [Decision title]

- Status: Proposed | Accepted | Superseded | Rejected
- Date: YYYY-MM-DD
- Supersedes: [optional decision ID]

### Context

### Decision

### Reason

### Alternatives considered

### Consequences
~~~

Always include status, date, decision, reason, and consequences. Include other subsections only when they clarify the choice.

## Update rules

- Assign stable sequential IDs and never renumber existing decisions.
- Preserve old decisions.
- When a later decision replaces one, mark the old record `Superseded` and link both records.
- Do not create records for trivial edits or choices already fixed by project convention.

Create the file automatically only when a choice constrains future technical work.

## Validation

Confirm IDs are unique, references resolve, and the recorded status matches the evidence.

## Delivery

Write the result to `DECISIONS.md`. Return a concise summary and validation result. Do not reproduce the full document in chat unless requested.
