# System Instructions: Technical Decision Log

## Role

Create or update `DECISIONS.md` as a lightweight architectural decision record for choices that constrain future work.

## Required behavior

- Assign stable sequential identifiers such as `D-001`.
- Before updating, list decision headings and search for the affected topic; read only matching records.
- Preserve old decisions.
- Change status to `Superseded` when a later decision replaces one, and link both records.
- Record alternatives only when they clarify the trade-off.
- Keep decisions short enough to scan but specific enough to guide implementation.
- Keep a short `Agent read route` below the introduction that tells future agents to search headings and maps major topics to relevant IDs.

## Decision structure

```md
## D-001 — [Decision title]

- Status: Proposed | Accepted | Superseded | Rejected
- Date: YYYY-MM-DD
- Supersedes: [optional decision ID]

### Context

### Decision

### Reason

### Alternatives considered

### Consequences
```

Use only relevant subsections, but always include status, date, decision, reason, and consequences.

## Inclusion rules

Create a decision record when a choice affects architecture, compatibility, data ownership, persistence, security, dependencies, public APIs, deployment, or long-term maintenance.

Do not create decision records for trivial edits or choices already dictated by an established project convention.

## File management

Write the result to `DECISIONS.md` in the project root. Never renumber existing decisions.
