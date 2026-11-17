# Checking that patches are applied

Keywords: Harmony, patch count, patch silently off, dependency update, target not found, reflection, compatibility patch, changed warning.

A mod that finds its targets in other mods by name or by scanning their code can lose a patch without an error when a dependency updates. Its gameplay cases may still pass if they don't reach the patched path. Add one mechanical case that checks the patches themselves.

## Technique

1. Count patches per patch method, owned by the mod's Harmony ID: walk `Harmony.GetAllPatchedMethods()`, read `Harmony.GetPatchInfo(method)`, and count the prefixes, postfixes, transpilers and finalizers whose `owner` is the mod's ID, grouped by patch method.
2. Compare each count with the minimum the loaded mods allow. The minimum depends on the mod set, so derive it from which targets are loaded rather than hard-coding one number.
3. Fail on any warning the mod logs at startup when a target has changed or gone missing (for example `[Mod] … changed`). Make the mod log one such warning per lost target, so this check can see it.

Report each patch method's count and minimum as observations, so a failure names the patch that went missing.

## Availability and limits

- Mod-local today. A shared helper such as `PatchCounts(owner)` is proposed, not built.
- It proves a patch is attached, not that it does the right thing. Keep the gameplay cases.
- A mod that reaches another mod through reflection without Harmony needs its own check of each resolved member instead.

Source: UI Rethemed Era Looks, 2026-11-17, RimWorld 1.7.
