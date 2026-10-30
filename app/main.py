"""FastAPI server: holds game state per game ID and serves the frontend.

The browser only ever receives what a player is allowed to see.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="battleship-rl")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Used by tests and to check the deployed Space is awake."""
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
