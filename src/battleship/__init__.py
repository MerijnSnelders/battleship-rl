"""Battleship game engine: the single source of truth for the rules.

Used by the website, the heuristic AIs and RL training alike.
"""

from battleship.board import (
    Board,
    FleetLockedError,
    GameOverError,
    IncompleteFleetError,
    InvalidPlacementError,
    InvalidShotError,
    NoShipError,
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
from battleship.view import PlayerView, SquareState

__all__ = [
    "Board",
    "FleetLockedError",
    "GameConfig",
    "GameOverError",
    "IncompleteFleetError",
    "InvalidPlacementError",
    "InvalidShotError",
    "NoShipError",
    "OffBoardError",
    "Orientation",
    "OverlapError",
    "PlacementFailedError",
    "PlayerView",
    "RepeatShotError",
    "SMALL",
    "STANDARD",
    "Ship",
    "ShipNotInFleetError",
    "ShotOffBoardError",
    "ShotOutcome",
    "ShotResult",
    "Square",
    "SquareState",
]
