# Test setup recipe index

Search this index by symptom, required state or game type. Read only the matching file or linked source section. Availability below describes the current implementation, not the desired one. Evidence comes from RimWorld 1.7.5000 rev1275 unless the recipe says otherwise.

| Need or search terms | Read | Availability |
| --- | --- | --- |
| Wall, blocked cell, footprint, interaction cell, sliding, tween | [Placement](placement.md) | Shared validation/observer |
| Bed, patient, LayDown, downed, CurrentBed, asleep, prisoner room | [Beds](beds.md) | Mod-local helpers; game facts shared |
| Prerequisite, guard, setup failure, coverage, control, reload | [Measurements](measurements.md) | Shared `Kit.Require`, `Wait.While`, `SkipUnlessPassed` |
| Session, focus, minimize, seed, research lost, wild animals, modpack, mod list, ModsConfig, foreign patch before startup, conflict gate | [Environment](environment.md) | Shared runner plus local modpack examples |
| Meditation, joy full, Meditate ends, psyfocus | [game facts](../game-facts.md#pawns-beds-and-rooms) | Holding psyfocus cannot measure its natural gain |
| Worker, work priority, research, bills, job never starts | `Harness/Kit.cs` (`Worker`) | Shared `Kit.Worker` |
| Apparel never picked up, optimize apparel, outfit policy, wear, gear up | [game facts](../game-facts.md#pawns-beds-and-rooms) | Put test apparel in a stockpile |
| Stat offset, quality, pain, clamp, age, gear | [game facts](../game-facts.md#stats) | Versioned facts; use an adult subject for offset ratios |

To add or revise a recipe, use [maintenance](../maintaining.md). Store expected mod behavior and run histories in the owning mod; link the evidence here.
