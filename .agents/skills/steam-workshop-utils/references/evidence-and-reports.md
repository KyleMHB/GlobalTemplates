# Evidence And Reports

Use this reference when changing signal extraction or report wording.

## Evidence Categories

- `incompatibility`: incompatible, conflicts, breaks with, not compatible.
- `multiplayer`: multiplayer, MP, server, dedicated server, co-op, singleplayer-only wording.
- `dependencies`: requires, dependencies, load before, load after, must be loaded.
- `version`: build, game version, updated for, supports version.
- `errors`: error, exception, crash, bug, broken, log spam, stack trace.
- `load_order`: load order, load before, load after, above/below wording.
- `overlap`: overlaps with, redundant with, duplicate functionality, does the same thing as, or both-mods-modify wording.
- `compatibility`: positive works-with, compatible-with, integration, compatibility-patch, or supported-alongside wording.
- `alternatives`: use another mod instead, replacement, better alternative, try another mod.
- `performance`: problem-focused performance reports such as lags the game, heavy lag, bad performance, FPS drops, stutter, slowdown, memory leak, causes lag, performance issue, TPS drops, or heavy mod.
- `sentiment_negative`: strongly negative wording such as unusable, abandoned, outdated, avoid this, not worth it, or similar reports.
- `resolved`: fixed, resolved, works now, no longer crashes, patched, issue is gone, or similar comments.

## Check Templates

Built-in templates live in `references/check-templates.json`.

- `basic` is the default modlist health check.
- `basic` defaults to `html`.
- `basic` is problem-focused: fulfilled dependency evidence and clean checks are suppressed from question results.
- Explicit `--format markdown`, `--format json`, or `--format html` overrides the template default.
- Template reports are grouped by question first, then detailed by mod.

## HTML Reports

- HTML reports are self-contained with inline CSS and local JavaScript.
- Do not embed external assets, Steam images, CDNs, or remote scripts.
- Link every reported mod title and Workshop ID to its Steam Workshop page.
- Link Workshop IDs found in evidence snippets.
- Link title mentions only when they exactly match another selected mod title.
- Escape all title, snippet, failure, and metadata text before rendering.
- Question sections, Mod Details, and mod cards are collapsible.
- Per-row Actions sections are collapsible and start closed.
- Static HTML reports show disabled resolve controls. Run with `--serve` to persist Mark resolved and Unresolve actions to SQLite.
- Basic Check HTML hides no-evidence sections by default; use the page checkbox to reveal them.
- Question evidence is capped at 10 visible rows by default, with a local Show more button for the rest.
- Filter controls operate on evidence rows and their parent question/mod sections. Parent sections without visible matching rows are hidden, and the page shows an empty state when no mod cards match.

## Reporting Rules

- Report snippets as evidence, not proof.
- Prefer `unknown` or "no configured evidence signals found" when the cache has no matching text.
- Treat description matches as direct author evidence.
- Treat comment matches as user-reported evidence.
- Include sync failures because missing comments can bias conclusions.
- In Basic Check question results, show only actionable problem evidence. Dependency checks are evidence-based: suppress clearly fulfilled dependency mentions and keep only missing or uncertain dependency evidence.
- Overlap and positive compatibility results must reference another selected mod by exact title or Workshop ID. Keep explicit conflicts separate from functional overlap.
- Version/build checks do not assume a target game version. They report outdated, unsupported, wrong-version, needs-update, or similar concern wording only.
- Exclude positive or neutral performance wording from Basic Check problem results, including reduces lag, no performance impact, minimal performance impact, performance friendly, improves FPS, optimized, better FPS, and less lag.
- Treat newer comments as more authoritative than older comments. Comment `position` is the recency signal; lower values are newer.
- If a newer resolved/fixed comment exists for the same mod and problem family, suppress the older active problem evidence from Basic Check and show it in the collapsed resolved section.
- Manual resolutions are stored in SQLite table `resolved_evidence` by evidence fingerprint: item ID, question ID, category, source type, source key, and normalized snippet hash.
- Manually resolved evidence is excluded from active Basic Check results and shown in the collapsed resolved section with resolution metadata.

## Common User Requests

- "Check if these mods are incompatible" means sync if requested, then report `incompatibility`, `dependencies`, and `load_order`.
- "Does it work in MP?" means report `multiplayer`, `errors`, and relevant description snippets.
- "Are users reporting problems?" means report `errors`, `incompatibility`, and recent comment-derived evidence.
- "Run a basic check" means use `--check basic`, which defaults to HTML output.
- "Are the mods compatible with this game version?" means include `version` and `incompatibility` concern evidence from metadata, descriptions, and comments unless the user provides a concrete version and asks for stricter comparison.
- "Highlight negative user sentiment" means include `sentiment_negative` evidence and keep it snippet-based rather than assigning a score.
