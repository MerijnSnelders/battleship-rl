# battleship-rl

Hosted Battleship game against heuristic AIs and a self-trained RL agent. It is a school Personal Experiment: the deliverable is a measured answer to the research question in `docs/plan.md`, so evaluation and tests matter as much as features.

## How we work together

- Never commit/push unless told otherwise.
- Alwyas explain what you created.

## Architecture rules

- `src/battleship/` is the single source of truth for game rules. The API, every AI and the Gymnasium environment call into it; rules live nowhere else, including the JavaScript frontend.
- The server holds game state per game ID. Responses only contain what the player may see: AI ship positions stay on the server until the game ends.
- The frontend is plain HTML, CSS and JavaScript in `app/static/`, no build step and no framework.
- Board size and fleet always come from `GameConfig`; tests run on `SMALL` and `STANDARD`.
- AIs share one interface so the API, benchmark and RL agent are interchangeable.

## Workflow

1. Branch from `develop`: `feature/<issue>-<short-name>` or `fix/<issue>-<short-name>`.
2. Done means: acceptance criteria in the issue all ticked, tests added for new behaviour, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` green.
3. PR into `develop` with `Closes #<issue>`. `main` only receives release PRs from `develop`, and every push to `main` deploys to Hugging Face Spaces.

Mark long simulation tests `@pytest.mark.slow`; CI runs everything.

## Writing style

English everywhere (code, docs, issues). Use commas, colons or parentheses instead of em dashes or en dashes in all text, including docs and commit messages.

## Records

- Training runs: one entry per run in `docs/experiments.md`.
- Things read or learned: `docs/research.md`.
- Trained models go to the Hugging Face Hub, never into git.
