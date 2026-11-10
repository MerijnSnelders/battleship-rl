import itertools
import time

import numpy as np
import pytest

from battleship.ai import MonteCarloAI, ProbabilityDensityAI, create, monte_carlo_ai
from battleship.board import Board
from battleship.config import SMALL, STANDARD, GameConfig
from battleship.ship import Orientation, Ship
from battleship.view import SquareState

H, V = Orientation.HORIZONTAL, Orientation.VERTICAL

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])

TINY = GameConfig(size=3, ships=(2, 1))


def board_with(config, *ships):
    return Board.from_ships(config, [Ship(start, length, o) for start, length, o in ships])


def fired(board, *squares):
    """Fire at the squares in order and return the view afterwards."""
    for square in squares:
        board.fire(square)
    return board.view()


def new_ai(config=SMALL, seed=0, samples=monte_carlo_ai.DEFAULT_SAMPLES):
    ai = MonteCarloAI(samples)
    ai.new_game(config, seed)
    return ai


def exact_occupancy(config, view):
    """The true fraction of possible layouts with a ship on each square, by listing them all."""
    remaining = list(config.ships)
    for ship in view.sunk_ships:
        remaining.remove(ship.length)
    grid = view.to_array()
    hits = set(zip(*np.nonzero(grid == SquareState.HIT), strict=True))

    def possible(length):
        placements = []
        for orientation in Orientation:
            for row in range(config.size):
                for col in range(config.size):
                    squares = Ship((row, col), length, orientation).squares
                    if all(r < config.size and c < config.size for r, c in squares) and all(
                        grid[square] in (SquareState.UNKNOWN, SquareState.HIT) for square in squares
                    ):
                        placements.append(frozenset(squares))
        return set(placements)  # a length-1 ship lies the same either way

    layouts = set()
    for ships in itertools.product(*(possible(length) for length in remaining)):
        covered = [square for ship in ships for square in ship]
        if len(covered) == len(set(covered)) and hits <= set(covered):
            # A set of ships, so swapping two ships of the same length is the same layout.
            layouts.add(frozenset(ships))
    counts = np.zeros((config.size, config.size))
    for layout in layouts:
        for square in itertools.chain.from_iterable(layout):
            counts[square] += 1
    counts /= len(layouts)
    counts[grid != SquareState.UNKNOWN] = 0
    return counts


def test_registered_as_monte_carlo():
    assert isinstance(create("monte_carlo"), MonteCarloAI)


def test_number_of_samples_is_configurable():
    view = Board.with_random_fleet(SMALL, 0).view()
    assert new_ai(samples=10).occupancy(view)[1] == 10
    assert new_ai().occupancy(view)[1] == monte_carlo_ai.DEFAULT_SAMPLES


def test_needs_at_least_one_sample():
    with pytest.raises(ValueError, match="samples"):
        MonteCarloAI(samples=0)


@pytest.mark.parametrize(("length", "placements"), [(1, 36), (2, 60), (3, 48)])
def test_placement_masks_list_every_placement_once(length, placements):
    masks = monte_carlo_ai._placement_masks(6, length)
    assert masks.shape == (placements, 36)
    assert np.all(masks.sum(axis=1) == length)
    assert len({mask.tobytes() for mask in masks}) == placements


# Sampling


@configs
def test_every_sample_holds_the_whole_fleet(config):
    fractions, samples = new_ai(config).occupancy(Board.with_random_fleet(config, 0).view())
    # Each sample covers exactly the fleet's squares, so the fractions add up to that.
    assert samples == monte_carlo_ai.DEFAULT_SAMPLES
    assert fractions.sum() == pytest.approx(config.ship_cells)


def test_samples_are_uniform_over_possible_layouts_on_an_empty_board():
    view = Board.with_random_fleet(TINY, 0).view()
    fractions, _ = new_ai(TINY, samples=20_000).occupancy(view)
    assert np.allclose(fractions, exact_occupancy(TINY, view), atol=0.02)


def test_samples_are_uniform_with_a_hit_and_a_miss():
    view = fired(board_with(TINY, ((0, 0), 2, H), ((2, 2), 1, H)), (1, 1), (0, 1))
    fractions, _ = new_ai(TINY, samples=20_000).occupancy(view)
    assert np.allclose(fractions, exact_occupancy(TINY, view), atol=0.02)


def test_samples_are_uniform_on_small_after_hits_misses_and_a_sink():
    board = board_with(SMALL, ((0, 3), 3, H), ((3, 0), 2, V), ((5, 4), 2, H))
    view = fired(board, (3, 0), (4, 0), (0, 4), (2, 2), (5, 0), (1, 4))
    assert len(view.sunk_ships) == 1
    fractions, _ = new_ai(SMALL, samples=20_000).occupancy(view)
    assert np.allclose(fractions, exact_occupancy(SMALL, view), atol=0.02)


def test_samples_never_cover_misses_or_sunk_squares():
    board = board_with(SMALL, ((0, 3), 3, H), ((3, 0), 2, V), ((5, 4), 2, H))
    view = fired(board, (3, 0), (4, 0), (2, 2))
    fractions, _ = new_ai().occupancy(view)
    assert fractions[2, 2] == fractions[3, 0] == fractions[4, 0] == 0
    # A square next to the sunk ship can still hold a ship.
    assert fractions[2, 0] > 0


# Shots and heatmap


@configs
def test_fires_at_a_square_with_the_highest_heatmap_score(config):
    for seed in range(3):
        board = Board.with_random_fleet(config, seed)
        ai = new_ai(config, seed, samples=200)
        while not board.is_game_over:
            view = board.view()
            heatmap = ai.heatmap(view)
            assert heatmap.dtype == float
            assert np.all((heatmap >= 0) & (heatmap <= 1))
            shot = ai.choose_shot(view)
            assert view.state(*shot) is SquareState.UNKNOWN
            assert heatmap[shot] == heatmap.max() > 0
            board.fire(shot)


def test_heatmap_is_the_occupancy_fractions():
    view = fired(Board.with_random_fleet(SMALL, 0), (0, 0), (3, 3))
    ai = new_ai()
    assert np.array_equal(ai.heatmap(view), ai.occupancy(view)[0])


def test_heatmap_and_shot_do_not_depend_on_call_order():
    view = fired(Board.with_random_fleet(STANDARD, 2), (4, 4), (5, 5))
    first, second = new_ai(STANDARD, 9), new_ai(STANDARD, 9)
    heatmap = first.heatmap(view)
    shot = second.choose_shot(view)
    assert np.array_equal(second.heatmap(view), heatmap)
    assert first.choose_shot(view) == shot


def test_ties_are_broken_at_random(monkeypatch):
    # Without samples the fallback counts tie exactly on the four centre squares.
    monkeypatch.setattr(monte_carlo_ai, "ATTEMPTS_PER_SAMPLE", 0)
    view = Board.with_random_fleet(SMALL, 0).view()
    chosen = {new_ai(seed=seed).choose_shot(view) for seed in range(200)}
    assert chosen == {(2, 2), (2, 3), (3, 2), (3, 3)}


def test_falls_back_to_probability_density_without_samples(monkeypatch):
    monkeypatch.setattr(monte_carlo_ai, "ATTEMPTS_PER_SAMPLE", 0)
    view = fired(Board.with_random_fleet(SMALL, 0), (0, 0), (2, 3))
    ai = new_ai()
    density = ProbabilityDensityAI()
    density.new_game(SMALL)
    expected = density.placement_counts(view)
    assert ai.occupancy(view)[1] == 0
    assert np.array_equal(ai.heatmap(view), expected)
    assert expected[ai.choose_shot(view)] == expected.max()


def test_stops_after_the_attempt_cap(monkeypatch):
    # Hits on two different ships make most random layouts fail, so few survive the cap.
    monkeypatch.setattr(monte_carlo_ai, "ATTEMPTS_PER_SAMPLE", 1)
    board = board_with(STANDARD, ((0, 0), 5, H), ((2, 0), 4, H), ((4, 0), 3, H),
                       ((6, 0), 3, H), ((8, 0), 2, H))  # fmt: skip
    view = fired(board, (0, 2), (4, 1), (8, 0))
    _, samples = new_ai(STANDARD).occupancy(view)
    assert 0 < samples < monte_carlo_ai.DEFAULT_SAMPLES


# Speed and strength


def play(config, board_seed, ai_seed):
    """Play one Monte Carlo AI game and return the number of shots it took."""
    board = Board.with_random_fleet(config, board_seed)
    ai = new_ai(config, ai_seed)
    while not board.is_game_over:
        board.fire(ai.choose_shot(board.view()))
    return board.shot_count


@pytest.mark.slow
def test_a_move_on_standard_takes_under_100_ms():
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
    assert np.mean(times) < 0.100
    assert max(times) < 0.100


@pytest.mark.slow
@pytest.mark.parametrize(
    ("config", "games", "low", "high"),
    [(SMALL, 1000, 16, 20), (STANDARD, 300, 41, 47)],
    ids=["small", "standard"],
)
def test_median_beats_hunt_target(config, games, low, high):
    # Measured over these seeded games: 18 on SMALL and 44 on STANDARD, against 22 and 60
    # for the Hunt/target AI and the same as the Probability density AI.
    shots = [play(config, board_seed=seed, ai_seed=10_000 + seed) for seed in range(games)]
    assert low <= np.median(shots) <= high
