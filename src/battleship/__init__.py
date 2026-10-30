"""Battleship game engine: the single source of truth for the rules.

Used by the website, the heuristic AIs and RL training alike.
"""

from battleship.config import SMALL, STANDARD, GameConfig

__all__ = ["GameConfig", "SMALL", "STANDARD"]
