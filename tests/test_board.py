import pytest

from battleship.board import (
    Board,
    IncompleteFleetError,
    InvalidPlacementError,
    OffBoardError,
    OverlapError,
    ShipNotInFleetError,
)
from battleship.config import SMALL, STANDARD
from battleship.ship import Orientation, Ship

H = Orientation.HORIZONTAL
V = Orientation.VERTICAL

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])


@configs
def test_legal_ship_is_accepted(config):
    board = Board(config)
    ship = Ship(start=(0, 0), length=config.ships[0], orientation=H)

    board.place(ship)

    assert board.ships == (ship,)


@configs
@pytest.mark.parametrize("orientation", [H, V])
def test_ship_may_end_exactly_on_the_last_row_or_column(config, orientation):
    length = config.ships[0]
    last_start = config.size - length
    start = (0, last_start) if orientation is H else (last_start, 0)
    board = Board(config)

    board.place(Ship(start=start, length=length, orientation=orientation))

    assert len(board.ships) == 1


@configs
@pytest.mark.parametrize("orientation", [H, V])
def test_ship_one_square_past_the_edge_is_off_the_board(config, orientation):
    length = config.ships[0]
    past_start = config.size - length + 1
    start = (0, past_start) if orientation is H else (past_start, 0)
    board = Board(config)

    with pytest.raises(OffBoardError):
        board.place(Ship(start=start, length=length, orientation=orientation))

    assert board.ships == ()


@configs
@pytest.mark.parametrize("orientation", [H, V])
@pytest.mark.parametrize("offset", [(-1, 0), (0, -1)], ids=["row", "column"])
def test_ship_starting_before_the_board_is_off_the_board(config, orientation, offset):
    board = Board(config)

    with pytest.raises(OffBoardError):
        board.place(Ship(start=offset, length=config.ships[0], orientation=orientation))


@configs
def test_ship_starting_beyond_the_board_is_off_the_board(config):
    board = Board(config)

    with pytest.raises(OffBoardError):
        board.place(Ship(start=(config.size, 0), length=config.ships[0], orientation=H))


def test_off_board_is_an_invalid_placement_and_a_value_error():
    assert issubclass(OffBoardError, InvalidPlacementError)
    assert issubclass(InvalidPlacementError, ValueError)


@configs
def test_crossing_ships_overlap(config):
    long, short = config.ships[0], config.ships[1]
    board = Board(config)
    flat = Ship(start=(1, 0), length=long, orientation=H)
    board.place(flat)

    with pytest.raises(OverlapError):
        board.place(Ship(start=(0, 0), length=short, orientation=V))

    assert board.ships == (flat,)


@configs
def test_ships_sharing_only_an_end_square_overlap(config):
    long, short = config.ships[0], config.ships[1]
    board = Board(config)
    board.place(Ship(start=(0, 0), length=long, orientation=H))

    with pytest.raises(OverlapError):
        board.place(Ship(start=(0, long - 1), length=short, orientation=H))


@configs
@pytest.mark.parametrize(
    "second_start",
    [
        lambda long: (1, 0),  # side by side, along the whole ship
        lambda long: (0, long),  # end to end in the same row
        lambda long: (1, long),  # corner to corner
    ],
    ids=["side-by-side", "end-to-end", "corner-to-corner"],
)
def test_touching_ships_are_allowed(config, second_start):
    long, short = config.ships[0], config.ships[1]
    board = Board(config)
    board.place(Ship(start=(0, 0), length=long, orientation=H))

    board.place(Ship(start=second_start(long), length=short, orientation=H))

    assert len(board.ships) == 2


def test_overlap_is_an_invalid_placement():
    assert issubclass(OverlapError, InvalidPlacementError)


@configs
def test_ship_with_a_length_the_fleet_does_not_have_is_rejected(config):
    foreign = max(config.ships) + 1
    board = Board(config)

    with pytest.raises(ShipNotInFleetError):
        board.place(Ship(start=(0, 0), length=foreign, orientation=H))

    assert board.ships == ()


@configs
def test_each_ship_of_the_fleet_can_be_placed_but_not_one_more(config):
    for length in sorted(set(config.ships)):
        board = Board(config)
        copies = config.ships.count(length)
        for row in range(0, 2 * copies, 2):
            board.place(Ship(start=(row, 0), length=length, orientation=H))

        with pytest.raises(ShipNotInFleetError):
            board.place(Ship(start=(2 * copies, 0), length=length, orientation=H))

        assert len(board.ships) == copies


@configs
def test_fleet_is_checked_before_the_board_edge(config):
    foreign = max(config.ships) + 1
    last = config.size - 1
    board = Board(config)

    with pytest.raises(ShipNotInFleetError):
        board.place(Ship(start=(last, last), length=foreign, orientation=H))


def test_ship_not_in_fleet_is_an_invalid_placement():
    assert issubclass(ShipNotInFleetError, InvalidPlacementError)


def full_fleet(config):
    """One legal ship per fleet entry, each on its own row, so none touch or overlap."""
    return [Ship(start=(2 * i, 0), length=n, orientation=H) for i, n in enumerate(config.ships)]


@configs
def test_board_is_complete_only_when_the_whole_fleet_is_placed(config):
    board = Board(config)
    assert not board.is_complete

    *most, last = full_fleet(config)
    for ship in most:
        board.place(ship)
    assert not board.is_complete

    board.place(last)
    assert board.is_complete


@configs
def test_from_ships_builds_a_complete_board(config):
    ships = full_fleet(config)

    board = Board.from_ships(config, ships)

    assert board.is_complete
    assert board.ships == tuple(ships)
    assert board.config is config


@configs
def test_from_ships_rejects_a_fleet_with_a_missing_ship(config):
    with pytest.raises(IncompleteFleetError):
        Board.from_ships(config, full_fleet(config)[:-1])


@configs
def test_from_ships_rejects_an_empty_fleet(config):
    with pytest.raises(IncompleteFleetError):
        Board.from_ships(config, [])


@configs
def test_from_ships_rejects_an_extra_ship(config):
    extra = Ship(start=(config.size - 1, 0), length=config.ships[0], orientation=H)

    with pytest.raises(ShipNotInFleetError):
        Board.from_ships(config, [*full_fleet(config), extra])


@configs
def test_from_ships_rejects_a_ship_of_the_wrong_length(config):
    *most, last = full_fleet(config)
    wrong = Ship(start=last.start, length=max(config.ships) + 1, orientation=H)

    with pytest.raises(ShipNotInFleetError):
        Board.from_ships(config, [*most, wrong])


@configs
def test_from_ships_passes_on_placement_errors(config):
    first, second, *rest = full_fleet(config)
    overlapping = Ship(start=first.start, length=second.length, orientation=V)

    with pytest.raises(OverlapError):
        Board.from_ships(config, [first, overlapping, *rest])


def test_incomplete_fleet_is_a_value_error_but_not_a_single_bad_placement():
    assert issubclass(IncompleteFleetError, ValueError)
    assert not issubclass(IncompleteFleetError, InvalidPlacementError)


@configs
def test_can_place_agrees_with_place_and_changes_nothing(config):
    long, short = config.ships[0], config.ships[1]
    board = Board(config)
    board.place(Ship(start=(1, 0), length=long, orientation=H))
    before = board.ships

    legal = Ship(start=(3, 0), length=short, orientation=H)
    off_board = Ship(start=(0, config.size - 1), length=short, orientation=H)
    overlapping = Ship(start=(0, 0), length=short, orientation=V)
    foreign = Ship(start=(3, 0), length=max(config.ships) + 1, orientation=H)

    assert board.can_place(legal)
    assert not board.can_place(off_board)
    assert not board.can_place(overlapping)
    assert not board.can_place(foreign)
    assert board.ships == before


@configs
def test_board_edge_is_checked_before_overlap(config):
    long, short = config.ships[0], config.ships[1]
    board = Board(config)
    board.place(Ship(start=(0, config.size - long), length=long, orientation=H))

    # Covers the last square of the first ship and runs past the edge.
    with pytest.raises(OffBoardError):
        board.place(Ship(start=(0, config.size - 1), length=short, orientation=H))
