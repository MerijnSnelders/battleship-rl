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

**Shot**:
Firing at one square of the opponent's board. Each square can be fired at only once, and only once the board is complete. The shots fired at a board are counted and remembered in order, each with the square and what it revealed.
_Avoid_: Attack, guess, move, strike

**Miss**:
A shot at a square that no ship covers.
_Avoid_: Splash, water

**Hit**:
A shot at a square covered by a ship that still has unhit squares afterwards.

**Sunk**:
What a shot reveals when it hits the last unhit square of a ship. The ship is then sunk, and its length and squares become known to the shooter.
_Avoid_: Destroyed, killed

**Player view**:
What the shooter knows about one board: for each square, whether it is unknown, a miss, a hit or sunk, plus the ships sunk so far. It never reveals a square that has not been fired at. Every square of a sunk ship shows as sunk, so a hit always belongs to a ship that is still afloat.
_Avoid_: Opponent view, tracking board, observation

**AI**:
A shooter that picks every shot from only the player view of the board it fires at and the game config. It is told when a new game starts, and from then on behaves as if it had never played before.
_Avoid_: Bot, opponent, strategy, agent (except for the RL agent, which is one kind of AI)

**Random AI**:
The baseline AI: every shot goes to a square chosen uniformly at random from the squares not fired at yet. It ignores hits and sunk ships entirely, so it is the lower bound every other AI must beat.
_Avoid_: Random fire, random strategy, dumb AI

**Hunt/target AI**:
The human-like AI: it fires in hunt mode while no hit is on the board and in target mode while at least one is. It stays in target mode after a sink if another ship has already been hit.
_Avoid_: Hunt AI, target AI, smart AI

**Hunt mode**:
Searching for a ship: a shot at a square chosen uniformly at random from the squares not fired at yet, exactly like the Random AI.
_Avoid_: Search mode, random mode

**Target mode**:
Finishing off a ship that has been hit: a shot next to the hits. Once two or more hits form a line, only the squares just past its ends are fired at, until both ends are blocked.
_Avoid_: Kill mode, destroy mode

**Possible placement**:
A placement of a ship still afloat that lies fully on the board and covers no miss and no sunk square, so the player view does not rule it out. It may cover hits. Each ship is judged on its own, so two possible placements may overlap.
_Avoid_: Legal placement (that means the board's own placement rules), candidate, option

**Probability density AI**:
The AI that counts, for every square, the possible placements covering it, and fires at a square with the highest count. A placement counts more heavily for every hit it covers, so it finishes off ships it has found.
_Avoid_: Density AI, probability AI, heatmap AI

**Possible layout**:
All the ships still afloat placed together so the player view does not rule them out: no two overlap, none covers a miss or a sunk square, and together they cover every hit. Unlike possible placements, a possible layout respects that ships cannot overlap.
_Avoid_: Consistent layout, configuration, arrangement

**Sample**:
One possible layout drawn at random, every possible layout being equally likely.

**Monte Carlo AI**:
The AI that draws many samples, and fires at the square not fired at yet that holds a ship in the most of them. When no sample can be found, it counts possible placements the way the Probability density AI does instead.
_Avoid_: MC AI, sampling AI, simulation AI

**Heatmap**:
An AI's score for every square, showing how much it wants to fire there. Only some AIs have one.
_Avoid_: Probability map, heat map

**Game over**:
Every ship on a board is sunk. No more shots may be fired at that board.
_Avoid_: Win, finished

**Benchmark game**:
One AI firing at one randomly placed fleet until game over. There is no opponent firing back, so nobody wins or loses.
_Avoid_: Match, round, episode (except inside RL training)

**Shots to finish**:
The number of shots a benchmark game took. Fewer is better. Its lowest possible value is the number of squares the fleet covers, its highest the number of squares on the board.
_Avoid_: Shots to win, score, game length

**Benchmark**:
Every AI playing the same set of benchmark games, board for board, so their shots to finish can be compared directly.
_Avoid_: Evaluation, tournament

## Rules of placement

- A placement is legal when the ship lies fully on the board, does not overlap another ship, and its length is still needed by the fleet.
- Ships that touch (side by side or corner to corner) are allowed; only overlap is forbidden.
- A board is **complete** when its placed ships match the fleet exactly.
