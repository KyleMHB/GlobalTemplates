# Skill lookup

Resolve skill availability separately from invocation permission. An agent's initial skill catalogue can omit explicit-only skills that are still installed. Use the current harness's discovery and loading mechanism when available.

Before reporting a named skill unavailable, check, in order:

1. The supplied path or resource identifier and the active harness's skill catalogue.
2. Skill roots supplied by the harness or configured by the user/project. Resolve environment variables and home directories in the current environment.
3. The repository's `.agents/skills/<skill-name>/SKILL.md` and any repository skill location declared by the active harness.
4. The shared user location `~/.agents/skills/<skill-name>/SKILL.md` when accessible.

Harness-specific locations are additional candidates only when that harness is active or the user identifies them. Examples include `$CODEX_HOME/skills` or `~/.codex/skills` for Codex, and `~/.claude/skills` for Claude. They are not prerequisites for other agents. Check named locations only; avoid broad filesystem scans.

Read an installed skill when explicitly invoked, even if absent from the catalogue; otherwise recommend its invocation when appropriate. Preserve explicit-only policies. Skill names in these documents identify workflows; use the active harness's supported syntax, or read the permitted `SKILL.md` directly when it has no skill loader. Optional `agents/openai.yaml` files are product metadata; other harnesses can use `SKILL.md` without them. If lookup fails, report which paths or resources were checked or inaccessible and apply any documented fallback.
