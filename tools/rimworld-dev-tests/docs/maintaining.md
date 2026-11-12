# Retaining testing learnings

## After a reusable discovery

1. Classify the cause: mod defect, lost setup prerequisite, harness defect, or game/environment change. Preserve the original failed result in the owning mod's ticket. Keep expected behavior sourced from design; changing it to match the observation is not a setup fix.
2. Search `docs/recipes/index.md` and the matching helpers. Update an existing recipe when it already owns the concept. Add a topic only when no existing one fits, then add its index row and `GUIDE_TOPICS` entry if it needs direct CLI access.
3. Record the symptom/search terms, cause, recommended technique, failed approaches, unsuitable measurements, cleanup/reload behavior, implementation location, game version/date and evidence link or run ID. Label source inspection and runtime observation separately. State whether code is shared, still local, or only proposed.
4. Inspect concrete callers for the same mistake. Apply corrections within the authorized task; record remaining consumers explicitly. Verify the changed behavior with the relevant existing checks or authorized focused run. A green build alone cannot promote a runtime claim.

Completion means the owning result is recorded, the recipe/index can locate the reusable part, and implementation availability and unverified scope are explicit. Routine passing runs do not need new recipes.

## When to promote code

Keep discoveries in recipes first. Extract a helper when there is a concrete repeated use and a small interface can hide the difficult setup correctly. Keep effect assertions in mod batches; expected values never belong in shared setup code.

Put broadly required lifecycle behavior in the runner core. Put scenario-specific behavior, such as bed holding, behind an explicitly used module. Install its hooks only for that use and scope mutations to runner-owned subjects. Provide release/cleanup at batch end, cancellation and failure, plus a documented reload policy. A module should own its mutable state instead of requiring every mod to clear several hidden dictionaries.

Use the existing DLL and source folders initially; create another package or extension mechanism only for a demonstrated build or lifecycle need. Keep a workaround for one mod in that mod, with a recipe link for future investigation. A mod-specific substitute bed check is one such workaround.

## Keep the catalog small

Merge duplicate lessons; replace superseded instructions with a short reason and pointer to the current recipe. Keep detailed run histories in the originating mod. Index by symptoms and game types rather than by chat date. Read only relevant topics and linked source sections; never require the whole catalog before a case.

Review stale lessons when a supported game version changes or evidence contradicts them. Retain important failed approaches where they prevent a repeat mistake. Source and documentation changes remain ordinary reviewable diffs: the running harness records evidence, while the agent updates recipes/code under the user's task scope. Test outcomes do not authorize weakening assertions or rewriting the harness automatically.
