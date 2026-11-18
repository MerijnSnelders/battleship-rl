"""Simulation tests: every registered AI plays a few hundred games, to catch broken AIs.

Every shot of every game is checked by `play` (on the board, never twice, never more shots
than squares, a well-formed heatmap). Game i uses the same seeding as benchmark game i, but
with its own seed, so these boards differ from the published benchmark.
"""

import pytest
from conftest import play

from battleship.ai import create, names
from battleship.benchmark import game_seeds
from battleship.config import SMALL, STANDARD

SIMULATION_SEED = 13
"""Seed of the simulated games, kept apart from the benchmark's seed 0."""

GAMES = 300
"""How many games every AI plays on every config."""

CONFIGS = {"small": SMALL, "standard": STANDARD}

SLOW = {("monte_carlo", "small"), ("monte_carlo", "standard"), ("probability_density", "standard")}
"""AI and config pairs that take over about 5 seconds locally, so may pass 10 in CI."""


def cases():
    return [
        pytest.param(
            name,
            config_name,
            marks=[pytest.mark.slow] if (name, config_name) in SLOW else [],
            id=f"{name}-{config_name}",
        )
        for name in names()
        for config_name in CONFIGS
    ]


@pytest.mark.parametrize(("name", "config_name"), cases())
def test_ai_finishes_every_game_with_legal_shots(name, config_name):
    config = CONFIGS[config_name]
    ai = create(name)
    for game in range(GAMES):
        board_seed, ai_seed = game_seeds(SIMULATION_SEED, game)
        label = f"{name} on {config_name}, seed {SIMULATION_SEED} game {game}"
        shots = play(ai, config, board_seed, ai_seed, label)
        assert config.ship_cells <= len(shots) <= config.cells, label
        assert len(set(shots)) == len(shots), label
