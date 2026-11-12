# Publish a mod release

Use this workflow for `$steam-workshop-utils publish`, `publish an update`, or `publish a new mod`. These are skill instructions, not standalone shell commands. A publish request authorizes uploading the selected release, its description, main preview, relevant screenshots, a useful Steam change note, and a public release comment. Honor exclusions such as "no comment" or "keep the existing preview". Configuring the skill does not authorize a live upload.

## Find the item first

1. Resolve the project, game App ID, release version, mod name, and publishing account from confirmed evidence. Check the source manifest, existing upload VDF, project `workshop-item.json` if present, README/Steam links, and the corresponding installed mod manifest when its path is known. Conflicting IDs require resolution rather than choosing one.
2. Verify candidates against fresh Steam metadata or the owner's signed-in page. Confirm consumer App ID, mod identity, creator, and publishing permission. A title match alone is insufficient. With no recorded ID, check the owner's published items for that game using the exact mod name and known project links. Keep the search bounded and owner-specific. Cached results can identify candidates but cannot establish ownership or absence.
3. If one existing owned item is confirmed, update it. If results are missing, inaccessible, ambiguous, or belong to someone else, ask: "What is this mod's Workshop ID or URL, or should I publish a new item?" Show candidate links when helpful. A failed search does not authorize creation. Continue local preparation while waiting, but wait for the answer before uploading.
4. An explicit `publish a new mod` request authorizes creation after the duplicate check. If an existing owned item is found, ask whether to update it or intentionally create a separate item. Otherwise no additional creation confirmation is needed. Resolve the title and visibility; an unqualified new publication means public visibility unless the user specifies otherwise. State that choice before submission.

Completion: a verified existing item ID or explicitly authorized new item after the duplicate check, plus a confirmed game App ID and publishing account.

## Load the game context

After resolving the game, read only its matching context before choosing package paths or publishing tools:

| Game | App ID | Context |
| --- | --- | --- |
| Wayward | `379210` | [games/wayward.md](games/wayward.md) |
| RimWorld | `294100` | [games/rimworld.md](games/rimworld.md) |

Select routes separately for content upload, item creation, metadata, and change notes. Use SteamCMD first where supported. A recorded limitation within the same scope is sufficient reason to use the specified browser or in-game route without repeating a failed attempt. Unverified means the route needs investigation, not that it is unsupported. Recheck conflicting evidence or behavior affected by game/tool updates against current official documentation or the installed publisher. For an unlisted game, establish its publishing route before uploading. These files guide tool choice; they do not expand the requested actions.

Keep each game context short, with identity and review date, a publishing-routes table, game-specific constraints, and evidence links. Label capabilities as documented, observed, or unverified. Record observations with the item, date, relevant game/tool version when known, and what was actually verified. Reserve unsupported claims for evidence establishing that limit. Keep shared authentication, gallery, comment, and verification rules here rather than duplicating them in every game file.

Completion: each requested action has a supported route or an explicit unresolved blocker, and the upload format is established.

## Prepare local artifacts first

Check for local documentation before drafting anything. Use existing project files as the publication source. Treat their copy as already unslopped: reuse it without rewriting, refreshing, reformatting, or running `$unslop` again. A publish request alone does not request edits to existing documents. Check identity, release version, and supported Steam formatting without modifying prose; report material inconsistencies rather than silently fixing them.

Resolve GlobalTemplates as described in this skill's `AGENTS.md`. Read its `template-routing.md` and the applicable template only when a document is missing or the user explicitly requests edits. Create missing applicable artifacts in the project before publication:

- `steam-description.md` from `Steam/steam-description-template.md`, using confirmed released behavior and Steam BBCode.
- `README.md` from `Git/readme-template.md`.
- `CHANGELOG.md` from `Git/change-log-template.md`, using implemented user-facing changes and confirmed release metadata. Preserve historical entries when explicit edits are requested.
- `TESTING.md` from `Git/testing-template.md` only when its creation is explicitly requested. Reuse an existing file unless edits were requested.
- Game metadata from its applicable template, such as `Steam/wayward/wayward-mod-json-template.md` or `Steam/rimworld/rimworld-about-xml-template.md`, only when missing or explicitly requested. Preserve stable identifiers and release metadata; publication alone does not justify a version bump.

Apply the public-copy rules in [update-workshop-item.md](update-workshop-item.md) and `$unslop` only to newly written copy or copy changed under an explicit editing request. Existing unchanged documents skip that pass.

Reuse existing `workshop-changenote.md` and `workshop-update-comment.md` when they cover the release being published, without rewriting or running `$unslop` again. If missing, derive and save them from the local changelog's latest verified user-facing changes, then apply `$unslop` to the new copy. If an existing draft refers to another release, report that mismatch and ask whether to refresh it. Exclude test results, validation/build/deployment reports, and internal process from new or explicitly edited copy. With no useful changes, omit an empty note or manufactured comment and explain why. For a first release, describe initial useful features rather than claiming prior fixes.

Publish the saved files rather than generating prose during submission. README, changelog, and testing files stay local or enter the mod package according to its release conventions; Steam has no separate README/changelog upload field.

## Prepare release and media

Run the project's existing release/build/package procedure and relevant checks. Inspect final contents and paths. Confirm the game's accepted upload format before selecting `contentfolder`; some games need an archive or specific directory layout. Keep credentials, upload drafts, logs, and agent research out of the uploaded content. Follow existing package conventions rather than uploading the entire working directory.

Reuse the current icon and Workshop preview. In-game icons and the main Workshop preview are separate assets; reuse one for both only when the project supports it. Inspect images and current Steam size/format limits before upload. If an icon is missing, use the appropriate image skill and match the established style. Preserve existing art unless a change is needed or requested.

Use relevant local gameplay screenshots, or capture real screenshots of the release when the game and capture tools are available. Save assets locally first. Generated art can be a preview or icon, but not evidence of gameplay. If capture is unavailable, retain the current gallery, report that limitation, and ask for screenshots if required to fulfill the request. Do not claim unavailable screenshots were captured or uploaded. On updates, compare the gallery before adding or replacing media, avoid duplicates, and preserve unrelated images.

Completion: applicable documents, upload package, preview, screenshot assets, note, and comment are prepared locally. Summarize identity, version, visibility, upload paths, and media changes before submission. The publish request supplies authorization; resolve actual identity/login/tool blockers without another routine approval round.

## Publish through the selected route

Apply the game context's route for content and creation. When it selects the in-game publisher, follow the installed game's publishing procedure and accepted package layout. Inspect any description, preview, tags, or visibility that the game submits alongside content and reconcile them with the prepared sources and requested scope before submission. Verify the returned item ID and preserve the game's identity file; persist a verified new ID in project identity metadata and relevant links. After an uncertain creation, inspect the game's result, identity file, logs, and owner's items before retrying. If the game cannot be operated with available tools, leave the release prepared and explain the specific user action required.

Use the following VDF procedure only for actions whose selected route is SteamCMD. For a metadata-only step, omit `contentfolder` and unrelated fields; treat change notes according to the game context rather than assuming a successful metadata update saved them.

Follow the platform-aware SteamCMD discovery, authentication, and fallback rules in [update-workshop-item.md](update-workshop-item.md). Let the user enter credentials or Steam Guard themselves if needed. Keep passwords and codes out of arguments, files, logs, and chat.

Prepare a project-local VDF outside the uploaded content. Use Valve's documented fields with escaped quoted KeyValues strings and literal multiline description text:

| Field | Existing update | New item |
| --- | --- | --- |
| `appid` | Verified game App ID | Verified game App ID |
| `publishedfileid` | Verified nonzero ID | `0` after creation authorization |
| `contentfolder` | Checked release content path | Checked release content path |
| `description` | Saved description | Saved description |
| `previewfile` | Prepared preview, or omit to preserve | Prepared main preview |
| `title` | Omit unless a rename was requested | Confirmed mod title |
| `visibility` | Omit unless a change was requested | Resolved visibility; public is `0` |
| `changenote` | Saved useful note, if any | Saved initial release note, if any |

The existing `scripts/prepare_workshop_update.py` is description-only and rejects creation. Prepare a full-release VDF separately; its `quote_vdf` utility can help with escaping. Do not silently broaden the helper or invent fields for gallery screenshots, comments, dependencies, or unsupported game metadata.

In an authenticated owner session, run `workshop_build_item <absolute-vdf-path>`. Inspect SteamCMD's result, logs, and live item. Process exit alone is insufficient. SteamCMD writes a successful creation's ID back into the VDF. Immediately persist the verified ID in established project identity metadata and update relevant project links. If current manifest rules reject Workshop IDs, save `workshop-item.json` containing `appid` and `publishedfileid` instead. Subsequent runs must use that ID, never reset it to zero.

After an uncertain creation, check the rewritten VDF, upload logs, and owner's recent items before retrying. If identity remains unknown, stop for resolution instead of another zero-ID upload. Allow one corrected retry of a confirmed failed update under the existing verification rules.

An available authenticated browser is a fallback for supported metadata/media actions after a concrete SteamCMD blocker or a recorded game-context limitation for that action. It substitutes for a binary upload only if the game's actual owner interface supports uploading content. Otherwise use the established in-game route or preserve the prepared package and report the blocker.

## Gallery and public comment

SteamCMD's documented VDF supports the main preview, not gallery images or public comments. For screenshots, prefer an authenticated Steamworks tool with additional-preview operations. Otherwise use the owner's signed-in gallery editor through available browser tools as a capability fallback and explain that reason. Check the gallery to avoid duplicates and preserve existing images unless replacement is intended.

After the release succeeds, post the saved comment using [Optional public update comment](update-workshop-item.md#optional-public-update-comment). `publish` includes this action by default unless excluded. Available authenticated browser tools are the capability fallback for comments; a SteamCMD change note is a separate feature. Follow the account/item checks, duplicate prevention, and live verification. After a failed release, leave the draft without announcing success. If the comment already exists, report it rather than posting twice.

## Verify and finish

Verify item ID, uploaded release, description/version, preview, requested gallery changes, change note, and comment separately. Use upload logs and live metadata/downloadable content evidence for binaries; an updated description alone does not prove the release uploaded. State limits when content-version evidence cannot be inspected. Confirm visibility and let the user accept the Workshop legal agreement themselves if Steam requires it.

Keep successful publication actions if a gallery/comment step fails. Report item link, release, local artifacts, documentation, media, note, comment, and remaining work. Save enough local outcome evidence to resume without another creation or duplicate comment. Skill configuration and offline validation do not upload a real mod.

## Official references

- [SteamCMD fields, creation, ID persistence, and logs](https://partner.steamgames.com/doc/features/workshop/implementation#SteamCmd)
- [Additional preview images](https://partner.steamgames.com/doc/api/isteamugc?language=english#AddItemPreviewFile)
