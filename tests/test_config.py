import pytest

from battleship.config import SMALL, STANDARD, GameConfig


def test_standard_fleet_matches_classic_rules():
    assert STANDARD.size == 10
    assert STANDARD.ships == (5, 4, 3, 3, 2)
    assert STANDARD.ship_cells == 17
    assert STANDARD.cells == 100


def test_small_board_for_training():
    assert SMALL.size == 6
    assert SMALL.ship_cells < SMALL.cells


@pytest.mark.parametrize(
    "size, ships",
    [
        (1, (1,)),  # board too small
        (5, ()),  # no ships
        (5, (6,)),  # ship longer than the board
        (2, (2, 2, 2)),  # fleet larger than the board
    ],
)
def test_invalid_configs_are_rejected(size, ships):
    with pytest.raises(ValueError):
        GameConfig(size=size, ships=ships)
