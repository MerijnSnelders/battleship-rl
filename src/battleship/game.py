"""A game: a human and an AI firing at each other's board in turns until one fleet is sunk.

Turn rules: the first shooter is chosen by an even coin flip once both boards are complete.
Every shot that strikes a ship (hit or sunk) earns another shot, so a turn ends at the first
miss or at game over. The AI takes its whole turn at once, right after the human misses.
"""

import secrets
from dataclasses import dataclass
from enum import Enum

import numpy as np

from battleship.ai.base import AI
from battleship.board import Board, IncompleteFleetError
from battleship.config import GameConfig
from battleship.ship import Ship, Square
from battleship.shot import ShotOutcome, ShotResult

SEED_BITS = 52
"""Size of a drawn seed, small enough to survive a round trip through JavaScript numbers."""


class Side(Enum):
    """One of the two players of a game."""

    HUMAN = "human"
    AI = "ai"


class Phase(Enum):
    """Where a game stands: placing ships, firing, or finished."""

    SETUP = "setup"
    PLAYING = "playing"
    OVER = "over"


class WrongPhaseError(Exception):
    """The action is not allowed in the game's current phase."""


@dataclass(frozen=True, eq=False)
class AIShot:
    """One shot of the AI and the heatmap it had just before firing it (None if it has none)."""

    result: ShotResult
    heatmap: np.ndarray | None


@dataclass(frozen=True)
class FireResult:
    """What one shot of the human set off: that shot, then the AI's turn if the human missed."""

    shot: ShotResult
    ai_turn: tuple[AIShot, ...]


class Game:
    """A human against an AI on two boards of the same config.

    The AI's board gets a randomly placed fleet right away. The human places ships during
    setup, then `start` flips the coin. From then on `fire` takes one human shot and, if it
    missed, plays the AI's whole turn. `seed` fixes the AI's fleet, the human's random
    fleets, the coin flip and every AI shot, so the same seed and the same human actions
    always replay the same game.
    """

    def __init__(self, config: GameConfig, ai: AI, seed: int | None = None) -> None:
        if seed is None:
            seed = secrets.randbits(SEED_BITS)
        if seed < 0:
            raise ValueError("seed must not be negative")
        self.seed = seed
        ai_fleet, human_fleet, coin, ai_rng = np.random.SeedSequence(seed).spawn(4)
        self.config = config
        self.ai = ai
        self.ai_board = Board.with_random_fleet(config, ai_fleet)
        self.human_board = Board(config)
        self._human_fleet_rng = np.random.default_rng(human_fleet)
        self._coin_rng = np.random.default_rng(coin)
        self._ai_seed = ai_rng
        self._phase = Phase.SETUP
        self._first_shooter: Side | None = None
        self._winner: Side | None = None

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def first_shooter(self) -> Side | None:
        """Who took the first turn, or None during setup."""
        return self._first_shooter

    @property
    def winner(self) -> Side | None:
        """Who sank the other side's whole fleet first, or None until the game is over."""
        return self._winner

    @property
    def turn(self) -> Side | None:
        """Whose shot is next, or None outside the playing phase.

        The AI's turn is played out inside `start` and `fire`, so between calls it is
        always the human's turn while the game is playing.
        """
        return Side.HUMAN if self._phase is Phase.PLAYING else None

    def place(self, ship: Ship) -> None:
        """Put one of the human's ships on their board (setup only)."""
        self._require(Phase.SETUP)
        self.human_board.place(ship)

    def remove(self, square: Square) -> Ship:
        """Take the human's ship covering `square` off their board (setup only)."""
        self._require(Phase.SETUP)
        return self.human_board.remove(square)

    def clear(self) -> None:
        """Take every ship off the human's board (setup only)."""
        self._require(Phase.SETUP)
        self.human_board.clear()

    def random_fleet(self) -> None:
        """Replace the human's board with a randomly placed fleet (setup only)."""
        self._require(Phase.SETUP)
        board = Board.with_random_fleet(self.config, self._human_fleet_rng)
        self.human_board.clear()
        for ship in board.ships:
            self.human_board.place(ship)

    def start(self) -> tuple[AIShot, ...]:
        """Flip the coin for the first shooter and start firing.

        Raises IncompleteFleetError if the human's fleet is not fully placed. If the AI won
        the flip, its opening turn is played and returned; otherwise the result is empty.
        """
        self._require(Phase.SETUP)
        if not self.human_board.is_complete:
            raise IncompleteFleetError("place the whole fleet before starting")
        self.ai.new_game(self.config, np.random.default_rng(self._ai_seed))
        self._phase = Phase.PLAYING
        self._first_shooter = Side.HUMAN if self._coin_rng.integers(2) == 0 else Side.AI
        if self._first_shooter is Side.AI:
            return self._ai_turn()
        return ()

    def fire(self, square: Square) -> FireResult:
        """Fire the human's shot at the AI's board, then play the AI's turn if it missed.

        An invalid shot raises the board's InvalidShotError and changes nothing.
        """
        self._require(Phase.PLAYING)
        shot = self.ai_board.fire(square)
        if self.ai_board.is_game_over:
            self._finish(Side.HUMAN)
            return FireResult(shot, ())
        if shot.outcome is ShotOutcome.MISS:
            return FireResult(shot, self._ai_turn())
        return FireResult(shot, ())

    def _ai_turn(self) -> tuple[AIShot, ...]:
        shots = []
        while True:
            view = self.human_board.view()
            heatmap = self.ai.heatmap(view)
            result = self.human_board.fire(self.ai.choose_shot(view))
            shots.append(AIShot(result, heatmap))
            if self.human_board.is_game_over:
                self._finish(Side.AI)
                break
            if result.outcome is ShotOutcome.MISS:
                break
        return tuple(shots)

    def _finish(self, winner: Side) -> None:
        self._phase = Phase.OVER
        self._winner = winner

    def _require(self, phase: Phase) -> None:
        if self._phase is not phase:
            raise WrongPhaseError(
                f"not allowed while the game is {self._phase.value}, only during {phase.value}"
            )
