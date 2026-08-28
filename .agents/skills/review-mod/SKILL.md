---
name: review-mod
description: Audit an existing or older game mod by reviewing its intent, repository structure, code quality, performance, compatibility, release artefacts, and current user-reported issues on Steam Workshop and GitHub. Use for a comprehensive mod health review or modernization assessment. Do not use for an ordinary code review limited to a small change or pull request.
---

# Review Mod

Produce an evidence-driven assessment of the mod in the current workspace. Adapt the review to the game and modding framework rather than assuming RimWorld, but apply the RimWorld checks below when relevant.

## Operating boundary

Default to a read-only audit. Inspect, build, test, research, and report, but do not edit project files, update dependencies, change Git state, publish, or modify Steam or GitHub. Implement fixes only when the user separately authorizes implementation.

Read applicable repository instructions first. Respect any instruction that limits templates, network access, builds, or external actions.

Ask for input only when a missing choice would materially alter the conclusions. State safe assumptions and continue with all unaffected work.

## Discover project identity

Do not initially ask the user for repository links or platform IDs. Search the project documentation and metadata first, including README files, manifests, mod descriptors, changelogs, release notes, Git remotes, badges, publishing scripts, Workshop-ID files, package IDs, dependency declarations, source comments, and references to upstream projects.

Attempt to identify:

- the official repository and issue tracker;
- the Steam Workshop page and Workshop ID;
- the original or upstream project when this is a fork;
- supported game and framework versions;
- required and optional dependencies;
- release pages, documentation, compatibility mods, and related projects.

Cross-check names, authors, package IDs, repository owners, descriptions, and release history. Classify each identity as confirmed, probable, ambiguous, or missing, and record where it was found. Ask the user only if unresolved ambiguity would make external research unreliable.

## Review the local project

Map the repository before judging individual files. Establish the mod's stated purpose, major features, architecture, data flow, lifecycle, build process, packaging, and release workflow. Compare documented behavior with the implementation and shipped artefacts.

Inspect relevant source, configuration, metadata, documentation, tests, CI, build and publishing scripts, bundled assemblies, generated outputs, localization, settings, screenshots, descriptions, changelogs, tags, and recent history. Search for stale, duplicated, unreachable, disabled, deprecated, unfinished, or misleading material.

Review important features end to end for:

- correctness, edge cases, validation, error handling, and recovery;
- architecture, responsibility boundaries, naming, readability, duplication, and unnecessary complexity;
- initialization, lifecycle, cleanup, ordering, concurrency, persistence, migrations, and save compatibility;
- compatibility, extensibility, logging, diagnostics, security where relevant, and meaningful test coverage.

Classify major features as sound, functional but fragile, incorrectly implemented, incomplete, obsolete, or unverified. Explain the practical consequence of weak implementations, not merely the stylistic concern.

## Review performance

Look for work performed every frame, tick, request, entity, or map; repeated scans, reflection, parsing, serialization, allocations, logging, filesystem or network calls; poor scaling; broad hooks; cache misuse; memory retention; and expensive loading or initialization.

Separate measured defects from plausible profiling candidates. Do not call code slow solely because it looks inelegant. Run safe existing benchmarks or profiling checks when available. Otherwise identify the suspected hot path and specify how to measure it.

## Check current compatibility

Treat versions, APIs, platform requirements, dependencies, and recommendations as time-sensitive. Verify them with current authoritative sources. Prefer official game, framework, dependency, Steam, and GitHub documentation. Record exact versions and dates.

For each possible update, state the current project approach, the current supported approach, whether action is required, recommended, or optional, the evidence, the expected benefit, and migration or compatibility risk. Do not recommend an update only because a newer release exists.

## Apply mod-specific checks

Review supported game versions, metadata, load order, dependencies, patching or hooking strategy, conflicts, save upgrade and removal behavior, localization, configuration defaults, multiplayer or synchronization concerns, packaged contents, error-log behavior, Workshop claims, and whether source matches the released artefact.

For RimWorld, examine `About/About.xml`, `SupportedVersions`, package IDs, dependencies, assemblies, Defs, XML patches, Harmony targets, static initialization, serialization, long-running saves, per-tick, per-pawn and per-map work, settings, compatibility code, and log spam. Verify current RimWorld and framework APIs rather than relying on memory.

## Research user reports

When verified external pages exist, inspect the Steam description, update notes, discussions, bug threads, and available recent comments, plus GitHub issues, recently closed issues, pull requests, discussions, releases, known issues, and relevant CI failures.

Use available Steam Workshop metadata and comment tooling when it provides better coverage or cached evidence. Use GitHub tools for repository-native evidence. Browse current authoritative pages when connector data is unavailable or incomplete.

Group reports by theme and prioritize recent, recurring, reproducible reports affecting supported versions. For meaningful reports, capture the source link and date, symptoms, affected version, reproduction details, maintainer response, workaround, present relevance, likely component, code evidence, and confidence.

Distinguish confirmed defects, likely defects, conflicts, configuration mistakes, obsolete reports, feature requests, and claims without enough evidence. Do not treat every comment as a bug or infer a code connection without support.

## Verify without mutation

Run the smallest relevant documented build, test, static-analysis, metadata, or packaging checks when safe. Report observed passes, warnings, failures, skipped checks, and environmental limitations. Do not hide missing tests or imply runtime validation that did not occur.

If the repository is too large for complete inspection, disclose the coverage boundary and selection method. Never describe a sampled review as comprehensive.

## Report findings

Lead with an executive verdict covering fitness for purpose, overall health, current compatibility, largest risks, and the appropriate level of maintenance. Give separately justified 1 to 10 ratings for correctness, architecture, maintainability, performance, compatibility/currentness, documentation, test confidence, and release quality.

Then provide:

1. Discovered project identities and their confidence.
2. A compact project and architecture map.
3. Findings ordered by severity.
4. Major-feature classifications.
5. Performance findings, separating measurements from risks.
6. A currency and compatibility table.
7. Steam and GitHub report themes linked to code evidence.
8. Validation performed and remaining gaps.
9. A prioritized roadmap: immediate fixes, short-term improvements, modernization, then optional refinements.
10. The safest coherent first implementation batch, without implementing it.

Give every significant finding a stable ID such as `AUDIT-001`, severity (Critical, High, Medium, Low, or Informational), confidence (High, Medium, or Low), precise file and line evidence where possible, affected versions, practical impact, concrete recommendation, verification method, and relevant external links.

Clearly separate confirmed defects, evidence-based concerns, speculative risks, maintainability improvements, and optional modernization. Avoid generic advice and do not recommend a rewrite without showing why incremental work is inadequate.

End by directly answering whether the mod is well written, whether any features are badly implemented, whether it is performant, whether it is outdated, whether its published claims remain accurate, the five highest-value improvements, and whether continued maintenance is worthwhile.
