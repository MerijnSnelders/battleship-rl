"""The HTTP API: game flow, refusals, hiding the AI's ships, expiry, opponents and stats."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import IDLE_LIMIT, GameStore
from battleship.ai import get, names
from battleship.config import CONFIGS

config_names = pytest.mark.parametrize("config", ["small", "standard"])


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def client(clock):
    return TestClient(create_app(GameStore(clock)))


def new_game(client, opponent="random", config="small", seed=1):
    response = client.post(
        "/api/games", json={"opponent": opponent, "config": config, "seed": seed}
    )
    assert response.status_code == 201, response.text
    return response.json()


def stacked(client, game_id, config):
    """Place every ship horizontally on its own row from the left edge."""
    for row, length in enumerate(CONFIGS[config].ships):
        body = {"start": [row, 0], "length": length, "orientation": "horizontal"}
        response = client.post(f"/api/games/{game_id}/ships", json=body)
        assert response.status_code == 200, response.text
    return response.json()


def started(client, opponent="random", config="small", seed=1):
    game = new_game(client, opponent, config, seed)
    client.post(f"/api/games/{game['id']}/ships/random")
    response = client.post(f"/api/games/{game['id']}/start")
    assert response.status_code == 200, response.text
    return response.json()


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"] == code
    assert response.json()["detail"]


def assert_ai_ships_hidden(state):
    """No AI ship square can be read from the state: only squares fired at are known."""
    assert state["ai_board"]["ships"] is None
    view = state["ai_board"]["view"]
    known = sum(square != "unknown" for row in view["grid"] for square in row)
    assert known == view["shot_count"]


def play_to_the_end(client, game_id, config):
    """Fire row by row at every square, never using knowledge the API did not give."""
    responses = []
    size = CONFIGS[config].size
    for row in range(size):
        for col in range(size):
            response = client.post(f"/api/games/{game_id}/fire", json={"row": row, "col": col})
            assert response.status_code == 200, response.text
            responses.append(response.json())
            if response.json()["state"]["phase"] == "over":
                return responses
    raise AssertionError("game did not end")


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "battleship-rl" in response.text


def test_opponents_lists_every_registered_ai_with_its_text(client):
    opponents = client.get("/api/opponents").json()

    assert [item["name"] for item in opponents] == list(names())
    for item in opponents:
        cls = get(item["name"])
        assert item["display_name"] == cls.display_name
        assert item["description"] == cls.description
        assert item["has_heatmap"] == cls.has_heatmap()


@config_names
def test_a_new_game_starts_in_setup_with_the_ai_fleet_hidden(client, config):
    state = new_game(client, config=config, seed=5)

    assert state["phase"] == "setup"
    assert state["seed"] == 5
    assert state["opponent"] == "random"
    assert state["config"] == {
        "size": CONFIGS[config].size,
        "ships": list(CONFIGS[config].ships),
    }
    assert state["human_board"]["ships"] == []
    assert state["human_board"]["unplaced"] == list(CONFIGS[config].ships)
    assert (state["turn"], state["first_shooter"], state["winner"]) == (None, None, None)
    assert_ai_ships_hidden(state)


def test_the_config_defaults_to_standard_and_a_seed_is_drawn(client):
    state = client.post("/api/games", json={"opponent": "random"}).json()

    assert state["config"]["size"] == 10
    assert isinstance(state["seed"], int)


def test_get_returns_the_same_state(client):
    state = new_game(client)

    assert client.get(f"/api/games/{state['id']}").json() == state


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"opponent": "nope"}, 404, "unknown_opponent"),
        ({"opponent": "random", "config": "huge"}, 404, "unknown_config"),
        ({"opponent": "random", "seed": -1}, 422, "invalid_request"),
        ({}, 422, "invalid_request"),
    ],
)
def test_creating_a_game_refuses_bad_input(client, body, status, code):
    assert_error(client.post("/api/games", json=body), status, code)


def test_an_unknown_game_is_not_found(client):
    assert_error(client.get("/api/games/nope"), 404, "game_not_found")
    assert_error(
        client.post("/api/games/nope/fire", json={"row": 0, "col": 0}), 404, "game_not_found"
    )


@config_names
def test_placing_ships_one_by_one_completes_the_fleet(client, config):
    game_id = new_game(client, config=config)["id"]

    state = stacked(client, game_id, config)

    assert state["human_board"]["unplaced"] == []
    assert len(state["human_board"]["ships"]) == len(CONFIGS[config].ships)
    first = state["human_board"]["ships"][0]
    assert first["start"] == [0, 0]
    assert first["orientation"] == "horizontal"
    assert first["squares"][-1] == [0, first["length"] - 1]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"start": [1, 5], "length": 2, "orientation": "horizontal"}, "off_board"),
        ({"start": [0, 0], "length": 4, "orientation": "horizontal"}, "ship_not_in_fleet"),
        ({"start": [0, 0], "length": 2, "orientation": "vertical"}, "overlap"),
        ({"start": [0, 0], "length": 0, "orientation": "vertical"}, "invalid_request"),
        ({"start": [0, 0], "length": 2, "orientation": "diagonal"}, "invalid_request"),
    ],
)
def test_bad_placements_are_refused_with_a_code(client, body, code):
    game_id = new_game(client)["id"]
    client.post(
        f"/api/games/{game_id}/ships",
        json={"start": [0, 0], "length": 3, "orientation": "horizontal"},
    )

    assert_error(client.post(f"/api/games/{game_id}/ships", json=body), 422, code)
    assert len(client.get(f"/api/games/{game_id}").json()["human_board"]["ships"]) == 1


def test_a_ship_is_removed_by_any_square_it_covers(client):
    game_id = new_game(client)["id"]
    stacked(client, game_id, "small")

    state = client.delete(f"/api/games/{game_id}/ships", params={"row": 0, "col": 2}).json()

    assert state["human_board"]["unplaced"] == [3]
    assert len(state["human_board"]["ships"]) == 2


def test_removing_from_open_water_or_with_half_a_square_is_refused(client):
    game_id = new_game(client)["id"]
    stacked(client, game_id, "small")

    response = client.delete(f"/api/games/{game_id}/ships", params={"row": 5, "col": 5})
    assert_error(response, 422, "no_ship")
    response = client.delete(f"/api/games/{game_id}/ships", params={"row": 0})
    assert_error(response, 422, "invalid_request")


def test_clearing_takes_off_every_ship(client):
    game_id = new_game(client)["id"]
    stacked(client, game_id, "small")

    state = client.delete(f"/api/games/{game_id}/ships").json()

    assert state["human_board"]["ships"] == []


def test_a_random_fleet_replaces_the_board(client):
    game_id = new_game(client)["id"]
    client.post(
        f"/api/games/{game_id}/ships",
        json={"start": [5, 0], "length": 3, "orientation": "horizontal"},
    )

    state = client.post(f"/api/games/{game_id}/ships/random").json()

    assert state["human_board"]["unplaced"] == []


def test_starting_needs_a_complete_fleet(client):
    game_id = new_game(client)["id"]

    assert_error(client.post(f"/api/games/{game_id}/start"), 422, "incomplete_fleet")


def test_starting_flips_the_coin_and_plays_the_ai_opening_if_it_won(client):
    firsts = set()
    for seed in range(30):
        result = started(client, seed=seed)
        state = result["state"]
        firsts.add(state["first_shooter"])
        assert state["phase"] == "playing"
        assert state["turn"] == "human"
        if state["first_shooter"] == "human":
            assert result["ai_turn"] == []
        else:
            assert len(result["ai_turn"]) >= 1
        assert state["human_board"]["view"]["shot_count"] == len(result["ai_turn"])
        assert_ai_ships_hidden(state)

    assert firsts == {"human", "ai"}


def test_setup_and_firing_are_refused_in_the_wrong_phase(client):
    game_id = new_game(client)["id"]
    assert_error(
        client.post(f"/api/games/{game_id}/fire", json={"row": 0, "col": 0}), 409, "wrong_phase"
    )

    client.post(f"/api/games/{game_id}/ships/random")
    client.post(f"/api/games/{game_id}/start")

    assert_error(client.post(f"/api/games/{game_id}/start"), 409, "wrong_phase")
    assert_error(client.post(f"/api/games/{game_id}/ships/random"), 409, "wrong_phase")
    assert_error(client.delete(f"/api/games/{game_id}/ships"), 409, "wrong_phase")


def test_bad_shots_are_refused_with_a_code(client):
    game_id = started(client)["state"]["id"]
    client.post(f"/api/games/{game_id}/fire", json={"row": 0, "col": 0})

    fire = f"/api/games/{game_id}/fire"
    assert_error(client.post(fire, json={"row": 0, "col": 0}), 422, "repeat_shot")
    assert_error(client.post(fire, json={"row": 6, "col": 0}), 422, "shot_off_board")
    assert_error(client.post(fire, json={"row": "a", "col": 0}), 422, "invalid_request")


def test_the_ai_replies_only_after_a_human_miss(client):
    game_id = started(client)["state"]["id"]

    for response in play_to_the_end(client, game_id, "small"):
        if response["shot"]["outcome"] != "miss":
            assert response["ai_turn"] == []
        elif response["state"]["winner"] != "human":
            assert len(response["ai_turn"]) >= 1
            outcomes = [shot["outcome"] for shot in response["ai_turn"]]
            assert "miss" not in outcomes[:-1]


@config_names
def test_ai_ships_stay_hidden_until_the_game_is_over(client, config):
    game_id = started(client, config=config)["state"]["id"]

    responses = play_to_the_end(client, game_id, config)

    for response in responses[:-1]:
        assert_ai_ships_hidden(response["state"])
    final = responses[-1]["state"]
    assert final["phase"] == "over"
    assert final["winner"] in {"human", "ai"}
    assert final["turn"] is None
    ships = final["ai_board"]["ships"]
    assert sorted(ship["length"] for ship in ships) == sorted(CONFIGS[config].ships)
    assert client.get(f"/api/games/{game_id}").json()["ai_board"]["ships"] == ships
    assert_error(
        client.post(f"/api/games/{game_id}/fire", json={"row": 0, "col": 0}), 409, "wrong_phase"
    )


def test_a_hidden_state_shows_every_ai_ship_square_as_unknown(clock):
    store = GameStore(clock)
    client = TestClient(create_app(store))
    state = started(client)["state"]
    with store.use(state["id"]) as entry:
        squares = {square for ship in entry.game.ai_board.ships for square in ship.squares}

    assert '"ships": null' in json.dumps(state["ai_board"])
    grid = state["ai_board"]["view"]["grid"]
    assert all(grid[row][col] == "unknown" for row, col in squares)


@pytest.mark.parametrize("opponent", names())
def test_every_opponent_plays_a_whole_game_with_heatmaps_as_promised(client, opponent):
    game_id = started(client, opponent=opponent)["state"]["id"]
    has_heatmap = get(opponent).has_heatmap()

    for response in play_to_the_end(client, game_id, "small"):
        for shot in response["ai_turn"]:
            heatmap = shot["heatmap"]
            if not has_heatmap:
                assert heatmap is None
                continue
            assert len(heatmap) == 6 and all(len(row) == 6 for row in heatmap)
            # Scaled so the top square is 1, or all 0 (Hunt/target in hunt mode).
            assert max(max(row) for row in heatmap) in {0, 1}
            assert min(min(row) for row in heatmap) >= 0


@pytest.mark.parametrize("opponent", names())
def test_the_state_carries_the_heatmap_of_the_next_ai_shot(client, opponent):
    has_heatmap = get(opponent).has_heatmap()
    game = new_game(client, opponent=opponent)
    assert game["human_board"]["heatmap"] is None

    state = started(client, opponent=opponent)["state"]
    for response in play_to_the_end(client, state["id"], "small"):
        if response["ai_turn"]:
            assert response["ai_turn"][0]["heatmap"] == state["human_board"]["heatmap"]
        state = response["state"]
        if state["phase"] == "over" or not has_heatmap:
            assert state["human_board"]["heatmap"] is None
        else:
            heatmap = state["human_board"]["heatmap"]
            assert len(heatmap) == 6 and all(len(row) == 6 for row in heatmap)
            assert max(max(row) for row in heatmap) in {0, 1}


def test_the_same_seed_gives_the_same_ai_fleet(client):
    def final_ai_ships(seed):
        game_id = started(client, seed=seed)["state"]["id"]
        return play_to_the_end(client, game_id, "small")[-1]["state"]["ai_board"]["ships"]

    assert final_ai_ships(3) == final_ai_ships(3)


def test_a_game_idle_for_over_an_hour_is_gone(client, clock):
    game_id = new_game(client)["id"]
    clock.now = IDLE_LIMIT - 1
    assert client.get(f"/api/games/{game_id}").status_code == 200

    clock.now += IDLE_LIMIT + 1

    assert_error(client.get(f"/api/games/{game_id}"), 404, "game_not_found")


@config_names
def test_stats_give_summaries_and_histograms(client, config):
    response = client.get("/api/stats", params={"config": config})

    assert response.status_code == 200
    data = response.json()
    assert data["config"]["size"] == CONFIGS[config].size
    assert {ai["name"] for ai in data["ais"]} <= set(names())
    for ai in data["ais"]:
        assert sum(count for _, count in ai["histogram"]) == ai["games"] == data["games"]
        assert "shots" not in ai


def test_stats_refuse_an_unknown_config_or_missing_results(client, tmp_path):
    assert_error(client.get("/api/stats", params={"config": "huge"}), 404, "unknown_config")

    empty = TestClient(create_app(GameStore(), results_dir=tmp_path))
    assert_error(empty.get("/api/stats"), 404, "no_stats")


@config_names
def test_setup_lists_the_legal_starts_of_every_length_still_to_place(client, config):
    game = new_game(client, config=config)
    lengths = list(dict.fromkeys(CONFIGS[config].ships))
    size = CONFIGS[config].size

    legal = game["human_board"]["legal_starts"]

    assert [item["length"] for item in legal] == lengths
    longest = legal[0]
    assert len(longest["horizontal"]) == size * (size - lengths[0] + 1)
    assert [0, size - lengths[0] + 1] not in longest["horizontal"]
    assert [size - lengths[0] + 1, 0] not in longest["vertical"]


def test_legal_starts_follow_the_ships_placed_and_vanish_after_setup(client):
    game = new_game(client, config="small")
    body = {"start": [0, 0], "length": 3, "orientation": "horizontal"}
    state = client.post(f"/api/games/{game['id']}/ships", json=body).json()

    legal = state["human_board"]["legal_starts"]
    assert [item["length"] for item in legal] == [2]
    assert [0, 1] not in legal[0]["horizontal"]
    assert [0, 0] not in legal[0]["vertical"]
    assert [1, 0] in legal[0]["vertical"]

    client.post(f"/api/games/{game['id']}/ships/random")
    full = client.get(f"/api/games/{game['id']}").json()
    assert full["human_board"]["legal_starts"] == []
    started_state = client.post(f"/api/games/{game['id']}/start").json()["state"]
    assert started_state["human_board"]["legal_starts"] is None
