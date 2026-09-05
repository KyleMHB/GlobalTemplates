# Changelog Template

## Use when

Use this template only when the user explicitly requests template-backed changelog work or a completed change has user, maintainer, or operational impact. Create or update `CHANGELOG.md` in the project root.

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

## Public copy

Run the installed `unslop` skill with its default crisp-human preset on release headings and entries after drafting and before delivery. Follow its core preservation, phrase, structure, silhouette, readability, and diff gates. Preserve dates, versions, issue references, names, identifiers, and Markdown structure. A blocking result means the changelog is incomplete.

If `unslop` or its validation scripts are unavailable, apply the Writing and copy rules from `AGENTS.md` manually and state in the delivery summary that automated Unslop validation was unavailable.

## Validation

Confirm the date is local and correct, the heading style matches existing history, entries are not duplicated, and all claims reflect completed work.

## Delivery

Write the result to `CHANGELOG.md`. Return a concise summary and validation result. Do not reproduce the full changelog in chat unless requested.
