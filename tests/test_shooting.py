import pytest

from battleship.board import (
    Board,
    GameOverError,
    IncompleteFleetError,
    InvalidShotError,
    RepeatShotError,
    ShotOffBoardError,
)
from battleship.config import SMALL, STANDARD, GameConfig
from battleship.ship import Orientation, Ship
from battleship.shot import ShotOutcome, ShotResult

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


def sink(board, ship):
    return [board.fire(square) for square in ship.squares]


@configs
def test_shot_at_open_water_is_a_miss(config):
    board = stacked_board(config)

    result = board.fire(empty_square(config))

    assert result == ShotResult(empty_square(config), ShotOutcome.MISS)
    assert result.sunk_ship is None
    assert result.sunk_length is None


@configs
def test_shot_at_a_ship_with_squares_left_is_a_hit(config):
    board = stacked_board(config)
    ship = board.ships[0]
    assert ship.length > 1

    result = board.fire(ship.start)

    assert result.outcome is ShotOutcome.HIT
    assert result.sunk_length is None


@configs
def test_hitting_the_last_square_of_a_ship_sinks_it(config):
    board = stacked_board(config)
    ship = board.ships[0]

    results = sink(board, ship)

    assert [r.outcome for r in results[:-1]] == [ShotOutcome.HIT] * (ship.length - 1)
    assert results[-1].outcome is ShotOutcome.SUNK
    assert results[-1].sunk_ship == ship
    assert results[-1].sunk_length == ship.length


def test_a_ship_of_length_one_sinks_with_one_shot():
    config = GameConfig(size=3, ships=(1,))
    ship = Ship(start=(1, 1), length=1, orientation=Orientation.VERTICAL)
    board = Board.from_ships(config, [ship])

    result = board.fire((1, 1))

    assert result.outcome is ShotOutcome.SUNK
    assert result.sunk_length == 1


@configs
def test_sinking_one_ship_does_not_sink_its_neighbour(config):
    board = stacked_board(config)

    sink(board, board.ships[0])
    result = board.fire(board.ships[1].start)

    assert board.ships[1].length > 1
    assert result.outcome is ShotOutcome.HIT


@configs
def test_game_is_over_once_every_ship_is_sunk(config):
    board = stacked_board(config)

    for ship in board.ships[:-1]:
        sink(board, ship)
        assert not board.is_game_over
    final = sink(board, board.ships[-1])

    assert final[-1].outcome is ShotOutcome.SUNK
    assert board.is_game_over


@configs
def test_new_board_is_not_game_over(config):
    assert not stacked_board(config).is_game_over


@configs
def test_shots_are_counted_and_recorded_in_order(config):
    board = stacked_board(config)

    first = board.fire(empty_square(config))
    second = board.fire(board.ships[0].start)

    assert board.shot_count == 2
    assert board.shots == (first, second)


@configs
def test_shot_count_at_game_over_is_ship_squares_plus_misses(config):
    board = stacked_board(config)

    board.fire(empty_square(config))
    for ship in board.ships:
        sink(board, ship)

    assert board.shot_count == config.ship_cells + 1


@configs
@pytest.mark.parametrize("hit", [False, True], ids=["miss", "hit"])
def test_firing_at_the_same_square_twice_is_rejected(config, hit):
    board = stacked_board(config)
    square = board.ships[0].start if hit else empty_square(config)
    board.fire(square)

    with pytest.raises(RepeatShotError):
        board.fire(square)

    assert board.shot_count == 1


@configs
@pytest.mark.parametrize("offset", [(-1, 0), (0, -1), (1, 0), (0, 1)])
def test_firing_off_the_board_is_rejected(config, offset):
    board = stacked_board(config)
    row, col = offset
    square = (row * config.size if row > 0 else row, col * config.size if col > 0 else col)

    with pytest.raises(ShotOffBoardError):
        board.fire(square)

    assert board.shot_count == 0


@configs
def test_firing_after_game_over_is_rejected(config):
    board = stacked_board(config)
    for ship in board.ships:
        sink(board, ship)

    with pytest.raises(GameOverError):
        board.fire(empty_square(config))

    assert board.shot_count == config.ship_cells


@configs
def test_firing_at_an_incomplete_board_is_rejected(config):
    board = Board(config)

    with pytest.raises(IncompleteFleetError):
        board.fire((0, 0))

    assert not board.is_game_over


@configs
def test_random_fleet_can_be_played_to_game_over(config):
    board = Board.with_random_fleet(config, rng=7)
    squares = [(row, col) for row in range(config.size) for col in range(config.size)]

    results = []
    for square in squares:
        if board.is_game_over:
            break
        results.append(board.fire(square))

    assert board.is_game_over
    sunk = sorted(r.sunk_length for r in results if r.outcome is ShotOutcome.SUNK)
    assert sunk == sorted(config.ships)


def test_shot_errors_are_invalid_shots_and_value_errors():
    for error in (ShotOffBoardError, RepeatShotError, GameOverError):
        assert issubclass(error, InvalidShotError)
    assert issubclass(InvalidShotError, ValueError)


def test_result_rejects_sunk_ship_without_sunk_outcome():
    ship = Ship(start=(0, 0), length=2, orientation=Orientation.HORIZONTAL)

    with pytest.raises(ValueError):
        ShotResult((0, 0), ShotOutcome.HIT, sunk_ship=ship)
    with pytest.raises(ValueError):
        ShotResult((0, 0), ShotOutcome.SUNK)
