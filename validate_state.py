#!/usr/bin/env python3
"""
validate_state.py — Validate story state files and chapter deltas.

Usage:
  uv run python validate_state.py --full
  uv run python validate_state.py --delta story/runtime/ch_0001/delta.json --chapter 1
"""

import argparse
import json
import sys
from pathlib import Path

from story_schema import (
    AuditResult,
    ChapterDelta,
    ChapterSummaries,
    CharacterMatrix,
    CurrentState,
    EmotionalArcs,
    PendingHooks,
    PowerLedgerFull,
    ProjectConfig,
    SubplotBoard,
    load_json,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"


# ---------------------------------------------------------------------------
# Schema validators
# ---------------------------------------------------------------------------

def validate_project() -> list[str]:
    """Validate story/project.json."""
    errors = []
    path = STORY_DIR / "project.json"
    if not path.exists():
        errors.append("story/project.json not found")
        return errors
    try:
        data = load_json(path)
        ProjectConfig(**data)
    except Exception as e:
        errors.append(f"story/project.json schema error: {e}")
    return errors


def validate_state_files() -> list[str]:
    """Validate all seven state JSON files against their schemas."""
    errors = []
    validators = {
        "state/current_state.json": CurrentState,
        "state/character_matrix.json": CharacterMatrix,
        "state/power_ledger.json": PowerLedgerFull,
        "state/pending_hooks.json": PendingHooks,
        "state/chapter_summaries.json": ChapterSummaries,
        "state/subplot_board.json": SubplotBoard,
        "state/emotional_arcs.json": EmotionalArcs,
    }
    for rel_path, schema_cls in validators.items():
        path = STORY_DIR / rel_path
        if not path.exists():
            errors.append(f"story/{rel_path} not found")
            continue
        try:
            data = load_json(path)
            schema_cls(**data)
        except Exception as e:
            errors.append(f"story/{rel_path} schema error: {e}")
    return errors


def validate_snapshot_index() -> list[str]:
    """Validate the snapshot commit index."""
    errors = []
    path = STORY_DIR / "memory" / "snapshots" / "commit_index.json"
    if not path.exists():
        # Not mandatory at init time
        return errors
    try:
        data = load_json(path)
        if "entries" not in data:
            errors.append("commit_index.json missing 'entries' field")
    except Exception as e:
        errors.append(f"commit_index.json parse error: {e}")
    return errors


# ---------------------------------------------------------------------------
# Delta validators
# ---------------------------------------------------------------------------

def validate_delta_schema(delta_path: Path) -> tuple[ChapterDelta | None, list[str]]:
    """Validate delta JSON against ChapterDelta schema."""
    errors = []
    if not delta_path.exists():
        errors.append(f"Delta file not found: {delta_path}")
        return None, errors
    try:
        data = load_json(delta_path)
        delta = ChapterDelta(**data)
        return delta, errors
    except Exception as e:
        errors.append(f"Delta schema error: {e}")
        return None, errors


def validate_delta_against_state(delta: ChapterDelta, chapter: int) -> list[str]:
    """Validate delta content against current state (hard checks)."""
    errors = []

    # Load current state
    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    power_ledger = PowerLedgerFull(**load_json(STORY_DIR / "state" / "power_ledger.json"))
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))

    existing_char_ids = set(char_matrix.characters.keys())
    existing_item_ids = set(power_ledger.items.keys())
    existing_resource_ids = set(power_ledger.resources.keys())
    existing_hook_ids = set(hooks.hooks.keys())

    # Check character updates reference existing characters
    for update in delta.character_updates:
        char_id = update.get("id", "")
        if char_id and char_id not in existing_char_ids and not update.get("new_character", False):
            errors.append(f"Character update references non-existent character: {char_id}")

    # Check resource updates
    for update in delta.resource_updates:
        res_id = update.get("id", "")
        action = update.get("action", "")
        if action == "consume" and res_id and res_id not in existing_resource_ids:
            errors.append(f"Resource consume references non-existent resource: {res_id}")
        if action == "create":
            # New resources are allowed, but must have required fields
            if not update.get("name"):
                errors.append(f"New resource missing 'name' field")

    # Check item updates
    for update in delta.item_updates:
        item_id = update.get("id", "")
        action = update.get("action", "")
        if action in ("transfer", "destroy", "upgrade") and item_id and item_id not in existing_item_ids:
            errors.append(f"Item action '{action}' references non-existent item: {item_id}")

    # Check hook updates
    for update in delta.hook_updates:
        hook_id = update.get("id", "")
        action = update.get("action", "")
        if action in ("advance", "resolve") and hook_id and hook_id not in existing_hook_ids:
            errors.append(f"Hook '{action}' references non-existent hook: {hook_id}")
        if action == "resolve":
            hook = hooks.hooks.get(hook_id)
            if hook and hook.status == "resolved":
                errors.append(f"Hook {hook_id} is already resolved, cannot resolve again")

    # Check power updates — no skipping levels
    for update in delta.power_updates:
        char_id = update.get("character_id", "")
        new_rank = update.get("new_rank")
        if char_id and new_rank is not None:
            current_max = 0
            for level in power_ledger.levels:
                if level.character_id == char_id and level.level_rank > current_max:
                    current_max = level.level_rank
            if new_rank > current_max + 1:
                errors.append(
                    f"Power level skip detected for {char_id}: "
                    f"current max rank {current_max}, attempting rank {new_rank}"
                )

    # Check that chapter_summary chapter matches
    if delta.chapter_summary:
        summary_ch = delta.chapter_summary.get("chapter", 0)
        if summary_ch and summary_ch != chapter:
            errors.append(
                f"Chapter summary chapter mismatch: delta says {summary_ch}, expected {chapter}"
            )

    return errors


def validate_future_info(delta: ChapterDelta, chapter: int) -> list[str]:
    """Check that delta doesn't reference future chapter information."""
    errors = []
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))

    # Collect all chapter numbers mentioned in the delta
    def check_chapter_ref(value, context):
        if isinstance(value, int) and value > chapter:
            errors.append(f"Future chapter reference ({value}) in {context}")
        elif isinstance(value, str):
            # Check for "ch_N" or "chapter N" patterns
            import re
            for m in re.finditer(r'ch[_\s]*(\d+)', value, re.IGNORECASE):
                ref_ch = int(m.group(1))
                if ref_ch > chapter:
                    errors.append(f"Future chapter reference (ch_{ref_ch}) in {context}")

    for fact in delta.new_facts:
        for k, v in fact.items():
            check_chapter_ref(v, f"new_facts.{k}")

    for update in delta.character_updates:
        for k, v in update.items():
            if k != "new_character":
                check_chapter_ref(v, f"character_updates.{k}")

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_full_validation() -> bool:
    """Run full state validation. Returns True if all pass."""
    print("=" * 60)
    print("Full State Validation")
    print("=" * 60)
    all_errors = []

    # Project
    errs = validate_project()
    if errs:
        all_errors.extend(errs)
        print(f"  [FAIL] project.json: {len(errs)} error(s)")
        for e in errs:
            print(f"         - {e}")
    else:
        print("  [PASS] project.json")

    # State files
    errs = validate_state_files()
    if errs:
        all_errors.extend(errs)
        print(f"  [FAIL] state files: {len(errs)} error(s)")
        for e in errs:
            print(f"         - {e}")
    else:
        print("  [PASS] state files (7/7)")

    # Snapshot index
    errs = validate_snapshot_index()
    if errs:
        all_errors.extend(errs)
        print(f"  [FAIL] snapshot index: {len(errs)} error(s)")
    else:
        print("  [PASS] snapshot index")

    print("=" * 60)
    if all_errors:
        print(f"VALIDATION FAILED: {len(all_errors)} error(s)")
        return False
    print("VALIDATION PASSED")
    return True


def run_delta_validation(delta_path: str, chapter: int) -> bool:
    """Validate a chapter delta. Returns True if all pass."""
    print("=" * 60)
    print(f"Delta Validation — Chapter {chapter}")
    print("=" * 60)
    all_errors = []

    # Schema
    delta, errs = validate_delta_schema(Path(delta_path))
    if errs:
        all_errors.extend(errs)
        print(f"  [FAIL] delta schema: {len(errs)} error(s)")
        for e in errs:
            print(f"         - {e}")
        print("=" * 60)
        print(f"VALIDATION FAILED: {len(all_errors)} error(s)")
        return False
    print("  [PASS] delta schema")

    # State consistency
    errs = validate_delta_against_state(delta, chapter)
    if errs:
        all_errors.extend(errs)
        print(f"  [FAIL] state consistency: {len(errs)} error(s)")
        for e in errs:
            print(f"         - {e}")
    else:
        print("  [PASS] state consistency")

    # Future info
    errs = validate_future_info(delta, chapter)
    if errs:
        all_errors.extend(errs)
        print(f"  [FAIL] future info check: {len(errs)} error(s)")
        for e in errs:
            print(f"         - {e}")
    else:
        print("  [PASS] no future info references")

    print("=" * 60)
    if all_errors:
        print(f"VALIDATION FAILED: {len(all_errors)} error(s)")
        return False
    print("VALIDATION PASSED")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate story state and deltas")
    parser.add_argument("--full", action="store_true", help="Run full state validation")
    parser.add_argument("--delta", type=str, help="Path to delta.json to validate")
    parser.add_argument("--chapter", type=int, help="Chapter number for delta validation")
    args = parser.parse_args()

    if args.full:
        success = run_full_validation()
        sys.exit(0 if success else 1)
    elif args.delta:
        if not args.chapter:
            print("Error: --chapter is required when using --delta", file=sys.stderr)
            sys.exit(1)
        success = run_delta_validation(args.delta, args.chapter)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
