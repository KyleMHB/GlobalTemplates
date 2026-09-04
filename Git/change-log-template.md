# Changelog Template

## Use when

Use this template only when the user explicitly requests template-backed changelog work or an approved completed change requires a useful historical entry. Create or update `CHANGELOG.md` in the project root.

## Evidence

Read only the newest relevant release or date section and inspect the completed changes. Record validated outcomes, not plans or unsupported claims.

## Structure

Keep `# Changelog` as the document title. Add a short read route below it:

> Agent read route: read only the newest relevant release; locate older versions by searching `^## ` headings.

Preserve the existing heading style, including version and date conventions. For a new changelog, use:

~~~md
# Changelog

Agent read route: read only the newest relevant release; locate older versions by searching `^## ` headings.

## YYYY-MM-DD
~~~

Add the newest section near the top. If the relevant section already exists, add entries to it instead of creating a duplicate.

Use only categories with entries:

- `Added` for new capabilities.
- `Changed` for behavior, workflow, configuration, or documentation changes.
- `Fixed` for corrected defects.
- `Removed` for deleted behavior or files.
- `Internal` for refactors, dependencies, build tooling, and maintainability work.

## Update rules

- Use concise bullets beginning with a clear past-tense verb.
- Describe impact without requiring the reader to inspect a diff.
- Preserve previous history.
- Omit mechanical edits, vague summaries, commit hashes, empty categories, and test mentions unless testing itself changed.
- Split mixed changes across categories when their impacts differ.

## Validation

Confirm the date is local and correct, the heading style matches existing history, entries are not duplicated, and all claims reflect completed work.

## Delivery

Write the result to `CHANGELOG.md`. Return a concise summary and validation result. Do not reproduce the full changelog in chat unless requested.
