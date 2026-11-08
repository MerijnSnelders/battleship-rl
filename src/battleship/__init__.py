"""Battleship game engine: the single source of truth for the rules.

Used by the website, the heuristic AIs and RL training alike.
"""

from battleship.board import (
    Board,
    GameOverError,
    IncompleteFleetError,
    InvalidPlacementError,
    InvalidShotError,
    OffBoardError,
    OverlapError,
    PlacementFailedError,
    RepeatShotError,
    ShipNotInFleetError,
    ShotOffBoardError,
)
from battleship.config import SMALL, STANDARD, GameConfig
from battleship.ship import Orientation, Ship, Square
from battleship.shot import ShotOutcome, ShotResult

__all__ = [
    "Board",
    "GameConfig",
    "GameOverError",
    "IncompleteFleetError",
    "InvalidPlacementError",
    "InvalidShotError",
    "OffBoardError",
    "Orientation",
    "OverlapError",
    "PlacementFailedError",
    "RepeatShotError",
    "SMALL",
    "STANDARD",
    "Ship",
    "ShipNotInFleetError",
    "ShotOffBoardError",
    "ShotOutcome",
    "ShotResult",
    "Square",
]
