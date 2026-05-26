# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Autonovel is an AI-powered novel writing pipeline. It supports two modes:

1. **Legacy short-form pipeline** (`run_pipeline.py`): seed → foundation → draft → revision → export. Produces 8-10万字 novels.
2. **Webnovel long-form pipeline** (`run_webnovel_pipeline.py` / `autonovel_cli.py`): chapter-by-chapter transaction loop targeting 100万字+ web serials with structured state tracking.

All content is in Chinese (简体中文). All code comments and docstrings are in English.

## Commands

```bash
# Setup
cp .env.example .env    # Add API keys (ANTHROPIC_API_KEY or MINIMAX_API_KEY)
uv sync                 # Install dependencies

# Unified CLI (preferred for webnovel pipeline)
uv run python autonovel_cli.py status                    # Dashboard
uv run python autonovel_cli.py genres                    # List available genre configurations
uv run python autonovel_cli.py init --title "书名" --genre "种田文" --tags "穿越,大女主,萌娃"
uv run python autonovel_cli.py init --title "书名" --genre "年代文" --tags "穿越,年代,甜宠"
uv run python autonovel_cli.py init --title "书名" --genre "总裁豪门" --tags "总裁,豪门,甜宠"
uv run python autonovel_cli.py generate seed              # Generate story concepts (short-form)
uv run python autonovel_cli.py generate seed --long-form  # Generate long-form seeds (500+ chapters)
uv run python autonovel_cli.py generate seed --target-words 500000  # Long-form with custom target (30万-200万字)
uv run python autonovel_cli.py generate foundation        # Generate foundation (auto-detects short/long, long-form auto-evaluates)
uv run python autonovel_cli.py run --chapter 1           # Single chapter
uv run python autonovel_cli.py run --volume 1 --chapters 1-20 --resume
uv run python autonovel_cli.py validate                  # State validation
uv run python autonovel_cli.py plan volume --volume 1
uv run python autonovel_cli.py plan chapter --chapter 1
uv run python autonovel_cli.py plan batch --start 1 --count 20  # Batch chapter plans (default 20)
uv run python autonovel_cli.py report                    # Progress report

# Direct script invocation (also valid)
uv run python run_webnovel_pipeline.py --chapter 1
uv run python validate_state.py --full
uv run python memory_retrieval.py rebuild
uv run python seed_lf.py --target-words 500000        # Long-form seed with custom target
uv run python evaluate.py --phase=foundation-lf       # Evaluate long-form foundation docs

# Legacy pipeline
uv run python run_pipeline.py --from-scratch

# Tests
uv run python -m unittest test_llm_client.py

# LLM smoke test
uv run python smoke_llm.py
```

## Architecture

### Two Pipeline Systems

**Legacy pipeline** (`run_pipeline.py`): Reads `voice.md`, `world.md`, `characters.md`, `outline.md`, `canon.md` directly. No structured state. Chapters go to `chapters/ch_XX.md`.

**Webnovel pipeline** (`run_webnovel_pipeline.py`): 11-step chapter transaction loop. Foundation phase auto-detects short-form (gen_world.py → gen_outline.py, 24 chapters) vs long-form (gen_world_lf.py → gen_master_outline.py → gen_outline_v1.py → init_state.py, 500+ chapters) based on `target_chapters >= 100` in project.json. Long-form foundation auto-runs `evaluate.py --phase=foundation-lf` and writes results to `story/foundation_eval.json`.
1. Generate chapter plan (`gen_chapter_plan.py` or `gen_batch_chapter_plans.py` for batch mode)
2. Assemble context (`memory_orchestrator.py`)
3. Draft chapter (`draft_chapter.py`)
4. Extract delta (`extract_delta.py`)
5. Webnovel audit (`webnovel_audit.py`)
6. Validate delta (`validate_state.py --delta`)
7. Apply delta to state (in-process)
8. Snapshot & git commit (`snapshot_state.py`)
9. Index chapter into FTS5 (`memory_retrieval.py`)
10. Update projections (`update_projections.py`)
11. Periodic validation (every 5 chapters)

Chapters go to `chapters/v{NNN}/ch_{NNNN}.md`. Each chapter is a database-like transaction: either fully accepted (committed) or discarded.

### State Management (`story/`)

All state lives in `story/state/` as JSON, validated by Pydantic schemas in `story_schema.py`:

| File | Purpose |
|------|---------|
| `project.json` | Title, genre, tags, targets, current chapter/volume |
| `character_matrix.json` | Characters with relationships, personality, speech patterns |
| `current_state.json` | Timeline position, recent events |
| `pending_hooks.json` | Foreshadowing debt tracking (open/advanced/resolved) |
| `chapter_summaries.json` | Per-chapter summaries with key events |
| `power_ledger.json` | Power levels, resources, items with quantities |
| `subplot_board.json` | Active/resolved subplot threads |
| `emotional_arcs.json` | Character emotional arc tracking |

All state entries have temporal fields: `source_chapter`, `valid_from_chapter`, `valid_until_chapter`, `last_seen_chapter`. This enables the system to prevent future-information leaks.

`story/memory/memory.sqlite` is the FTS5 database for retrieval. `story/memory/snapshots/` holds ZIP snapshots and `commit_index.json`.

### Genre System (`genres/`)

The pipeline supports multiple genre configurations. Each genre provides:
- System prompts for all pipeline roles (seed_writer, architect, chapter_writer, etc.)
- Prompt fragments for each generation stage (seed, world, characters, outline, etc.)
- Evaluation dimensions and weights
- Reader personas for the reader panel
- Voice template (tone, rhythm, vocabulary hints)
- Writing craft reference document

Genre configs live in `genres/` as YAML files, loaded by `genres/genre_registry.py`:
- `_base.yaml` — Shared webnovel conventions + genre_map (name → filename)
- `zhongtian.yaml` — 种田文 config
- `niandai.yaml` — 年代文 config (1950s-1990s China)
- `zongcai.yaml` — 总裁豪门 config (modern CEO/billionaire romance)
- `craft/*.md` — Genre-specific writing craft references

Usage: `genre = load_genre_for_project()` reads `story/project.json` → genre field → loads YAML → deep-merges with `_base.yaml`. Falls back to 种田文 if genre not found.

Key consumers: `seed.py`, `seed_lf.py`, `gen_world*.py`, `gen_characters*.py`, `gen_outline*.py`, `gen_master_outline.py`, `gen_canon.py`, `draft_chapter.py`, `gen_revision.py`, `adversarial_edit.py`, `evaluate.py`, `reader_panel.py`.

### Key Shared Code

- **`story_schema.py`**: All Pydantic models, `count_cn_words()`, `load_json()`/`save_json()`/`load_yaml()`/`save_yaml()`. Import from here for any state manipulation.
- **`llm_client.py`**: `call_text_model()` — shared LLM call with retry logic. Supports Anthropic native and MiniMax (via Anthropic-compatible endpoint). Provider selected by `AUTONOVEL_LLM_PROVIDER` env var.
- **`memory_retrieval.py`**: SQLite FTS5 indexing and search. Temporal-filtered, entity-tagged retrieval.

### Pipeline Flags

The webnovel pipeline supports:
- `--resume`: Skip chapters that already have accepted snapshots
- `--continue-on-failure`: Don't stop at first chapter failure
- `--audit-warn`: Treat audit blocking issues as warnings (development mode)
- `--dry-run`: Show what would run without executing

## LLM Provider Configuration

Set in `.env`:
- `AUTONOVEL_LLM_PROVIDER`: `anthropic` or `minimax`
- `ANTHROPIC_API_KEY` / `MINIMAX_API_KEY`: Provider keys
- `AUTONOVEL_WRITER_MODEL`, `AUTONOVEL_JUDGE_MODEL`, `AUTONOVEL_REVIEW_MODEL`: Model names
- `AUTONOVEL_API_BASE_URL`: Optional endpoint override (MiniMax default: `https://api.minimaxi.com/anthropic`)

Writer model uses temperature 0.8; judge/review models use temperature 0.3. All calls go through `llm_client.py` which handles 429 retries.

## Framework Docs

These markdown files define writing constraints and are read by LLM prompts:
- `CRAFT.md` — Writing craft education (plot, character, prose)
- `ANTI-SLOP.md` — Word-level AI trace detection rules
- `ANTI-PATTERNS.md` — Structural AI pattern detection
- `voice.md` — Narrative voice identity and guardrails
- `program.md` — Per-phase agent instructions
