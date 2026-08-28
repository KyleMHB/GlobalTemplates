# Local Game Modlists

Use this reference when the user asks to check currently enabled mods for a game.

## Workflow

1. Identify the exact game and platform context.
2. Search official docs, wiki pages, or well-established community docs for the game's modlist/config locations.
3. Cite the sources used for path discovery.
4. Inspect only documented paths and user-provided paths.
5. Determine whether the file format distinguishes enabled and disabled mods.
6. Extract Workshop IDs only when they are represented directly or can be mapped from documented Steam Workshop metadata.
7. Feed extracted IDs into `scripts/sync_workshop.py`, `scripts/sync_workshop.py resync --list NAME`, or `scripts/report_workshop.py`.

## Resync Workflow

- Use documented game config paths or user-provided paths to extract the current enabled Workshop IDs.
- Preview membership changes with `scripts/sync_workshop.py resync --list NAME --ids "..."`.
- Apply only after the user accepts the diff: `scripts/sync_workshop.py resync --list NAME --ids "..." --apply`.
- Removed mods become archived in the named list and are hidden from `report_workshop.py --list NAME` by default.
- Use `report_workshop.py --list NAME --include-archived` only for audit/debug reports.
- Use `purge-archived --list NAME --apply` only when the user wants archived mods permanently deleted from the local cache.

## Constraints

- Do not broadly scan the disk.
- Do not infer enabled/disabled state if the game does not store it in the inspected files.
- If a game supports named presets, list detected presets and ask the user which one to analyze unless the request already names one.
- Keep game-specific parsers outside v1 unless the user explicitly asks to add a maintained adapter.
