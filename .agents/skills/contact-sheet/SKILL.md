---
name: contact-sheet
description: "Make a shareable comparison image of artwork: one or more items across their versions, with arrows showing the change. Use for before/after sheets, version histories and art to post on Discord."
---

The sheet comes from `tools/contact-sheet/contact_sheet.py` in the Templates repository that bundles this skill (two folders above this skill's folder, or the Templates root the user's instructions name). Below, `sheet` means `python <templates-root>/tools/contact-sheet/contact_sheet.py`, run from the project that holds the art. It needs Pillow; use the project's artwork interpreter when plain `python` lacks it.

## 1. Choose the rows and versions

A row is one item. Its images run oldest to newest, and the last one is the version being shown off.

- **The versions are files on disk or known commits.** Use `--item`. Each image is a path, the name of an image tracked by git (`SunstoneArray`), or `REV:path` for a committed version.
- **The versions are the file's own git history.** Use `--history COUNT`, which takes the last COUNT distinct versions and captions each with the date it was committed.

Rows may hold different numbers of versions. Shorter rows sit to the right so the current versions line up. When a sheet has column headings, give every row the same number of versions, repeating an image for an item that did not change; the sheet marks it `=` and "unchanged".

Done when: you can name each row's images in order, and you have looked at where older versions live (a `previous-production` folder, a commit) instead of guessing.

## 2. Render

~~~bash
# Several items, shared column headings
sheet -o work/contact-sheets/sunstone.png --title "Sunstone fixtures" --subtitle "Fewer, larger crystals" \
  --labels Before "First pass" Current \
  --item Array old/SunstoneArray.png b634a49:Textures/Things/Building/Misc/SunstoneArray.png SunstoneArray \
  --item Vessel old/SunstoneVessel.png b634a49:Textures/Things/Building/Misc/SunstoneVessel.png SunstoneVessel

# One item, its last four versions from git
sheet -o work/contact-sheets/vessel.png --history 4 SunstoneVessel

# A plain before and after
sheet -o work/contact-sheets/array.png --labels Before After --item "Sunstone array" old.png new.png
~~~

- Write the sheet to an ignored folder in the project (`work/contact-sheets/` where `work/` is ignored), never among shipped textures.
- `--title`, `--subtitle` and `--footer` are optional. A single row with no title uses its label as the title.
- Arrows and the highlight take each row's colour from its art; `--accent #hex` sets one colour for all rows. `--backdrop #hex` changes the tile behind the art, and `--cell` the tile size.
- Keep to four columns or fewer. Discord shrinks wider images until the art is hard to read.

Done when: the command printed the output path and size.

## 3. Check and hand over

Open the image and check that every row reads oldest to newest, the labels match the versions, and no tile is empty by mistake. Give the user the file. Say which version each column is and where it came from. Posting it is the user's step.
