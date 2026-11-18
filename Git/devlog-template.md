# Devlog Template

## Use when

Use this template when the user explicitly requests a devlog, or when a session in a project that already has a `DEVLOG.md` produces a moment worth showing to players. Create `DEVLOG.md` in the project root only on explicit request.

A moment is a change someone outside the project could see and would care about:

- the project is announced or started;
- a feature works for the first time;
- artwork, an animation or a sound is chosen, replaced or redone;
- a visible mistake is fixed;
- footage or screenshots are filmed again;
- a release.

Refactors, tests, tooling and documentation are not moments.

## Evidence

Read the newest entries only. Take the change from the completed work and the before and after from files you have looked at, never from memory of what a version looked like.

## Structure

~~~md
# [Project] Devlog

<!-- Agent read route: read the newest entries; find others by searching `^## ` headings or `Post: not drafted`. -->

## YYYY-MM-DD: [short title]

- Kind: announcement | before-after | vote | mistake-fixed | milestone | release
- What changed: [one or two plain sentences a player would understand]
- What was wrong: [for before-after and mistake-fixed; the fault in plain words]
- Before: [path, `REV:path` or recording; when it was made]
- After: [path or recording; when it was made]
- Asset: [path of the built image or clip] | not built
- Post: not drafted | drafted ([path]) | posted ([where], YYYY-MM-DD)
~~~

Add the newest entry at the top. Leave out lines that do not apply.

## Update rules

- Write the entry in the session that made the moment, while the old version still exists.
- Record where each capture lives when it is made. Captures stay in ignored folders, so the entry is the only record of them.
- Never film or render over an old capture. Give each take its own folder, so the before survives the after.
- When the old version is a committed file, name it as `REV:path` instead of copying it.
- Quote the user's own words about what was wrong when they gave them. They make the best post text.
- Change `Asset` and `Post` as the post is built, drafted and posted. Only the user posts.

## Validation

Confirm every path and revision in the entry exists, and that the date is local and correct.

## Delivery

Write the entry to `DEVLOG.md`. Mention it in one line of the delivery summary. Do not reproduce the devlog in chat unless requested. To turn an entry into a post, use the `devlog-post` skill.
