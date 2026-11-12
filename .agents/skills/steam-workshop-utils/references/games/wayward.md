# Wayward Workshop context

App ID: `379210`  
Reviewed: 2026-10-06  
Observed SteamCMD version: `1788292693`; Wayward build was not recorded.

## Publishing routes

| Action | Route | Status and limits |
| --- | --- | --- |
| Upload mod content | In-game publisher | Observed implementation packages a ZIP and publishes through legacy RemoteStorage. SteamCMD content upload is unverified; no binary upload completed in the cited investigation. |
| Create an item | In-game publisher | Observed implementation supports creation and writes the returned `publishedFileId` to `mod.json`. Creation was not exercised in the cited investigation. |
| Update description | SteamCMD first; browser fallback | Observed working on a live item. Verify the saved live description. |
| Update main preview | SteamCMD first; browser fallback | Observed working on a live item. Verify the live preview separately. |
| Publish a change note | Submit with the content release through the game's supported note mechanism, then verify | Unverified for content releases. Metadata-only SteamCMD attempts on a live item reported success without saving a note. Inspect the game's note controls before relying on them. |
| Repair an existing change note | Browser owner editor | Observed working on a live item. Editing an entry does not establish that the browser can create a new entry. |

Gallery images and public comments follow the shared publishing workflow. The Workshop web page is not an established binary-upload route.

## Constraints

- Preserve the game's `publishedFileId` in `mod.json`; let the publisher write a new ID and verify it against the live item. Do not invent an ID or clear it to force creation.
- Use the game's ZIP publishing procedure for content. A metadata VDF with no `contentfolder` updates metadata only.
- Inspect the installed publisher's treatment of manifest tags, preview, title, and description before submission. The inspected update implementation omitted title and description for existing items; submit the saved Workshop description separately when required.
- Keep a content release pending until the binary upload succeeds. A metadata update or browser note repair cannot establish that result.

## Evidence

- Investigation of a live Wayward item, 2026-10-06. Description/preview submission succeeded, and an existing blank note was repaired and verified through the browser. Multiline and single-line metadata-only note submissions reported success but created no new live entry. The exact internal cause remains unconfirmed; this is not a universal SteamCMD limitation.
- That investigation inspected `resources/app.asar` under the confirmed Wayward installation, entry `out/js/game/Production.js`, including `publishMod`, archive creation, Steam Cloud sharing, and Workshop submission. Resolve the installed game path from project/user configuration or the Steam library and recheck the implementation if the game changes.
- [Official mod.json reference](https://github.com/WaywardGame/types/wiki/mod.json) documents the publisher-managed ID and game-applied content tags.
- [Valve SteamCMD fields](https://partner.steamgames.com/doc/features/workshop/implementation#SteamCmd) describe the generic VDF route; they do not establish Wayward ZIP compatibility.
