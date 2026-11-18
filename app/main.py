"""FastAPI server: holds game state per game ID and serves the frontend.

The browser only ever receives what a player is allowed to see. Every rule is applied by
`battleship.game.Game`; this module only translates HTTP to game calls and back. The routes
are described in docs/api.md.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import serialize
from app.store import GameNotFoundError, GameStore
from battleship.ai import UnknownAIError, create, get, names
from battleship.benchmark import results_path, stats
from battleship.board import (
    FleetLockedError,
    GameOverError,
    IncompleteFleetError,
    NoShipError,
    OffBoardError,
    OverlapError,
    RepeatShotError,
    ShipNotInFleetError,
    ShotOffBoardError,
)
from battleship.config import CONFIGS
from battleship.game import Game, WrongPhaseError
from battleship.ship import Orientation, Ship

STATIC_DIR = Path(__file__).parent / "static"
RESULTS_DIR = Path(__file__).parent.parent / "results"

MAX_SEED = 2**63 - 1
"""The largest seed a client may choose."""


class UnknownConfigError(KeyError):
    """No config with this name."""


class StatsNotFoundError(KeyError):
    """No benchmark results exist for this config."""


class InvalidRequestError(ValueError):
    """The request is well-formed JSON but its fields do not fit together."""


ERRORS: list[tuple[type[Exception], int, str]] = [
    (GameNotFoundError, 404, "game_not_found"),
    (UnknownAIError, 404, "unknown_opponent"),
    (UnknownConfigError, 404, "unknown_config"),
    (StatsNotFoundError, 404, "no_stats"),
    (WrongPhaseError, 409, "wrong_phase"),
    (FleetLockedError, 409, "wrong_phase"),
    (GameOverError, 409, "wrong_phase"),
    (OverlapError, 422, "overlap"),
    (OffBoardError, 422, "off_board"),
    (ShipNotInFleetError, 422, "ship_not_in_fleet"),
    (NoShipError, 422, "no_ship"),
    (IncompleteFleetError, 422, "incomplete_fleet"),
    (ShotOffBoardError, 422, "shot_off_board"),
    (RepeatShotError, 422, "repeat_shot"),
    (InvalidRequestError, 422, "invalid_request"),
]
"""Every refusal the API can give: exception, HTTP status and the error code in the body."""


class NewGame(BaseModel):
    opponent: str
    config: str = "standard"
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)


class Placement(BaseModel):
    start: tuple[int, int]
    length: int = Field(ge=1)
    orientation: Orientation


class Target(BaseModel):
    row: int
    col: int


def error_body(code: str, detail: str) -> dict[str, str]:
    return {"error": code, "detail": detail}


def create_app(store: GameStore | None = None, results_dir: Path = RESULTS_DIR) -> FastAPI:
    """Build the server. Tests pass their own store (with a fake clock) and results folder."""
    app = FastAPI(title="battleship-rl")
    app.state.store = store if store is not None else GameStore()
    games: GameStore = app.state.store

    for exc_type, status, code in ERRORS:

        def handler(_: Request, exc: Exception, status: int = status, code: str = code):
            detail = exc.args[0] if exc.args else code
            return JSONResponse(error_body(code, str(detail)), status_code=status)

        app.add_exception_handler(exc_type, handler)

    @app.exception_handler(RequestValidationError)
    def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return JSONResponse(error_body("invalid_request", problems), status_code=422)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Used by tests and to check the deployed Space is awake."""
        return {"status": "ok"}

    @app.get("/api/opponents")
    def opponents() -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "display_name": get(name).display_name,
                "description": get(name).description,
                "has_heatmap": get(name).has_heatmap(),
            }
            for name in names()
        ]

    @app.get("/api/stats")
    def benchmark_stats(config: str = "standard") -> dict[str, Any]:
        if config not in CONFIGS:
            raise UnknownConfigError(f"no config named {config!r}")
        path = results_path(config, results_dir)
        if not path.exists():
            raise StatsNotFoundError(f"no benchmark results for {config!r}")
        return _cached_stats(path, path.stat().st_mtime_ns)

    @app.post("/api/games", status_code=201)
    def new_game(body: NewGame) -> dict[str, Any]:
        if body.config not in CONFIGS:
            raise UnknownConfigError(f"no config named {body.config!r}")
        game = Game(CONFIGS[body.config], create(body.opponent), body.seed)
        game_id = games.add(game, body.opponent)
        return serialize.state(game_id, body.opponent, game)

    @app.get("/api/games/{game_id}")
    def game_state(game_id: str) -> dict[str, Any]:
        with games.use(game_id) as entry:
            return serialize.state(game_id, entry.opponent, entry.game)

    @app.post("/api/games/{game_id}/ships")
    def place_ship(game_id: str, body: Placement) -> dict[str, Any]:
        with games.use(game_id) as entry:
            entry.game.place(Ship(body.start, body.length, body.orientation))
            return serialize.state(game_id, entry.opponent, entry.game)

    @app.delete("/api/games/{game_id}/ships")
    def remove_ships(
        game_id: str,
        row: Annotated[int | None, Query()] = None,
        col: Annotated[int | None, Query()] = None,
    ) -> dict[str, Any]:
        """With `row` and `col`, remove the ship covering that square; without, remove all."""
        if (row is None) != (col is None):
            raise InvalidRequestError("give both row and col, or neither")
        with games.use(game_id) as entry:
            if row is None or col is None:
                entry.game.clear()
            else:
                entry.game.remove((row, col))
            return serialize.state(game_id, entry.opponent, entry.game)

    @app.post("/api/games/{game_id}/ships/random")
    def random_fleet(game_id: str) -> dict[str, Any]:
        with games.use(game_id) as entry:
            entry.game.random_fleet()
            return serialize.state(game_id, entry.opponent, entry.game)

    @app.post("/api/games/{game_id}/start")
    def start(game_id: str) -> dict[str, Any]:
        with games.use(game_id) as entry:
            opening = entry.game.start()
            return {
                "ai_turn": serialize.ai_turn(opening),
                "state": serialize.state(game_id, entry.opponent, entry.game),
            }

    @app.post("/api/games/{game_id}/fire")
    def fire(game_id: str, body: Target) -> dict[str, Any]:
        with games.use(game_id) as entry:
            result = entry.game.fire((body.row, body.col))
            return {
                "shot": serialize.shot(result.shot),
                "ai_turn": serialize.ai_turn(result.ai_turn),
                "state": serialize.state(game_id, entry.opponent, entry.game),
            }

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


@lru_cache(maxsize=8)
def _cached_stats(path: Path, mtime_ns: int) -> dict[str, Any]:
    """The stats of one results file, read again only when the file changes."""
    return stats(json.loads(path.read_text()))


app = create_app()
