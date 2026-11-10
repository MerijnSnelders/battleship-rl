"""The Probability density AI: fire where the most possible placements overlap."""

from collections import Counter

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from battleship.ai.base import AI
from battleship.ai.registry import register
from battleship.ship import Square
from battleship.view import PlayerView, SquareState

HIT_WEIGHT = 100
"""How much more a possible placement counts for every hit it covers."""


@register("probability_density")
class ProbabilityDensityAI(AI):
    """Fires at a square covered by the most possible placements of the ships still afloat.

    For every ship not sunk yet, it tries every horizontal and vertical placement on the
    board. A placement is possible if it covers no miss and no sunk square. Every square
    a possible placement covers gets HIT_WEIGHT ** k added, where k is the number of hits
    the placement covers. One hit therefore outweighs any number of placements elsewhere,
    and placements along a line of hits outweigh those crossing just one of them.

    Each ship is counted on its own, so overlap between the remaining ships is ignored.
    Ties for the highest count are broken at random. It keeps no state between shots.
    """

    def _choose_shot(self, view: PlayerView) -> Square:
        counts = self.placement_counts(view)
        best = counts.max()
        if best == 0:  # cannot happen in a real game, but never fire at a fired square
            squares = self.unknown_squares(view)
        else:
            rows, cols = np.nonzero(counts == best)
            squares = [(int(row), int(col)) for row, col in zip(rows, cols, strict=True)]
        return squares[int(self.rng.integers(len(squares)))]

    def _heatmap(self, view: PlayerView) -> np.ndarray:
        """The weighted placement counts as floats."""
        return self.placement_counts(view).astype(float)

    def placement_counts(self, view: PlayerView) -> np.ndarray:
        """The weighted count of possible placements covering each square, as int64.

        Every square already fired at is 0.
        """
        grid = view.to_array()
        blocked = (grid == SquareState.MISS) | (grid == SquareState.SUNK)
        hits = (grid == SquareState.HIT).astype(np.int64)
        counts = np.zeros((view.size, view.size), dtype=np.int64)
        for length, ships in _remaining_ships(self.config.ships, view).items():
            row_counts = _row_counts(blocked, hits, length)
            col_counts = _row_counts(blocked.T, hits.T, length).T
            counts += ships * (row_counts + col_counts)
        counts[grid != SquareState.UNKNOWN] = 0
        return counts


def _remaining_ships(fleet: tuple[int, ...], view: PlayerView) -> Counter[int]:
    """How many ships of each length are still afloat."""
    remaining = Counter(fleet)
    remaining.subtract(ship.length for ship in view.sunk_ships)
    return +remaining


def _row_counts(blocked: np.ndarray, hits: np.ndarray, length: int) -> np.ndarray:
    """The weighted counts of the possible placements of one ship lying along the rows."""
    size = blocked.shape[1]
    starts = size - length + 1
    possible = ~sliding_window_view(blocked, length, axis=1).any(axis=2)
    hits_covered = sliding_window_view(hits, length, axis=1).sum(axis=2)
    weights = np.where(possible, HIT_WEIGHT**hits_covered, 0)
    counts = np.zeros(blocked.shape, dtype=np.int64)
    for offset in range(length):
        counts[:, offset : offset + starts] += weights
    return counts
