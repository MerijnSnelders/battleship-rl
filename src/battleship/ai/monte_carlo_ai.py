"""The Monte Carlo AI: fire where a ship lies in the most randomly drawn possible layouts."""

import numpy as np

from battleship.ai.base import AI
from battleship.ai.probability_density_ai import ProbabilityDensityAI, remaining_ships
from battleship.ai.registry import register
from battleship.config import GameConfig
from battleship.ship import Orientation, Ship, Square
from battleship.view import PlayerView, SquareState

DEFAULT_SAMPLES = 1000
"""How many samples the AI draws per shot unless told otherwise."""

ATTEMPTS_PER_SAMPLE = 50
"""How many random layouts may be tried per sample wanted before the AI gives up."""

BATCH_SIZE = 4096
"""How many random layouts are tried at once."""


@register("monte_carlo")
class MonteCarloAI(AI):
    """Fires at the square that holds a ship in the most samples.

    Each shot it draws `samples` possible layouts of the ships still afloat, every one
    equally likely, by rejection sampling: each ship gets a placement drawn uniformly from
    its possible placements, and the layout is thrown away if two ships overlap or a hit
    is left uncovered. What survives is uniform over all possible layouts. The heatmap is
    the fraction of samples in which each square holds a ship.

    At most `samples * ATTEMPTS_PER_SAMPLE` layouts are tried, so a move never hangs. If
    fewer samples survive, the heatmap uses those; if none survive, it falls back to the
    Probability density AI's placement counts for that shot.

    Sampling uses a generator seeded from the game and the number of shots so far, so
    asking for the heatmap never changes the next shot. It keeps no state between shots
    apart from a cache of the last heatmap.
    """

    def __init__(self, samples: int = DEFAULT_SAMPLES) -> None:
        super().__init__()
        if samples < 1:
            raise ValueError("samples must be at least 1")
        self.samples = samples
        self._fallback = ProbabilityDensityAI()
        self._game_seed = 0
        self._cache: tuple[bytes, np.ndarray, bool] | None = None
        self._masks: dict[int, np.ndarray] = {}

    def new_game(self, config: GameConfig, rng: int | np.random.Generator | None = None) -> None:
        super().new_game(config, rng)
        self._fallback.new_game(config)
        self._game_seed = int(self.rng.integers(2**63))
        self._cache = None
        self._masks = {length: _placement_masks(config.size, length) for length in config.ships}

    def _choose_shot(self, view: PlayerView) -> Square:
        scores, _ = self._scores(view)
        unknown = view.to_array().ravel() == SquareState.UNKNOWN
        best = scores.ravel()[unknown].max()
        candidates = np.nonzero(unknown & (scores.ravel() == best))[0]
        pick = int(self._view_rng(view, stream=1).choice(candidates))
        return divmod(pick, view.size)

    def _heatmap(self, view: PlayerView) -> np.ndarray:
        """The fraction of samples holding a ship on each square (or the fallback counts)."""
        return self._scores(view)[0].copy()

    def occupancy(self, view: PlayerView) -> tuple[np.ndarray, int]:
        """The fraction of samples with a ship on each square, and how many samples there were.

        Squares already fired at are 0. With no samples the fractions are all 0.
        """
        rng = self._view_rng(view, stream=0)
        grid = view.to_array().ravel()
        blocked = (grid == SquareState.MISS) | (grid == SquareState.SUNK)
        hits = np.nonzero(grid == SquareState.HIT)[0]

        choices = []
        for length, count in remaining_ships(self.config.ships, view).items():
            masks = self._masks[length]
            possible = masks[~masks[:, blocked].any(axis=1)]
            if len(possible) == 0:
                return np.zeros((view.size, view.size)), 0
            choices.extend([possible] * count)

        occupied = np.zeros(grid.size, dtype=np.int64)
        found = 0
        tries_left = self.samples * ATTEMPTS_PER_SAMPLE
        while found < self.samples and tries_left > 0:
            batch = min(BATCH_SIZE, tries_left)
            tries_left -= batch
            layouts = np.zeros((batch, grid.size), dtype=np.uint8)
            for possible in choices:
                layouts += possible[rng.integers(len(possible), size=batch)]
            fits = (layouts <= 1).all(axis=1) & (layouts[:, hits] == 1).all(axis=1)
            accepted = layouts[fits][: self.samples - found]
            occupied += accepted.sum(axis=0, dtype=np.int64)
            found += len(accepted)

        fractions = occupied / found if found else occupied.astype(float)
        fractions[grid != SquareState.UNKNOWN] = 0
        return fractions.reshape(view.size, view.size), found

    def _scores(self, view: PlayerView) -> tuple[np.ndarray, bool]:
        """The heatmap for this view and whether it is the fallback, cached per view."""
        key = view.to_array().tobytes()
        if self._cache is None or self._cache[0] != key:
            fractions, found = self.occupancy(view)
            if found:
                self._cache = (key, fractions, False)
            else:
                self._cache = (key, self._fallback.placement_counts(view).astype(float), True)
        return self._cache[1], self._cache[2]

    def _view_rng(self, view: PlayerView, stream: int) -> np.random.Generator:
        """A generator fixed by the game, the number of shots so far and its purpose."""
        return np.random.default_rng([self._game_seed, view.shot_count, stream])


def _placement_masks(size: int, length: int) -> np.ndarray:
    """Every placement of a ship of this length that fits on the board, as square masks.

    One row per placement, one column per square (row by row), 1 where the ship lies.
    """
    rows = []
    for orientation in Orientation:
        if length == 1 and orientation is Orientation.VERTICAL:
            break  # a ship of length 1 lies the same either way
        for row in range(size):
            for col in range(size):
                squares = Ship((row, col), length, orientation).squares
                if all(r < size and c < size for r, c in squares):
                    mask = np.zeros(size * size, dtype=np.uint8)
                    mask[[r * size + c for r, c in squares]] = 1
                    rows.append(mask)
    return np.array(rows)
