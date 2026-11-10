"""Look up an AI by name, so the API and the benchmark can pick one from a string."""

from collections.abc import Callable

from battleship.ai.base import AI

_REGISTRY: dict[str, type[AI]] = {}


class UnknownAIError(KeyError):
    """No AI is registered under this name."""


def register[T: type[AI]](name: str) -> Callable[[T], T]:
    """Class decorator that makes an AI available under `name`.

    The class must be built without arguments. A name can be registered only once.
    """

    def decorator(cls: T) -> T:
        if not (isinstance(cls, type) and issubclass(cls, AI)):
            raise TypeError(f"{cls!r} is not an AI subclass")
        if name in _REGISTRY:
            raise ValueError(f"an AI named {name!r} is already registered")
        _REGISTRY[name] = cls
        return cls

    return decorator


def create(name: str) -> AI:
    """A fresh AI of the given name. Call `new_game` on it before the first shot."""
    try:
        cls = _REGISTRY[name]
    except KeyError:
        known = ", ".join(_REGISTRY) or "none"
        raise UnknownAIError(f"no AI named {name!r} (registered: {known})") from None
    return cls()


def names() -> tuple[str, ...]:
    """The names of every registered AI, in the order they were registered."""
    return tuple(_REGISTRY)
