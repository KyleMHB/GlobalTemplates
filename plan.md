# Documentation Cleanup Plan

## Summary

Reduce GlobalTemplates to six templates: README, changelog, testing, Steam description, Wayward metadata, and RimWorld metadata.

Remove the aggregate project-memory documents, preserve five qualifying architectural decisions as ADRs, move the Matt Pocock setup policy into its owning skill, and remove the personal forking request from generated README and Steam copy under `E:\Coding`.

## GlobalTemplates changes

- Delete the PROJECT, HISTORY, DECISIONS, and Matt Pocock setup template sources.
- Remove the `project-overview`, `engineering-history`, `technical-decisions`, and `matt-pocock-skills-setup` entries from `templates.json`.
- Remove the deleted templates from the README catalog, project-memory guidance, and `AGENTS.md` routing table.
- Keep `templates.json` at schema version 2 because its structure does not change.
- Keep the testing template. Creating `TESTING.md` requires an explicit request; an existing file permits automatic updates when its procedures, expectations, or evidence materially change.
- Continue allowing automatic changelog creation for completed changes with useful user, maintainer, or operational impact.
- Replace the uncommitted 2026-09-06 changelog entry with entries covering the reduced catalog, setup-policy relocation, activation rules, and forking-copy removal.
- Preserve older changelog entries, including truthful references to documents that existed at the time.

## Setup skill

- Add `references/personal-setup-policy.md` under the installed `setup-matt-pocock-skills` skill.
- Move the existing local issue-tracker, triage, domain-layout, instruction-file routing, conflict-handling, and validation defaults into that reference.
- Update the skill entrypoint to read the bundled reference instead of the GlobalTemplates file or GitHub fallback URL.
- Retain the prompt-driven fallback when the bundled reference cannot be read.
- Leave the skill's explicit-invocation policy and UI metadata unchanged.

## Project-memory cleanup

Delete `PROJECT.md`, `HISTORY.md`, and `DECISIONS.md` from:

- Better Crafting
- QualityCraftingXP
- Orbital Recovery Network

Do not migrate their general project or history prose. Delete the modified, uncommitted QualityCraftingXP history as authorized.

Remove live links to the deleted documents from project documentation. Update LivingWorld's shared resource guide so it no longer instructs agents to read them. Keep references to `TESTING.md`.

### ADR backfill

Before deleting the decision logs, create five short accepted ADRs under each project's `docs/adr/` directory:

1. Better Crafting: server-authoritative ordered operations.
2. QualityCraftingXP: QualityCrafting owns permanent progression, while the add-on persists only incomplete counters.
3. QualityCraftingXP: one deployable source shared with the conditional linked-source test harness.
4. Orbital Recovery Network: server-authoritative real-pod respawn with no teleport fallback.
5. Orbital Recovery Network: UE4SS runtime with a minimal IMM bridge.

Use sequential four-digit filenames beginning at `0001` in each project. Keep each ADR concise and preserve only the decision, reason, and any non-obvious consequence.

## Public-copy cleanup

- Remove the personal forking request and its disclaimer from the README and Steam source templates.
- Rename `Contributing and Forking Policy` to `Contributing`, retaining the contribution invitation.
- Rename `License and Forking Policy` to `License`, retaining license, copyright, attribution, and fork-history content.
- Update the Steam section-order validator and its fixtures to require `License` under the revised name.
- Apply the same cleanup to all 14 matching `README.md` and 11 matching `steam-description.md` files under `E:\Coding`.
- Include nested release-package copies and files in non-Git directories.
- Preserve each file's existing line endings and all unrelated edits.
- Leave `CONTRIBUTING.md`, saved reviews, and project changelogs unchanged.
- Do not publish updated Steam descriptions or deploy release-package copies.

## Validation

1. Run `scripts/test-validator.ps1` and `scripts/validate-templates.ps1`. Both must pass with six mapped templates.
2. Run the skill creator's `quick_validate.py` against `setup-matt-pocock-skills`.
3. Confirm the setup skill's bundled policy reference resolves and its fallback remains reachable when the reference is unavailable.
4. Parse `templates.json` and confirm no deleted or orphaned template remains.
5. Confirm the five ADR filenames are sequential and their contents match the approved source decisions.
6. Search for stale live links to PROJECT, HISTORY, and DECISIONS outside preserved changelog history.
7. Search the targeted README and Steam files for the removed policy wording and combined headings. The result must be empty.
8. Run the required crisp-human checks on changed reader-facing copy. Treat pre-existing soft cadence warnings as advisory.
9. Review every affected working-tree diff, with particular care in repositories that already contain uncommitted changes.

## Constraints

- Do not migrate project or history prose beyond the five approved ADRs.
- Do not edit policy occurrences in `CONTRIBUTING.md` or saved review documents.
- Do not add project-level changelog entries for this copy cleanup.
- Do not change code, runtime behavior, schemas, mod versions, or release artifacts.
- Do not commit, push, publish, upload, or deploy.
- Request filesystem approval when implementation reaches projects or the personal skill directory outside the current writable workspace.
