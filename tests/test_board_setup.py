"""Changing a board during setup: what is left to place, removing ships, clearing."""

import pytest

from battleship.board import Board, FleetLockedError, NoShipError
from battleship.config import SMALL, STANDARD
from battleship.ship import Orientation, Ship

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])


def row_ship(row, length):
    return Ship(start=(row, 0), length=length, orientation=Orientation.HORIZONTAL)


@configs
def test_an_empty_board_still_needs_the_whole_fleet(config):
    assert Board(config).unplaced == config.ships


@configs
def test_unplaced_drops_one_ship_per_placed_length(config):
    board = Board(config)
    board.place(row_ship(0, config.ships[-1]))

    assert board.unplaced == config.ships[:-1]


def test_unplaced_keeps_the_second_ship_of_a_shared_length():
    board = Board(STANDARD)
    board.place(row_ship(0, 3))

    assert board.unplaced == (5, 4, 3, 2)


@configs
def test_remove_takes_off_the_ship_covering_any_of_its_squares(config):
    board = Board(config)
    ship = row_ship(0, config.ships[0])
    board.place(ship)

    removed = board.remove(ship.squares[-1])

    assert removed == ship
    assert board.ships == ()
    assert board.unplaced == config.ships


@configs
def test_remove_on_open_water_raises_and_changes_nothing(config):
    board = Board(config)
    ship = row_ship(0, config.ships[0])
    board.place(ship)

    with pytest.raises(NoShipError):
        board.remove((config.size - 1, config.size - 1))
    assert board.ships == (ship,)


@configs
def test_clear_takes_off_every_ship(config):
    board = Board.with_random_fleet(config, 1)

    board.clear()

    assert board.ships == ()
    assert not board.is_complete


@configs
def test_ships_are_locked_once_a_shot_is_fired(config):
    board = Board.with_random_fleet(config, 1)
    ship = board.ships[0]
    board.fire(ship.start)

    with pytest.raises(FleetLockedError):
        board.remove(ship.start)
    with pytest.raises(FleetLockedError):
        board.clear()
    assert board.ships[0] == ship
