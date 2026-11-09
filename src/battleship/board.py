"""A player's board and the ships placed on it."""

from collections import Counter
from collections.abc import Iterable
from typing import Self

import numpy as np

from battleship.config import GameConfig
from battleship.ship import Orientation, Ship, Square
from battleship.shot import ShotOutcome, ShotResult
from battleship.view import PlayerView

MAX_PLACEMENT_TRIES = 100_000
"""How many random boards `Board.with_random_fleet` tries before giving up."""


class InvalidPlacementError(ValueError):
    """A ship cannot be placed on the board as requested."""


class ShipNotInFleetError(InvalidPlacementError):
    """The fleet has no ship of this length left to place."""


class OffBoardError(InvalidPlacementError):
    """Part of the ship lies outside the board."""


class OverlapError(InvalidPlacementError):
    """The ship would cover a square that another ship already covers."""


class IncompleteFleetError(ValueError):
    """The ships given do not make up the whole fleet."""


class PlacementFailedError(ValueError):
    """No randomly placed fleet was found within the allowed number of tries."""


class InvalidShotError(ValueError):
    """A shot cannot be fired at the board as requested."""


class ShotOffBoardError(InvalidShotError):
    """The square fired at lies outside the board."""


class RepeatShotError(InvalidShotError):
    """The square has already been fired at."""


class GameOverError(InvalidShotError):
    """Every ship on the board is already sunk, so no more shots are accepted."""


class Board:
    """One player's grid of squares and the ships placed on it."""

    def __init__(self, config: GameConfig) -> None:
        self.config = config
        self._ships: list[Ship] = []
        self._shots: list[ShotResult] = []
        self._fired: set[Square] = set()

    @classmethod
    def from_ships(cls, config: GameConfig, ships: Iterable[Ship]) -> Self:
        """Build a board holding exactly the fleet, or raise if the ships do not match it."""
        board = cls(config)
        for ship in ships:
            board.place(ship)
        if not board.is_complete:
            raise IncompleteFleetError("the ships given do not make up the whole fleet")
        return board

    @classmethod
    def with_random_fleet(
        cls, config: GameConfig, rng: int | np.random.Generator | None = None
    ) -> Self:
        """Build a complete board with a randomly placed fleet.

        Every complete board is equally likely: each ship gets a placement chosen uniformly
        from all placements that fit on the board, and the whole board is drawn again
        whenever two ships overlap. `rng` is a seed or a numpy Generator (which is advanced,
        so an RL environment can pass its own); the same seed always gives the same board.
        Ships come out in fleet order.
        """
        generator = np.random.default_rng(rng)
        for _ in range(MAX_PLACEMENT_TRIES):
            ships = [_random_ship(config.size, length, generator) for length in config.ships]
            covered = [square for ship in ships for square in ship.squares]
            if len(covered) == len(set(covered)):
                return cls.from_ships(config, ships)
        raise PlacementFailedError(
            f"no randomly placed fleet found in {MAX_PLACEMENT_TRIES} tries; "
            "the fleet is too crowded for this board"
        )

    @property
    def ships(self) -> tuple[Ship, ...]:
        """The ships placed so far, in the order they were placed."""
        return tuple(self._ships)

    @property
    def is_complete(self) -> bool:
        """Whether every ship of the fleet has been placed."""
        return len(self._ships) == len(self.config.ships)

    @property
    def shots(self) -> tuple[ShotResult, ...]:
        """Every shot fired at this board, in the order it was fired."""
        return tuple(self._shots)

    @property
    def shot_count(self) -> int:
        """How many shots have been fired at this board."""
        return len(self._shots)

    @property
    def is_game_over(self) -> bool:
        """Whether every ship on this complete board has been sunk."""
        return self.is_complete and all(self._is_sunk(ship) for ship in self._ships)

    def view(self) -> PlayerView:
        """A snapshot of this board as the shooter sees it: never any unhit ship square."""
        return PlayerView.from_shots(self.config.size, self.shots, self.is_game_over)

    def fire(self, square: Square) -> ShotResult:
        """Fire at a square and return what it reveals, or raise and change nothing.

        Raises IncompleteFleetError if the fleet is not fully placed yet, GameOverError if
        every ship is already sunk, ShotOffBoardError for a square outside the board and
        RepeatShotError for a square fired at before. Rejected shots are not counted.
        """
        if not self.is_complete:
            raise IncompleteFleetError("cannot fire before the whole fleet is placed")
        if self.is_game_over:
            raise GameOverError("every ship is already sunk")
        row, col = square
        square = (int(row), int(col))
        size = self.config.size
        if not (0 <= square[0] < size and 0 <= square[1] < size):
            raise ShotOffBoardError(f"square {square} is not on a {size}x{size} board")
        if square in self._fired:
            raise RepeatShotError(f"square {square} has already been fired at")

        self._fired.add(square)
        ship = next((ship for ship in self._ships if square in ship.squares), None)
        if ship is None:
            result = ShotResult(square, ShotOutcome.MISS)
        elif self._is_sunk(ship):
            result = ShotResult(square, ShotOutcome.SUNK, sunk_ship=ship)
        else:
            result = ShotResult(square, ShotOutcome.HIT)
        self._shots.append(result)
        return result

    def _is_sunk(self, ship: Ship) -> bool:
        return self._fired.issuperset(ship.squares)

    def can_place(self, ship: Ship) -> bool:
        """Whether `place` would accept this ship right now."""
        try:
            self._check(ship)
        except InvalidPlacementError:
            return False
        return True

    def place(self, ship: Ship) -> None:
        """Put a ship on the board, or raise InvalidPlacementError and change nothing."""
        self._check(ship)
        self._ships.append(ship)

    def _check(self, ship: Ship) -> None:
        unplaced = Counter(self.config.ships) - Counter(placed.length for placed in self._ships)
        if unplaced[ship.length] == 0:
            raise ShipNotInFleetError(
                f"the fleet has no ship of length {ship.length} left to place"
            )
        size = self.config.size
        if any(not (0 <= row < size and 0 <= col < size) for row, col in ship.squares):
            raise OffBoardError(f"ship at {ship.start} does not fit on a {size}x{size} board")
        taken = {square for placed in self._ships for square in placed.squares}
        if taken.intersection(ship.squares):
            raise OverlapError(f"ship at {ship.start} overlaps another ship")


def _random_ship(size: int, length: int, generator: np.random.Generator) -> Ship:
    """A ship chosen uniformly from every placement of this length that fits on the board."""
    orientation = Orientation.HORIZONTAL if generator.integers(2) == 0 else Orientation.VERTICAL
    along = int(generator.integers(size - length + 1))
    across = int(generator.integers(size))
    start = (across, along) if orientation is Orientation.HORIZONTAL else (along, across)
    return Ship(start=start, length=length, orientation=orientation)
