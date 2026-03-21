## Cursor Cloud specific instructions

### Overview

flomo-cli is a Python CLI tool (reverse-engineered Flomo Web API client). Single-service, no databases, no Docker.

### Prerequisites

- Python >= 3.10 (system Python 3.12 is fine)
- `uv` package manager — installed to `~/.local/bin` (already on PATH after setup)

### Common commands

See `README.md` "开发" section for full details. Quick reference:

| Action | Command |
|---|---|
| Install deps | `uv sync --dev` |
| Run tests | `uv run pytest -v` |
| Run single test | `uv run pytest tests/test_signing.py -v` |
| CLI help | `uv run flomo --help` |
| CLI version | `uv run flomo --version` |

### Notes

- No linter is configured in the project (no ruff/flake8/mypy/pylint). Syntax-check via `python -m py_compile` if needed.
- All 63 tests are fully mocked (no network access required). Safe to run in any environment.
- Live CLI commands (e.g. `flomo list`, `flomo new`) require a Flomo account token. Set `FLOMO_TOKEN` env var or run `flomo login`. Without auth, `flomo status --json` returns `{"ok": false, "authenticated": false}` — useful as a smoke test.
- The project uses `hatchling` as build backend. `uv sync --dev` installs the package in editable mode automatically.
