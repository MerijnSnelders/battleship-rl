"""The player view: what the shooter knows about a board, and nothing more."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Self

import numpy as np

from battleship.ship import Ship
from battleship.shot import ShotOutcome, ShotResult


class SquareState(IntEnum):
    """What the shooter knows about one square. The values are the codes in `to_array`."""

    UNKNOWN = 0
    MISS = 1
    HIT = 2
    SUNK = 3


@dataclass(frozen=True, eq=False)
class PlayerView:
    """A snapshot of one board as the shooter sees it.

    Built only from the shots fired at the board, so unhit ship squares can never leak.
    Every square of a sunk ship is SUNK; HIT means part of a ship that is still afloat.
    """

    size: int
    sunk_ships: tuple[Ship, ...]
    shot_count: int
    is_game_over: bool
    _grid: np.ndarray = field(repr=False)

    @classmethod
    def from_shots(cls, size: int, shots: tuple[ShotResult, ...], is_game_over: bool) -> Self:
        """Build the view from the shots fired at a board, in the order they were fired."""
        grid = np.full((size, size), SquareState.UNKNOWN, dtype=np.int8)
        sunk_ships: list[Ship] = []
        for shot in shots:
            if shot.outcome is ShotOutcome.MISS:
                grid[shot.square] = SquareState.MISS
            elif shot.outcome is ShotOutcome.HIT:
                grid[shot.square] = SquareState.HIT
            else:
                assert shot.sunk_ship is not None
                sunk_ships.append(shot.sunk_ship)
                for square in shot.sunk_ship.squares:
                    grid[square] = SquareState.SUNK
        grid.flags.writeable = False
        return cls(size, tuple(sunk_ships), len(shots), is_game_over, grid)

    def state(self, row: int, col: int) -> SquareState:
        """What the shooter knows about one square."""
        return SquareState(int(self._grid[row, col]))

    def to_array(self) -> np.ndarray:
        """The view as a size x size int8 array of `SquareState` codes (a fresh copy)."""
        return self._grid.copy()

    def to_dict(self) -> dict[str, Any]:
        """The view as JSON-ready plain types for the API."""
        names = {state.value: state.name.lower() for state in SquareState}
        return {
            "size": self.size,
            "grid": [[names[int(code)] for code in row] for row in self._grid],
            "sunk_ships": [
                {
                    "length": ship.length,
                    "squares": [list(square) for square in ship.squares],
                }
                for ship in self.sunk_ships
            ],
            "shot_count": self.shot_count,
            "game_over": self.is_game_over,
        }
