# Game API

The HTTP API the frontend uses to play a game against an AI and to show the benchmark results. Words like **game**, **turn**, **phase** and **player view** have the meaning given in [CONTEXT.md](../CONTEXT.md).

The server holds every game. The rules are applied by `battleship.game.Game`, and `app/` only translates HTTP to game calls. A response never contains anything the human may not know: the AI's ships are only included once the game is over.

All bodies are JSON. Squares are `[row, col]`, counted from the top-left square `[0, 0]`.

## A game from start to finish

1. `GET /api/opponents` to fill the opponent selector.
2. `POST /api/games` with the chosen opponent. The phase is `setup`, and the AI's fleet is already placed (and hidden).
3. Place the human's fleet: `POST .../ships` one ship at a time, `POST .../ships/random`, `DELETE .../ships?row=&col=` to take a ship off, `DELETE .../ships` to clear. Every response is the new state, including `legal_starts`, so the frontend never needs to know the placement rules. There is no move: moving or turning a ship is a remove followed by a place.
4. `POST .../start` once `human_board.unplaced` is empty. A coin flip picks the first shooter. If the AI wins it, its opening turn is in the response. The phase becomes `playing`.
5. `POST .../fire` for each human shot. A hit or sink earns another shot, so `ai_turn` is empty. After a miss the AI takes its whole turn (until its first miss or game over), and every AI shot is in `ai_turn`, in order.
6. When either fleet is sunk the phase becomes `over`, `winner` is set and `ai_board.ships` reveals the AI's fleet.

Between requests it is always the human's turn while the game is playing, because the AI's turn is played out inside `start` and `fire`.

## Endpoints

| Method | Path | Body or query | Returns |
| --- | --- | --- | --- |
| GET | `/api/health` | | `{"status": "ok"}` |
| GET | `/api/opponents` | | list of opponents |
| GET | `/api/stats` | `?config=standard` (or `small`) | benchmark summary |
| POST | `/api/games` | `{"opponent", "config"?, "seed"?}` | state (201) |
| GET | `/api/games/{id}` | | state |
| POST | `/api/games/{id}/ships` | `{"start": [r, c], "length", "orientation"}` | state |
| DELETE | `/api/games/{id}/ships` | `?row=&col=` for one ship, nothing for all | state |
| POST | `/api/games/{id}/ships/random` | | state |
| POST | `/api/games/{id}/start` | | `{"ai_turn", "state"}` |
| POST | `/api/games/{id}/fire` | `{"row", "col"}` | `{"shot", "ai_turn", "state"}` |

### Opponents

```json
[
  {
    "name": "probability_density",
    "display_name": "Probability density",
    "description": "Fires where the ships still afloat fit in the most ways.",
    "has_heatmap": true
  }
]
```

`name` is what `POST /api/games` takes. The list follows the AI registry, so a new AI shows up here without frontend changes. Show the heatmap toggle only when `has_heatmap` is true.

### Creating a game

```json
{"opponent": "hunt_target", "config": "standard", "seed": 42}
```

- `config` is `standard` (10x10, ships 5, 4, 3, 3, 2) or `small` (6x6, ships 3, 2, 2). It defaults to `standard`.
- `seed` is optional, between 0 and 2^63 - 1. It fixes the AI's fleet, the human's random fleets, the coin flip and every AI shot, so the same seed and the same human actions replay the same game. Without it the server draws one below 2^52 (safe as a JavaScript number) and returns it in the state.

### State

```json
{
  "id": "3q2-xY...",
  "opponent": "hunt_target",
  "config": {"size": 10, "ships": [5, 4, 3, 3, 2]},
  "seed": 42,
  "phase": "playing",
  "turn": "human",
  "first_shooter": "ai",
  "winner": null,
  "human_board": {
    "ships": [{"start": [0, 0], "length": 5, "orientation": "horizontal", "squares": [[0, 0], "..."]}],
    "unplaced": [],
    "legal_starts": null,
    "view": {"size": 10, "grid": [["unknown", "miss", "..."]], "sunk_ships": [], "shot_count": 3, "game_over": false}
  },
  "ai_board": {
    "view": {"size": 10, "grid": [["hit", "unknown", "..."]], "sunk_ships": [], "shot_count": 1, "game_over": false},
    "ships": null
  }
}
```

- `phase` is `setup`, `playing` or `over`.
- `turn` is `human` while playing, otherwise `null`. `first_shooter` is `null` during setup, and `winner` is `null` until the game is over. All three hold `human` or `ai`.
- `human_board.ships` are the human's own ships. `unplaced` lists the lengths still to place, in fleet order. `view` shows what the AI's shots revealed.
- `human_board.legal_starts` lists, during setup, every legal placement of the ships still to place: one entry per distinct length in `unplaced`, holding the start squares that are legal for each orientation. Outside setup it is `null`. The frontend looks a placement up here to colour its preview, so it never needs the placement rules:

  ```json
  [{"length": 3, "horizontal": [[0, 0], [0, 1], "..."], "vertical": [[0, 0], "..."]}, {"length": 2, "...": "..."}]
  ```
- `ai_board.view` is the human's player view of the AI's board. Each square is `unknown`, `miss`, `hit` or `sunk`, and the ships sunk so far are listed with their squares. `ai_board.ships` stays `null` until the phase is `over`.

### Shots and the AI's turn

```json
{
  "shot": {"square": [0, 0], "outcome": "miss", "sunk_ship": null},
  "ai_turn": [
    {"square": [3, 3], "outcome": "miss", "sunk_ship": null, "heatmap": [[0.4286, 0.6429, "..."], "..."]}
  ],
  "state": {"...": "..."}
}
```

- `outcome` is `miss`, `hit` or `sunk`. A sinking shot carries the sunk ship in `sunk_ship`.
- `ai_turn` lists the AI's shots in the order fired. Each one carries the AI's heatmap from just before that shot: a size x size grid scaled so the square the AI wants most is 1 (all 0 when it has no preference, like Hunt/target in hunt mode), with 0 on every square already fired at. It is `null` for AIs without a heatmap. Replay the list one shot at a time to show the AI "thinking".
- `start` returns the same `ai_turn` list for the AI's opening turn, which is empty if the human fires first.

### Stats

`GET /api/stats?config=standard` summarises `results/benchmark.json` (or `results/benchmark_small.json`) without the raw shots:

```json
{
  "config": {"size": 10, "ships": [5, 4, 3, 3, 2]},
  "games": 10000,
  "seed": 0,
  "ais": [
    {
      "name": "probability_density",
      "display_name": "Probability density",
      "games": 10000,
      "mean": 44.7, "median": 44.0, "std": 9.2, "ci95": [44.5, 44.9], "min": 20, "max": 83,
      "histogram": [[20, 1], [21, 3], "..."]
    }
  ]
}
```

AIs are sorted from fewest to most mean shots to finish. Each `histogram` entry is `[shots to finish, number of games]`, for every shot count that occurred.

## Errors

Every refusal has the same body:

```json
{"error": "overlap", "detail": "ship at (0, 0) overlaps another ship"}
```

Use `error` to choose what to show, and `detail` is a readable message. A refused action changes nothing.

| Status | `error` | When |
| --- | --- | --- |
| 404 | `game_not_found` | unknown game ID, or the game expired |
| 404 | `unknown_opponent` | no AI with that name |
| 404 | `unknown_config` | no config with that name |
| 404 | `no_stats` | no benchmark results for that config |
| 409 | `wrong_phase` | placing or starting after setup, or firing outside the playing phase |
| 422 | `overlap` | the ship would cover another ship |
| 422 | `off_board` | part of the ship lies outside the board |
| 422 | `ship_not_in_fleet` | no ship of that length is left to place |
| 422 | `no_ship` | no ship covers the square to remove |
| 422 | `incomplete_fleet` | starting before the whole fleet is placed |
| 422 | `shot_off_board` | the square fired at is outside the board |
| 422 | `repeat_shot` | the square was already fired at |
| 422 | `invalid_request` | the body or query has missing or wrongly typed fields |

## Expiry and limits

Games live in the server's memory only, so a restart (for example a new deploy) ends them all.

- A game that no request touched for over an hour is removed, and its ID then returns `game_not_found`. Every request to a game, including `GET`, counts as touching it.
- The server keeps at most 1,000 games. Creating another drops the one idle the longest.
- Game IDs are random and unguessable, but there are no accounts: anyone with an ID can play that game.
- Requests to the same game are handled one at a time, while different games run in parallel.
