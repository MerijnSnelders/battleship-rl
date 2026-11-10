# Research

## Battleship strategies (issue #6)

Sub-question 1 (Library): which strategies exist and roughly how well do they perform?

All figures below come from the DataGenetics article [1] and apply to the standard
10x10 board with ships of length 5, 4, 3, 3 and 2 (`STANDARD` in `GameConfig`). They are
the source's numbers, not our own measurements: our benchmark will measure every
implemented strategy again.

### 1. Random fire

**How it works.** Every turn the AI picks a random square it has not shot at yet. It
ignores everything it has learned, including hits.

**Expected performance.** The dumbest strategy possible, but an essential baseline. The
median game takes 96 shots [1], so on average almost the whole board has to be shot
before the last ship sinks. This is the lower bound every other strategy must beat.

**Our measurement.** Our Random AI played 2,000 games per config (board seeds 0 to 1999,
AI seeds 10000 to 11999). STANDARD (10x10, 17 ship squares): median 97, mean 95.6, min 69,
max 100. SMALL (6x6, 7 ship squares): median 33, mean 32.4, min 17, max 36. Both agree with
theory: the shot count is the position of the last ship square in a random order of the
board, so the expected mean is 17 x 101 / 18 = 95.4 on STANDARD and 7 x 37 / 8 = 32.4 on
SMALL. The slow test `test_median_matches_random_fire_theory` guards these numbers.

**Will we implement it?** Yes, as the baseline AI.

**Sources.** [1], [2], [3]

### 2. Hunt/target (random fire, then hunt)

**How it works.** The AI has two modes:

- *Hunt:* fire at random, exactly like random fire, until a shot hits.
- *Target:* after a hit, push the four neighbouring squares (up, down, left, right) onto
  a stack and fire at them one by one. Every new hit adds its own neighbours. Once the
  stack is empty, go back to hunt mode.

This is how most people play: search at random, then finish off a ship once it is found.

**Expected performance.** A clear improvement over random fire [1]. The source shows it
only in a graph and gives no median, so there is no verified figure: our own benchmark
will measure it.

**Our measurement.** Our Hunt/target AI played the same 2,000 games per config (board
seeds 0 to 1999, AI seeds 10000 to 11999). STANDARD: median 60, mean 60.1, min 23, max 99.
SMALL: median 22, mean 22.5, min 8, max 36. That is 37 shots fewer than random fire on the
median. Our version also follows the line of hits (it only fires past the two ends of a
line) and reads sunk ships from the player view, which the basic stack version in [1]
does not, so it already does slightly better than the 64 quoted for parity. The slow test
`test_median_beats_random_fire` guards these numbers.

**Will we implement it?** Yes.

**Sources.** [1], [2], [3]

### 3. Checkerboard (parity)

**How it works.** A refinement of hunt mode. The smallest ship has length 2, so every
ship covers at least one square of each colour of a checkerboard pattern. In hunt mode
the AI therefore only fires at squares of one colour, which halves the squares it has to
search. Target mode stays the same.

**Expected performance.** Hunt/target with parity has a median of 64 shots [1].

**Will we implement it?** No, because of time constraints.

**Sources.** [1], [2], [3]

### 4. Probability density

**How it works.** At the start of every turn, the AI takes each ship that has not sunk
yet and tries every horizontal and vertical placement of it on the board. A placement
counts if it does not cross a miss or a sunk ship. For every placement that counts, each
square it covers gets +1. Adding up the counts of all remaining ships gives a heat map,
and the AI fires at the square with the highest total. Placements through a known hit are
weighted heavily, so the AI naturally finishes off a ship it has found [1].

Two things are worth noting:

- It needs the "sunk" message to know which ships are left, so it uses more of the game's
  information than hunt/target does.
- Each ship is counted on its own, so the method ignores that ships cannot overlap. The
  heat map is a cheap approximation of the true probabilities, not the exact values.

**Expected performance.** A median of 42 shots, and in 100 million simulated games no
game took longer than 73 shots [1]. This is far better than random fire and hunt/target.

**Our measurement.** Our Probability density AI played the same 2,000 games per config
(board seeds 0 to 1999, AI seeds 10000 to 11999). STANDARD: median 44, mean 44.6, min 22,
max 71. SMALL: median 18, mean 17.9, min 8, max 27. That is close to the source's 42 and
16 shots fewer than our Hunt/target AI on the median. Each placement counts 100 times
more for every hit it covers (`HIT_WEIGHT`), so one hit outweighs everything else and a
line of hits is followed automatically. A move takes 0.4 ms on average and 6 ms at most
on STANDARD, well under the 50 ms limit. The slow tests `test_median_beats_hunt_target`
and `test_a_move_on_standard_takes_under_50_ms` guard these numbers.

**Will we implement it?** Yes.

**Sources.** [1], [2], [3]

### 5. Monte Carlo sampling

**How it works.** Instead of counting each ship on its own, the AI samples complete fleet
layouts: all remaining ships placed together, without overlap, consistent with every shot
so far (every hit covered, no ship on a miss, sunk ships where they were sunk). It
generates many such layouts, counts how often each square holds a ship, and fires at the
square that is occupied most often. With enough samples this approaches the true
probability for each square, which probability density only approximates.

The cost is computing time: the AI needs many valid layouts every turn, and finding them
gets harder as more constraints pile up.

**Expected performance.** None of our sources gives a shot count, so there is no verified
figure: our own benchmark will measure it. We expect it to match or slightly beat
probability density, because it does not ignore overlaps.

**Will we implement it?** Yes.

**Sources.** [2], [3]

### Conclusion

The strategies form a clear ladder: random fire (96 shots) < hunt/target < parity (64) <
probability density (42) <= Monte Carlo sampling. Each step uses more of the information
the game provides.

**Hypothesis for the RL agent.** We expect a well-trained RL agent to behave like a mix of
the two strongest strategies, depending on the phase of the game:

- **Early in the game** almost nothing is known and the number of possible fleet layouts
  is huge. The agent cannot consider them all, so a good policy should behave like Monte
  Carlo sampling: an estimate of where ships are likely to be, based on a broad picture
  of all possible layouts.
- **Late in the game** most ships have sunk and few layouts remain. Those can all be
  counted, so a good policy should behave like an exact probability density: fire at the
  square that most of the remaining placements cover.

The agent is given none of these rules. It only sees the board and gets a reward, so if
this behaviour appears it has to discover it itself. Whether it does is part of what the
experiment will test.

### Sources

1. Nick Berry, "Battleship", DataGenetics, 29 December 2011.
   <https://www.datagenetics.com/blog/december32011/index.html>
2. Vsauce2, "The Battleship Algorithm", YouTube.
   <https://www.youtube.com/watch?v=LbALFZoRrw8>
3. Digital Genius, "How to 'always' win at Battleship?", YouTube.
   <https://www.youtube.com/watch?v=8FctDuTfcO8>
