"""The benchmark: every AI plays the same seeded benchmark games, so their shots to finish compare.

Run it from the command line:

    uv run python -m battleship.benchmark                    # every AI, 10,000 games, STANDARD
    uv run python -m battleship.benchmark --config small     # the 6x6 board
    uv run python -m battleship.benchmark --ai monte_carlo   # one AI, merged into the results

Board i and the AI's random generator for board i are both drawn from
`SeedSequence([seed, i])`, so every AI faces exactly the same boards, and the results do not
depend on how many worker processes play them.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from battleship.ai import create, names
from battleship.board import Board
from battleship.config import SMALL, STANDARD, GameConfig

DEFAULT_GAMES = 10_000
"""How many benchmark games every AI plays unless told otherwise."""

CONFIGS: dict[str, GameConfig] = {"standard": STANDARD, "small": SMALL}
"""The configs the command line can benchmark, by name."""

RESULTS_DIR = Path("results")
"""Where the command line writes its JSON and chart."""

CHUNKS_PER_WORKER = 4
"""How many pieces each AI's games are split into per worker, to keep the workers busy."""

DISPLAY_NAMES = {"hunt_target": "Hunt/target"}
"""Chart labels that differ from the registry name with underscores turned into spaces."""


def display_name(name: str) -> str:
    """How an AI is named in the chart, matching the glossary."""
    return DISPLAY_NAMES.get(name, name.replace("_", " ").capitalize())


class BenchmarkMismatchError(ValueError):
    """Existing results were made with other settings, so new ones cannot be merged in."""


def game_seeds(seed: int, game: int) -> tuple[np.random.SeedSequence, np.random.SeedSequence]:
    """The seeds of benchmark game `game`: one for the board and one for the AI."""
    board_seed, ai_seed = np.random.SeedSequence([seed, game]).spawn(2)
    return board_seed, ai_seed


def play_games(ai_name: str, config: GameConfig, seed: int, games: Iterable[int]) -> list[int]:
    """Play the given benchmark games with one AI and return their shots to finish, in order."""
    ai = create(ai_name)
    shots = []
    for game in games:
        board_seed, ai_seed = game_seeds(seed, game)
        board = Board.with_random_fleet(config, np.random.default_rng(board_seed))
        ai.new_game(config, np.random.default_rng(ai_seed))
        while not board.is_game_over:
            board.fire(ai.choose_shot(board.view()))
        shots.append(board.shot_count)
    return shots


@dataclass(frozen=True)
class AIResult:
    """The shots to finish of one AI over every benchmark game, with summary statistics."""

    name: str
    shots: tuple[int, ...]
    seconds_per_game: float

    @property
    def mean(self) -> float:
        return float(np.mean(self.shots))

    @property
    def median(self) -> float:
        return float(np.median(self.shots))

    @property
    def std(self) -> float:
        """Sample standard deviation; 0 for a single game."""
        return float(np.std(self.shots, ddof=1)) if len(self.shots) > 1 else 0.0

    @property
    def ci95(self) -> tuple[float, float]:
        """95% confidence interval of the mean (normal approximation)."""
        margin = 1.96 * self.std / math.sqrt(len(self.shots))
        return (self.mean - margin, self.mean + margin)

    def summary(self) -> dict[str, Any]:
        """Statistics without the raw shots, for printing."""
        low, high = self.ci95
        return {
            "mean": round(self.mean, 3),
            "median": self.median,
            "std": round(self.std, 3),
            "ci95": [round(low, 3), round(high, 3)],
            "min": min(self.shots),
            "max": max(self.shots),
            "seconds_per_game": round(self.seconds_per_game, 5),
        }


def run_benchmark(
    ai_names: Sequence[str],
    config: GameConfig,
    games: int = DEFAULT_GAMES,
    seed: int = 0,
    workers: int = 1,
) -> dict[str, AIResult]:
    """Let every AI play benchmark games 0 to `games - 1` and collect their shots to finish.

    With more than one worker the games are spread over processes; the shots come out the
    same whatever the number of workers.
    """
    if games < 1:
        raise ValueError("games must be at least 1")
    if workers < 1:
        raise ValueError("workers must be at least 1")
    for name in ai_names:
        create(name)  # fail fast on an unknown name

    chunk_count = max(1, min(games, workers * CHUNKS_PER_WORKER))
    bounds = np.linspace(0, games, chunk_count + 1).astype(int)
    chunks = [range(start, stop) for start, stop in zip(bounds, bounds[1:], strict=False)]

    results = {}
    if workers == 1:
        for name in ai_names:
            start = time.perf_counter()
            shots = play_games(name, config, seed, range(games))
            results[name] = AIResult(name, tuple(shots), (time.perf_counter() - start) / games)
        return results

    with ProcessPoolExecutor(max_workers=workers) as pool:
        for name in ai_names:
            start = time.perf_counter()
            futures = [pool.submit(play_games, name, config, seed, chunk) for chunk in chunks]
            shots = [shot for future in futures for shot in future.result()]
            # Wall-clock time spread over the workers, so a rough cost per game.
            elapsed = (time.perf_counter() - start) * workers / games
            results[name] = AIResult(name, tuple(shots), elapsed)
    return results


def _git_commit() -> str | None:
    """The current commit, with "-dirty" when the working tree has changes, or None."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{commit}-dirty" if dirty else commit


def to_json(
    results: dict[str, AIResult],
    config: GameConfig,
    games: int,
    seed: int,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The results as a JSON-ready dict, merged into `existing` results if given.

    Raises BenchmarkMismatchError if `existing` was made with another config, game count or
    seed, because its shots would then not be comparable board for board.
    """
    settings = {"config": {"size": config.size, "ships": list(config.ships)}, "games": games}
    settings["seed"] = seed
    if existing is not None:
        theirs = {key: existing.get(key) for key in settings}
        if theirs != settings:
            raise BenchmarkMismatchError(
                f"existing results were made with {theirs}, not {settings}; "
                "use the same settings or write to another file"
            )
    ais = dict(existing["ais"]) if existing is not None else {}
    commit = _git_commit()
    date = datetime.now(UTC).isoformat(timespec="seconds")
    for name, result in results.items():
        ais[name] = {**result.summary(), "commit": commit, "date": date, "shots": result.shots}
    return {**settings, "ais": ais}


def dumps(data: dict[str, Any]) -> str:
    """The results as indented JSON, with each AI's shots on one line so the file stays readable."""
    placeholders = {
        **data,
        "ais": {name: {**ai, "shots": f"@shots:{name}@"} for name, ai in data["ais"].items()},
    }
    text = json.dumps(placeholders, indent=2)
    for name in data["ais"]:
        shots = json.dumps(list(data["ais"][name]["shots"]))
        text = text.replace(json.dumps(f"@shots:{name}@"), shots)
    return text + "\n"


def draw_chart(data: dict[str, Any], path: Path) -> None:
    """Save a chart of the shots to finish distribution of every AI in `data`."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    config = data["config"]
    size = config["size"]
    lowest, highest = sum(config["ships"]), size * size
    bins = np.arange(lowest, highest + 2) - 0.5
    ranked = sorted(data["ais"].items(), key=lambda item: item[1]["mean"])

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=120)
    for index, (name, ai) in enumerate(ranked):
        colour = f"C{index}"
        weights = np.full(len(ai["shots"]), 100 / len(ai["shots"]))
        label = f"{display_name(name)} (mean {ai['mean']:.1f})"
        ax.hist(ai["shots"], bins=bins, weights=weights, histtype="step", lw=1.8, color=colour)
        ax.axvline(ai["mean"], color=colour, ls="--", lw=1, label=label)
    ax.set_xlim(lowest - 1, highest + 1)
    ax.set_xlabel("Shots to finish (fewer is better)")
    ax.set_ylabel("Share of games (%)")
    ax.set_title(f"Benchmark: {data['games']:,} games per AI on a {size}x{size} board")
    ax.legend(title="Dashed line: mean")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", choices=CONFIGS, default="standard")
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--ai",
        action="append",
        choices=names(),
        help="AI to benchmark, may be repeated (default: every AI)",
    )
    parser.add_argument("--workers", type=int, default=None, help="processes (default: all cores)")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR, help="output directory")
    args = parser.parse_args(argv)

    config = CONFIGS[args.config]
    stem = "benchmark" if args.config == "standard" else f"benchmark_{args.config}"
    json_path, chart_path = args.out / f"{stem}.json", args.out / f"{stem}.png"
    existing = json.loads(json_path.read_text()) if json_path.exists() else None
    ai_names = args.ai or list(names())
    workers = args.workers or (os.cpu_count() or 1)

    try:
        # Check settings before spending minutes on games.
        to_json({}, config, args.games, args.seed, existing)
    except BenchmarkMismatchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"{args.games:,} games on {args.config} with {workers} workers")
    results = {}
    for name in ai_names:
        result = run_benchmark([name], config, args.games, args.seed, workers)[name]
        results[name] = result
        print(f"  {name:<20} {result.summary()}")

    data = to_json(results, config, args.games, args.seed, existing)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(dumps(data))
    draw_chart(data, chart_path)
    print(f"wrote {json_path} and {chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
