---
name: clip-compare
description: "Make a shareable before/after video: two or more clips side by side under labels. Use for showing how an animation, effect or scene changed between versions, and for motion to post on Discord. For still artwork use contact-sheet."
---

The video comes from `tools/clip-compare/clip_compare.py` in the Templates repository that bundles this skill (two folders above this skill's folder, or the Templates root the user's instructions name). Below, `compare` means `python <templates-root>/tools/clip-compare/clip_compare.py`, run from the project that holds the footage. It needs FFmpeg; `compare` finds one on PATH or in the RimWorld test harness's `work/ffmpeg/`.

## 1. Find the footage

The newest version usually has a recording or can be filmed. The old version often exists only as footage someone kept.

- Look for kept footage first: the project's `DEVLOG.md` entries, then ignored output folders such as `work/`, then recorded test runs in the test harness's own output folder, all sorted by date.
- Find the commit where the feature first worked and compare its date with your oldest footage. Footage from days later is a middle stage, not the first take: an edited promo comes long after the first recorded test run. Label a panel "first" only when its date matches that commit, and tell the user the date so they can correct you.
- When the change took several steps, show three stages instead of two.
- Film the old version from an old commit only when no footage exists, and only with the project's permission to build, deploy and launch.
- A cut that was edited for release has title cards and fades. Use the raw shot when it exists.

Done when: you can name one file per version and say when each was filmed.

## 2. Choose the moments

Each panel needs a start and a length, in seconds.

1. Make a frame grid of each file, one frame every second or two with the time drawn on it, and look at it.
2. Pick the same beat of the action in each version, such as the dive or the hit, so the panels show the same thing.
3. Start after any fade-in and end before any fade-out or caption card. A panel that goes dark reads as a broken video.
4. Keep the output to 15 seconds or less.

A short old clip loops under a longer new one. Pass ZOOM above 1 when the subject is a few pixels wide at panel size; it crops to the centre of the frame, so it suits footage whose camera follows the subject.

Done when: you have LABEL, FILE, START, LENGTH and ZOOM for every panel.

## 3. Render

~~~bash
compare -o work/posts/dive/dive-before-after.mp4 --still 1.2 \
  --clip "First take" work/promo-old/cut.mp4 6 6.3 \
  --clip Now work/promo/footage/diver/clip.mp4 8.5 10 1.5
~~~

- Write to an ignored folder in the project, never among shipped files.
- Labels say what the version is in a word or two: "First take", "Before", "Now". Oldest first.
- `--still SECONDS` writes a PNG of one frame for places where an image posts better than a video. Choose a time when every panel shows its subject.
- `--layout stack` puts the panels above each other for phone-first platforms.
- With three or more stages, use `--layout feature --panel 640x360`: the older stages share the top row and the newest fills the row beneath them, so the result gets the most room.

Done when: the command printed the output path, length and size, with no size warning.

## 4. Check and hand over

Make a frame grid of the output that includes the first frame, the last frame and the frames either side of each loop point. Check that no panel is dark or on a caption card, the labels match the versions, and the still shows every subject. The first frame is the video's preview on Discord and YouTube: every panel in it must show its subject, so never add a fade-in. Give the user the files. Say what each panel is, when it was filmed, and anything that makes the comparison uneven, such as one side being sped up or zoomed. Posting it is the user's step.
