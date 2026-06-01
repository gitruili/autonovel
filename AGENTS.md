# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.12 novel-generation pipeline. Most executable modules live at the repository root: `autonovel_cli.py` is the unified CLI, `run_pipeline.py` runs the full book pipeline, and `gen_*.py`, `evaluate.py`, `review.py`, and `validate_state.py` implement stages. Genre configuration lives in `genres/`, with craft notes in `genres/craft/`. Runtime novel state and plans live in `story/`; treat `story/state/*.json` and `story/plans/*.yaml` as structured project data. Typesetting assets are under `typeset/`, the static landing page is under `landing/`, and tests are root-level `test_*.py` files.

## Build, Test, and Development Commands

- `uv sync`: install dependencies from `pyproject.toml` and `uv.lock`.
- `uv run python autonovel_cli.py genres`: list supported genres.
- `uv run python autonovel_cli.py init --title "My Novel" --genre "年代文"`: initialize a story workspace.
- `uv run python autonovel_cli.py status`: inspect current project state.
- `uv run python run_pipeline.py --from-scratch`: run the full pipeline from foundation through export.
- `uv run python smoke_llm.py`: verify LLM configuration before long runs.
- `uv run python -m unittest discover -p 'test_*.py'`: run the test suite.

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, clear function names, and `pathlib.Path` for filesystem paths where practical. Keep CLI scripts executable with `if __name__ == "__main__":` entry points. Name new pipeline stages with the existing verb-object pattern, such as `gen_volume_plan.py` or `build_arc_summary.py`. Keep prompt/config data in YAML or Markdown instead of embedding large genre-specific blocks in Python.

## Testing Guidelines

Tests use `unittest` and `unittest.mock`; no pytest fixtures are required. Add new tests as `test_<feature>.py` at the root, with classes named `Test<Feature>`. Prefer deterministic tests that mock environment variables, API calls, and filesystem-heavy behavior. For genre changes, cover registry loading, prompt fragments, fallbacks, and project initialization.

## Commit & Pull Request Guidelines

Recent history mostly follows Conventional Commits, for example `feat: add ...`, `fix: ...`, and `refactor: ...`; concise Chinese summaries are also present. Use a scoped, imperative subject naming the affected pipeline area. Pull requests should include the behavior change, commands run, new environment variables, and notes on generated artifacts or story-state migrations. Include screenshots only for `landing/`, cover, or typesetting changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` locally and never commit real API keys. LLM, art, and audiobook commands may call external services, so run smoke checks before batch jobs and keep generated media or large outputs out of commits unless intentional.
