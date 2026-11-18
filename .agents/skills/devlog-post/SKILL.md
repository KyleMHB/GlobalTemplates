---
name: devlog-post
description: "Turn a moment from a project's development into a post for Discord or social media: an announcement, a before/after, an artwork vote, a mistake fixed, a milestone or a release. Use when the user wants to show progress on a mod or project, or asks what could be posted."
---

A post is one moment, one asset and a few plain sentences. The moments live in the project's `DEVLOG.md`, written as the work happens (see `Git/devlog-template.md` in the Templates repository that bundles this skill).

## 1. Pick the moment

- Read the project's `DEVLOG.md` and list the entries marked `Post: not drafted`.
- With no devlog, or none that fits, find moments in the commit history, tickets and ignored output folders, and offer the user the two or three strongest. Add the chosen one to the devlog.
- One moment per post. A post that shows three changes shows none of them well.

Done when: the user has agreed which moment the post is about.

## 2. Build the asset

| Kind | Asset | Made with |
| --- | --- | --- |
| announcement | concept art or a first screenshot | the project's own captures |
| before-after, still art | versions of the art with arrows | the `contact-sheet` skill |
| before-after, motion | clips side by side under labels | the `clip-compare` skill |
| vote | candidates in one image, each with a letter | the `contact-sheet` skill, labels `A`, `B`, `C` |
| mistake-fixed | a clip or screenshot of the fault beside the fix | `clip-compare` or `contact-sheet` |
| milestone | a short recording of the feature working | the project's recording tools |
| release | the best existing clip or image, plus the link | none |

Write assets and drafts to one ignored folder per post, such as `work/posts/<date>-<slug>/`. Film new footage only when the entry's captures cannot show the moment, and only with the project's permission to launch.

Done when: you have opened the asset and it shows the moment without the text.

## 3. Draft the text

Read `writing-copy.md` in the Templates repository first. Then write `post.md` beside the asset with a section per platform the user posts to. Ask which platforms once, and record the answer in the project's instructions.

- Write as the author, in the first person, in their words where the devlog quotes them.
- Say what the reader is looking at in the first sentence. Name the project in full once.
- For a before-after or a mistake, say plainly what was wrong before saying what changed. That honesty is the point of the post.
- Leave out test results, ticket numbers, commit hashes and tool names.
- State anything that makes a comparison uneven, such as an older clip that runs sped up.
- A vote says what is being chosen, how to vote (a reaction per letter, or the platform's poll) and when it closes. Ask the user whether the result decides the art or only informs it, and say which in the post.
- When the author profile the user's instructions name has an AI disclosure, ask once whether posts carry it, and follow the answer.
- Include a link only when the user gave it or the project's files state it.

Lengths: a Discord post reads well at up to about 120 words with a short list. For X or Bluesky, write one or two sentences under 280 characters.

Done when: each platform section stands on its own next to the asset.

## 4. Hand over and record

Give the user the asset and `post.md`. Say where each capture came from and what the post leaves out. Set the devlog entry's `Asset` and `Post` lines. Posting is the user's step: after they say it is posted, record where and when.
