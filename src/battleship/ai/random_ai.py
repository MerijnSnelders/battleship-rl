"""The Random AI: the baseline every other AI must beat."""

from battleship.ai.base import AI
from battleship.ai.registry import register
from battleship.ship import Square
from battleship.view import PlayerView


@register("random")
class RandomAI(AI):
    """Fires at a square chosen uniformly at random from the squares not fired at yet.

    It ignores hits and sunk ships entirely and keeps no state between shots, so the
    shot depends only on the view and the game's random generator.
    """

    display_name = "Random"
    description = "Fires at any square not fired at yet, ignoring every hit."
    explanation = (
        "Every shot goes to a square chosen uniformly at random from the squares not fired at "
        "yet. It ignores hits and sunk ships, so it usually needs most of the board to finish. "
        "It is the lower bound: any AI that learns something from its shots should beat it."
    )

    def _choose_shot(self, view: PlayerView) -> Square:
        squares = self.unknown_squares(view)
        return squares[int(self.rng.integers(len(squares)))]
