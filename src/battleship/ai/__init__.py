"""AI opponents: random, hunt/target, probability density, Monte Carlo and the RL agent.

Every AI module is imported here so its `@register` decorator runs and `create` can find it.
"""

from battleship.ai.base import AI
from battleship.ai.hunt_target_ai import HuntTargetAI
from battleship.ai.monte_carlo_ai import MonteCarloAI
from battleship.ai.probability_density_ai import ProbabilityDensityAI
from battleship.ai.random_ai import RandomAI
from battleship.ai.registry import UnknownAIError, create, names, register

__all__ = [
    "AI",
    "HuntTargetAI",
    "MonteCarloAI",
    "ProbabilityDensityAI",
    "RandomAI",
    "UnknownAIError",
    "create",
    "names",
    "register",
]
