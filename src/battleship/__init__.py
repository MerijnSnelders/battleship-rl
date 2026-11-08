"""Battleship game engine: the single source of truth for the rules.

Used by the website, the heuristic AIs and RL training alike.
"""

from battleship.board import (
    Board,
    IncompleteFleetError,
    InvalidPlacementError,
    OffBoardError,
    OverlapError,
    ShipNotInFleetError,
)
from battleship.config import SMALL, STANDARD, GameConfig
from battleship.ship import Orientation, Ship, Square

__all__ = [
    "Board",
    "GameConfig",
    "IncompleteFleetError",
    "InvalidPlacementError",
    "OffBoardError",
    "Orientation",
    "OverlapError",
    "SMALL",
    "STANDARD",
    "Ship",
    "ShipNotInFleetError",
    "Square",
]
