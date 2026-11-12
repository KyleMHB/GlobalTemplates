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
~/.steam-workshop/steam-workshop.sqlite
```

Override with `--db` or `STEAM_WORKSHOP_DB`. If neither is set and the new default does not exist, both scripts reuse an existing `~/.codex/data/steam-workshop/steam-workshop.sqlite` cache. No files are moved or deleted.

Core tables:

- `workshop_items`: one row per successfully observed Workshop item, including raw Steam JSON. `last_metadata_sync` is the time of the actual successful metadata observation and is not advanced by failed attempts.
- `workshop_description_versions`: the structured current mod-version declaration extracted from the item title or description, including declared, missing, and ambiguous outcomes, the supporting excerpt, limitations, and the successful metadata observation time.
- `workshop_artifact_versions`: bounded, data-only `mod.json` inspection evidence for a Workshop ZIP. Successful evidence records the semantic version, manifest path, observation time, and Steam content reference. The latest attempt fields separately retain unavailable, unsupported, malformed, or bounded outcomes; a failed attempt never overwrites prior successful evidence.
- `collections`: collection-to-child mapping.
- `comments`: available public comments, keyed by stable Steam comment ID when available and carrying author identity, display name, profile URL, original posted time, source link, and a separate collection time. `legacy_fragments_json` records old fragment hashes for author, visible timestamp, and body nodes observed inside that canonical comment's DOM ancestry. Duplicate hashes are retained on every matching canonical comment so consumers can surface ambiguity. Legacy text-keyed rows remain valid cache records.
- `comment_sync_state`: restart-safe `complete`, `partial`, or `failed` coverage plus observed totals, the backfill and revisit cursors, and the latest provider error.
- `evidence`: extracted snippets grouped by category.
- `sync_failures`: current failure by item and stage. A successful attempt clears the matching stage failure; `last_seen` identifies the failed attempt and does not replace a prior successful observation time.
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
- Fetch a bounded number of comment pages per item and resume from persisted state on the next manual sync.
- Fetch comments only when `workshop_items.creator` is present; record a comment sync failure instead of calling the comment endpoint without a creator SteamID.
- Store canonical comments with Steam's stable comment ID so position shifts, body edits, and author enrichment update the same row. Existing text-keyed cache rows remain readable for compatibility. Repeated and overlapping pages are idempotent, and absence from an incomplete fetch never deletes cached history.
- Derive legacy fragment mappings only while parsing nodes within a canonical comment container. A fragment's text or display name is supporting evidence and may map to several comments; it is not a unique identity by itself.
- Continue on per-item failures and record the failure.
- Treat a requested item omitted from the metadata response as a metadata failure. Preserve any older successful `workshop_items` row and its `last_metadata_sync` so consumers can show stale Evidence alongside the failed current attempt.
- Artifact downloads are capped at 8 MiB. ZIP inspection is capped at 2,048 entries, 32 MiB declared uncompressed content, and 256 KiB per `mod.json`. Never extract or execute archive content. A cached artifact version applies only while its recorded content reference matches the current successful Workshop metadata observation.
- Do not refresh during report generation.
- Do not download images or media.

## Compatibility Notes

Steam endpoints and community HTML can change. If comment parsing starts returning empty comment sets for active items, inspect the raw response shape before changing report logic.
