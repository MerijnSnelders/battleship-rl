import numpy as np
import pytest

from battleship.ai import AI, UnknownAIError, create, names, register
from battleship.ai import registry as registry_module
from battleship.board import Board, GameOverError
from battleship.config import SMALL, STANDARD
from battleship.view import SquareState

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])


class FirstUnknownAI(AI):
    """Test-only AI: fires at the first square not fired at yet."""

    def _choose_shot(self, view):
        return self.unknown_squares(view)[0]


class RandomWithHeatmapAI(AI):
    """Test-only AI: fires at random using its rng and shows a flat heatmap."""

    def _choose_shot(self, view):
        squares = self.unknown_squares(view)
        return squares[int(self.rng.integers(len(squares)))]

    def _heatmap(self, view):
        return (view.to_array() == SquareState.UNKNOWN).astype(float)


TEST_AIS = {"first_unknown": FirstUnknownAI, "random_with_heatmap": RandomWithHeatmapAI}


def every_ai():
    """Factories for the test-only AIs and every registered AI, so new AIs are covered."""
    factories = dict(TEST_AIS)
    for name in names():
        factories[name] = lambda name=name: create(name)
    return pytest.mark.parametrize("make_ai", factories.values(), ids=factories.keys())


@pytest.fixture
def clean_registry(monkeypatch):
    monkeypatch.setattr(registry_module, "_REGISTRY", {})


def play(ai, config, seed):
    """Play one full game on a seeded board and return the shots in order."""
    board = Board.with_random_fleet(config, seed)
    ai.new_game(config, seed)
    shots = []
    while not board.is_game_over:
        view = board.view()
        heatmap = ai.heatmap(view)
        if heatmap is not None:
            assert heatmap.shape == (config.size, config.size)
            assert np.all(heatmap >= 0)
            assert np.all(heatmap[view.to_array() != SquareState.UNKNOWN] == 0)
        shot = ai.choose_shot(view)
        board.fire(shot)  # raises for a square off the board or fired at before
        shots.append(shot)
        assert len(shots) <= config.cells
    return shots


# Contract: every AI


@every_ai()
@configs
def test_ai_finishes_a_game_with_legal_shots(make_ai, config):
    shots = play(make_ai(), config, seed=1)
    assert len(shots) == len(set(shots))


@every_ai()
@configs
def test_same_seed_gives_the_same_game(make_ai, config):
    assert play(make_ai(), config, seed=7) == play(make_ai(), config, seed=7)


@every_ai()
@configs
def test_reused_ai_plays_like_a_fresh_one(make_ai, config):
    reused = make_ai()
    play(reused, config, seed=3)
    assert play(reused, config, seed=4) == play(make_ai(), config, seed=4)


@every_ai()
@configs
def test_asking_for_the_heatmap_does_not_change_the_shot(make_ai, config):
    view = Board.with_random_fleet(config, 5).view()
    plain, curious = make_ai(), make_ai()
    plain.new_game(config, 5)
    curious.new_game(config, 5)
    curious.heatmap(view)
    assert curious.choose_shot(view) == plain.choose_shot(view)


# Base class rules


def test_choose_shot_before_new_game_raises():
    view = Board.with_random_fleet(SMALL, 0).view()
    with pytest.raises(RuntimeError, match="new_game"):
        FirstUnknownAI().choose_shot(view)


def test_heatmap_before_new_game_raises():
    view = Board.with_random_fleet(SMALL, 0).view()
    with pytest.raises(RuntimeError, match="new_game"):
        FirstUnknownAI().heatmap(view)


def test_choose_shot_after_game_over_raises():
    board = Board.with_random_fleet(SMALL, 0)
    ai = FirstUnknownAI()
    ai.new_game(SMALL)
    while not board.is_game_over:
        board.fire(ai.choose_shot(board.view()))
    with pytest.raises(GameOverError):
        ai.choose_shot(board.view())


def test_view_of_another_board_size_raises():
    ai = FirstUnknownAI()
    ai.new_game(SMALL)
    with pytest.raises(ValueError, match="board"):
        ai.choose_shot(Board.with_random_fleet(STANDARD, 0).view())


def test_heatmap_is_none_by_default():
    ai = FirstUnknownAI()
    ai.new_game(SMALL)
    assert ai.heatmap(Board.with_random_fleet(SMALL, 0).view()) is None


def test_ai_without_choose_shot_cannot_be_built():
    class Incomplete(AI):
        pass

    with pytest.raises(TypeError):
        Incomplete()


@configs
def test_unknown_squares_skips_squares_fired_at(config):
    board = Board.with_random_fleet(config, 0)
    board.fire((0, 0))
    board.fire((1, 2))
    unknown = AI.unknown_squares(board.view())
    assert len(unknown) == config.cells - 2
    assert (0, 0) not in unknown and (1, 2) not in unknown
    assert unknown[0] == (0, 1)


# Registry


def test_registered_ai_can_be_created_by_name(clean_registry):
    register("first_unknown")(FirstUnknownAI)
    ai = create("first_unknown")
    assert isinstance(ai, FirstUnknownAI)
    assert create("first_unknown") is not ai


def test_names_lists_ais_in_registration_order(clean_registry):
    register("b")(FirstUnknownAI)
    register("a")(RandomWithHeatmapAI)
    assert names() == ("b", "a")


def test_unknown_name_raises(clean_registry):
    register("first_unknown")(FirstUnknownAI)
    with pytest.raises(UnknownAIError, match="first_unknown"):
        create("nope")
    with pytest.raises(KeyError):
        create("nope")


def test_name_can_be_registered_only_once(clean_registry):
    register("dup")(FirstUnknownAI)
    with pytest.raises(ValueError, match="already registered"):
        register("dup")(RandomWithHeatmapAI)


def test_only_ai_subclasses_can_be_registered(clean_registry):
    with pytest.raises(TypeError):
        register("not_an_ai")(dict)


def test_register_returns_the_class_unchanged(clean_registry):
    assert register("first_unknown")(FirstUnknownAI) is FirstUnknownAI
