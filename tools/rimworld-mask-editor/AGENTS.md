# RimWorld Mask Editor: agent entry point

Keep reusable editor/gallery/export/review code here. Keep artwork, recipes, review records and historical gallery exclusions in the selected mod. Read its instructions before changing assets.

| Task | Read |
| --- | --- |
| Open the editor or choose another mod | README.md, Install and open; `python mask-editor.py --help` |
| Paint, select, preview, queue a review or save recipe-backed edits | [mask guide](../../Steam/rimworld/mask-editor-guide.md) |
| Mask encoding or tint/icon/overlap diagnosis | The relevant section of [artwork guide](../../Steam/rimworld/rimworld-art-guide.md) |
| Modify behavior | Search the matching method in `mask-editor.py`, `mask_gallery.py`, `mask_review.py` or `export-layered-artwork.py`; inspect its existing tests |

After code changes run the relevant existing tests in `tests/`. Preserve fractional coverage, saved recipe inputs, review history and promotion checks. Mechanical checks and CPU previews do not establish in-game visual acceptance. Do not open or modify unrelated artwork during tooling verification.
