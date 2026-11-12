# RimWorld object artwork guide

Reusable guidance for object sprites, directional variants, material masks, menu icons, draw settings and effects. Project requirements and approved references define the visual target; this is not an official Ludeon art specification. Keep each mod's designs, exceptions, tooling commands and acceptance records in that mod.

## Read route

Search headings with `rg -n '^##|^###' Steam/rimworld/rimworld-art-guide.md` from the Templates root, then read only the relevant sections.

| Task or symptom | Section |
| --- | --- |
| New object or localized correction | [Define the object](#1-define-the-object-before-generating-it), [approve a master](#2-approve-one-master-design) |
| Layers, mixed materials, repeat failures | [Route choice](#choose-ownership-polygons-or-separate-layers), [evidence limits](#evidence-still-needed) |
| Rotations change shape or feature count | [Directional views](#3-derive-the-other-views-from-that-design) |
| Framing, resize, anchor or export | [Export](#4-export-color-and-material-regions-together), [numeric framing](#numeric-framing-for-separate-generation), [texture constraints](#engine-texture-constraints) |
| Paint a mask or review gallery artwork | [Mask editor](mask-editor-guide.md) |
| Tint fringe, mask anatomy or darkened fixed colors | [Material-mask encoding](#material-mask-encoding), [renderer diagnosis](#diagnose-the-layer-before-regenerating-artwork) |
| Dim or undersized menu icon | [UI material](#preserve-the-ui-material), [native icon scale](#calculate-scale-from-the-actual-native-function) |
| Trees or furniture overlap incorrectly | [Draw ordering](#treat-draw-ordering-as-renderer-behavior) |
| Style, borders, facets, palette or animation | [Visual style](#visual-style-reference), [prompt scaffold](#prompt-scaffold) |
| Review or deployment | [Review](#5-review-at-the-sizes-and-paths-the-game-uses), [deployment](#6-deploy-the-reviewed-scope), [acceptance record](#acceptance-record) |
| Vanilla references, naming or file conventions | [Vanilla art source](#vanilla-art-source) |
| Art reads as generated, or does not fit vanilla | [Measured vanilla rendering](#measured-vanilla-rendering), [fit to vanilla](#fit-to-vanilla), [outline defaults](#outline-defaults) |
| Weapon sprite points the wrong way when held | [Weapon orientation](#weapon-orientation) |

## Vanilla art source

Ludeon publishes RimWorld's source art through the [RimWorld art source forum post](https://ludeon.com/forums/index.php?topic=2325.0), which links a public [Dropbox folder](https://www.dropbox.com/sh/mz6zjq3f1d654f3/AACX_OMdBG_J78hF2Ph-HzM3a?dl=0). Recorded 2026-11-09: `Game art source` holds one zip per release (core, Royalty, Ideology, Biotech, Anomaly, Odyssey), laid out like the game's `Textures` tree (`Things/Building/...`, `Terrain`, `UI`, `World`). The folder was updated through 2025 although the post was last edited in 2021. Large zips cannot be previewed in the browser; downloading one requires the user's permission.

Use it as the reference for vanilla camera, contour, palette, detail density and file conventions. Apply the same provenance rule as for another mod's art: check Ludeon's current mod and content policy before redistributing derived pixels. The post's "do as you like" answer addressed technical requirements, not licensing.

Conventions observed in an Odyssey sample (scaled previews; native dimensions and mask alpha not measured):

- Directional graphics ship `_north`, `_east` and `_south` only; see [directional views](#3-derive-the-other-views-from-that-design).
- Complex objects are split into parts: `OutfitStand_Base/Body/Head_<dir>`, `GravEngine` with `_Orb` and `_Cooldown`, `AncientHeatVent` with a separate `Glow` texture.
- Dedicated `_MenuIcon` textures are common, including directional ones (`OutfitStand_MenuIcon_east`).
- A single-graphic mask uses an `M` suffix (`AncientHeatVentM`). Core directional source masks append `m` to the direction with no separator (`Bed_northm`, `Bed_eastm`, `Bed_southm`); confirm the installed texture names match.
- Much of the core set ships as layered `.psd` only (1,761 PSD versus 1,661 PNG in the 2025 core zip).
- Linked walls ship as `_Atlas` textures with a `_MenuIcon`; this guide does not yet cover atlas artwork.

### Measured vanilla rendering

Measured 2026-11-10 from an extracted copy of the core zip (376 PNG and PSD sprites, including eight melee weapons not tabled; PSDs composited with `psd_tools`, since Pillow's PSD reader corrupts many of them). Each sprite was treated as 64 pixels per cell. Figures are medians with the quartile range in brackets.

| Group | Exterior outline, px | Saturation p90 of coloured pixels | Interior detail | Hard interior edges |
| --- | --- | --- | --- | --- |
| Furniture (79) | 2 (2–3) | 0 (tintable greyscale) | 2.3 (1.7–3.0) | 5% |
| Misc buildings (66) | 3 (2–3) | 0.32 (0–0.78) | 2.5 (1.3–3.8) | 5% |
| Power (17) | 4 (4–5) | 0.35 (0.21–0.47) | 2.8 (1.5–4.3) | 8% |
| Production (69) | 3 (3–5) | 0.42 (0.21–0.60) | 2.9 (1.5–3.6) | 5% |
| Sculptures (22) | 2 (2–2) | 0 | 6.4 (4.2–8.6) | 14% |
| Resources (115) | 3 (3–4) | 0.46 (0.18–0.66) | 4.4 (2.8–7.0) | 9% |

- **Outline:** the run of pixels darker than 0.3 (largest channel) counted inward from the silhouette on every row and column. It is pure black and unbroken on every group measured: 100% of edge scans start on it.
- **Interior detail:** mean absolute luminance step between neighbouring fill pixels, times 100. **Hard edges:** the share of those steps above 0.12.
- **What this means:** vanilla draws a heavy black contour around a few large, smoothly shaded shapes in muted colour. Tintable objects are greyscale.

**Strict outline figures.** Re-measured the same day with stricter definitions: only pixels with every channel at 25 of 255 or below count as outline; width is perpendicular from the alpha edge, with no blending resample; and pixels per cell come from each definition's full draw size in `Data/Core/Defs`. That confirmed 64 pixels per cell for buildings and resources and 128 for weapons. Medians with quartiles:

- Buildings (462) and resource stacks (103): 2px exterior (buildings 1.3–3, stacks 2–2). The silhouette edge pixel is pure black; the 0.3 threshold above reads about 1px wider because vanilla often has a dark grey band inside the black line.
- Weapons (38): 1.0px (1.0–1.5). An earlier 2px figure came from resampling, which blends the line into the alpha edge.
- Evenness: the 10th to 90th percentile of local width spans 1.0px or less on 98 percent of stacks and 75 percent of buildings.
- Black lines between materials: 1.5px on stacks, 2px on buildings (quartiles 1–2.7).

To compare a mod sprite's outline, measure it in its own pixels and convert the width with its canvas and draw size: pixels × 64 ÷ pixels per cell. RimWorld stretches the canvas to the draw size, so when their shapes differ the two axes have different pixels per cell (canvas width ÷ draw width across, canvas height ÷ draw height down); convert each direction with its own. For the other figures, resample it to 64 pixels per cell first, then measure the same way. A sprite authored at 400 pixels per cell with a 6px contour has a 1px contour in vanilla terms. Dense flat facets, near-full saturation and a contour under 2px are the measurable signs of art that reads as generated beside vanilla. The figures describe the core set only, and DLC art was not measured.

## Engine texture constraints

Historical guidance recorded from the [RimWorld wiki texture tutorial](https://rimworldwiki.com/wiki/Modding_Tutorials/Textures) on 2026-11-02, when the page was marked Under Review. Treat it as a starting point; check the target game's importer and project conventions for version-sensitive decisions.

- Export width and height in multiples of four, preferably powers of two when appropriate. Masters may use different dimensions.
- The reference described vanilla at roughly 64 pixels per cell and newer DLC/mods at roughly 128. Larger textures spend more VRAM. Choose resolution for normal game zoom and record deliberate exceptions.
- Match canvas proportions to draw size when possible. Record visible bounds, padding, footprint, draw size and base anchor independently; tall art need not occupy every cell it covers visually.
- Preserve color data under transparent sprite pixels when the importer needs it to avoid fringes. Mask bleed has different causes; use the encoding section rather than applying sprite-alpha fixes to masks.
- Match contour weight to approved references at displayed size. The historical wiki figure of about 2px per 64px of cell resolution agrees with the [measured vanilla rendering](#measured-vanilla-rendering) (2–3px for buildings and resources). Scale it by the sprite's pixels per cell, not its canvas size.
- Texture paths share a namespace across loaded content. Prefer distinctive mod-prefixed paths and inspect intentional overrides and load order.
- PNG is the practical format because it keeps transparency; Tynan recommended PNG and power-of-two sizes in the 2014 [art source thread](https://ludeon.com/forums/index.php?topic=2325.0). Check current importer behavior before treating that advice as a rule.

## Workflow

### 1. Define the object before generating it

Read the current request and inspect the nearest approved sibling, its color sprite, masks, directions and consuming XML. Historical prompts can contain superseded designs. Check provenance and edit permission for references from another mod; put any authorized replacement in the intended integration rather than editing the installed upstream copy.

For a new design, record the relevant contract fields. For a localized edit, name the change, protected regions and affected views; preserve the existing contract.

| Property | Record |
| --- | --- |
| Identity | What must be recognizable at normal zoom |
| Geometry | Silhouette, parts, feature counts, relative sizes and spacing |
| Materials | Fixed colors versus construction tint; visible ownership at joins |
| Camera | Approved reference and visible top/front/side depth |
| Variants | Directions, shared features and occlusion |
| Placement | Footprint, canvas, alpha bounds, draw size and anchor |
| Edit scope | Allowed changes and protected features/pixels |

Assign each attached image a role: edit target/design, own-family motif, rendering, palette or layout. For a redo, start from the object's own design and list what to retain, replace and borrow. A same-role rendering example supplies camera, shading and contour treatment; its housing geometry is borrowed only when explicitly chosen. Describe replacement construction positively and name removed parts. Completion includes a design that remains recognizable as its own family, rather than a recoloured rendering example.

For simplification, describe which broad shading planes remain and which surfaces become smooth. A facet count can diagnose complexity but cannot replace visual judgment. Use the project's master/provenance registry when one exists. Completion means the contract identifies what survives across affected views.

### 2. Approve one master design

Generate a complete representative design and obtain the needed design feedback before deriving material layers or a full family. Distinguish a *selected* design, which is still being refined, from an *approved* one, which is final. Say which you are recording when the author chooses. **Approval is final:** an approved design's pixels never change to satisfy a rule, measurement or later review; only a redo the author asks for reopens it. After approval, add only its material mask and views or frames computed from it by recipe. Anything with new pixels, or a change of framing or colour, is a new candidate.

On approval, record the source, its export recipe and the exported texture's hash with the author's words and date. Requests, references, attempts and tool details are optional, kept when the project asks for them. Keep a layered master when the tool produces one, as vanilla does for some sources. Compare it with the approved sibling at intended display size. Record a model version only when the tool exposes it.

Use the active image-editing tool instructions for new artwork and repainting. Deterministic mask/export operations preserve source artwork. A flattened image cannot guarantee independently editable parts; record that limitation. For exact-preservation edits, compare pixels and alpha outside the permitted region. If they drift, restore the protected region with a declared transform and inspect the join, or retain the result as unapproved.

After a spatial failure, change the supplied evidence or method: a labelled layout, isolated component or derivation from the complete design. Repeating coordinates more emphatically does not improve control. After two attempts repeat the defect, change method or stop. Completion means the master meets the contract at game scale.

### Choose ownership polygons or separate layers

Vanilla commonly splits objects into separate textures for parts that move, change state or glow (see [vanilla art source](#vanilla-art-source)). Prefer separate textures for such parts over painting every state into one image.

Freeze the selected complete design before partitioning it. Record the route per material join. Use ownership polygons when visible ownership is clear; separate material layers when pixels blend or ownership is ambiguous. Generated components must agree on geometry, camera and lighting. A prompt requesting a dark inter-material contour is a provisional technique, not proof that the output is separable.

Keep source, ownership/layers and transform in one export recipe. Export color and mask together; fix the recipe inputs and re-export. A painted mask override is an explicit input whose validity must be revisited after color/framing changes. Do not reconstruct invisible surfaces to partition visible pixels.

Before design selection, a colour-only concept may leave ownership explicitly unresolved. Use a fixed-colour source and the project's unresolved-material validation route, with no inherited polygons or painted overrides. Any generated zero mask is a placeholder, not a partition or tint-review result. Author the actual ownership after selection.

A coherent generated part may be split deterministically when the cut follows its real contour. Layer order cannot fix pixels assigned to the wrong part. Inspect joins at normal display size. Correct misplaced partitions or placement first; when the source itself is ambiguous, choose a localized edit, separate component or new generation according to the preservation contract. Neither editing nor regeneration guarantees preservation.

### Evidence still needed

Mechanical success, visual acceptance and runtime behavior are separate. One successful object establishes feasibility, not prompt reliability, directional consistency or cross-object efficiency. Record attempts and corrections only when the project asks for that record; open questions alone do not authorize throwaway experiments, bulk redraws or gameplay builds. Review a candidate in-game when the feature and task scope permit it. A CPU preview cannot establish native shader or menu behavior.

### 3. Derive the other views from that design

Treat directions as views of one physical object. Reuse parts, proportions and palette; repaint facing depth for the fixed camera instead of rotating a shaded painting.

Vanilla directional graphics ship north, east and south only, which indicates west is produced by mirroring east. Verify the consuming graphic class's west handling in the installed source before relying on it. When west is mirrored, the east view must read correctly when flipped: no text or logos, no handed details that must stay on one side, and lighting that remains plausible mirrored. Compare feature counts including occluded parts, spacing, visible faces, contour/facet weight and head/foot or wall-facing orientation. Inspect each sheet cell individually. Completion means every required direction meets the same contract without introducing another design.

### 4. Export color and material regions together

Measure alpha bounds, preserve the approved aspect ratio, scale uniformly and pad transparently. Apply the same crop, scale and translation to the color and material regions. Preserve antialiasing; a small set of principal shade values does not mean a PNG should contain only that many RGB values. Hard thresholds and repeated reduction can damage contours.

Derive masks from explicit ownership or layers. RGB thresholds and horizontal cutoffs cannot reliably distinguish highlights, shadows and irregular material joins. Include rear surfaces visible through gaps. Keep color transparency separate from mask opacity. Completion means dimensions, filenames and placement agree, intended material surfaces are covered and protected features remain excluded.

### 5. Review at the sizes and paths the game uses

Compare changed views with approved siblings at estimated game size; for most pieces one such sheet at normal game zoom is enough. For a new family, or when the family's style may have drifted, also put vanilla sprites of the same role on the sheet at the same pixels per cell: a sheet of only the mod's own art cannot show that drift. A 64/96/128px series can reveal detail loss but is not a universal tile-size rule. Use a common pixels-per-cell scale for comparison sheets and label footprint, draw size, status and estimated framing. For simplification, show current and candidate side by side. Mark unreviewed views and framing/protected-region drift.

Check identity separately from rendering: compare retained silhouette, internal features and motif with the object's own family and any rendering reference. Colour and small ornament alone do not distinguish copied construction. Use a neutral silhouette comparison when shape confusion is the issue; do not treat it as a substitute for internal-feature or palette review. A passing contour measurement does not excuse lost identity.

Run the project's existing art checks and previews. They establish only their measured properties. Judge recognition, proportions, separation and clutter at normal zoom; apply the project's policy for increased-zoom or human inspection. For tintable objects compare neutral, dark and light materials, and review map sprites and menu icons separately. For effects compare 1x and faster speeds, single and repeated fixtures. Label renderer models as models.

Completion means the relevant mechanical checks pass and required visual review is complete or explicitly pending. Project/user instructions determine review timing and whether game launch or computer use is permitted.

### 6. Deploy the reviewed scope

Follow project permissions and deployment tooling. List intended files/fields, compare the installed baseline, back it up and verify installed bytes against the reviewed candidate. Preserve unrelated concurrent source/staged/installed changes; prefer selected XML edits when appropriate. Record source, transformations, mask encoding, definitions, hashes and reload requirements. Store large captures, rejected candidates and backups in ignored working output. A successful copy does not establish that the game loaded it.

## Visual style reference

### Fit to vanilla

Choose the style anchor from where the mod will be played. For a modpack, measure the neighbouring mods' art as well as vanilla, and ask the author which of the mod's own pieces they consider right; those pieces are the house style. Vanilla then supplies a short list of rules, not the whole look. A mod with a strong identity, such as faceted crystals, should not be pushed all the way to vanilla's smooth shading and muted colour.

The vanilla traits below are the ones to check a family against, using the [measured vanilla rendering](#measured-vanilla-rendering). Contour and shape count are the safest to adopt; shading and colour are the author's call:

- **Contour:** black, unbroken, 2px at 64 pixels per cell for buildings and resources (up to 3px stays within vanilla's range), and 1–1.5px on weapons, as the strict outline figures measure it. This is the trait most worth stating in every generation request: it is cheap to state, easy to measure, and a mod's own approved pieces are often thinner than they look at preview size, so do not take them as the outline reference for new art. The figure guides generation and is reported beside candidates; it never reopens art the author has approved.
- **Shading:** a few large shapes with smooth shading. Many small flat facets with hard edges and white highlight streaks read as generated, even when each piece looks good alone at preview size.
- **Colour:** a default for mods without their own rule: keep the saturated end of a fixed-colour object near 0.7 or below, because full saturation glows against terrain. A project's house style overrides it.
- **Shape count:** vanilla objects are a handful of parts. Ornament that disappears at game zoom adds noise, not identity.
- **One rendering for the whole mod:** families may differ in motif, silhouette and hue. They should not differ in contour weight, shading method or detail density.

Do not correct a whole mod with a deterministic filter. A filter that caps saturation, blurs facets and thickens contours can hit the vanilla numbers while adding artefacts, washing out colour and removing the character that made the good pieces good. Matching measurements is not the same as looking right. Regenerate the pieces that depart most from the house style, when the author asks for a redo. Do not run outline passes either: thickening, redrawing or blackening a contour after generation tends to turn thin parts into black spikes. Meet the contour through generation, or ship the art as drawn once approved.

### Outline defaults

These follow from the [strict outline figures](#measured-vanilla-rendering) and suit any mod aiming to sit beside vanilla. A mod may set its own aim inside the ranges. Widths are at 64 pixels per cell, converted per axis as described there.

1. **Black:** every channel 25 of 255 or below. A darker shading band inside the line is fill, not outline.
2. **Unbroken** around the silhouette, except edges cut by the canvas or hidden behind a wall.
3. **Inside** the silhouette: the line's outer edge is the alpha edge, so it never changes silhouette, framing or mask extent.
4. **Width:** buildings and resource stacks 2.0–3.0px; weapons 1.0–2.0px.
5. **Even:** local width varies by 1.0px or less.
6. **Material boundaries:** a black line of 1.0–2.0px. No lines between facets of the same material; those edges are value changes.
7. **Thin parts** under 8px wide (a shard, post or haft) use about 1.5px, so the line never fills the part and a small spiky piece does not read heavy.
8. **Nothing else at the edge:** no second keyline, light rim, glow or drop shadow.

State the width in source pixels in the generation request (target width ÷ the planned export scale) and measure after export. These are generation targets reported beside a candidate, never a reason to change approved art ([approval is final](#2-approve-one-master-design)).

### Weapon orientation

Draw melee weapons horizontal with the tip to the right, and set `equippedAngleOffset` to -65 for swung weapons; ranged weapons aim right with the barrel vertically centred ([RimWorld wiki texture tutorial](https://rimworldwiki.com/wiki/Modding_Tutorials/Textures), recorded 2026-11-08). To fix an existing vertical sprite, rotate it on a square canvas that keeps the grip pivot rather than redrawing it, then recompute draw size and `uiIconScale`.

### Numeric framing for separate generation

Record a common source canvas, per-part visible bounds, rim/occlusion geometry and base anchor. Supply numbers as composition targets, then use deterministic export for final scale and placement; generation does not guarantee coordinates. Preserve visible tips, spacing and joins while extending hidden geometry when required.

Record source bounds, projected visible size and source pixels per output pixel after all transforms. Require at least one native source pixel per output pixel after placement and final export, choosing higher density before generation when needed; regenerate rather than enlarge inadequate source detail. Uniform reduction is acceptable when final detail, bounds and anchors hold. A fixed minimum reduction factor is not evidence of quality. Broad shapes and contours still need judgment.

### Silhouette and detail

Make objects recognizable through their outer shape and a few large divisions. Keep gaps open after reduction. Match the mod's approved contours. For a RimWorld-style family, use dark exterior and inter-material borders; show same-material facets and overlap through broad shading, spacing or silhouettes rather than black internal seams. Empty openings may remain dark. Keep only detail that communicates construction, material or identity at normal zoom.

### Materials and shading

Use a few principal light/body/shadow values per material while preserving antialiasing and modest variation. Avoid photographic lighting or noisy texture added for a large preview. Make crystalline materials read through angular shape and broad planes rather than flame-like gradients. Give housings readable rims, depth and material joins under construction tint.

### Camera and family consistency

Match approved camera, depth, lighting, contour weight and detail density. Keep each family's distinctive motifs and silhouettes. A taller object is not a front-view illustration placed on the map, and a horizontal view is not automatically a rotated vertical painting. Project designs decide palettes, parts, footprint exceptions and protected assets.

### Glow and motion

Keep environmental glow/particles separate from the solid sprite unless baked effects are approved. The object should read with the effect off. Judge particle size, density, travel and lifetime at game zoom and speed; a pleasing browser preview can resemble unintended steam or condensation in-game.

## Material-mask encoding

The following single-channel construction-tint notes were verified against the installed RimWorld 1.7/Waylith renderer on 2026-10-29. Recheck shaders and native lookup for another runtime or graphic type; this is not a universal multi-channel mask specification.

| Region | Red | Green/blue | Alpha |
| --- | --- | --- | --- |
| Full construction tint | 255 | 0 | 255 |
| Fixed color, protected contour or opening | 0 | 0 | 255 |
| Antialiased material coverage | 1–254 | 0 | 255 |

Opaque black excludes tint; it does not make the color sprite opaque. The color sprite retains its transparency. The recorded `MaskGate.glsl` and `CutoutComplex.frag.glsl` behavior is:

```text
gate = clamp(sampledMaskAlpha * 255, 0, 1)
weight = sampledMaskRed * gate
output = sampledColor * (1 - weight + weight * constructionColor)
```

RGB bleed into transparent texels can create excessive tint at a filtered boundary when even a small alpha makes the gate one. Store exclusions as opaque black and fractional coverage in red for this encoding. Inspect legacy coverage before conversion: applying alpha coverage twice can weaken a boundary. A historical alpha-coverage repair used `round(oldRed * clamp(oldMaskAlpha / colorAlpha, 0, 1))`, zero where color alpha was zero and new alpha 255; that formula is specific to that input encoding.

Match the consuming graphic's native mask naming convention. Single and directional graphics can differ; verify lookup rather than guessing underscore placement.

## Renderer and menu icons

### Diagnose the layer before regenerating artwork

| Symptom | Compare first | Likely change |
| --- | --- | --- |
| Broken contour without tint | Raw sprite and tinted output | Source outline |
| Fringe or fixed-color darkening under tint | Ownership, channels, independently filtered mask | Mask partition/encoding |
| Bright map object, dim whole menu icon | Native icon material and plain override | UI rendering/definition |
| Correct source looks compressed | Aspect, padding, draw size, footprint | Export/display proportions |
| Features change across rotations | Every view and approved master | Variant geometry/placement |
| Trees or wall attachments overlap unexpectedly | Layers, depth and reversed positions | Draw ordering |

A larger canvas does not repair a wrong contour, ownership region or rendering path. Change the layer supported by the comparison.

### Filter before applying tint in a renderer model

Sample sprite and mask independently at target size before applying shader equations. Compositing at full resolution before downsampling can hide game filtering failures. State loader/filter/bleed approximations; a CPU model is not exact GPU evidence.

### Preserve the UI material

Vanilla often ships dedicated `_MenuIcon` textures, so a dedicated icon is a normal choice. The caveat concerns tint: in the recorded 1.7 runtime, an explicit `uiIconPath` selects the plain-texture branch of `BuildableDef.PostLoad`, bypassing `ResolveIcon` and its mask-aware UI material. For tintable objects, prefer native graphic-derived icons when framing permits. For a dedicated icon, verify its matching mask and UI material path. A nearby mask file alone does not prove it is used; untinted objects can legitimately use plain icons.

### Calculate scale from the actual native function

For graphic-derived icons, the recorded `GenUI.IconDrawScale` uses:

```text
effectiveScale = uiIconScale * min(drawSize.x / footprint.x,
                                  drawSize.y / footprint.z)
```

Build commands apply a further `0.85` factor in `Command.DrawIcon`. Texture aspect fitting, alpha bounds, padding, offsets and call site also matter. Using the larger ratio can make the correction wrong. Inspect `defaultPlacingRot` for the chosen directional sprite/mask. Consuming XML owns current values; recheck native functions for another version.

### Treat draw ordering as renderer behavior

Inspect comparable vanilla definitions, inherited drawing modes/layers, footprints, offsets and mesh behavior. One altitude does not define a complete screen-position sort. Test both the reported arrangement and reversed foreground/background positions; raising every tall object may solve one overlap and break another. Record tradeoffs separately from icon scale and painted perspective.

## Prompt scaffold

Supply real references and fill only relevant fields:

> RimWorld object sprite matching reference A's camera, contour weight, broad shading and detail density at game zoom. Heavy unbroken black contour and a few large shapes. [Shading and colour as the house-style reference shows them.] Reference B controls [shape]; C controls [palette]. Draw [object and exact parts/counts]. Preserve [silhouette, proportions, spacing, material joins]. Change only [regions/properties]. Use [material colors] and broad readable planes with smooth antialiasing. Dark borders on exterior/inter-material seams; same-material form through shading. [Direction] view of the same approved object[; east view must read correctly when mirrored for west, so no text or one-sided details]. Genuine transparency, complete object, [canvas/framing].

For local edits specify protected regions and newly exposed surfaces. Describe geometry instead of repeatedly requesting more detail. Preserve accepted prompts and selected sources in the mod's artwork record.

## Acceptance record

Keep one approval record per piece: the approved texture's hash, the author's words and the date, in the mod's own registry, where its checks can fail when an approved texture changes. Mask and computed views add their hashes when finished. In-game confirmation is a separate, single review at the end of a body of work, recorded with what was loaded. Approval of one view or material does not approve the others. Finish authorized work and state any remaining review explicitly.

## Sources

Project-specific requirements and histories belong in each mod's own artwork documents; they are not defaults for other mods.

Vanilla conventions were sampled from Ludeon's public art source (Odyssey zip, browser previews) on 2026-11-09. Vanilla rendering figures were measured from an extracted copy of the core zip on 2026-11-10.

Primary renderer evidence: installed `Data/Core/Shaders/MaskGate.glsl`, `Map/CutoutComplex.frag.glsl`, `Map/CutoutComplexUI.frag.glsl`, and native `BuildableDef.PostLoad/ResolveIcon`, `GenUI.IconDrawScale`, `Designator_Build`, `Command.DrawIcon`. Technical notes retain their original version/date scope; recheck them against another game build before relying on them.
