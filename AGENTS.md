# Agent Instructions

## Pointers

Resolve shared files from this checkout or a user/project-configured Templates root. If unavailable and network access is allowed, use `https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/`. Paths in this file are relative to that root.

- **User-facing copy:** before writing reader-facing prose (README, changelog, Steam description, `About.xml` or `mod.json` descriptions), read `writing-copy.md`.
- **Templates:** before creating or editing `README.md`, `CHANGELOG.md`, `TESTING.md`, `steam-description.md`, `mod.json` or `About/About.xml`, read `template-routing.md`. This includes a completed change with useful user, maintainer or operational impact (changelog), and a material change to an existing `TESTING.md`'s procedures.
- **RimWorld testing or artwork:** read the short [RimWorld agent read route](Steam/rimworld/agent-guide.md), then only the relevant harness or artwork topic.
- **Missing skill:** before reporting a named skill unavailable, read `skill-lookup.md`.

## Engineering workflow routing

The named skills below are optional integrations. Resolve them through [skill lookup](skill-lookup.md) and use the active harness's invocation mechanism. When unavailable, follow the same planning or implementation outcome directly, respect explicit invocation requirements, and report any capability that prevents completion. A reference to a skill does not require installing it.

- Choose the route by unresolved decisions and session size. For requirements or design discussions that fit one session, recommend `grill-with-docs`; for planning that spans sessions, recommend `wayfinder`.
- For a settled single-session build, proceed directly to implementation. For a multi-session build, use `to-spec` then `to-tickets`, followed by `implement` per ready ticket or `implement-spec` when whole-spec orchestration is requested.
- Preserve planning context through ticket creation where practical; start each per-ticket implementation fresh from its ticket and completed blockers.
- Count implementation's completed `code-review` as the review step when explicitly requested. Use `pr` when writing a PR body; recommend `retro` when the session reveals useful improvements to instructions, tooling, or checks.
- Respect the installed skills' invocation rules. Upstream's planning and implementation entry points are user-invoked; do not auto-invoke `tdd` or `code-review` unless explicitly requested by the user. A user's explicit `implement` or `implement-spec` invocation counts as that request for the steps those skills define.
- When choosing a planning route or coordinating a multi-session build, read `Git/matt-pocock-workflow.md` for prerequisites, rationale, handoffs, and the verified v1.3.1 sequence.

## Implementation & Verification

A project's own instructions for testing and verification take precedence over this section.

- Complete the requested user workflow end to end before optional cleanup, refactoring, hardening, or documentation. Include UI, logic, persistence, and integrations where the request requires them.
- Define completion by observable requested behavior. A passing build alone does not establish that the feature works.
- Verify with the existing build, relevant existing fast tests, and one focused check of the changed behavior where practical. Do not create test infrastructure.
- After those checks pass, stop. Repeat or broaden verification only for a specific failure, subsequent code change, or concrete unresolved risk; seeking more confidence alone is insufficient.
- Do not turn unavailable tooling or unrelated failures into additional projects. Report the limitation accurately and finish all unaffected requested work.
- Before delivering, compare the result with the original request. Complete missing in-scope behavior; report genuine blockers without claiming completion.
- Keep architecture audits, compatibility matrices, benchmarks, evidence reports, and separate review or hardening passes opt-in unless explicitly required by the task.
- Only handle failure modes that are realistic in normal usage or explicitly requested. Do not invent defensive boilerplate for hypothetical invalid states.
- Do not write new unit tests, reflection tests, test harnesses, or temporary probe scripts unless the user explicitly asks for tests, explicitly invokes a skill that requires them, or the task is a dedicated bug-reproduction ticket.
- Restore temporary environment changes before delivery; after an interruption, prioritize safe restoration when work resumes.
- Follow existing project conventions and prefer built-in APIs or existing utilities. Keep business logic, presentation, persistence, and integrations reasonably separated without over-abstracting.
- Preserve public APIs and behavior unless the task requires changing them. Comments explain why. Follow established naming; absent a convention, use `camelCase` for values and functions, `PascalCase` for types, and `kebab-case` for files.
- Never hardcode secrets or add external services, telemetry, production dependencies, destructive migrations, or data deletion without explicit approval.
- Keep raw captures, generated reports, deployment copies, and temporary probes local or ignored. Commit only durable specifications, concise evidence summaries, and reusable tooling.

## Git

A project's own Git instructions take precedence over this section.

- Commit only when the user asks or an invoked workflow (such as `implement`) defines a commit step. Never push, force-push, rewrite published history, or delete a remote branch without explicit approval.
- Commit small, self-contained changes directly to the current branch, including the default branch. Create a branch only for work that spans sessions, needs review before it lands, or runs in a parallel worktree.
- Integrate a finished branch with a fast-forward or one merge commit, then delete it locally. Offer to delete its remote copy so merged branches do not pile up.
- Keep one logical change per commit. Split unrelated edits from the same session into separate commits by staging specific paths; never `git add -A` when the tree holds unrelated or untracked work.
- Write the subject as an imperative sentence (`Add …`, `Fix …`) of at most about 72 characters, without a type prefix such as `feat:` or a trailing period, unless the project already uses Conventional Commits. When a commit touches several files or its reason is not obvious from the diff, add a body that says why.
- Before committing, review `git status` and the staged diff for stray files such as raw captures, probes, and secrets.

## Delivery

Lead with the outcome. Include validation and material caveats. Mention versioning, documentation, changelog, Git, or deployment status only when relevant.
