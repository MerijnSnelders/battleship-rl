import time

import numpy as np
import pytest

from battleship.ai import ProbabilityDensityAI, create
from battleship.ai.probability_density_ai import HIT_WEIGHT
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
    ai = ProbabilityDensityAI()
    ai.new_game(config, seed)
    return ai


def reference_counts(config, view, remaining=None):
    """The weighted counts worked out the slow way, one placement at a time.

    `remaining` is the lengths of the ships still afloat; by default the fleet minus the
    sunk ships.
    """
    if remaining is None:
        remaining = list(config.ships)
        for ship in view.sunk_ships:
            remaining.remove(ship.length)
    counts = np.zeros((config.size, config.size), dtype=np.int64)
    for length in remaining:
        for orientation in Orientation:
            for row in range(config.size):
                for col in range(config.size):
                    squares = Ship((row, col), length, orientation).squares
                    if any(r >= config.size or c >= config.size for r, c in squares):
                        continue
                    states = [view.state(r, c) for r, c in squares]
                    if SquareState.MISS in states or SquareState.SUNK in states:
                        continue
                    weight = HIT_WEIGHT ** states.count(SquareState.HIT)
                    for square in squares:
                        counts[square] += weight
    counts[view.to_array() != SquareState.UNKNOWN] = 0
    return counts


# Three ships far apart, so single hits and misses are easy to set up.
SPREAD_OUT = (((0, 3), 3, H), ((3, 0), 2, V), ((5, 4), 2, H))


def test_registered_as_probability_density():
    assert isinstance(create("probability_density"), ProbabilityDensityAI)


# Counting


def test_counts_on_an_empty_board():
    counts = new_ai().placement_counts(Board.with_random_fleet(SMALL, 0).view())
    # Corner: the length-3 ship fits 2 ways, each length-2 ship 2 ways.
    assert counts[0, 0] == 2 + 2 * 2
    # Centre: the length-3 ship fits 6 ways, each length-2 ship 4 ways.
    assert counts[2, 2] == 6 + 2 * 4
    assert np.array_equal(counts, counts.T)


def test_miss_blocks_the_placements_through_it():
    view = fired(small_board(*SPREAD_OUT), (0, 1))
    counts = new_ai().placement_counts(view)
    # Only the vertical placements through the corner are left.
    assert counts[0, 0] == 1 + 2 * 1
    assert counts[0, 1] == 0


def test_only_ships_not_yet_sunk_are_counted():
    view = fired(small_board(*SPREAD_OUT), (3, 0), (4, 0), (5, 4), (5, 5))
    assert len(view.sunk_ships) == 2
    counts = new_ai().placement_counts(view)
    assert np.array_equal(counts, reference_counts(SMALL, view, remaining=[3]))
    # (4, 4) only fits the sunk length-2 ships, never the length-3 ship.
    assert counts[4, 4] == reference_counts(SMALL, view, remaining=[3])[4, 4]


def test_sunk_squares_block_placements():
    view = fired(small_board(*SPREAD_OUT), (3, 0), (4, 0))
    counts = new_ai().placement_counts(view)
    # (2, 0) sits right above the sunk ship, so no vertical placement reaches below it.
    assert counts[2, 0] == reference_counts(SMALL, view)[2, 0]
    assert counts[3, 0] == counts[4, 0] == 0


def test_lone_hit_makes_its_neighbours_the_best_squares():
    view = fired(small_board(*SPREAD_OUT), (0, 4))
    counts = new_ai().placement_counts(view)
    neighbours = {(0, 3), (0, 5), (1, 4)}
    best = {(int(r), int(c)) for r, c in zip(*np.nonzero(counts == counts.max()), strict=True)}
    assert best <= neighbours
    assert all(counts[square] > HIT_WEIGHT for square in neighbours)


def test_line_of_hits_makes_its_ends_the_best_squares():
    view = fired(small_board(((0, 2), 3, H), ((3, 0), 2, V), ((5, 4), 2, H)), (0, 3), (0, 4))
    for seed in range(50):
        assert new_ai(seed=seed).choose_shot(view) in {(0, 2), (0, 5)}


@configs
def test_counts_match_the_reference_through_whole_games(config):
    for seed in range(5):
        board = Board.with_random_fleet(config, seed)
        ai = new_ai(config, seed)
        while not board.is_game_over:
            view = board.view()
            assert np.array_equal(ai.placement_counts(view), reference_counts(config, view))
            board.fire(ai.choose_shot(view))


# Shots and heatmap


def test_ties_are_broken_at_random():
    view = Board.with_random_fleet(SMALL, 0).view()
    chosen = {new_ai(seed=seed).choose_shot(view) for seed in range(200)}
    assert chosen == {(2, 2), (2, 3), (3, 2), (3, 3)}


@configs
def test_fires_at_a_square_with_the_highest_heatmap_score(config):
    for seed in range(10):
        board = Board.with_random_fleet(config, seed)
        ai = new_ai(config, seed)
        while not board.is_game_over:
            view = board.view()
            heatmap = ai.heatmap(view)
            assert heatmap.dtype == float
            assert np.array_equal(heatmap, ai.placement_counts(view))
            shot = ai.choose_shot(view)
            assert heatmap[shot] == heatmap.max() > 0
            board.fire(shot)


# Speed and strength


def play(config, board_seed, ai_seed):
    """Play one Probability density AI game and return the number of shots it took."""
    board = Board.with_random_fleet(config, board_seed)
    ai = new_ai(config, ai_seed)
    while not board.is_game_over:
        board.fire(ai.choose_shot(board.view()))
    return board.shot_count


@pytest.mark.slow
def test_a_move_on_standard_takes_under_50_ms():
    times = []
    for seed in range(20):
        board = Board.with_random_fleet(STANDARD, seed)
        ai = new_ai(STANDARD, seed)
        while not board.is_game_over:
            view = board.view()
            start = time.perf_counter()
            shot = ai.choose_shot(view)
            times.append(time.perf_counter() - start)
            board.fire(shot)
    assert np.mean(times) < 0.050
    assert max(times) < 0.050


@pytest.mark.slow
@pytest.mark.parametrize(
    ("config", "low", "high"),
    [(SMALL, 16, 20), (STANDARD, 41, 47)],
    ids=["small", "standard"],
)
def test_median_beats_hunt_target(config, low, high):
    # Measured over these 2000 seeded games: 18 on SMALL and 44 on STANDARD, against 22
    # and 60 for the Hunt/target AI (see research.md).
    games = 2000
    shots = [play(config, board_seed=seed, ai_seed=10_000 + seed) for seed in range(games)]
    assert low <= np.median(shots) <= high
