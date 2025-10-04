# Repository Guidelines

## Project Structure & Module Organization
DryBox sources live in `drybox/`: `core/` hosts the simulation runner and scenario resolution, `net/` implements bearer models and SAR helpers, `radio/` emulates audio channels, and `gui/` contains the PySide6 UI stubs. Integration tests and fixtures sit under `drybox/tests/`, with reusable adapter doubles in `drybox/tests/adapters/`. Reference adapters live in `adapters/`, while reusable assets stay in `drybox/scenarios/` (YAML), `drybox/schema/` (JSON), and `drybox/WAV/` (PCM samples). Use `runs/` for per-experiment artifacts; the runner mirrors this directory when you pass `--out`.

## Build, Test, and Development Commands
Install dependencies with `uv sync` (falls back to `pip install -e .[dev]` if uv is unavailable). Run `make test` to execute the curated pytest suite with coverage and strict failures. For manual runs, `./drybox/tests/run_tests.sh -k bytelink` respects the repo’s virtualenv detection and accepts pytest selectors. Launch a full simulation with:
```bash
uv run drybox-run --scenario drybox/scenarios/test_scenario.yaml \
  --left adapters/nade_adapter.py --right adapters/nade_adapter.py \
  --out runs/dev-local
```
Adjust adapters or `--tick-ms`/`--seed` as needed.

## Coding Style & Naming Conventions
Target Python 3.11+, four-space indentation, and `snake_case` for modules/functions. Prefer dataclasses for structured payloads, keep pure functions in `core`/`net`, and reserve side effects for orchestration layers. Maintain type hints and descriptive docstrings for public entry points. Use f-strings and pathlib; avoid bare `print` outside CLI/UI code.

## Testing Guidelines
Add unit tests beside the code (`drybox/tests/<domain>/`) and keep names descriptive (`test_<behavior>_imports`). Pytest with `--cov=drybox/core --cov=drybox/net` runs by default; aim to keep new modules within that coverage envelope. Integration scenarios belong in `test_integration_audio.py` or new files under `tests/` with the `integration_` prefix. When introducing CLI flags or schema changes, capture them in YAML fixtures and validate with `ScenarioResolved` helpers.

## Commit & Pull Request Guidelines
Follow the conventional commit prefixes already in history (`fix:`, `refactor:`, `feat:`) and keep subjects under 72 characters. In PRs, describe the scenario or adapter affected, list new commands or configs, and attach links to relevant specs (`Spec_*.md`). Provide `make test` output or run IDs, note schema migrations, and include screenshots/log excerpts for UI or metrics-facing tweaks.

## Scenario & Adapter Tips
Adapters must expose an `Adapter` class; pass the path (optionally `:CustomClass`) to `drybox-run`. Document any external binaries they call. When creating new scenarios, reuse keys from `schema/scenario.json` to stay compatible with validation and update schemas when introducing new attributes.
