"""The Hunt/target AI: random fire until a hit, then finish off the ship."""

import numpy as np

from battleship.ai.base import AI
from battleship.ai.registry import register
from battleship.ship import Square
from battleship.view import PlayerView, SquareState

_NEIGHBOUR_STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1))


@register("hunt_target")
class HuntTargetAI(AI):
    """Fires in hunt mode while no hit is on the board and in target mode while one is.

    Hunt mode fires at a random square not fired at yet. Target mode fires next to the
    hits: a lone hit gets its unknown neighbours, and a straight line of hits only gets
    the squares just past its two ends. When both ends are blocked, the line must be
    several ships side by side, so every unknown neighbour of the line is a target.

    The targets are read from the view on every shot, so the AI keeps no state between
    shots. A hit always belongs to a ship still afloat, so it stays in target mode after
    a sink as long as another ship has been hit.
    """

    def _choose_shot(self, view: PlayerView) -> Square:
        squares = self.target_squares(view) or self.unknown_squares(view)
        return squares[int(self.rng.integers(len(squares)))]

    def _heatmap(self, view: PlayerView) -> np.ndarray:
        """1 on every target square in target mode; all zeros in hunt mode."""
        heatmap = np.zeros((view.size, view.size), dtype=float)
        for square in self.target_squares(view):
            heatmap[square] = 1.0
        return heatmap

    @staticmethod
    def target_squares(view: PlayerView) -> list[Square]:
        """The squares target mode picks from, row by row; empty in hunt mode."""
        grid = view.to_array()
        targets: set[Square] = set()
        for group in _hit_groups(grid):
            targets.update(_line_ends(grid, group) or _unknown_neighbours(grid, group))
        return sorted(targets)


def _hit_groups(grid: np.ndarray) -> list[list[Square]]:
    """The hits split into groups of squares that touch side by side."""
    hits = {(int(r), int(c)) for r, c in zip(*np.nonzero(grid == SquareState.HIT), strict=True)}
    groups = []
    while hits:
        stack = [hits.pop()]
        group = []
        while stack:
            row, col = stack.pop()
            group.append((row, col))
            for d_row, d_col in _NEIGHBOUR_STEPS:
                neighbour = (row + d_row, col + d_col)
                if neighbour in hits:
                    hits.remove(neighbour)
                    stack.append(neighbour)
        groups.append(sorted(group))
    return groups


def _is_unknown(grid: np.ndarray, square: Square) -> bool:
    row, col = square
    size = grid.shape[0]
    return 0 <= row < size and 0 <= col < size and grid[row, col] == SquareState.UNKNOWN


def _line_ends(grid: np.ndarray, group: list[Square]) -> list[Square]:
    """The unknown squares just past both ends of a straight line of two or more hits.

    Empty for a lone hit, a group that is not a straight line, or a line blocked at both
    ends. A group is sorted and connected, so a straight one has no gaps.
    """
    if len(group) < 2:
        return []
    (first_row, first_col), (last_row, last_col) = group[0], group[-1]
    if first_row == last_row:
        ends = [(first_row, first_col - 1), (last_row, last_col + 1)]
    elif first_col == last_col:
        ends = [(first_row - 1, first_col), (last_row + 1, last_col)]
    else:
        return []
    return [square for square in ends if _is_unknown(grid, square)]


def _unknown_neighbours(grid: np.ndarray, group: list[Square]) -> list[Square]:
    """Every unknown square directly above, below, left or right of a hit in the group."""
    return [
        (row + d_row, col + d_col)
        for row, col in group
        for d_row, d_col in _NEIGHBOUR_STEPS
        if _is_unknown(grid, (row + d_row, col + d_col))
    ]
