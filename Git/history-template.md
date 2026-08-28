# System Instructions: Engineering History

## Role

Create or update `HISTORY.md` as an append-only engineering record of meaningful implementation work, failures, evidence, corrections, and lessons.

## Required behavior

- Add newest entries near the top.
- Before updating, list entry headings and read only the newest entries relevant to the task; do not scan the file from top to bottom.
- Preserve failed attempts and mark them superseded; do not silently erase them.
- Separate observed evidence from assumptions and conclusions.
- Record why a change was made, not every command used to make it.
- Include exact errors or log evidence only when they materially help future diagnosis.
- Cross-reference decisions or tests when useful.
- Keep a short `Agent read route` below the introduction with a heading-search command and a compact list of recent topics.

## Entry structure

Use only the subsections relevant to the entry:

```md
## YYYY-MM-DD — [Version or milestone]: [Short title]

### Problem

### Evidence

### Decision or change

### Result

### Remaining issues

### Lesson
```

For a rejected experiment, use:

```md
### Attempt

### Why it was rejected
```

## Inclusion rules

Record:

- Significant features and behavior changes.
- Root causes of important defects.
- Compatibility discoveries.
- Failed approaches likely to be retried accidentally.
- Test evidence that changed the implementation direction.
- Operational incidents and recovery lessons.

Do not record:

- Routine file reads or commands.
- Pure formatting changes.
- Unsupported speculation presented as fact.
- Secrets, credentials, private tokens, or sensitive personal data.

## File management

Write the result to `HISTORY.md` in the project root. Preserve prior history unless correcting a factual error or duplicate.
