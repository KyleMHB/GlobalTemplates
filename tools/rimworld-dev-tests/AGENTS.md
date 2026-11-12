# RimWorld test harness: agent entry point

Use this guide for writing cases, changing harness code or triaging results. Read the target mod's instructions and `TESTING.md` for permission, expected behavior and required checks. This guide grants no run or deployment permission.

## Read only what the task needs

From this directory, run `python rimtest.py guide [topic]`. No mod config or game process is needed. A mod wrapper also supports `guide`.

| Task | Topic | Source |
| --- | --- | --- |
| Add a mod adapter or write a case | `authoring` | [Authoring](docs/authoring.md) |
| Find a pitfall or setup technique | `recipes` | [Recipe index](docs/recipes/index.md) |
| Pawn in a wall, invalid layout, visual sliding | `placement` | [Placement](docs/recipes/placement.md) |
| Patient leaving bed, downing, sleep, prisoner beds | `beds` | [Beds](docs/recipes/beds.md) |
| Guard a measurement; classify a setup failure | `measurements` | [Measurements](docs/recipes/measurements.md) |
| Session, background execution, modpack interference | `environment` | [Environment](docs/recipes/environment.md) |
| Record a run or investigate capture startup | `recording` | [Recording](docs/recording.md) |
| Preserve a new learning or promote shared code | `maintaining` | [Maintenance](docs/maintaining.md) |

Search the recipe index first, then read matching topics. For other subjects use `rg -n -i '<symptom or game type>' docs Harness`; inspect matching sections and callers. Read `README.md` only for build/install details.

Before changing setup, distinguish a mod defect from a lost prerequisite or changed game/mod behavior. After resolving a reusable setup problem, follow `maintaining`; completion includes recording its evidence and limits. Keep expected values in the mod's own spec.
