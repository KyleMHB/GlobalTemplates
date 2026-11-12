# RimWorld mask editor

The RimWorld Mask Editor is bundled in `tools/rimworld-mask-editor`. In examples, `<mask-editor-root>` is that folder and `<mod-root>` is the target mod. For broader sprite, material and renderer decisions, read only the matching section of the [artwork guide](rimworld-art-guide.md#read-route). Project instructions own approved artwork and review/deployment permissions.

## Open the selected mod

```powershell
python "<mask-editor-root>/mask-editor.py" --project "<mod-root>" --gallery
python "<mask-editor-root>/mask-editor.py" --project "<mod-root>" "Textures/Things/Example.png" "Textures/Things/Example_m.png"
```

Use the project's configured Python when it has one. Paths with spaces require quoting; PowerShell uses `&` before a quoted executable. Leave the editor visible for a human handoff. With Start-Process, quote individual arguments inside ArgumentList too.

## Gallery and review process

The gallery lists mod textures and design candidates, labels current approved images only when their registry hashes match, and puts requested mask reviews first. Search/filter to the intended object. An approved image label is not mask approval. Superseded designs are hidden by project configuration but retained on disk. The selected mod owns its `artwork/mask-reviews.json` and optional `artwork/mask-editor.json` settings.

For a recipe-backed candidate, open the queued recipe through the gallery so saving updates its recipe and review record. The shared exporter creates a current candidate when needed. A source-layer preview without a matching export is not proof that the current output was reviewed. Painting pauses briefly after opening an item to avoid accidental strokes.

## Paint and select

Paint/Erase edits construction-tint coverage. Brush size, shape, opacity and hardness control strokes; separate strokes build coverage. Use Line or Pen selection for polygons/freehand outlines, Shift to add, Alt to subtract, Enter to close, Ctrl+I to invert and Escape to clear. Fill/Erase selection affects only the selected area. Undo/Redo retain up to 100 changes. Wheel zooms and middle-drag pans.

Outline brush and Outline line paint black on the color artwork, using the current brush/selection settings. Color edits are saved too. Straight lines show a guide during dragging and commit on release. Ctrl+S saves to the opened mask; a new mask prompts for a name. Save As to a different path does not relink the recipe.

P toggles mask/light-tint preview; Shift+P cycles light, dark, wood and mask. These are CPU models, not game renders. Inspect at intended display size using the mod's review policy.

## Save and promote

The editor accepts opaque-red masks and retains unpainted fractional red coverage. It does not convert legacy encodings. For recipe-backed edits, saving creates/updates output-resolution `paintedMask` and, for outline edits, `paintedColor`. These inputs replace generated outputs; revisit them after changing source layers or framing. Color transparency and mask opacity are distinct; see the artwork guide's encoding section.

Saving candidates under `work/` records the reviewed state but does not promote them to `Textures/`. Recipe promotion checks that reviewed output still matches the current recipe and baseline before applying. Follow the target mod's existing review and deployment process; preserve saved human edits when resuming. If a mod lacks a registry, plain image/mask editing still works, while approval and recipe metadata remain unavailable.

## Extend without mod-specific code

Configure historical exclusions, extra source candidates and texture-to-recipe overrides in the mod's `artwork/mask-editor.json`. Reuse the shared gallery and review process rather than copying it. Keep design contracts and acceptance evidence in the mod; promote general discoveries into this guide with version/evidence limits.
