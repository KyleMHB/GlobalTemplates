# Building an illustrated Steam Workshop page

Use this guide when creating or revising a mod's Workshop description, explanatory images, thumbnail or gallery artwork. Start with the existing [description template](steam-description-template.md): it owns section order, evidence requirements, version declarations, attribution, license wording and support links. This guide adds the artwork and preview workflow.

## Deliverables

Keep the editable description in the mod repository as `steam-description.md` (Steam BBCode despite the extension). Keep durable images in `docs/images/workshop/` and their rendering scripts in `scripts/`. Keep previews, alternatives, contact sheets and publication captures in ignored `artifacts/`. Store source artwork or generation prompts where the project already keeps them.

The preview tool lives beside this guide as `preview-workshop.py`. It uses Python 3.9 or newer and the standard library. It renders local HTML; it does not upload, edit Steam or verify remote URLs.

## 1. Establish the facts

Read the current source, release metadata, settings, dependencies, license and upstream attribution. Establish the Workshop item ID and repository URL. Record what a fresh install does, how settings take effect, what the player must do, and any actual save risks. Distinguish available features from enabled defaults.

For each numerical illustration, identify the authoritative data and formula. Read presets from mod source or structured configuration and native game values from the corresponding game definitions. Label the preset, enabled effects, baseline and rounding assumptions needed to interpret the result. Changing a preset requires rebuilding its affected images.

Done: every public claim and illustrated number has a source; unresolved compatibility, multiplayer or save claims remain qualified.

## 2. Structure the page

Follow the description template's order. A fork, obsolete or discontinued mod opens with the template's one-line status notice above Description. The agreed illustrated layout is:

1. **Description:** the concrete player benefit and initial behaviour. Include the template's mod-version declaration when authoritative release metadata exists.
2. **Features:** a short scannable list, followed by illustrated feature subsections. Use one heading and short explanation per concept. Put numerical examples here when they help explain a feature.
3. **How to Use:** exact in-game menu path, minimum setup steps and any save/restart requirement.
4. **Settings and Configuration:** additional behaviour players need to understand; avoid repeating the feature pitch.
5. **Requirements and Dependencies:** confirmed requirements.
6. **Compatibility, Load Order, Multiplayer, and Save Safety:** evidenced integrations, load order, limitations and consequences of adding/removing the mod.
7. **Fork History:** required for a fork; explain its purpose and meaningful differences.
8. **Credits**, then **License**, following the template's applicability rules.
9. **Links:** final section when links apply; follow the template for repository and support badges.

Conditional sections follow the template. Integrations belong with compatibility, rather than under an unrelated chart heading. Player-facing content comes before provenance.

Keep group headings, introductions and explanatory notes as native Steam text. Export item catalogues as separate images, one image per item row, so they can be arranged individually. Omit duplicate group headings, subtitles and branding footers inside those images. Keep item names and the details needed to read a diagram beside the artwork.

For BBCode, use `[h1]` for primary sections and `[h2]` for their feature subsections. Keep explanatory prose as actual text so readers can select and translate it. Images carry visual relationships and examples, rather than the entire manual.

Done: the first three content sections are Description, Features and How to Use; Links is last; applicable safety and attribution content is preserved.

## 3. Write the copy

Follow the description template's Credits and "Author voice and image text" sections.

Name what the mod changes and why a player would use it. Use familiar in-game names, concrete verbs and short paragraphs. Distinguish selection from activation, assignment from effects, presets from individual overrides, and native behaviour from added behaviour where relevant.

Explain consequential limits beside their feature: for example, changing market value can affect trade valuation and wealth, while removing stored quality may lose saved tiers. Use only risks supported by the mod. Keep research notes, testing results and agent workflow details out of the public description.

Apply the installed `unslop` skill to newly written or changed `steam-description.md` prose as required by the template. Preserve BBCode, facts, links and identifiers. Reuse unchanged approved copy. Guide prose and internal reports are outside that automatic `unslop` scope.

Done: the text accurately describes the candidate release, reads plainly, and has been through the template's public-copy pass.

## 4. Build the images

One approach that works: deterministic Python/Pillow composition with original local game sprites and the game's font, with the renderer reading values from the mod's settings and the installed game definitions. That keeps the diagrams consistent with the implementation.

Reuse the method, adapting the visual language to the mod:

- Use the actual item artwork with its defined in-game proportions. Centre the visible object on its portrait background, including deliberate offsets for flat objects. Prefer an existing high-resolution portrait over enlarging a tiny directional sprite.
- Give each panel one job: choosing targets, enabling effects, explaining precedence, setting strength or comparing outcomes. Split a panel when it needs unrelated examples to make sense.
- Use relevant sprites and plausible combinations. A bed beside switches for unrelated effects makes the controls harder to understand.
- Make the baseline and changed result easy to compare. Distinguish direct multipliers from percentages, and benefit curves from inverse cost/cooldown curves.
- Show several enabled effects together when the feature allows combinations. Input boxes can illustrate editable factors; label them with the terminology players see in-game.
- Use consistent type sizes and a shared palette across panels. For tier diagrams, match labels and results to tier colours while keeping editable input values white. Include names so colour is not the only cue.
- Centre compositions and trim unused vertical space. Avoid decorative fill beneath line charts. Use clear points and smooth antialiased lines and elbow connectors.
- Check small text at the final preview width. Increase or shorten labels instead of relying on a large source image to make them legible.

The original preview used a **636-pixel content column**. Treat that as a review setting, not a guaranteed Steam dimension. The original rules panel was 1672 × 941; the gallery/title artwork included a 1920 × 1080 image. These are project choices, not universal Steam upload requirements.

On that project, the font needed a plain lowercase `o` in place of its decorative capital `O`, plus a fallback font for `%`. Check glyph coverage before composing labels. Keep font and sprite extraction prerequisites explicit; the existing renderers depend on a local game archive, Pillow, zstandard and a local font. Do not distribute extracted game assets or fonts without checking their terms.

Done: inspect every panel at preview width; labels fit, numbers match the current mod and the panel communicates its intended relationship.

## 5. Host and preview

Published `[img]` tags need publicly accessible image URLs. Keep a local file for each hosted image. Prefer a durable release or maintained branch path; check that a temporary feature branch will survive before publishing its URLs. The local preview cannot establish that a URL is publicly accessible.

Generate a preview from the Templates checkout root. These examples use a sibling `MyMod` checkout; substitute the confirmed project paths and use `python3` if that is the environment's Python command:

```text
python Steam/preview-workshop.py ../MyMod/steam-description.md --output ../MyMod/artifacts/workshop-description-preview.html --title "My Mod: Workshop preview"
```

For hosted images that have local equivalents, map their URL prefix to the local folder. Keep the trailing slash on the prefix. Use the actual confirmed repository URL:

```text
python Steam/preview-workshop.py ../MyMod/steam-description.md --output ../MyMod/artifacts/workshop-description-preview.html --image-map "https://raw.githubusercontent.com/OWNER/REPO/refs/heads/main/docs/images/workshop/=../MyMod/docs/images/workshop"
```

Repeat `--image-map` for multiple hosts/folders. Longer prefixes take precedence. Relative image paths resolve beside the description. Mapped or relative images must exist; unmapped remote images remain remote and produce a warning. The file uses absolute local image URLs, so regenerate it after moving the project.

### Preview the Workshop thumbnail and gallery

Pass `--thumbnail` for the Workshop item icon and repeat `--gallery` for each gallery image, in its intended order. The page places a large gallery viewer and clickable image strip above the description, with the item thumbnail in the right-hand summary panel, following Steam's item-page arrangement. The panel stacks below the gallery on narrow screens. GIF thumbnails remain animated.

```text
python Steam/preview-workshop.py ../MyMod/steam-description.md --output ../MyMod/artifacts/workshop-page-preview.html --title "My Mod" --game "RimWorld" --author "Your Name" --thumbnail ../MyMod/About/Preview.gif --gallery ../MyMod/docs/images/workshop/title-1920x1080.png --gallery ../MyMod/docs/images/workshop/settings.png
```

Use the project's actual media paths. These flags accept local PNG, JPG, GIF and WebP files; relative flag paths resolve from the command's working directory. Combine them with `--image-map` for inline description illustrations. Omitting both media flags keeps the description-only preview. Supplying only one shows a clear missing-media message for the other.

Click a gallery thumbnail, use Previous/Next, or focus a gallery control and press the left/right arrow keys to change the displayed image. Inspect the main artwork, smaller gallery thumbnails and item icon for readable lettering and cropping. The viewer fits the complete image within a 16:9 frame; it does not stretch the artwork. This local preview approximates Steam's layout and does not fetch or verify the currently published gallery, item statistics or upload limits.

The tool prints the description length and warns when it exceeds Steam's 8,000-character limit, which includes BBCode tags.

Open the HTML in a local browser. Regenerate and reload after editing the source or images. Use `--width 360` with a separate output file for a narrow-column pass. Review the complete page once, batch corrections, then check the changed panels.

The supported subset is headings h1–h3, bold, italic, underline, strike, lists, numbered lists, HTTP(S) links in both `[url=...]` and `[url]...[/url]` forms, images, linked images and dividers. Tag names are case-insensitive. Unsupported tags are shown literally with warnings; unbalanced supported tags stop generation. The renderer checks structure and local image existence, while section order, claims, typography and public URL availability remain review tasks.

Done: the preview renders the actual description and current local assets with no unexplained markup or missing images.

## 6. Publish the requested parts

Treat description text, inline hosted images, Workshop thumbnail/icon, gallery media, downloadable mod content and release notes as separate deliverables. Updating one does not establish that the others changed. A description update alone can leave the icon and gallery stale until a separate publication pass.

When publication is requested, use the installed Steam Workshop publishing workflow and the game's supported route. Resolve the existing item before creating anything. That skill owns current SteamCMD/browser choices and authorization rules; this guide does not grant publication or public-comment permission.

Check the live description, external images, thumbnail and gallery for the parts requested. Compare representative chart values to the candidate release. Report any part that remains unverified. Preserve useful changelog content and prepare release notes when the authorized publishing workflow calls for them.

Steam's [formatting reference](https://steamcommunity.com/comment/Announcement/formattinghelp) documents the basic markup. Its [UGC API reference](https://partner.steamgames.com/doc/api/isteamugc?language=english) exposes description, primary preview and additional preview operations separately. Consult the game's current publishing requirements for thumbnail formats and limits rather than assuming the inline image dimensions apply.

## Reusable boundary

The preview has no hardcoded title, image list, working directory or Pillow dependency. Keep game-specific asset extraction and statistical calculations in each mod's own scripts. This avoids turning a description preview into a game-specific publishing framework.
