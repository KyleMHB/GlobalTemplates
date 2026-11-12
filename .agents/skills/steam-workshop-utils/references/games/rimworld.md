# RimWorld Workshop context

App ID: `294100`  
Reviewed: 2026-10-06  
No local RimWorld publisher or game-specific SteamCMD submission was tested for this context.

## Publishing routes

| Action | Route | Status and limits |
| --- | --- | --- |
| Upload mod content or create an item | Establish SteamCMD compatibility; use the in-game publisher when its game-managed metadata is needed | Unverified for SteamCMD in RimWorld. Ludeon documents game upload behavior and supported-version tagging, but the current publisher UI and its creation/update controls still need inspection. |
| Update description or main preview | SteamCMD first after confirming compatibility; browser fallback | Documented generic Valve fields; game-specific behavior is unverified. Verify each live result. |
| Publish a change note | Submit with a supported content-release route, then verify | Unverified for RimWorld. Generic `changenote` support does not prove that a metadata-only submission creates an entry. Do not carry Wayward's observed failure over to this game. |
| Repair an existing change note | Browser owner editor when available | Unverified for a RimWorld item. Check that the owner controls support the requested edit. |

Gallery images and public comments follow the shared publishing workflow. The Workshop web page is not an established binary-upload route.

## Constraints

- Preserve the mod folder's `About/About.xml` and version-specific content layout. Ludeon documents shared root content and version directories for multi-version mods; inspect the project's current loading configuration before packaging.
- Treat `supportedVersions` in `About/About.xml` as declared game compatibility, not the mod's release version. The game's uploader applies corresponding Workshop tags according to Ludeon's documentation. Verify those tags after upload; the generic SteamCMD VDF has no documented field that reproduces this game-specific step.
- Resolve the existing item from project evidence. Check `About/PublishedFileId.txt` when present and verify its value against the live item; its handling by the current publisher remains unverified here. Preserve the existing identity file on updates.
- Before selecting SteamCMD for content or creation, establish the accepted package path and how required game-managed tags and metadata will be retained. If unresolved, prepare the release and inspect the in-game publisher rather than guessing an upload format.

## Evidence

- [Official Steam store entry](https://store.steampowered.com/app/294100/RimWorld/) identifies the game App ID.
- [Ludeon multi-version mod documentation](https://ludeon.com/blog/2019/01/1-0-update-brings-multi-version-mod-support/), 2019-01-20, documents `supportedVersions`, shared/version-specific content, and automatic Workshop version tags. This is historical documentation; confirm behavior against the current publisher when it affects the chosen route.
- [Valve SteamCMD fields](https://partner.steamgames.com/doc/features/workshop/implementation#SteamCmd) document generic content, description, preview, creation, and change-note fields. They do not establish RimWorld-specific compatibility or metadata handling.
