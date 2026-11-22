"""A game of a human against an AI: setup, the coin flip, turns, extra shots and the winner."""

import numpy as np
import pytest
from conftest import FirstUnknownAI, RandomWithHeatmapAI

from battleship.ai import create
from battleship.board import IncompleteFleetError, OverlapError, RepeatShotError
from battleship.config import SMALL, STANDARD
from battleship.game import Game, Phase, Side, WrongPhaseError
from battleship.ship import Orientation, Ship
from battleship.shot import ShotOutcome

configs = pytest.mark.parametrize("config", [SMALL, STANDARD], ids=["small", "standard"])


def stacked_fleet(config):
    """Every ship horizontal on its own row from the left edge."""
    return [
        Ship(start=(row, 0), length=length, orientation=Orientation.HORIZONTAL)
        for row, length in enumerate(config.ships)
    ]


def game_in_setup(config, ai=None, seed=0):
    game = Game(config, ai or FirstUnknownAI(), seed)
    for ship in stacked_fleet(config):
        game.place(ship)
    return game


def started(config, first, ai=None):
    """A started game whose coin flip went to `first`, found by trying seeds in order."""
    for seed in range(100):
        game = game_in_setup(config, ai or FirstUnknownAI(), seed)
        game.start()
        if game.first_shooter is first:
            return game
    raise AssertionError("no seed in range gave that first shooter")


def ai_ship_squares(game):
    return [square for ship in game.ai_board.ships for square in ship.squares]


def ai_open_water(game):
    taken = set(ai_ship_squares(game))
    size = game.config.size
    return [(row, col) for row in range(size) for col in range(size) if (row, col) not in taken]


@configs
def test_a_new_game_is_in_setup_with_a_complete_ai_fleet(config):
    game = Game(config, FirstUnknownAI(), 0)

    assert game.phase is Phase.SETUP
    assert game.ai_board.is_complete
    assert game.human_board.ships == ()
    assert game.turn is None
    assert game.first_shooter is None
    assert game.winner is None


def test_without_a_seed_one_is_drawn_and_kept():
    game = Game(SMALL, FirstUnknownAI())

    assert 0 <= game.seed < 2**52
    replay = Game(SMALL, FirstUnknownAI(), game.seed)
    assert replay.ai_board.ships == game.ai_board.ships


def test_a_negative_seed_is_refused():
    with pytest.raises(ValueError):
        Game(SMALL, FirstUnknownAI(), -1)


@configs
def test_placement_goes_through_the_board_rules(config):
    game = Game(config, FirstUnknownAI(), 0)
    game.place(stacked_fleet(config)[0])
    second = Ship(start=(0, 0), length=config.ships[1], orientation=Orientation.VERTICAL)

    with pytest.raises(OverlapError):
        game.place(second)


@configs
def test_remove_and_clear_change_the_human_board(config):
    game = game_in_setup(config)

    game.remove((0, 0))
    assert game.human_board.unplaced == (config.ships[0],)
    game.clear()
    assert game.human_board.ships == ()


@configs
def test_random_fleet_replaces_the_whole_board(config):
    game = game_in_setup(config)

    game.random_fleet()

    assert game.human_board.is_complete
    assert game.human_board.ships != tuple(stacked_fleet(config))


def test_random_fleet_gives_a_new_board_each_time():
    game = Game(STANDARD, FirstUnknownAI(), 0)
    game.random_fleet()
    first = game.human_board.ships

    game.random_fleet()

    assert game.human_board.ships != first


@configs
def test_starting_with_an_incomplete_fleet_is_refused(config):
    game = Game(config, FirstUnknownAI(), 0)
    game.place(stacked_fleet(config)[0])

    with pytest.raises(IncompleteFleetError):
        game.start()
    assert game.phase is Phase.SETUP


def test_the_coin_flip_lands_on_both_sides_and_depends_on_the_seed():
    firsts = []
    for seed in range(40):
        game = game_in_setup(SMALL, seed=seed)
        game.start()
        firsts.append(game.first_shooter)
        replay = game_in_setup(SMALL, seed=seed)
        replay.start()
        assert replay.first_shooter is game.first_shooter

    assert set(firsts) == {Side.HUMAN, Side.AI}


@configs
def test_human_first_gets_no_ai_shots_on_start(config):
    game = game_in_setup(config, seed=0)
    for seed in range(100):
        game = game_in_setup(config, seed=seed)
        opening = game.start()
        if game.first_shooter is Side.HUMAN:
            assert opening == ()
            assert game.human_board.shot_count == 0
            return
    raise AssertionError("no seed gave the human the first turn")


@configs
def test_ai_first_plays_its_opening_turn_on_start(config):
    for seed in range(100):
        game = game_in_setup(config, seed=seed)
        opening = game.start()
        if game.first_shooter is Side.AI:
            assert len(opening) >= 1
            assert game.human_board.shot_count == len(opening)
            assert opening[-1].result.outcome is ShotOutcome.MISS or game.phase is Phase.OVER
            return
    raise AssertionError("no seed gave the AI the first turn")


@configs
def test_setup_actions_are_refused_once_playing(config):
    game = started(config, Side.HUMAN)

    with pytest.raises(WrongPhaseError):
        game.random_fleet()
    with pytest.raises(WrongPhaseError):
        game.clear()
    with pytest.raises(WrongPhaseError):
        game.remove((0, 0))
    with pytest.raises(WrongPhaseError):
        game.start()


def test_firing_during_setup_is_refused():
    game = game_in_setup(SMALL)

    with pytest.raises(WrongPhaseError):
        game.fire((0, 0))


@configs
def test_a_hit_earns_the_human_another_shot(config):
    game = started(config, Side.HUMAN)
    ai_shots_before = game.human_board.shot_count

    result = game.fire(game.ai_board.ships[0].start)

    assert result.shot.outcome is ShotOutcome.HIT
    assert result.ai_turn == ()
    assert game.human_board.shot_count == ai_shots_before
    assert game.turn is Side.HUMAN


@configs
def test_a_sink_also_earns_another_shot(config):
    game = started(config, Side.HUMAN)
    ship = game.ai_board.ships[-1]

    results = [game.fire(square) for square in ship.squares]

    assert results[-1].shot.outcome is ShotOutcome.SUNK
    assert all(result.ai_turn == () for result in results)


@configs
def test_a_miss_hands_the_ai_a_turn_that_ends_at_its_first_miss(config):
    game = started(config, Side.HUMAN)

    result = game.fire(ai_open_water(game)[0])

    assert result.shot.outcome is ShotOutcome.MISS
    outcomes = [shot.result.outcome for shot in result.ai_turn]
    assert len(outcomes) >= 1
    assert outcomes[-1] is ShotOutcome.MISS or game.winner is Side.AI
    assert ShotOutcome.MISS not in outcomes[:-1]
    assert game.human_board.shot_count == len(outcomes)


@configs
def test_an_invalid_shot_changes_nothing(config):
    game = started(config, Side.HUMAN)
    square = game.ai_board.ships[0].start
    game.fire(square)

    with pytest.raises(RepeatShotError):
        game.fire(square)
    assert game.ai_board.shot_count == 1
    assert game.phase is Phase.PLAYING


@configs
def test_the_human_wins_by_sinking_the_whole_ai_fleet(config):
    game = started(config, Side.HUMAN)

    results = [game.fire(square) for square in ai_ship_squares(game)]

    assert results[-1].ai_turn == ()
    assert game.phase is Phase.OVER
    assert game.winner is Side.HUMAN
    assert game.turn is None
    with pytest.raises(WrongPhaseError):
        game.fire(ai_open_water(game)[0])


@configs
def test_the_ai_wins_by_sinking_the_whole_human_fleet(config):
    game = started(config, Side.HUMAN)

    for square in ai_open_water(game):
        result = game.fire(square)
        if game.phase is Phase.OVER:
            break

    assert game.winner is Side.AI
    assert game.human_board.is_game_over
    assert result.ai_turn[-1].result.outcome is ShotOutcome.SUNK


@configs
def test_every_ai_shot_carries_the_heatmap_it_was_chosen_from(config):
    game = started(config, Side.HUMAN, ai=RandomWithHeatmapAI())

    turn = game.fire(ai_open_water(game)[0]).ai_turn

    fired = set()
    for shot in turn:
        assert shot.heatmap.shape == (config.size, config.size)
        assert shot.heatmap[shot.result.square] > 0
        for square in fired:
            assert shot.heatmap[square] == 0
        fired.add(shot.result.square)


def test_an_ai_without_a_heatmap_shows_none():
    game = started(SMALL, Side.HUMAN)

    turn = game.fire(ai_open_water(game)[0]).ai_turn

    assert all(shot.heatmap is None for shot in turn)


@configs
@pytest.mark.parametrize("ai_name", ["random", "hunt_target", "probability_density"])
def test_the_same_seed_and_actions_replay_the_same_game(config, ai_name):
    def play(seed):
        game = Game(config, create(ai_name), seed)
        game.random_fleet()
        game.start()
        shots = []
        for square in ai_open_water(game) + ai_ship_squares(game):
            if game.phase is Phase.OVER:
                break
            shots.extend(shot.result for shot in game.fire(square).ai_turn)
        return game.ai_board.ships, game.human_board.ships, game.first_shooter, shots

    assert play(7) == play(7)
    assert play(7) != play(8)


heatmap_ais = pytest.mark.parametrize(
    "ai_name", ["hunt_target", "probability_density", "monte_carlo"]
)


def test_the_next_heatmap_is_none_outside_the_playing_phase():
    game = game_in_setup(SMALL, ai=create("probability_density"))
    assert game.ai_heatmap() is None

    game.start()
    assert game.ai_heatmap() is not None

    for square in ai_ship_squares(game):
        game.fire(square)
    assert game.phase is Phase.OVER
    assert game.ai_heatmap() is None


def test_the_next_heatmap_is_none_for_an_ai_without_one():
    game = started(SMALL, Side.HUMAN, ai=create("random"))

    assert game.ai_heatmap() is None


@configs
@heatmap_ais
def test_the_next_heatmap_is_the_one_the_next_ai_shot_is_chosen_from(config, ai_name):
    game = started(config, Side.HUMAN, ai=create(ai_name))

    for square in ai_open_water(game)[:5]:
        if game.phase is not Phase.PLAYING:
            break
        expected = game.ai_heatmap()
        turn = game.fire(square).ai_turn
        assert np.array_equal(turn[0].heatmap, expected)


@configs
@heatmap_ais
def test_asking_for_the_next_heatmap_never_changes_the_game(config, ai_name):
    def play(ask):
        game = Game(config, create(ai_name), 3)
        game.random_fleet()
        game.start()
        shots = []
        for square in ai_open_water(game) + ai_ship_squares(game):
            if game.phase is Phase.OVER:
                break
            if ask:
                game.ai_heatmap()
            shots.extend(shot.result for shot in game.fire(square).ai_turn)
        return shots

    assert play(ask=True) == play(ask=False)


def test_a_heatmap_of_a_real_ai_is_on_the_board():
    game = started(SMALL, Side.HUMAN, ai=create("probability_density"))

    turn = game.fire(ai_open_water(game)[0]).ai_turn

    assert all(isinstance(shot.heatmap, np.ndarray) for shot in turn)
