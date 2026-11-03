import pytest

from battleship.ship import Orientation, Ship


def test_horizontal_ship_runs_to_higher_columns():
    ship = Ship(start=(2, 1), length=3, orientation=Orientation.HORIZONTAL)

    assert ship.squares == ((2, 1), (2, 2), (2, 3))


def test_vertical_ship_runs_to_higher_rows():
    ship = Ship(start=(2, 1), length=3, orientation=Orientation.VERTICAL)

    assert ship.squares == ((2, 1), (3, 1), (4, 1))


def test_ship_of_length_one_covers_only_its_start():
    ship = Ship(start=(0, 4), length=1, orientation=Orientation.VERTICAL)

    assert ship.squares == ((0, 4),)


@pytest.mark.parametrize("length", [0, -1])
def test_ship_needs_a_positive_length(length):
    with pytest.raises(ValueError):
        Ship(start=(0, 0), length=length, orientation=Orientation.HORIZONTAL)
