"""The games the server is holding, by game ID, and their removal once idle.

Games live in memory only. A game nobody touched for over `IDLE_LIMIT` seconds is removed
the next time anyone uses the store, and at most `MAX_GAMES` are kept: creating one more
drops the game idle the longest. Each game has its own lock, so two requests can never
change the same game at once while other games carry on.
"""

import secrets
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from battleship.game import Game

IDLE_LIMIT = 60 * 60
"""Seconds without a request after which a game is removed."""

MAX_GAMES = 1000
"""How many games the server holds at most."""


class GameNotFoundError(KeyError):
    """No game with this ID: it never existed or was removed after being idle."""


@dataclass
class Entry:
    game: Game
    opponent: str
    last_used: float
    lock: threading.Lock = field(default_factory=threading.Lock)


class GameStore:
    """Holds games by ID. `clock` returns seconds and can be replaced in tests."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        idle_limit: float = IDLE_LIMIT,
        max_games: int = MAX_GAMES,
    ) -> None:
        self._clock = clock
        self._idle_limit = idle_limit
        self._max_games = max_games
        self._entries: dict[str, Entry] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            self._expire(self._clock())
            return len(self._entries)

    def add(self, game: Game, opponent: str) -> str:
        """Keep a new game and return its ID, a random string nobody can guess."""
        game_id = secrets.token_urlsafe(16)
        with self._lock:
            now = self._clock()
            self._expire(now)
            while len(self._entries) >= self._max_games:
                oldest = min(self._entries, key=lambda key: self._entries[key].last_used)
                del self._entries[oldest]
            self._entries[game_id] = Entry(game, opponent, now)
        return game_id

    @contextmanager
    def use(self, game_id: str) -> Iterator[Entry]:
        """Hold one game's lock while working on it, and mark it as used just now.

        Raises GameNotFoundError for an unknown or removed ID.
        """
        with self._lock:
            now = self._clock()
            self._expire(now)
            entry = self._entries.get(game_id)
            if entry is None:
                raise GameNotFoundError(f"no game with ID {game_id!r}; it may have expired")
            entry.last_used = now
        with entry.lock:
            yield entry

    def _expire(self, now: float) -> None:
        idle = [
            key for key, entry in self._entries.items() if now - entry.last_used > self._idle_limit
        ]
        for key in idle:
            del self._entries[key]
