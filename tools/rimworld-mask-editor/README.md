# RimWorld Mask Editor

A standalone editor, gallery, review queue and recipe exporter for RimWorld artwork. Artwork, recipes, review history and mod-specific gallery settings stay in the target mod repository.

## Install and open

Use Python with Tkinter and install the image dependency:

```powershell
python -m pip install -r requirements.txt
python mask-editor.py --project "<path-to>/My Mod" --gallery
python mask-editor.py --project "<path-to>/My Mod" "Textures/Things/Example.png"
```

`--project` defaults to the current directory. Relative image/mask arguments resolve inside that project. You can also supply a mask as the second positional argument. The editor window is interactive; launch it visibly for a user handoff.

The gallery scans the target's `Textures/`, optional `artwork/objects.json`, design sources, current recipe exports and review queue. A registry is optional for plain textures. Recipe-backed edits retain painted color/mask inputs and review records; saving a candidate does not automatically promote it into production textures. Use the bundled `export-layered-artwork.py` for the same recipe format without a per-mod exporter copy.

The optional `artwork/mask-editor.json` contains `supersededDesigns`, `supersededTextures`, `sourceCandidates` and `recipeOverrides`. These filter historical designs and map nonstandard texture paths to recipes. Each mod supplies its own choices in that file; the shared tool has no mod-specific defaults.

## Guidance and checks

The short [agent guide](AGENTS.md) points to the common mask/artwork guidance. Run existing shared tests with `python -m unittest discover -s tests -v`. Tests cover editor behavior, review/promotion and recipe placement; they do not approve artwork appearance.
