# Patients in beds

Keywords: bed, patient, LayDown, CurrentBed, InBed, downed, sleep, prisoner, reservation, job loop.

## Establish and observe occupancy separately

Vanilla `CurrentBed` requires a spawned pawn with a job, an in-bed posture and a sleeping slot at its cell. Standing on a bed cell is insufficient. Downing a patient can leave it in `Wait_Downed`, also insufficient.

A bed-rest helper should maintain a real LayDown job, assign a non-medical bed, feed the patient and cap rest at about 30%. A fully rested patient can end LayDown immediately. Establish `CurrentBed() == bed` before measuring. Check it independently through `Kit.Require` or `Wait.While`, including every patient in a comparison. Guard the required injury too; a healed cut cannot measure continued healing.

`Kit.Immobilise` additionally intercepts a held pawn's new-job selection. Keep BedRest and the occupancy guard. `Kit.Release` ends the hold; batch cleanup clears it, and reload requires registration of the new pawn objects. The hold limits repeated LayDown starts to three per tick, retaining bed validity and reservation diagnostics when it gives up.

## Check the bed before strengthening a hold

One prisoner bed makes its room a prison cell; vanilla then marks the other beds for prisoners. Keep colonist and prisoner wards separate, and refresh room state after marking prisoner beds. Mixing them produces invalid colonist beds and thousands of job-loop errors; reissuing jobs more often does not fix that setup.

A pawn walking toward its bed may already have LayDown targeting it. The maintenance helper can see that job and skip repositioning. For an explicitly controlled return, stop its old jobs, put it on a valid bed cell, reapply maintenance and wait for actual occupancy before measuring.

## Limits and rejected shortcuts

BedRest changes needs and position. Immobilisation changes job choice. Use them for controlled mechanical effects; they cannot establish natural bed selection, walking, sleep recovery or a normal medical workflow. In-bed is not asleep: check `pawn.jobs.curDriver.asleep` separately. Release rest maintenance before measuring natural waking or rest gain.

A mod may substitute the assigned bed during its own treatment pass. That is a local mechanical-test intervention, not a shared solution or evidence that vanilla counted a patient as in bed. Keep real-workflow coverage separate. A standalone pass does not rule out a later run-all failure; preserve that evidence.

## Availability and evidence

Bed-rest, bed-check and keep-in-bed helpers are not exported by `RimWorldDevTests.dll`; each mod writes its own. Promote one to the shared `Kit` only with a concrete consumer, bounded lifecycle and focused verification; see `guide maintaining`.

Game facts were checked against RimWorld 1.7.5000 IL on 2026-11-06; see [game facts](../game-facts.md#pawns-beds-and-rooms). No cross-mod runtime verification is claimed.
