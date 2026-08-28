# RimWorld About.xml Template

## Use when

Use this template only when the user explicitly requests template-backed RimWorld metadata. Create or update `About/About.xml` only when the repository clearly targets RimWorld or the user explicitly identifies it as a RimWorld mod.

## Evidence

Look for an existing `About/About.xml`, RimWorld folders such as `Defs`, `Patches`, `Textures`, `Assemblies`, `Languages`, or `Sounds`, Verse or Unity references, and clear project documentation. Infer only values supported by project files or direct instructions.

## Output

Write valid XML with `<ModMetaData>` as the root. Include the UTF-8 XML declaration unless an existing file safely omits it. Preserve formatting, element order, comments, and established structure when updating.

Required fields:

- `<packageId>`
- `<name>`
- `<author>` for one author or `<authors>` with `<li>` entries for multiple authors
- `<description>`
- `<supportedVersions>`

Example:

~~~xml
<?xml version="1.0" encoding="utf-8"?>
<ModMetaData>
  <packageId>authorname.modname</packageId>
  <name>Example Mod</name>
  <author>Author Name</author>
  <description>Adds a concise player-facing improvement to RimWorld.</description>
  <supportedVersions>
    <li>1.6</li>
  </supportedVersions>
  <modVersion>1.0.0</modVersion>
  <url>https://github.com/example/example-mod</url>
</ModMetaData>
~~~

## Preservation and safety

For an existing file:

- Preserve `packageId`, supported versions, authors, dependencies, load-order rules, incompatibilities, URLs, optional metadata, and comments unless the requested change affects them.
- Remove fields only when they are invalid, obsolete, duplicated, unsupported, or explicitly requested.

For a new file, ask for required values that cannot be inferred. Do not leave placeholders or guess supported versions, dependency IDs, load order, incompatibilities, or authorship.

Treat `packageId` as a stable dependency identifier. Use a globally unique namespaced ID such as `authorname.modname`, prefer lowercase, and avoid spaces, underscores, hyphens, special characters, and trailing periods. For a fork, continuation, or drop-in replacement, ask whether the original ID must be preserved.

## Optional metadata

Add only confirmed and useful fields:

- `<modVersion>`
- `<url>`
- `<modIconPath>`
- `<descriptionsByVersion>`
- `<modDependencies>` or `<modDependenciesByVersion>`
- `<loadBefore>`, `<loadAfter>`, `<forceLoadBefore>`, or `<forceLoadAfter>`
- `<incompatibleWith>`

Use package IDs where RimWorld expects them. Reserve force-load rules for confirmed strict requirements and incompatibilities for confirmed conflicts. Add `IgnoreIfNoMatchingField="True"` when older supported versions require it.

Dependency example:

~~~xml
<modDependencies>
  <li>
    <packageId>brrainz.harmony</packageId>
    <displayName>Harmony</displayName>
    <steamWorkshopUrl>steam://url/CommunityFilePage/2009463077</steamWorkshopUrl>
  </li>
</modDependencies>
~~~

## Version and description

Update `<modVersion>` only when the project uses it and a completed behavior, compatibility, or feature change requires a bump. Preserve the existing version format and synchronize relevant project fields. Do not bump for documentation, formatting, exploration, failed work, or mechanical edits.

Keep `<description>` concise and plain text. Exclude full Workshop copy, README content, changelog entries, license text, and Markdown or BBCode. XML-escape reserved characters.

## Validation

Parse the result as XML and confirm:

- The root is `<ModMetaData>`.
- Required fields are present and non-empty.
- Reserved characters are escaped.
- No placeholders remain.
- Stable package and dependency IDs changed only when authorized.
- Version changes follow project policy.
- Markdown and BBCode are absent.

## Delivery

Write the result to `About/About.xml`. Return a concise field-change summary and validation result. Do not reproduce the full XML in chat unless requested.
