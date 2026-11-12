# RimWorld localisation facts

Verified 2026-11-09 against RimWorld 1.7.5000 rev1275 (vanilla language archives under `Data/Core/Languages`) and by building a translated mod. Recheck against another game build before relying on a fact.

- **Two kinds of file:** `Languages/<Language>/Keyed/*.xml` holds text C# reads with `"Key".Translate(args)`; `Languages/<Language>/DefInjected/<DefType>/*.xml` overrides def fields by path. English def text needs no DefInjected file: the defs are the English.
- **Language folder names:** vanilla folders carry a native name (`ChineseSimplified (简体中文)`, `Russian (Русский)`); mods use the short legacy name (`ChineseSimplified`, `Russian`, `German`), which the game also matches.
- **Load folders:** each folder `LoadFolders.xml` loads may have its own `Languages/`, so translations of DLC- or mod-conditional defs belong in that folder (for example `Integrations/<X>/Languages/`).
- **DefInjected paths:** list items are addressed by index after `ParentName` inheritance (`Bear_Grizzly.lifeStages.0.label` in vanilla) or by handle; vanilla addresses comps by comp class (`Apparel_SmokepopBelt.comps.CompApparelReloadable.chargeNoun`). Job report tokens `TargetA`/`TargetB` must survive translation.
- **Arguments:** `{0}` is positional; `pawn.Named("PAWN")` exposes `{PAWN_labelShort}`, `{PAWN_possessive}`, `{PAWN_objective}` and friends, which resolve with the target language's grammar. Translate whole sentences: word order differs between languages, so concatenated fragments cannot be translated.
- **When `Translate()` works:** Keyed data loads during play-data loading, before `LongEventHandler.ExecuteWhenFinished` callbacks and `[StaticConstructorOnStartup]`. Static field initialisers that can run from the mod's constructor (for example via `GetSettings`) translate too early, so store keys there and translate when text is shown.
- **`TaggedString` in conditionals:** `cond ? "Key".Translate() : ""` fails to compile with CS0172/CS0034 because `TaggedString` and `string` convert both ways. Add `.ToString()` to the translated side.
- **Vanilla keys:** `Data/<Core|DLC>/Languages/English/Keyed` in the install lists them; Ideology's darklight toggle uses `ToggleDarklightOn`/`ToggleDarklightOff`(`Desc`).
- **Deploy scripts:** a deploy step with a fixed folder list ships no translations until `Languages` is added.
