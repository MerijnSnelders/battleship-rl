"""Battleship game engine: the single source of truth for the rules.

Used by the website, the heuristic AIs and RL training alike.
"""

from battleship.board import (
    Board,
    IncompleteFleetError,
    InvalidPlacementError,
    OffBoardError,
    OverlapError,
    PlacementFailedError,
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
    "PlacementFailedError",
    "SMALL",
    "STANDARD",
    "Ship",
    "ShipNotInFleetError",
    "Square",
]
