"""The interface every AI implements, so the API, the benchmark and the RL agent can swap them.

Rule on state: an AI instance may be reused for many games, but `new_game` must be called
before the first shot of every game. After `new_game` the AI behaves exactly as if it had
never played before: nothing it learned in an earlier game may influence the new one. The
only things an AI may base a shot on are the game config, its random generator and the
player view it is handed, so it can never see where the opponent's ships are.
"""

from abc import ABC, abstractmethod

import numpy as np

from battleship.board import GameOverError
from battleship.config import GameConfig
from battleship.ship import Square
from battleship.view import PlayerView, SquareState


class AI(ABC):
    """A shooter that picks every shot from the player view and the game config alone.

    Subclasses implement `_choose_shot` and, if they have one, `_heatmap`. To keep state
    between shots of one game, override `new_game`, call `super().new_game(...)` and clear
    that state there.
    """

    def __init__(self) -> None:
        self._config: GameConfig | None = None
        self._rng: np.random.Generator | None = None

    def new_game(self, config: GameConfig, rng: int | np.random.Generator | None = None) -> None:
        """Start a new game and forget everything about earlier ones.

        `rng` is a seed or a numpy Generator; the same seed and the same views always give
        the same shots.
        """
        self._config = config
        self._rng = np.random.default_rng(rng)

    @property
    def config(self) -> GameConfig:
        """The config of the current game."""
        if self._config is None:
            raise RuntimeError("call new_game before asking the AI for a shot")
        return self._config

    @property
    def rng(self) -> np.random.Generator:
        """The random generator of the current game, the only source of chance an AI may use."""
        if self._rng is None:
            raise RuntimeError("call new_game before asking the AI for a shot")
        return self._rng

    def choose_shot(self, view: PlayerView) -> Square:
        """The square to fire at next: always on the board and never fired at before.

        Raises RuntimeError before `new_game`, ValueError for a view of another board size
        and GameOverError once every ship is sunk.
        """
        self._check(view)
        if view.is_game_over:
            raise GameOverError("every ship is already sunk")
        return self._choose_shot(view)

    def heatmap(self, view: PlayerView) -> np.ndarray | None:
        """How much the AI wants to fire at each square, or None if it has no heatmap.

        A heatmap is a size x size float array of non-negative scores on the AI's own
        scale, with 0 on every square already fired at. Asking for it never changes the
        next shot.
        """
        self._check(view)
        return self._heatmap(view)

    @abstractmethod
    def _choose_shot(self, view: PlayerView) -> Square:
        """Pick the next square; only called for a running game of the right size."""

    def _heatmap(self, view: PlayerView) -> np.ndarray | None:
        """The heatmap for this view; AIs without one keep this default."""
        return None

    @staticmethod
    def unknown_squares(view: PlayerView) -> list[Square]:
        """Every square not fired at yet, row by row from the top-left."""
        rows, cols = np.nonzero(view.to_array() == SquareState.UNKNOWN)
        return [(int(row), int(col)) for row, col in zip(rows, cols, strict=True)]

    def _check(self, view: PlayerView) -> None:
        if view.size != self.config.size:
            raise ValueError(
                f"view of a {view.size}x{view.size} board, but the game is "
                f"{self.config.size}x{self.config.size}"
            )
