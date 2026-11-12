import json

import numpy as np
import pytest

from battleship.ai import UnknownAIError, names
from battleship.benchmark import (
    BenchmarkMismatchError,
    dumps,
    game_seeds,
    main,
    play_games,
    run_benchmark,
    to_json,
)
from battleship.board import Board
from battleship.config import SMALL, STANDARD

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])

# Monte Carlo is slow, so the fast tests leave it out; the slow ones cover every AI.
FAST_AIS = [name for name in names() if name != "monte_carlo"]


def board(seed, game):
    return Board.with_random_fleet(STANDARD, np.random.default_rng(game_seeds(seed, game)[0]))


def test_board_depends_only_on_seed_and_game():
    assert board(0, 7).ships == board(0, 7).ships
    assert board(0, 7).ships != board(0, 8).ships
    assert board(0, 7).ships != board(1, 7).ships


@configs
def test_shots_lie_between_fleet_squares_and_board_squares(config):
    results = run_benchmark(FAST_AIS, config, games=10)
    for result in results.values():
        assert len(result.shots) == 10
        assert all(config.ship_cells <= shots <= config.cells for shots in result.shots)


def test_summary_statistics_are_ordered():
    result = run_benchmark(["random"], SMALL, games=20)["random"]
    summary = result.summary()
    assert summary["min"] <= summary["median"] <= summary["max"]
    assert summary["min"] <= summary["mean"] <= summary["max"]
    low, high = summary["ci95"]
    assert low <= summary["mean"] <= high
    assert summary["std"] >= 0


def test_same_seed_gives_same_shots():
    first = run_benchmark(FAST_AIS, SMALL, games=15, seed=3)
    second = run_benchmark(FAST_AIS, SMALL, games=15, seed=3)
    assert {n: r.shots for n, r in first.items()} == {n: r.shots for n, r in second.items()}


def test_other_seed_gives_other_shots():
    first = run_benchmark(["random"], SMALL, games=15, seed=0)["random"]
    second = run_benchmark(["random"], SMALL, games=15, seed=1)["random"]
    assert first.shots != second.shots


def test_worker_count_does_not_change_shots():
    single = run_benchmark(FAST_AIS, SMALL, games=12, seed=5, workers=1)
    double = run_benchmark(FAST_AIS, SMALL, games=12, seed=5, workers=2)
    assert {n: r.shots for n, r in single.items()} == {n: r.shots for n, r in double.items()}


def test_play_games_matches_run_benchmark_board_for_board():
    shots = run_benchmark(["hunt_target"], SMALL, games=6, seed=2)["hunt_target"].shots
    assert play_games("hunt_target", SMALL, 2, range(3, 6)) == list(shots[3:])


def test_unknown_ai_is_rejected():
    with pytest.raises(UnknownAIError):
        run_benchmark(["nope"], SMALL, games=1)


@pytest.mark.parametrize("bad", [{"games": 0}, {"workers": 0}])
def test_invalid_counts_are_rejected(bad):
    with pytest.raises(ValueError):
        run_benchmark(["random"], SMALL, **({"games": 1} | bad))


def test_json_holds_settings_statistics_and_raw_shots():
    results = run_benchmark(["random", "hunt_target"], SMALL, games=8, seed=4)
    data = json.loads(dumps(to_json(results, SMALL, 8, 4)))
    assert data["config"] == {"size": 6, "ships": [3, 2, 2]}
    assert (data["games"], data["seed"]) == (8, 4)
    for name, result in results.items():
        ai = data["ais"][name]
        assert ai["shots"] == list(result.shots)
        for key in ["mean", "median", "std", "ci95", "min", "max", "seconds_per_game", "date"]:
            assert key in ai
        assert "commit" in ai


def test_merge_keeps_other_ais():
    first = to_json(run_benchmark(["random"], SMALL, games=5), SMALL, 5, 0)
    merged = to_json(run_benchmark(["hunt_target"], SMALL, games=5), SMALL, 5, 0, first)
    assert set(merged["ais"]) == {"random", "hunt_target"}
    assert merged["ais"]["random"] == first["ais"]["random"]


@pytest.mark.parametrize(
    ("config", "games", "seed"), [(STANDARD, 5, 0), (SMALL, 6, 0), (SMALL, 5, 1)]
)
def test_merge_refuses_other_settings(config, games, seed):
    existing = to_json(run_benchmark(["random"], SMALL, games=5), SMALL, 5, 0)
    with pytest.raises(BenchmarkMismatchError):
        to_json({}, config, games, seed, existing)


def test_command_line_writes_json_and_chart_and_merges(tmp_path):
    args = ["--config", "small", "--games", "6", "--workers", "1", "--out", str(tmp_path)]
    assert main([*args, "--ai", "random"]) == 0
    assert main([*args, "--ai", "hunt_target"]) == 0
    data = json.loads((tmp_path / "benchmark_small.json").read_text())
    assert set(data["ais"]) == {"random", "hunt_target"}
    assert (tmp_path / "benchmark_small.png").stat().st_size > 0


def test_command_line_refuses_mismatched_merge(tmp_path, capsys):
    args = ["--config", "small", "--workers", "1", "--out", str(tmp_path), "--ai", "random"]
    assert main([*args, "--games", "4"]) == 0
    assert main([*args, "--games", "5"]) == 1
    assert "existing results" in capsys.readouterr().err


@pytest.mark.slow
def test_every_ai_finishes_on_both_configs():
    for config in [SMALL, STANDARD]:
        results = run_benchmark(list(names()), config, games=5, workers=2)
        assert all(len(result.shots) == 5 for result in results.values())


@pytest.mark.slow
def test_ais_rank_as_expected():
    results = run_benchmark(["random", "hunt_target", "probability_density"], STANDARD, 200, 0, 4)
    means = {name: result.mean for name, result in results.items()}
    assert means["random"] > means["hunt_target"] > means["probability_density"]
