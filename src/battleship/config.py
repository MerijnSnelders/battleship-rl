"""Game configuration: board size and fleet.

Kept configurable so RL training can start on a small board (6x6) and scale up.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GameConfig:
    """Board size and ship lengths for one game."""

    size: int = 10
    ships: tuple[int, ...] = (5, 4, 3, 3, 2)

    def __post_init__(self) -> None:
        if self.size < 2:
            raise ValueError("board size must be at least 2")
        if not self.ships:
            raise ValueError("fleet must contain at least one ship")
        if any(length < 1 or length > self.size for length in self.ships):
            raise ValueError("every ship must fit on the board")
        if sum(self.ships) > self.size * self.size:
            raise ValueError("fleet does not fit on the board")

    @property
    def cells(self) -> int:
        """Total number of squares on the board."""
        return self.size * self.size

    @property
    def ship_cells(self) -> int:
        """Number of squares that must be hit to win."""
        return sum(self.ships)


STANDARD = GameConfig()
SMALL = GameConfig(size=6, ships=(3, 2, 2))
