import numpy as np
import pytest

from battleship.ai import RandomAI, create
from battleship.board import Board
from battleship.config import SMALL, STANDARD
from battleship.view import SquareState

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])


def play(config, board_seed, ai_seed):
    """Play one Random AI game and return the number of shots it took."""
    board = Board.with_random_fleet(config, board_seed)
    ai = RandomAI()
    ai.new_game(config, ai_seed)
    while not board.is_game_over:
        board.fire(ai.choose_shot(board.view()))
    return board.shot_count


def test_registered_as_random():
    assert isinstance(create("random"), RandomAI)


@configs
def test_has_no_heatmap(config):
    ai = RandomAI()
    ai.new_game(config, 0)
    assert ai.heatmap(Board.with_random_fleet(config, 0).view()) is None


@configs
def test_fires_only_at_squares_not_fired_at(config):
    board = Board.with_random_fleet(config, 0)
    for square in [(0, 0), (1, 1), (2, 3), (config.size - 1, config.size - 1)]:
        board.fire(square)
    view = board.view()
    for seed in range(200):
        ai = RandomAI()
        ai.new_game(config, seed)
        assert view.state(*ai.choose_shot(view)) is SquareState.UNKNOWN


@configs
def test_last_unknown_square_is_chosen(config):
    board = Board.with_random_fleet(config, 0)
    last = board.ships[0].squares[0]
    for row in range(config.size):
        for col in range(config.size):
            if (row, col) != last:
                board.fire((row, col))
    ai = RandomAI()
    ai.new_game(config, 0)
    assert ai.choose_shot(board.view()) == last


def test_every_square_can_be_chosen_first():
    view = Board.with_random_fleet(SMALL, 0).view()
    counts = np.zeros((SMALL.size, SMALL.size), dtype=int)
    for seed in range(3600):
        ai = RandomAI()
        ai.new_game(SMALL, seed)
        counts[ai.choose_shot(view)] += 1
    # 100 picks expected per square; a uniform picker stays well inside this band.
    assert counts.min() > 50 and counts.max() < 150


@pytest.mark.slow
@pytest.mark.parametrize(
    ("config", "low", "high"),
    [(SMALL, 30, 35), (STANDARD, 94, 98)],
    ids=["small", "standard"],
)
def test_median_matches_random_fire_theory(config, low, high):
    # The shot count is the position of the last ship square in a random order of the
    # board, so the median is known in advance (about 96 on STANDARD, see research.md).
    games = 2000
    shots = [play(config, board_seed=seed, ai_seed=10_000 + seed) for seed in range(games)]
    assert low <= np.median(shots) <= high
