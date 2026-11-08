import numpy as np
import pytest

from battleship import board as board_module
from battleship.board import Board, PlacementFailedError
from battleship.config import SMALL, STANDARD, GameConfig
from battleship.ship import Orientation

SEEDS = range(1_000)

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])


@pytest.fixture(scope="module")
def boards():
    """1,000 randomly placed fleets per config, one per seed."""
    return {
        config: [Board.with_random_fleet(config, seed) for seed in SEEDS]
        for config in (SMALL, STANDARD)
    }


@configs
def test_every_randomly_placed_fleet_is_legal(config, boards):
    for board in boards[config]:
        assert board.is_complete
        assert board.config is config
        assert tuple(ship.length for ship in board.ships) == config.ships

        covered = [square for ship in board.ships for square in ship.squares]
        assert len(covered) == len(set(covered)), "ships overlap"
        assert all(0 <= row < config.size and 0 <= col < config.size for row, col in covered)


@configs
def test_same_seed_gives_the_same_board(config):
    assert Board.with_random_fleet(config, 42).ships == Board.with_random_fleet(config, 42).ships


@configs
def test_seed_and_generator_with_that_seed_agree(config):
    from_seed = Board.with_random_fleet(config, 7)
    from_generator = Board.with_random_fleet(config, np.random.default_rng(7))

    assert from_seed.ships == from_generator.ships


@configs
def test_a_shared_generator_moves_on_between_boards(config):
    generator = np.random.default_rng(0)

    first = Board.with_random_fleet(config, generator)
    second = Board.with_random_fleet(config, generator)

    assert first.ships != second.ships


@configs
def test_without_a_seed_a_board_is_still_complete(config):
    assert Board.with_random_fleet(config).is_complete


@configs
def test_every_square_is_covered_by_some_board(config, boards):
    covered = {
        square for board in boards[config] for ship in board.ships for square in ship.squares
    }

    assert len(covered) == config.cells


@configs
def test_every_ship_length_appears_in_both_orientations(config, boards):
    seen = {(ship.length, ship.orientation) for board in boards[config] for ship in board.ships}

    for length in set(config.ships):
        assert (length, Orientation.HORIZONTAL) in seen
        assert (length, Orientation.VERTICAL) in seen


@configs
def test_longest_ship_starts_on_every_square_it_can(config, boards):
    longest = max(config.ships)
    last = config.size - longest
    possible = {
        (row, col)
        for row in range(config.size)
        for col in range(config.size)
        if row <= last or col <= last
    }

    starts = {
        ship.start for board in boards[config] for ship in board.ships if ship.length == longest
    }

    assert starts == possible


@configs
def test_different_seeds_give_different_boards(config, boards):
    distinct = {frozenset(board.ships) for board in boards[config]}

    assert len(distinct) >= 990


def test_too_crowded_fleet_raises_after_the_try_limit(monkeypatch):
    # Three ships of 3 on a 3x3 board only fit as three rows or three columns,
    # so a single try fails for most seeds.
    crowded = GameConfig(size=3, ships=(3, 3, 3))
    monkeypatch.setattr(board_module, "MAX_PLACEMENT_TRIES", 1)

    failures = 0
    for seed in range(50):
        try:
            board = Board.with_random_fleet(crowded, seed)
        except PlacementFailedError:
            failures += 1
        else:
            assert board.is_complete

    assert failures > 0


def test_crowded_fleet_is_found_with_enough_tries():
    crowded = GameConfig(size=3, ships=(3, 3, 3))

    board = Board.with_random_fleet(crowded, 0)

    orientations = {ship.orientation for ship in board.ships}
    assert len(orientations) == 1


def test_placement_failed_is_a_value_error():
    assert issubclass(PlacementFailedError, ValueError)
