"""The game store: IDs, removal of idle games and the cap on how many are kept."""

import pytest
from conftest import FirstUnknownAI

from app.store import IDLE_LIMIT, GameNotFoundError, GameStore
from battleship.config import SMALL
from battleship.game import Game


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


def new_game():
    return Game(SMALL, FirstUnknownAI(), 0)


def test_a_stored_game_can_be_used_by_its_id(clock):
    store = GameStore(clock)
    game = new_game()

    game_id = store.add(game, "random")

    with store.use(game_id) as entry:
        assert entry.game is game
        assert entry.opponent == "random"


def test_ids_are_unique_and_hard_to_guess(clock):
    store = GameStore(clock)
    ids = {store.add(new_game(), "random") for _ in range(50)}

    assert len(ids) == 50
    assert all(len(game_id) >= 20 for game_id in ids)


def test_an_unknown_id_is_not_found(clock):
    with pytest.raises(GameNotFoundError), GameStore(clock).use("nope"):
        pass


def test_a_game_idle_for_over_an_hour_is_removed(clock):
    store = GameStore(clock)
    game_id = store.add(new_game(), "random")

    clock.now = IDLE_LIMIT + 1

    with pytest.raises(GameNotFoundError), store.use(game_id):
        pass
    assert len(store) == 0


def test_a_game_idle_for_exactly_an_hour_is_kept(clock):
    store = GameStore(clock)
    game_id = store.add(new_game(), "random")

    clock.now = IDLE_LIMIT

    with store.use(game_id):
        pass


def test_using_a_game_keeps_it_alive(clock):
    store = GameStore(clock)
    game_id = store.add(new_game(), "random")

    for step in range(1, 4):
        clock.now = step * (IDLE_LIMIT - 1)
        with store.use(game_id):
            pass

    assert len(store) == 1


def test_idle_games_are_removed_when_any_game_is_used(clock):
    store = GameStore(clock)
    store.add(new_game(), "random")
    clock.now = IDLE_LIMIT / 2
    fresh = store.add(new_game(), "random")

    clock.now = IDLE_LIMIT + 1
    with store.use(fresh):
        pass

    assert len(store) == 1


def test_a_full_store_drops_the_game_idle_the_longest(clock):
    store = GameStore(clock, max_games=3)
    ids = []
    for step in range(3):
        clock.now = step
        ids.append(store.add(new_game(), "random"))
    clock.now = 10
    with store.use(ids[0]):
        pass

    store.add(new_game(), "random")

    assert len(store) == 3
    with pytest.raises(GameNotFoundError), store.use(ids[1]):
        pass
    with store.use(ids[0]):
        pass
