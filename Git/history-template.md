# Engineering History Template

## Use when

Use this template only when the user explicitly requests template-backed engineering history or meaningful implementation evidence should be preserved across sessions. Create or update `HISTORY.md` in the project root.

## Read route

List entry headings and read only the newest entries relevant to the task. Keep a short `Agent read route` below the introduction with a heading-search command and recent topic names.

## Entry structure

Use only relevant subsections:

~~~md
## YYYY-MM-DD - [Version or milestone]: [Short title]

### Problem

### Evidence

### Decision or change

### Result

### Remaining issues

### Lesson
~~~

For rejected work, use `Attempt` and `Why it was rejected`.

## Inclusion rules

Record:

- Significant features and behavior changes.
- Root causes of important defects.
- Compatibility discoveries.
- Failed approaches likely to be repeated.
- Test evidence that changed implementation direction.
- Operational incidents and recovery lessons.

Do not record routine commands, formatting changes, unsupported speculation, secrets, credentials, private tokens, or sensitive personal data.

## Update and validation

Add newest entries near the top. Preserve prior entries and failed attempts; mark superseded information instead of deleting it. Separate observations, assumptions, and conclusions. Confirm dates, versions, errors, and cross-references against available evidence.

## Delivery

Write the result to `HISTORY.md`. Return a concise summary and validation result. Do not reproduce the full document in chat unless requested.
