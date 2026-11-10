import numpy as np
import pytest

from battleship.ai import HuntTargetAI, create
from battleship.board import Board
from battleship.config import SMALL, STANDARD
from battleship.ship import Orientation, Ship
from battleship.view import SquareState

H, V = Orientation.HORIZONTAL, Orientation.VERTICAL

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])


def small_board(*ships):
    """A SMALL board (6x6, fleet 3, 2, 2) holding exactly these ships."""
    return Board.from_ships(SMALL, [Ship(start, length, o) for start, length, o in ships])


def fired(board, *squares):
    """Fire at the squares in order and return the view afterwards."""
    for square in squares:
        board.fire(square)
    return board.view()


def new_ai(config=SMALL, seed=0):
    ai = HuntTargetAI()
    ai.new_game(config, seed)
    return ai


# Two length-2 ships side by side in columns 1 and 2, and the length-3 ship far away.
SIDE_BY_SIDE = (((1, 1), 2, V), ((1, 2), 2, V), ((4, 0), 3, H))


def test_registered_as_hunt_target():
    assert isinstance(create("hunt_target"), HuntTargetAI)


# Hunt mode


@configs
def test_hunt_mode_without_hits(config):
    board = Board.with_random_fleet(config, 0)
    ship_squares = {square for ship in board.ships for square in ship.squares}
    misses = [
        (row, col)
        for row in range(config.size)
        for col in range(config.size)
        if (row, col) not in ship_squares
    ][:5]
    view = fired(board, *misses)
    ai = new_ai(config)
    assert HuntTargetAI.target_squares(view) == []
    assert np.all(ai.heatmap(view) == 0)
    assert view.state(*ai.choose_shot(view)) is SquareState.UNKNOWN


def test_hunt_mode_reaches_every_square():
    view = Board.with_random_fleet(SMALL, 0).view()
    counts = np.zeros((SMALL.size, SMALL.size), dtype=int)
    for seed in range(3600):
        counts[new_ai(seed=seed).choose_shot(view)] += 1
    # 100 picks expected per square; a uniform picker stays well inside this band.
    assert counts.min() > 50 and counts.max() < 150


# Target mode


def test_lone_hit_targets_its_four_neighbours():
    view = fired(small_board(((2, 2), 3, H), ((0, 0), 2, H), ((5, 0), 2, H)), (2, 3))
    assert HuntTargetAI.target_squares(view) == [(1, 3), (2, 2), (2, 4), (3, 3)]


def test_lone_hit_in_a_corner_targets_the_squares_on_the_board():
    view = fired(small_board(((0, 0), 3, H), ((2, 0), 2, H), ((5, 0), 2, H)), (0, 0))
    assert HuntTargetAI.target_squares(view) == [(0, 1), (1, 0)]


def test_lone_hit_skips_squares_already_fired_at():
    board = small_board(((2, 2), 3, H), ((0, 0), 2, H), ((5, 0), 2, H))
    view = fired(board, (1, 3), (2, 3))
    assert HuntTargetAI.target_squares(view) == [(2, 2), (2, 4), (3, 3)]


def test_every_neighbour_of_a_lone_hit_can_be_chosen():
    view = fired(small_board(((2, 2), 3, H), ((0, 0), 2, H), ((5, 0), 2, H)), (2, 3))
    chosen = {new_ai(seed=seed).choose_shot(view) for seed in range(200)}
    assert chosen == {(1, 3), (2, 2), (2, 4), (3, 3)}


def test_horizontal_line_targets_only_its_ends():
    view = fired(small_board(((2, 1), 3, H), ((0, 0), 2, H), ((5, 0), 2, H)), (2, 2), (2, 3))
    assert HuntTargetAI.target_squares(view) == [(2, 1), (2, 4)]


def test_vertical_line_targets_only_its_ends():
    view = fired(small_board(((1, 4), 3, V), ((0, 0), 2, H), ((5, 0), 2, H)), (1, 4), (2, 4))
    assert HuntTargetAI.target_squares(view) == [(0, 4), (3, 4)]


def test_line_against_the_edge_targets_its_open_end():
    view = fired(small_board(((2, 0), 3, H), ((0, 0), 2, H), ((5, 0), 2, H)), (2, 0), (2, 1))
    assert HuntTargetAI.target_squares(view) == [(2, 2)]


def test_line_blocked_at_both_ends_targets_every_neighbour():
    # The two hits lie in a row, but they belong to two vertical ships side by side.
    view = fired(small_board(*SIDE_BY_SIDE), (1, 0), (1, 3), (1, 1), (1, 2))
    assert HuntTargetAI.target_squares(view) == [(0, 1), (0, 2), (2, 1), (2, 2)]


def test_stays_in_target_mode_after_a_sink_while_a_hit_remains():
    view = fired(small_board(*SIDE_BY_SIDE), (1, 1), (1, 2), (2, 1))
    assert len(view.sunk_ships) == 1
    assert HuntTargetAI.target_squares(view) == [(0, 2), (1, 3), (2, 2)]


def test_returns_to_hunt_mode_after_the_last_hit_ship_is_sunk():
    view = fired(small_board(*SIDE_BY_SIDE), (1, 1), (2, 1))
    assert len(view.sunk_ships) == 1
    ai = new_ai()
    assert HuntTargetAI.target_squares(view) == []
    assert np.all(ai.heatmap(view) == 0)


# Heatmap and shots across whole games


@configs
def test_target_mode_shots_and_heatmap_match_the_targets(config):
    for seed in range(20):
        board = Board.with_random_fleet(config, seed)
        ai = new_ai(config, seed)
        while not board.is_game_over:
            view = board.view()
            targets = HuntTargetAI.target_squares(view)
            heatmap = ai.heatmap(view)
            expected = np.zeros((config.size, config.size))
            for square in targets:
                expected[square] = 1.0
            assert np.array_equal(heatmap, expected)
            has_hit = bool(np.any(view.to_array() == SquareState.HIT))
            assert bool(targets) == has_hit
            shot = ai.choose_shot(view)
            if targets:
                assert shot in targets
            board.fire(shot)


def play(config, board_seed, ai_seed):
    """Play one Hunt/target AI game and return the number of shots it took."""
    board = Board.with_random_fleet(config, board_seed)
    ai = new_ai(config, ai_seed)
    while not board.is_game_over:
        board.fire(ai.choose_shot(board.view()))
    return board.shot_count


@pytest.mark.slow
@pytest.mark.parametrize(
    ("config", "low", "high"),
    [(SMALL, 20, 24), (STANDARD, 57, 63)],
    ids=["small", "standard"],
)
def test_median_beats_random_fire(config, low, high):
    # Measured over these 2000 seeded games: 22 on SMALL and 60 on STANDARD, far below
    # random fire (about 32 and 96, see test_random_ai.py and research.md).
    games = 2000
    shots = [play(config, board_seed=seed, ai_seed=10_000 + seed) for seed in range(games)]
    assert low <= np.median(shots) <= high
