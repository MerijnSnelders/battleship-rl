"""Ships and the squares they cover."""

from dataclasses import dataclass
from enum import Enum

Square = tuple[int, int]
"""A position on a board as (row, column), counted from the top-left square (0, 0)."""


class Orientation(Enum):
    """Whether a ship runs along a row or down a column."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass(frozen=True)
class Ship:
    """A straight run of squares, from its top-left end to the right or downwards."""

    start: Square
    length: int
    orientation: Orientation

    def __post_init__(self) -> None:
        if self.length < 1:
            raise ValueError("ship length must be at least 1")

    @property
    def squares(self) -> tuple[Square, ...]:
        """Every square the ship covers, starting at the top-left end."""
        row, col = self.start
        if self.orientation is Orientation.HORIZONTAL:
            return tuple((row, col + i) for i in range(self.length))
        return tuple((row + i, col) for i in range(self.length))
