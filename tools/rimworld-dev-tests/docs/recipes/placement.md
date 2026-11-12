# Safe pawn and fixture placement

Keywords: wall, blocked cell, footprint, room edge, interaction cell, teleport, sliding, tween.

## Placement before measurement

Validate the complete rotated building footprint and its interaction cell. Choose an open area before building. Pawn spawn and teleport destinations must be in bounds and walkable. Reject an invalid destination as setup failure; correct the layout rather than repeatedly teleporting a subject into a wall.

Wandering pawns may enter a footprint after the area was selected. A relocation helper should move them to a free standable cell outside the footprint and records the move. `Kit.Room` moves pawns off the wall line, including the door, before building. Loose-object clearing is opt-in and disclosed; it must preserve objects a case measures. A nearest-cell search must return an explicit invalid result when there is no valid destination, then fail setup.

These relocations belong to fixture setup. During a measurement observe a blocked pawn and invalidate the window; automatic relocation could conceal broken pathfinding or collision behavior.

## Actual position versus visual sliding

The shared runner's `WallCheck` observes blocked pawn cells every 30 ticks and records the pawn, blocker, tick and current case. It warns; it does not prevent placement or invalidate a case by itself. Add a per-tick `Wait.While` guard when valid position is a measurement prerequisite.

At accelerated tick rates, a pawn's draw tween can lag its real cell and appear to slide through walls. The shared runner snaps draw positions after each simulated tick. Check `pawn.Position` and walkability before treating an animation artifact as a gameplay failure.

## Where the code is

- Shared: `Harness/Kit.cs` (`Area`, `Place`, `Room`, `Worker`) and `Harness/Runner.cs` (`WallCheck`, `SnapDrawPositions`). `Place` currently rejects occupied footprints; it does not relocate pawns automatically.

Cleanup: stop position holds before testing movement, restore the intended starting state, and reacquire objects after reload. Keep unrelated recipients out of effect/budget tests, and measure actual room and roof state rather than inferring it from coordinates.
