"""Shots fired at a board and what they reveal."""

from dataclasses import dataclass
from enum import Enum

from battleship.ship import Ship, Square


class ShotOutcome(Enum):
    """What a shot reveals: nothing, part of a ship, or the last unhit square of a ship."""

    MISS = "miss"
    HIT = "hit"
    SUNK = "sunk"


@dataclass(frozen=True)
class ShotResult:
    """One shot: the square fired at and what it revealed.

    A shot that hits the last unhit square of a ship is SUNK, not HIT, and carries that
    ship so it can be shown as sunk. Every other shot has no sunk ship.
    """

    square: Square
    outcome: ShotOutcome
    sunk_ship: Ship | None = None

    def __post_init__(self) -> None:
        if (self.outcome is ShotOutcome.SUNK) != (self.sunk_ship is not None):
            raise ValueError("a sunk ship is given exactly when the outcome is SUNK")

    @property
    def sunk_length(self) -> int | None:
        """Length of the ship this shot sank, or None if it sank nothing."""
        return self.sunk_ship.length if self.sunk_ship is not None else None
