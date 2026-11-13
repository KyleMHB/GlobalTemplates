# RimWorld Workshop context

App ID: `294100`  
Reviewed: 2026-11-13  
Observed on item `3838124135` with SteamCMD `1794425457` and RimWorld 1.7.5005. The in-game publisher was not used.

## Publishing routes

| Action | Route | Status and limits |
| --- | --- | --- |
| Update content, description, main preview, title or visibility of an existing item | Steam client route (`scripts/publish_via_client.py` with the game's `steam_api64.dll`); SteamCMD second | Client route: a tag-only update was observed working 2026-11-13 and left the desktop client signed in; content, description, preview, title and visibility have not been sent through it yet, so verify the first of each closely. SteamCMD: observed working 2026-11-12 and 2026-11-13 for content, description and preview, and a download of the live item matched the uploaded folder byte for byte. Each SteamCMD login signed the desktop Steam client out. |
| Set tags | Steam client route with `--tags`; in-game publisher otherwise | SteamCMD's documented VDF has no tag field, and the item it created had no tags (observed 2026-11-13). Established RimWorld mods carry `Mod` plus one tag per supported version, such as `1.6` and `1.7`. Pass the full set: `Mod` and every version in `supportedVersions`. Observed working through the client route 2026-11-13: the live item then showed `Mod`, `1.6` and `1.7`, with content, description and visibility unchanged. |
| Create an item | SteamCMD; in-game publisher when its game-managed metadata is needed | SteamCMD creation observed working 2026-11-12, writing the ID back to the VDF. The new item has no tags; set them afterwards. The in-game publisher's controls remain uninspected. |
| Publish a change note | Submit with the content update, then verify | Sent with a SteamCMD content update 2026-11-13; the live change-note entry was not checked. Generic `changenote` support does not prove that a metadata-only submission creates an entry. Do not carry Wayward's observed failure over to this game. |
| Repair an existing change note | Browser owner editor when available | Unverified for a RimWorld item. Check that the owner controls support the requested edit. |

Gallery images and public comments follow the shared publishing workflow. The Workshop web page is not an established binary-upload route.

## Constraints

- Preserve the mod folder's `About/About.xml` and version-specific content layout. Ludeon documents shared root content and version directories for multi-version mods; inspect the project's current loading configuration before packaging.
- Treat `supportedVersions` in `About/About.xml` as declared game compatibility, not the mod's release version. The game's uploader applies corresponding Workshop tags according to Ludeon's documentation. Verify those tags after upload; the generic SteamCMD VDF has no documented field that reproduces this game-specific step.
- Resolve the existing item from project evidence. Check `About/PublishedFileId.txt` when present and verify its value against the live item; its handling by the current publisher remains unverified here. Preserve the existing identity file on updates.
- Upload the mod folder itself as the content folder: the folder holding `About/`, `LoadFolders.xml` and the version folders, as it sits in the game's `Mods` directory. Observed working 2026-11-12.
- After any creation or content upload that did not go through the in-game publisher, read the live tags and set the version tags if they are missing.

## Evidence

- [Official Steam store entry](https://store.steampowered.com/app/294100/RimWorld/) identifies the game App ID.
- [Ludeon multi-version mod documentation](https://ludeon.com/blog/2019/01/1-0-update-brings-multi-version-mod-support/), 2019-01-20, documents `supportedVersions`, shared/version-specific content, and automatic Workshop version tags. This is historical documentation; confirm behavior against the current publisher when it affects the chosen route.
- [Valve SteamCMD fields](https://partner.steamgames.com/doc/features/workshop/implementation#SteamCmd) document generic content, description, preview, creation, and change-note fields. They do not establish RimWorld-specific compatibility or metadata handling.
