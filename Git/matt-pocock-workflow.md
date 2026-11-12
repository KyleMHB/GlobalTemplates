# Matt Pocock engineering workflow

Verified against upstream v1.3.1 on 6 October 2026. This is a routing reference, not a requirement to run every step for every change. Read the installed skill before applying it; its instructions govern that step. Check upstream again when upgrading the skills.

These skills are optional integrations. Resolve available skills with [skill lookup](../skill-lookup.md). Use the active harness's invocation mechanism and preserve each skill's invocation policy. If a skill is absent, carry out the requested planning or implementation directly with the applicable repository rules. Do not claim to have run an unavailable skill.

For whole-specification work, use subagents and separate worktrees only when the current environment supports them and the requested workflow authorizes them. Otherwise execute ready tickets sequentially, preserving their blockers and context handoffs, and state that orchestration is sequential. Missing tracker or worktree capabilities require a local handoff or a reported blocker, not an invented integration or an automatic installation.

## Choose a route

| Situation | Route |
| --- | --- |
| Clear, small change | Implement directly; use the implementation skill when explicitly requested. |
| Requirements or design need discussion, and planning fits one session | `grill-with-docs`, then choose the build route below. |
| Planning itself spans sessions because the effort is large and uncertain | `wayfinder`; resolve its decision map, then feed the main map into `to-spec`. |
| Settled build fits one session | `implement` in the current planning context. |
| Settled build spans sessions | `to-spec` → `to-tickets` → `implement` per ticket, or `implement-spec` for the whole ticket graph. |
| Difficult bug, intermittent failure, or regression | `diagnosing-bugs`; establish a reproducible feedback loop before choosing a fix. |
| Incoming issue needs clarification | `triage`; tickets produced by `to-tickets` are already agent-ready. |

Planning size and build size are separate decisions. A feature can be straightforward to plan but still require several implementation sessions.

## Steps and reasons

| Skill | When to use it | Purpose and completion |
| --- | --- | --- |
| `setup-matt-pocock-skills` | Before the repository's first engineering flow, when configuration is missing | Configure the tracker, triage labels, and domain-document layout the other skills assume. |
| `grill-with-docs` | A plan or design needs decisions that fit one conversation | Resolve requirements, scope, terminology, and design choices. Retain domain vocabulary in `GLOSSARY.md` and architectural decisions in ADRs. |
| `wayfinder` | A large, uncertain effort cannot be planned in one session | Create a map of decision tickets, resolve them across sessions, and record linked decisions. Planning is complete when the route is clear and no unresolved in-scope decisions remain. These are decision tickets, separate from implementation tickets. |
| `to-spec` | Settled decisions need to survive a multi-session build | Synthesize the conversation or completed wayfinder map into a buildable specification. Agree testing seams with the user and record scope and decisions already made. |
| `to-tickets` | Work needs independently executable slices | Draft verifiable slices sized for fresh sessions and declare genuine blockers. Obtain the user's approval of the breakdown, then publish to the configured tracker. It can also accept an existing plan or settled conversation directly. |
| `implement` | One concrete piece of work or one ready ticket | Build using TDD where possible at agreed seams, run applicable checks, review the change with `code-review`, then commit to the current branch. |
| `implement-spec` | The user wants a whole specification orchestrated rather than driving tickets individually | Execute ready tickets through implementer subagents in separate worktrees, integrate onto one branch, and review the integration diff. |
| `code-review` | Implementation close-out or a standalone branch/PR review | Review against coding standards and the originating specification. A completed review within implementation satisfies this step; repeat when changes or unresolved findings warrant it. |
| `pr` | Writing a pull request body | Explain the change with a compact visual, before/after evidence, reversibility, and blast radius. This skill shapes the body; branch management, pushing, and PR creation remain separate actions within the authorized task. |
| `retro` | After a build, especially when the session exposed recurring friction | Suggest improvements to the agent's environment: navigation, instructions, tooling, checks, and standards. Use it when there is something useful to learn rather than making it a compulsory step. |

## Handoffs and invocation

- Preserve the planning conversation through specification and ticket creation where practical. If context pressure requires compaction, do it at a phase boundary with decisions and source references retained.
- Start each per-ticket implementation in a fresh context using its self-contained ticket. Work only tickets whose blockers are complete.
- Run a retrospective in the session it examines, or supply that session's log.
- In v1.3.1, `setup-matt-pocock-skills`, `grill-with-docs`, `wayfinder`, `to-spec`, `to-tickets`, `implement`, `implement-spec`, and `retro` are user-invoked. Recommend the next suitable command and respect explicit user invocation; a routing document does not automatically invoke the chain.
- Do not auto-invoke `tdd` or `code-review` during normal implementation unless the user explicitly asks for TDD or a review pass. An explicit `implement` or `implement-spec` invocation counts as that request for the steps those skills define. Load a skill through the mechanism available in the current harness only when explicitly requested.
- For a design question that needs runnable evidence, use a prototype and bring its findings back into planning.

## Versioned sources

- [v1.3.1 release](https://github.com/mattpocock/skills/releases/tag/v1.3.1)
- [Workflow router](https://github.com/mattpocock/skills/blob/v1.3.1/skills/engineering/ask-matt/SKILL.md)
- [Wayfinder](https://github.com/mattpocock/skills/blob/v1.3.1/skills/engineering/wayfinder/SKILL.md)
- [To spec](https://github.com/mattpocock/skills/blob/v1.3.1/skills/engineering/to-spec/SKILL.md)
- [To tickets](https://github.com/mattpocock/skills/blob/v1.3.1/skills/engineering/to-tickets/SKILL.md)
- [Implement](https://github.com/mattpocock/skills/blob/v1.3.1/skills/engineering/implement/SKILL.md)
- [PR body](https://github.com/mattpocock/skills/blob/v1.3.1/skills/engineering/pr/SKILL.md)
- [Invocation conventions](https://github.com/mattpocock/skills/blob/v1.3.1/.agents/invocation.md)
