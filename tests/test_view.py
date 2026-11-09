import json

import numpy as np
import pytest

from battleship.board import Board
from battleship.config import SMALL, STANDARD
from battleship.ship import Orientation, Ship
from battleship.view import PlayerView, SquareState

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])


def stacked_board(config):
    """Every ship horizontal on its own row from the left edge; the last row stays empty."""
    ships = [
        Ship(start=(row, 0), length=length, orientation=Orientation.HORIZONTAL)
        for row, length in enumerate(config.ships)
    ]
    return Board.from_ships(config, ships)


def empty_square(config):
    return (config.size - 1, config.size - 1)


def ship_squares(board):
    return {square for ship in board.ships for square in ship.squares}


@configs
def test_a_fresh_board_shows_every_square_unknown(config):
    view = stacked_board(config).view()

    array = view.to_array()
    assert array.shape == (config.size, config.size)
    assert array.dtype == np.int8
    assert (array == SquareState.UNKNOWN).all()
    assert view.sunk_ships == ()
    assert view.shot_count == 0
    assert not view.is_game_over


@configs
def test_a_miss_shows_as_miss(config):
    board = stacked_board(config)
    board.fire(empty_square(config))

    view = board.view()

    assert view.state(*empty_square(config)) is SquareState.MISS
    assert view.shot_count == 1


@configs
def test_a_hit_shows_as_hit_and_the_rest_of_the_ship_stays_unknown(config):
    board = stacked_board(config)
    ship = board.ships[0]
    board.fire(ship.start)

    view = board.view()

    assert view.state(*ship.start) is SquareState.HIT
    for square in ship.squares[1:]:
        assert view.state(*square) is SquareState.UNKNOWN


@configs
def test_every_square_of_a_sunk_ship_shows_as_sunk(config):
    board = stacked_board(config)
    ship = board.ships[0]
    for square in ship.squares:
        board.fire(square)

    view = board.view()

    assert all(view.state(*square) is SquareState.SUNK for square in ship.squares)
    assert view.sunk_ships == (ship,)


@configs
@pytest.mark.parametrize("seed", range(20))
def test_unhit_ship_squares_never_show_in_the_array(config, seed):
    """Random shots at a random board: only squares fired at may ever be known."""
    rng = np.random.default_rng(seed)
    board = Board.with_random_fleet(config, rng)
    squares = [(r, c) for r in range(config.size) for c in range(config.size)]
    order = rng.permutation(len(squares))

    for index in order[: len(squares) // 2]:
        if board.is_game_over:
            break
        board.fire(squares[index])
        array = board.view().to_array()
        fired = {shot.square for shot in board.shots}
        covered = ship_squares(board)
        sunk = {sq for shot in board.shots if shot.sunk_ship for sq in shot.sunk_ship.squares}
        for square in squares:
            if square not in fired:
                # A square never fired at is unknown, even if a ship covers it.
                assert array[square] == SquareState.UNKNOWN
            elif square in sunk:
                assert array[square] == SquareState.SUNK
            elif square in covered:
                assert array[square] == SquareState.HIT
            else:
                assert array[square] == SquareState.MISS


@configs
def test_the_json_never_mentions_unhit_ship_squares(config):
    board = stacked_board(config)
    ship = board.ships[0]
    board.fire(ship.start)
    board.fire(empty_square(config))

    data = board.view().to_dict()

    hidden = ship_squares(board) - {ship.start}
    for row, col in hidden:
        assert data["grid"][row][col] == "unknown"
    assert data["sunk_ships"] == []
    assert "ships" not in data


@configs
def test_the_json_shape(config):
    board = stacked_board(config)
    ship = board.ships[-1]
    for square in ship.squares:
        board.fire(square)
    board.fire(empty_square(config))

    data = board.view().to_dict()

    assert json.loads(json.dumps(data)) == data
    assert data["size"] == config.size
    assert len(data["grid"]) == config.size
    assert all(len(row) == config.size for row in data["grid"])
    row, col = empty_square(config)
    assert data["grid"][row][col] == "miss"
    assert data["sunk_ships"] == [
        {"length": ship.length, "squares": [list(sq) for sq in ship.squares]}
    ]
    assert data["shot_count"] == ship.length + 1
    assert data["game_over"] is False


@configs
def test_game_over_shows_in_the_view(config):
    board = stacked_board(config)
    for ship in board.ships:
        for square in ship.squares:
            board.fire(square)

    view = board.view()

    assert view.is_game_over
    assert view.to_dict()["game_over"] is True
    assert len(view.sunk_ships) == len(config.ships)
    assert (view.to_array() == SquareState.SUNK).sum() == config.ship_cells


@configs
def test_the_view_is_a_snapshot(config):
    board = stacked_board(config)
    view = board.view()

    board.fire(empty_square(config))

    assert view.state(*empty_square(config)) is SquareState.UNKNOWN
    assert view.shot_count == 0


def test_changing_the_array_does_not_change_the_view():
    board = stacked_board(SMALL)
    view = board.view()

    array = view.to_array()
    array[:] = SquareState.SUNK

    assert view.state(0, 0) is SquareState.UNKNOWN


def test_square_state_codes_are_stable():
    """AIs and the RL agent depend on these codes."""
    assert [state.value for state in SquareState] == [0, 1, 2, 3]
    assert isinstance(stacked_board(SMALL).view(), PlayerView)
