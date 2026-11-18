"""Helpers shared by the contract tests and the simulation tests of the AIs."""

import numpy as np
import pytest

from battleship.ai import AI, create, names
from battleship.board import Board
from battleship.config import GameConfig
from battleship.ship import Square
from battleship.view import SquareState


class FirstUnknownAI(AI):
    """Test-only AI: fires at the first square not fired at yet."""

    def _choose_shot(self, view):
        return self.unknown_squares(view)[0]


class RandomWithHeatmapAI(AI):
    """Test-only AI: fires at random using its rng and shows a flat heatmap."""

    def _choose_shot(self, view):
        squares = self.unknown_squares(view)
        return squares[int(self.rng.integers(len(squares)))]

    def _heatmap(self, view):
        return (view.to_array() == SquareState.UNKNOWN).astype(float)


TEST_AIS = {"first_unknown": FirstUnknownAI, "random_with_heatmap": RandomWithHeatmapAI}


def every_ai(include_test_ais: bool = True):
    """Parametrize `make_ai` over every registered AI, so new AIs are covered automatically.

    With `include_test_ais` the test-only AIs above are added in front.
    """
    factories = dict(TEST_AIS) if include_test_ais else {}
    for name in names():
        factories[name] = lambda name=name: create(name)
    return pytest.mark.parametrize("make_ai", factories.values(), ids=factories.keys())


def play(
    ai: AI,
    config: GameConfig,
    board_seed: int | np.random.SeedSequence,
    ai_seed: int | np.random.SeedSequence | None = None,
    game: str = "game",
) -> list[Square]:
    """Play one full game on a seeded board, check every shot and heatmap, return the shots.

    `ai_seed` defaults to `board_seed`. `game` names the game in failure messages, so a
    broken AI can be replayed.
    """
    board = Board.with_random_fleet(config, np.random.default_rng(board_seed))
    ai.new_game(config, np.random.default_rng(board_seed if ai_seed is None else ai_seed))
    shots: list[Square] = []
    fired: set[Square] = set()
    while not board.is_game_over:
        view = board.view()
        heatmap = ai.heatmap(view)
        if heatmap is not None:
            assert heatmap.shape == (config.size, config.size), f"{game}: heatmap shape"
            assert np.all(heatmap >= 0), f"{game}: negative heatmap score"
            unknown = view.to_array() == SquareState.UNKNOWN
            assert np.all(heatmap[~unknown] == 0), f"{game}: heatmap scores a square fired at"
        shot = ai.choose_shot(view)
        row, col = shot
        assert 0 <= row < config.size and 0 <= col < config.size, f"{game}: {shot} off board"
        assert shot not in fired, f"{game}: fired at {shot} twice"
        board.fire(shot)
        shots.append(shot)
        fired.add(shot)
        assert len(shots) <= config.cells, f"{game}: more shots than squares on the board"
    return shots
