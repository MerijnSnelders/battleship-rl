# battleship-rl

Hosted Battleship game against heuristic AIs and a self-trained RL agent. It is a school Personal Experiment answering one research question: how does a reinforcement learning agent compare to heuristic strategies in Battleship, and how can it be developed, evaluated and deployed in a reproducible and testable way? Evaluation and tests matter as much as features.

## Ownership: check the issue label first

- `rl` and `research` issues belong to the owner: he writes this code and these notes himself (RL environment, reward, training config, RL evaluation, study notes). Act as a tutor: explain, ask questions, review his work, point to docs. Keep code in chat to small illustrative snippets; the implementation in the repo is his.
- All other issues (`engine`, `ai`, `backend`, `frontend`, `infra`, `docs`): build them, open a PR, the owner reviews.

## Architecture rules

- `src/battleship/` is the single source of truth for game rules. The API, every AI and the Gymnasium environment call into it; rules live nowhere else, including the JavaScript frontend.
- The server holds game state per game ID. Responses only contain what the player may see: AI ship positions stay on the server until the game ends.
- The frontend is plain HTML, CSS and JavaScript in `app/static/`, with no build step and no framework.
- Board size and fleet always come from `GameConfig`; tests run on `SMALL` and `STANDARD`.
- AIs share one interface so the API, benchmark and RL agent are interchangeable.

## Workflow

1. Branch from `develop`: `feature/<issue>-<short-name>` or `fix/<issue>-<short-name>`.
2. Done means: every acceptance criterion in the issue ticked, tests added for new behaviour, and `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` all green.
3. PR into `develop` with `Closes #<issue>`. `main` only receives release PRs from `develop`, and every push to `main` deploys to Hugging Face Spaces.

Mark long simulation tests `@pytest.mark.slow`; CI runs everything.

## Writing style

English everywhere (code, docs, issues). Use commas, colons or parentheses instead of em dashes or en dashes in all text, including docs and commit messages.

## Records

- Training runs: one entry per run in `docs/experiments.md`.
- Things read or learned: `docs/research.md`.
- Trained models go to the Hugging Face Hub, never into git.
