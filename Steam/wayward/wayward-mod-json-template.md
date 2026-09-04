# Wayward mod.json Template

## Use when

Use this template only when the user explicitly requests template-backed Wayward metadata. Create or update `mod.json` only when the repository clearly targets Wayward or the user explicitly identifies it as a Wayward mod.

## Evidence

Look for an existing `mod.json`, a `Mod.ts` or `Mod.js` entrypoint, Wayward imports or tooling, and clear project documentation. Infer only values supported by project files or direct instructions.

## Output

Write valid JSON with no comments, trailing commas, prose, BBCode, Markdown, or unresolved placeholders. Preserve existing indentation and key order when updating.

Required fields:

- `name`: stable player-facing name.
- `description`: short, plain-text summary.
- `version`: existing project version format.
- `author`: confirmed author name or names.
- At least one content field supported by the mod.

Common content fields:

- `file`: JavaScript entrypoint, without `.js` when that matches Wayward convention.
- `waywardVersion`: confirmed or tool-generated Wayward version.
- `languages`: language JSON paths, without `.json` when appropriate.
- `customizations`, `imageOverrides`: JSON booleans when matching content exists.
- `stylesheets`: stylesheet paths, without `.css` when appropriate.

Example:

~~~json
{
  "name": "Example Mod",
  "description": "Adds a concise player-facing improvement to Wayward.",
  "version": "1.0.0",
  "author": "Author Name",
  "file": "out/Mod",
  "waywardVersion": "2.12.0-beta",
  "multiplayer": "incompatible"
}
~~~

## Update rules

For an existing file:

- Preserve `publishedFileId`, dependencies, tags, content fields, `waywardVersion`, multiplayer status, and save-safety fields unless the requested change affects them.
- Change the name or externally assigned identifiers only when explicitly requested.
- Remove fields only when they are obsolete, invalid, duplicated, or explicitly requested.

For a new file, ask for required values that cannot be inferred. Do not guess authorship, Workshop IDs, dependency IDs, tags, supported versions, or compatibility.

## Multiplayer and save safety

Valid `multiplayer` values are `clientside`, `compatible`, `serverside`, and `incompatible`. Preserve or omit the field when compatibility is unknown.

Use `unloadable: true` only with evidence that removal is save-safe. Do not mark content-registering mods unloadable without supporting evidence. Use `allowUnlockingMilestones: true` only when explicitly intended.

Dependencies contain exact Steam Workshop `publishedFileId` strings. Use JSON booleans and arrays with their correct types.

## Version and description

Bump `version` only for completed behavior, compatibility, or feature changes and keep it synchronized with other project version fields. Do not bump for documentation, formatting, exploration, failed work, or mechanical edits. Ask when the correct bump is ambiguous.

Keep `description` shorter than the Workshop description. Exclude changelog, README, license, and forking-policy text.

## Validation

Parse the result as JSON and confirm:

- Required fields are present and non-empty.
- At least one supported content field exists.
- Arrays and booleans use the correct JSON types.
- No placeholders remain.
- Stable IDs and preserved fields changed only when authorized.
- Version changes follow project policy.
- Markdown and BBCode are absent.

## Delivery

Write the result to `mod.json`. Return a concise field-change summary and validation result. Do not reproduce the full JSON in chat unless requested.
