# Battleship

The rules of Battleship as played by humans, heuristic AIs and the RL agent. This glossary fixes the words used in code, docs and issues.

## Language

**Square**:
One position on a board, addressed by row and column, counted from the top-left square.
_Avoid_: Cell, tile, coordinate

**Board**:
The grid of squares belonging to one player, together with the ships placed on it.
_Avoid_: Grid, map, field

**Ship**:
A straight run of one or more adjacent squares on a board, identified by where it lies and how long it is.
_Avoid_: Boat, vessel

**Orientation**:
Whether a ship runs horizontally (along a row) or vertically (along a column).
_Avoid_: Direction, rotation

**Placement**:
Putting a ship on a board at a start square with an orientation. The start square is the ship's top-left end, so a ship never extends left or up from it.
_Avoid_: Position, deployment

**Fleet**:
The ships a game config prescribes for each player, given as ship lengths. Several ships may share a length.
_Avoid_: Army, ship set

**Randomly placed fleet**:
The whole fleet placed on an empty board by chance, so the board is complete. Every complete board is equally likely, and the same seed always gives the same board.
_Avoid_: Random fleet, random board

## Rules of placement

- A placement is legal when the ship lies fully on the board, does not overlap another ship, and its length is still needed by the fleet.
- Ships that touch (side by side or corner to corner) are allowed; only overlap is forbidden.
- A board is **complete** when its placed ships match the fleet exactly.
