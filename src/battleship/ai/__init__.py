"""AI opponents: random, hunt/target, probability density, Monte Carlo and the RL agent.

Every AI module is imported here so its `@register` decorator runs and `create` can find it.
"""

from battleship.ai.base import AI
from battleship.ai.random_ai import RandomAI
from battleship.ai.registry import UnknownAIError, create, names, register

__all__ = ["AI", "RandomAI", "UnknownAIError", "create", "names", "register"]
