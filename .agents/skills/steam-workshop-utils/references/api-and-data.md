# Steam Workshop API And Data

Use this reference when changing request behavior, API endpoints, or the SQLite schema.

## Data Sources

- Metadata: `ISteamRemoteStorage/GetPublishedFileDetails/v1/`.
- Collections: `ISteamRemoteStorage/GetCollectionDetails/v1/`.
- Comments: Steam Community comment rendering for `PublishedFile_Public` using `/comment/PublishedFile_Public/render/{creator_steamid}/{publishedfileid}/`.

Prefer official Web API endpoints for metadata and collection expansion. Use `STEAM_WEB_API_KEY` when available, but keep public fallback behavior where Steam permits it.

## Local DB

Default DB path:

```text
~/.codex/data/steam-workshop/steam-workshop.sqlite
```

Override with `--db` or `STEAM_WORKSHOP_DB`.

Core tables:

- `workshop_items`: one row per Workshop item, including raw Steam JSON.
- `collections`: collection-to-child mapping.
- `comments`: recent public comment text, capped per item by sync settings.
- `evidence`: extracted snippets grouped by category.
- `sync_failures`: latest failure by item and stage.
- `modlists`: named saved modlist profiles.
- `modlist_items`: current membership for each named list, with `active` or `archived` status.

Report-time tables:

- `resolved_evidence`: manually resolved Basic Check evidence rows.

## Named Modlist Resync

- `resync --list NAME` compares supplied current Workshop IDs against `modlist_items`.
- Preview mode is read-only and does not create the DB if it does not exist.
- `--apply` creates/updates the named list, marks supplied IDs active, and marks removed active IDs archived.
- Re-added archived IDs are restored to active state without deleting existing cached data.
- Applied resync refreshes added mods and unchanged active mods whose `last_metadata_sync` is older than 24 hours.
- `purge-archived --list NAME` previews archived entries for that named list.
- `purge-archived --list NAME --apply` deletes archived IDs for that list from `modlist_items`, `workshop_items`, `comments`, `evidence`, `sync_failures`, `resolved_evidence`, and related `collections` rows.

## Request Policy

- Batch metadata requests.
- Fetch comments with limited concurrency.
- Fetch comments only when `workshop_items.creator` is present; record a comment sync failure instead of calling the comment endpoint without a creator SteamID.
- Store comments with stable text-based keys so shifted Steam comment positions update existing rows instead of creating duplicates. Each sync removes previously cached comments that are no longer in the retained recent-comment window.
- Continue on per-item failures and record the failure.
- Do not refresh during report generation.
- Do not download images or media.

## Compatibility Notes

Steam endpoints and community HTML can change. If comment parsing starts returning empty comment sets for active items, inspect the raw response shape before changing report logic.
