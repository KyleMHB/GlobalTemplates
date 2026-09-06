# Changelog

Agent read route: read only the newest relevant release; locate older versions by searching `^## ` headings.

## 2026-09-06

### Changed

- Reduced the catalog to README, changelog, testing, Steam description, Wayward metadata, and RimWorld metadata templates.
- Moved the `setup-matt-pocock-skills` policy into the installed skill, including its local issue, triage, domain-layout, instruction-file, conflict, and validation defaults.
- Clarified that changelog updates may be created automatically when they are materially useful, while new testing guides require an explicit request and existing guides may receive material updates.
- Removed the personal forking request from generated README and Steam Workshop copy.

## 2026-09-05

### Changed

- Marked five template outputs as public-facing and required Unslop validation for their reader-visible copy.
- Audited the five public template instructions with Unslop and replaced vague changelog and Steam guidance with concrete criteria.
- Updated the template manifest to schema version 2 with an explicit `publicFacing` classification.

### Internal

- Added validator coverage for public-copy classification, instructions, and fallback disclosure.

## 2026-09-04

### Changed

- Clarified when ordinary, project-memory, and changelog templates may activate.
- Defined guarded permission for validated local commits.
- Standardized the required workflow-template headings and made Steam Links conditional.

### Internal

- Expanded template validation to detect orphaned templates, structural contract violations, and malformed Steam BBCode.
- Added positive and negative validator coverage for the stricter contract.
