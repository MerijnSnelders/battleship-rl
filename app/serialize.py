"""Turn games, ships, shots and heatmaps into the JSON the browser receives.

The one rule here: the AI's ships appear only once the game is over. Everything else about
the AI's board goes out as a player view, which never shows a square not fired at.
"""

from typing import Any

import numpy as np

from battleship.game import AIShot, Game, Phase
from battleship.ship import Orientation, Ship
from battleship.shot import ShotResult

HEATMAP_DECIMALS = 4
"""Heatmap values are rounded to this many decimals to keep responses small."""


def ship(ship: Ship) -> dict[str, Any]:
    return {
        "start": list(ship.start),
        "length": ship.length,
        "orientation": ship.orientation.value,
        "squares": [list(square) for square in ship.squares],
    }


def shot(result: ShotResult) -> dict[str, Any]:
    return {
        "square": list(result.square),
        "outcome": result.outcome.value,
        "sunk_ship": ship(result.sunk_ship) if result.sunk_ship is not None else None,
    }


def heatmap(scores: np.ndarray | None) -> list[list[float]] | None:
    """The heatmap scaled so the square the AI wants most is 1, or None if it has none."""
    if scores is None:
        return None
    highest = float(scores.max())
    scaled = scores / highest if highest > 0 else np.zeros_like(scores, dtype=float)
    return np.round(scaled, HEATMAP_DECIMALS).tolist()


def ai_turn(shots: tuple[AIShot, ...]) -> list[dict[str, Any]]:
    """The AI's shots in the order fired, each with the heatmap it was chosen from."""
    return [{**shot(item.result), "heatmap": heatmap(item.heatmap)} for item in shots]


def legal_starts(game: Game) -> list[dict[str, Any]]:
    """For each length still to place, the start squares of its legal placements.

    The frontend looks placements up here instead of knowing the placement rules itself.
    """
    board = game.human_board
    result = []
    for length in dict.fromkeys(board.unplaced):
        starts: dict[str, list[list[int]]] = {item.value: [] for item in Orientation}
        for placement in board.legal_placements(length):
            starts[placement.orientation.value].append(list(placement.start))
        result.append({"length": length, **starts})
    return result


def state(game_id: str, opponent: str, game: Game) -> dict[str, Any]:
    """Everything the human may know about a game, enough to draw it after a page reload."""
    over = game.phase is Phase.OVER
    return {
        "id": game_id,
        "opponent": opponent,
        "config": {"size": game.config.size, "ships": list(game.config.ships)},
        "seed": game.seed,
        "phase": game.phase.value,
        "turn": _side(game.turn),
        "first_shooter": _side(game.first_shooter),
        "winner": _side(game.winner),
        "human_board": {
            "ships": [ship(item) for item in game.human_board.ships],
            "unplaced": list(game.human_board.unplaced),
            "legal_starts": legal_starts(game) if game.phase is Phase.SETUP else None,
            "view": game.human_board.view().to_dict(),
            "heatmap": heatmap(game.ai_heatmap()),
        },
        "ai_board": {
            "view": game.ai_board.view().to_dict(),
            "ships": [ship(item) for item in game.ai_board.ships] if over else None,
        },
    }


def _side(side: Any) -> str | None:
    return side.value if side is not None else None
