# Timberborn manifest.json Template

## Use when

Use this template only when the user explicitly requests template-backed Timberborn metadata. Create or update `manifest.json` only when the repository clearly targets Timberborn or the user explicitly identifies it as a Timberborn mod.

## Evidence

Look for an existing `manifest.json`, `version-*` folders, `*.blueprint.json` files, `Localizations/*.csv`, `workshop_data.json`, references to `Timberborn.*.dll` or `Bindito.Core`, and clear project documentation. Infer only values supported by project files or direct instructions. Field behaviour is recorded in [game facts](game-facts.md#mod-discovery-and-manifest), verified on game version 1.1.2.8.

## Output

Write strict JSON with no comments, trailing commas, raw control characters (escape newlines as `\n`), prose, BBCode, Markdown, or unresolved placeholders. The game's parser tolerates some of these, but strict tools and validators do not. Preserve existing indentation and key order when updating.

Required fields:

- `Name`: player-facing name. The in-game Workshop uploader uses it as the item title.
- `Version`: the mod's version, dot-separated integers such as `1.2.0`. Anything after a `-` is ignored; a non-numeric part fails the manifest.
- `Id`: stable, globally unique identifier other mods depend on, namespaced such as `AuthorName.ModName`. Must be non-empty.
- `MinimumGameVersion`: earliest supported game version in the same numeric format. It only adds a mod-manager warning on older games; it does not block loading.

Optional fields:

- `Description`: plain-text summary. The in-game uploader offers it as the Workshop description.
- `RequiredMods`: array of `{ "Id": "...", "MinimumVersion": "..." }`. Loaded first; a missing or older one shows a warning. `MinimumVersion` defaults to `0`.
- `OptionalMods`: same shape, usually `Id` only. Loaded first when present, with no warning when absent.

The game reads no other keys. Preserve community extras such as `ModIOID` or `AuthorName` in an existing file, but do not add them expecting an effect.

Example:

~~~json
{
  "Name": "Example Mod",
  "Version": "1.0.0",
  "Id": "AuthorName.ExampleMod",
  "MinimumGameVersion": "1.1.2.0",
  "Description": "Adds a concise player-facing improvement to Timberborn.",
  "RequiredMods": [
    {
      "Id": "Harmony",
      "MinimumVersion": "2.3.3"
    }
  ],
  "OptionalMods": []
}
~~~

Add the `Harmony` dependency only for a code mod that patches with Harmony; the game does not ship it.

## Version folders

When the mod has `version-*` folders, the game ignores the root and reads the `manifest.json` inside the chosen folder. Edit every affected folder's manifest, keep `Id` identical across them, and set each `MinimumGameVersion` no higher than its folder's version.

## Update rules

For an existing file:

- Preserve `Id`, dependencies and their minimum versions, `MinimumGameVersion`, extra keys, and the folder layout unless the requested change affects them.
- Preserve `workshop_data.json` and its `ItemId`; it ties uploads to the existing Workshop item.
- Change `Name` or `Id` only when explicitly requested. Changing `Id` breaks every mod that depends on it.
- Remove fields only when they are invalid, obsolete, duplicated, or explicitly requested.

For a new file, ask for required values that cannot be inferred. Do not guess authorship, dependency IDs, or the minimum game version. For a fork or continuation, ask whether the original `Id` must be preserved.

## Public copy

Run the installed `unslop` skill on the `Description` value only after drafting and before delivery. Reinsert the edited value without changing JSON structure, escaping, or any other field.

If `unslop` is unavailable, apply the rules in `writing-copy.md` manually and state in the delivery summary that `unslop` was unavailable.

## Version and description

Bump `Version` only for completed behavior, compatibility, or feature changes and keep it synchronized with other project version fields and every version folder that ships the change. Raise a dependency's `MinimumVersion` only when the mod needs that version's behaviour. Do not bump for documentation, formatting, exploration, failed work, or mechanical edits. Ask when the correct bump is ambiguous.

Keep `Description` shorter than the Workshop description. Exclude changelog, README, license, and Markdown or BBCode.

## Validation

Parse every edited `manifest.json` as strict JSON and confirm:

- `Name`, `Version`, `Id` and `MinimumGameVersion` are present and non-empty.
- `Version`, `MinimumGameVersion` and every `MinimumVersion` are dot-separated integers.
- Dependency arrays hold objects with an `Id`.
- `Id` is unchanged unless authorized, and identical across version folders.
- No placeholders, raw control characters, Markdown, or BBCode remain.
- Version changes follow project policy.

## Delivery

Write the result to `manifest.json` in the mod root or each affected `version-*` folder. Return a concise field-change summary and validation result. Do not reproduce the full JSON in chat unless requested.
