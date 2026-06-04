#!/usr/bin/env python3
"""
run_webnovel_pipeline.py — Webnovel long-form pipeline orchestrator.

Runs the complete chapter transaction loop:
  chapter plan -> context assembly -> draft -> delta extraction ->
  audit -> validation -> state apply -> snapshot -> git commit

Supports volume/chapter dual-layer progress with periodic summaries
and volume-end compaction.

Usage:
  uv run python run_webnovel_pipeline.py --chapter 1
  uv run python run_webnovel_pipeline.py --volume 1 --chapters 1-20
  uv run python run_webnovel_pipeline.py --volume-range 1-3
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from story_schema import (
    ChapterContext,
    ChapterDelta,
    ChapterSummaries,
    CharacterMatrix,
    CurrentState,
    EmotionalArcs,
    PendingHooks,
    PowerLedgerFull,
    ProjectConfig,
    SubplotBoard,
    count_cn_words,
    load_json,
    save_json,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"

# Global flag: when True, audit failures are warnings instead of blockers
AUDIT_WARN_MODE = False


def get_chapters_v_dir(volume: int) -> Path:
    """Get the chapters directory for a given volume number."""
    return BASE_DIR / "chapters" / f"v{volume:03d}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def banner(text: str, char: str = "=", width: int = 60):
    """Print a visible step banner."""
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}\n")


def get_runtime_dir(chapter: int) -> Path:
    """Get the runtime directory for a chapter."""
    return STORY_DIR / "runtime" / f"ch_{chapter:04d}"


def load_project() -> ProjectConfig:
    """Load project config."""
    data = load_json(STORY_DIR / "project.json")
    return ProjectConfig(**data)


def save_project(proj: ProjectConfig):
    """Save project config."""
    save_json(STORY_DIR / "project.json", proj.model_dump())


def git_commit(message: str) -> str:
    """Stage all changes and commit. Returns commit hash."""
    subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, check=True)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if "nothing to commit" in result.stdout:
            return "(no changes)"
        print(f"Git commit failed: {result.stderr}", file=sys.stderr)
        return ""
    # Get commit hash
    hash_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    return hash_result.stdout.strip()[:12]


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step_ensure_volume_plan(chapter: int) -> bool:
    """Phase 1: Ensure the volume plan and outline exist before generating a chapter."""
    proj = load_project()
    volume = proj.current_volume
    
    plan_yaml = STORY_DIR / "plans" / f"volume_{volume:03d}.yaml"
    plan_md = STORY_DIR / "plans" / f"volume_{volume:03d}_outline.md"
    
    if plan_yaml.exists() and plan_md.exists():
        return True
        
    banner(f"Step 0: Ensure Volume {volume} Plan")
    
    if not plan_yaml.exists():
        print(f"  Generating {plan_yaml.name}...")
        res = subprocess.run([sys.executable, "gen_volume_plan.py", "--volume", str(volume)], cwd=BASE_DIR)
        if res.returncode != 0:
            print(f"  [ERROR] gen_volume_plan.py failed")
            return False
            
    if not plan_md.exists():
        print(f"  Generating {plan_md.name}...")
        res = subprocess.run([sys.executable, "gen_volume_outline.py", "--volume", str(volume)], cwd=BASE_DIR)
        if res.returncode != 0:
            print(f"  [ERROR] gen_volume_outline.py failed")
            return False
            
    return True


def step_gen_chapter_plan(chapter: int) -> bool:
    """Phase 2: Generate chapter plan and intent."""
    banner(f"Step 1: Generate Chapter Plan — Chapter {chapter}")
    rt_dir = get_runtime_dir(chapter)
    rt_dir.mkdir(parents=True, exist_ok=True)

    plan_path = STORY_DIR / "plans" / f"chapter_{chapter:04d}.yaml"
    intent_path = rt_dir / "intent.md"

    if plan_path.exists() and intent_path.exists():
        print(f"  Chapter plan found: {plan_path}")
        return True

    # Generate plan using LLM
    result = subprocess.run(
        [sys.executable, "gen_chapter_plan.py", "--chapter", str(chapter)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and plan_path.exists():
        print(f"  Chapter plan generated: {plan_path}")
        return True
    else:
        print(f"  [ERROR] gen_chapter_plan.py failed: {result.stderr}")
        return False


def step_assemble_context(chapter: int) -> bool:
    """Phase 2: Assemble context.json for the writer."""
    banner(f"Step 2: Assemble Context — Chapter {chapter}")
    rt_dir = get_runtime_dir(chapter)
    context_path = rt_dir / "context.json"

    if context_path.exists():
        print(f"  Context found: {context_path}")
        return True

    result = subprocess.run(
        [sys.executable, "memory_orchestrator.py",
         "--chapter", str(chapter),
         "--out", str(context_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and context_path.exists():
        print(f"  Context assembled: {context_path}")
        return True
    else:
        print(f"  [ERROR] memory_orchestrator.py failed: {result.stderr}")
        return False


def step_draft_chapter(chapter: int) -> bool:
    """Phase 2: Generate chapter draft."""
    banner(f"Step 3: Draft Chapter — Chapter {chapter}")
    rt_dir = get_runtime_dir(chapter)
    draft_path = rt_dir / "draft.md"

    if draft_path.exists():
        print(f"  Draft found: {draft_path}")
        return True

    # Try running draft_chapter.py with context
    context_path = rt_dir / "context.json"
    if context_path.exists():
        print(f"  Running draft_chapter.py with context...")
        result = subprocess.run(
            [sys.executable, "draft_chapter.py", str(chapter),
             "--context", str(context_path),
             "--out", str(draft_path)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  Draft saved: {draft_path}")
            return True
        else:
            print(f"  [ERROR] Draft failed: {result.stderr}")
            return False
    else:
        print(f"  [ERROR] No context available for drafting")
        return False


def step_extract_delta(chapter: int) -> bool:
    """Phase 3: Extract delta from draft."""
    banner(f"Step 4: Extract Delta — Chapter {chapter}")
    rt_dir = get_runtime_dir(chapter)
    delta_path = rt_dir / "delta.json"
    draft_path = rt_dir / "draft.md"

    if delta_path.exists():
        print(f"  Delta found: {delta_path}")
        return True

    if not draft_path.exists():
        print(f"  [ERROR] No draft found: {draft_path}")
        return False

    result = subprocess.run(
        [sys.executable, "extract_delta.py",
         "--chapter", str(chapter),
         "--draft", str(draft_path),
         "--out", str(delta_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and delta_path.exists():
        print(f"  Delta extracted: {delta_path}")
        return True
    else:
        print(f"  [ERROR] extract_delta.py failed: {result.stderr}")
        return False


def step_webnovel_audit(chapter: int) -> bool:
    """Phase 4: Run webnovel audit on draft."""
    banner(f"Step 5: Webnovel Audit — Chapter {chapter}")
    rt_dir = get_runtime_dir(chapter)
    audit_path = rt_dir / "audit.json"
    draft_path = rt_dir / "draft.md"
    delta_path = rt_dir / "delta.json"

    if audit_path.exists():
        print(f"  Audit found: {audit_path}")
        return True

    if not draft_path.exists() or not delta_path.exists():
        print(f"  [ERROR] Missing draft or delta for audit")
        return False

    result = subprocess.run(
        [sys.executable, "webnovel_audit.py",
         "--chapter", str(chapter),
         "--draft", str(draft_path),
         "--delta", str(delta_path),
         "--out", str(audit_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    # Audit may return non-zero for warnings, but we still want the report
    if not audit_path.exists():
        print(f"  [ERROR] webnovel_audit.py failed: {result.stderr}")
        return False

    print(f"  Audit report: {audit_path}")

    # Check audit result
    from story_schema import AuditResult
    audit_data = load_json(audit_path)
    audit = AuditResult(**audit_data)

    if audit.blocking_issues:
        print(f"  [BLOCKING] {len(audit.blocking_issues)} blocking issue(s):")
        for issue in audit.blocking_issues:
            print(f"    - {issue}")
        if AUDIT_WARN_MODE:
            print(f"  [WARN MODE] Blocking issues treated as warnings")
        else:
            return False

    if audit.warnings:
        print(f"  [WARN] {len(audit.warnings)} warning(s):")
        for w in audit.warnings:
            print(f"    - {w}")

    print(f"  Overall score: {audit.overall_score:.1f}")
    return True


def step_validate_delta(chapter: int) -> bool:
    """Phase 3: Validate delta against state."""
    banner(f"Step 6: Validate Delta — Chapter {chapter}")
    rt_dir = get_runtime_dir(chapter)
    delta_path = rt_dir / "delta.json"

    if not delta_path.exists():
        print(f"  [ERROR] No delta found: {delta_path}")
        return False

    result = subprocess.run(
        [sys.executable, "validate_state.py",
         "--delta", str(delta_path),
         "--chapter", str(chapter)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"  [FAIL] Delta validation failed")
        return False
    print("  [PASS] Delta validated")
    return True


def step_apply_delta(chapter: int) -> bool:
    """Phase 3: Apply delta to state files.

    Loads all state, applies all changes, then saves all at once.
    If any exception occurs during apply, no state files are written,
    keeping disk state consistent.
    """
    banner(f"Step 7: Apply Delta — Chapter {chapter}")
    rt_dir = get_runtime_dir(chapter)
    delta_path = rt_dir / "delta.json"

    if not delta_path.exists():
        print(f"  [ERROR] No delta found")
        return False

    delta_data = load_json(delta_path)
    delta = ChapterDelta(**delta_data)

    # Load current state
    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    power_ledger = PowerLedgerFull(**load_json(STORY_DIR / "state" / "power_ledger.json"))
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))
    emotional_arcs = EmotionalArcs(**load_json(STORY_DIR / "state" / "emotional_arcs.json"))
    current_state = CurrentState(**load_json(STORY_DIR / "state" / "current_state.json"))

    # NOTE: All modifications below are on in-memory objects.
    # State files are only saved at the end of this function.
    # If any exception occurs during apply, save never happens
    # and disk state remains consistent.

    # Apply character updates
    for update in delta.character_updates:
        char_id = update.pop("id", "")
        if not char_id:
            continue
        if char_id in char_matrix.characters:
            char = char_matrix.characters[char_id]
            # Handle field/value format from LLM
            if "field" in update and "value" in update:
                field_name = update["field"]
                if hasattr(char, field_name):
                    setattr(char, field_name, update["value"])
                elif field_name == "灵根状态":
                    char.personality = (char.personality + f" [灵根: {update['value']}]").strip()
            else:
                for k, v in update.items():
                    if k != "new_character" and hasattr(char, k):
                        setattr(char, k, v)
            char.last_seen_chapter = chapter
        elif update.get("new_character"):
            from story_schema import Character
            update.pop("new_character", None)
            # Handle field/value format: use id as name
            if "name" not in update:
                update["name"] = char_id
            if "field" in update and "value" in update:
                field_info = f"{update.pop('field')}: {update.pop('value')}"
                update["personality"] = field_info
            update["id"] = char_id
            update["source_chapter"] = chapter
            update["last_seen_chapter"] = chapter
            char_matrix.characters[char_id] = Character(**update)

    # Apply resource updates
    for update in delta.resource_updates:
        from story_schema import Resource
        action = update.get("action", "create")
        res_id = update.pop("id", None) or update.get("name", "") or f"res_{chapter}_{len(power_ledger.resources)}"
        if action == "create":
            update.pop("action", None)
            update["source_chapter"] = chapter
            update["last_seen_chapter"] = chapter
            if "name" not in update:
                update["name"] = res_id
            # Strip None values — JSON null for optional string fields (e.g. owner)
            # would fail Pydantic str validation
            clean = {k: v for k, v in update.items() if v is not None}
            power_ledger.resources[res_id] = Resource(id=res_id, **clean)
        elif action == "update" and res_id in power_ledger.resources:
            res = power_ledger.resources[res_id]
            for k, v in update.items():
                if k not in ("action", "id") and hasattr(res, k):
                    # Skip non-numeric values for numeric fields (quantity)
                    if k == "quantity" and not isinstance(v, (int, float)):
                        continue
                    setattr(res, k, v)
            res.quantity = max(0.0, res.quantity)
            res.last_seen_chapter = chapter
        elif action == "consume":
            if res_id and res_id not in power_ledger.resources:
                # Implicit create for non-existent resource
                from story_schema import Resource
                power_ledger.resources[res_id] = Resource(
                    id=res_id,
                    name=update.get("name", res_id),
                    category=update.get("category", ""),
                    quantity=0,
                    unit=update.get("unit", ""),
                    owner=update.get("owner") or "",
                    source_chapter=chapter,
                    last_seen_chapter=chapter,
                )
            if res_id in power_ledger.resources:
                qty = update.get("quantity", 0)
                if isinstance(qty, (int, float)):
                    power_ledger.resources[res_id].quantity = max(0.0, power_ledger.resources[res_id].quantity - qty)
                power_ledger.resources[res_id].last_seen_chapter = chapter
        elif action == "update" and res_id in power_ledger.resources:
            res = power_ledger.resources[res_id]
            for k, v in update.items():
                if k not in ("action", "id") and hasattr(res, k):
                    if k == "quantity" and not isinstance(v, (int, float)):
                        continue
                    setattr(res, k, v)
            res.last_seen_chapter = chapter

    # Apply item updates — process creates first, then other actions
    # This ensures transfer/destroy on same-chapter-created items work
    from story_schema import Item
    create_updates = [u for u in delta.item_updates if u.get("action") == "create"]
    other_updates = [u for u in delta.item_updates if u.get("action") != "create"]

    for update in create_updates:
        raw_id = update.pop("id", None)
        raw_name = update.get("name", "")
        item_id = raw_id or raw_name or f"item_{chapter}_{len(power_ledger.items)}"
        update.pop("action", None)
        update.pop("new_owner", None)
        update["source_chapter"] = chapter
        update["last_seen_chapter"] = chapter
        update["acquired_chapter"] = chapter
        if "name" not in update:
            update["name"] = item_id
        clean = {k: v for k, v in update.items() if v is not None}
        power_ledger.items[item_id] = Item(id=item_id, **clean)

    for update in other_updates:
        action = update.get("action", "")
        raw_id = update.pop("id", None)
        raw_name = update.get("name", "")
        item_id = raw_id or raw_name or f"item_{chapter}_{len(power_ledger.items)}"
        if action == "transfer" and item_id in power_ledger.items:
            power_ledger.items[item_id].owner = update.get("new_owner", "")
            power_ledger.items[item_id].last_seen_chapter = chapter
        elif action == "transfer" and item_id not in power_ledger.items:
            # Item not found — likely a hallucinated item name, skip silently
            pass
        elif action == "destroy" and item_id in power_ledger.items:
            power_ledger.items[item_id].status = "expired"
            power_ledger.items[item_id].valid_until_chapter = chapter

    # Apply hook updates
    for update in delta.hook_updates:
        from story_schema import ForeshadowHook
        action = update.get("action", "create")
        hook_id = update.pop("id", "")
        if action == "create":
            update.pop("action", None)
            update["source_chapter"] = chapter
            update["planted_chapter"] = chapter
            update["last_seen_chapter"] = chapter
            if not hook_id:
                hook_id = f"hook_{chapter}_{len(hooks.hooks)}"
            hooks.hooks[hook_id] = ForeshadowHook(id=hook_id, **update)
        elif action == "advance" and hook_id in hooks.hooks:
            hooks.hooks[hook_id].hook_type = "advance"
            hooks.hooks[hook_id].last_seen_chapter = chapter
        elif action == "resolve" and hook_id in hooks.hooks:
            hooks.hooks[hook_id].status = "resolved"
            hooks.hooks[hook_id].valid_until_chapter = chapter
            hooks.hooks[hook_id].last_seen_chapter = chapter

    # Apply power updates
    for update in delta.power_updates:
        from story_schema import PowerLevel
        char_id = update.get("character_id", "")
        if char_id:
            new_level = PowerLevel(
                id=f"power_{char_id}_{chapter}",
                character_id=char_id,
                level_name=update.get("level_name", ""),
                level_rank=update.get("new_rank", 0),
                breakthrough_chapter=chapter,
                source_chapter=chapter,
                last_seen_chapter=chapter,
            )
            power_ledger.levels.append(new_level)

    # Apply subplot updates
    for update in delta.subplot_updates:
        from story_schema import Subplot
        action = update.get("action", "update")
        subplot_id = update.pop("id", "")
        if action == "create":
            update.pop("action", None)
            update["source_chapter"] = chapter
            update["last_seen_chapter"] = chapter
            if not subplot_id:
                subplot_id = f"subplot_{chapter}_{len(subplots.subplots)}"
            subplots.subplots[subplot_id] = Subplot(id=subplot_id, **update)
        elif action == "update" and subplot_id in subplots.subplots:
            sp = subplots.subplots[subplot_id]
            for k, v in update.items():
                if k not in ("action", "id") and hasattr(sp, k):
                    setattr(sp, k, v)
            sp.last_seen_chapter = chapter
            if chapter not in sp.chapters_involved:
                sp.chapters_involved.append(chapter)

    # Apply emotional arc updates
    for update in delta.emotional_arc_updates:
        from story_schema import EmotionalArc
        action = update.get("action", "create")
        arc_id = update.pop("id", "")
        if action == "create":
            update.pop("action", None)
            update["source_chapter"] = chapter
            update["last_seen_chapter"] = chapter
            update["start_chapter"] = chapter
            if not arc_id:
                arc_id = f"arc_{chapter}_{len(emotional_arcs.arcs)}"
            emotional_arcs.arcs[arc_id] = EmotionalArc(id=arc_id, **update)
        elif action == "update" and arc_id in emotional_arcs.arcs:
            arc = emotional_arcs.arcs[arc_id]
            for k, v in update.items():
                if k not in ("action", "id") and hasattr(arc, k):
                    setattr(arc, k, v)
            arc.last_seen_chapter = chapter

    # Apply chapter summary
    if delta.chapter_summary:
        from story_schema import ChapterSummary
        ch_key = f"ch_{chapter}"
        summary = ChapterSummary(
            chapter=chapter,
            source_chapter=chapter,
            last_seen_chapter=chapter,
            **delta.chapter_summary,
        )
        summaries.summaries[ch_key] = summary

    # Update project state
    proj = load_project()
    proj.current_chapter = chapter
    # Count words from draft
    draft_path = get_runtime_dir(chapter) / "draft.md"
    if draft_path.exists():
        draft_text = draft_path.read_text(encoding="utf-8")
        words = count_cn_words(draft_text)
        proj.current_chars += words

    # Update current_state recent events
    if delta.chapter_summary:
        current_state.recent_events.append({
            "chapter": chapter,
            "event": delta.chapter_summary.get("summary", "")[:200],
            "impact": "normal",
        })
        # Keep only last 10 events
        if len(current_state.recent_events) > 10:
            current_state.recent_events = current_state.recent_events[-10:]

    # Save all state files
    save_json(STORY_DIR / "state" / "character_matrix.json", char_matrix.model_dump())
    save_json(STORY_DIR / "state" / "power_ledger.json", power_ledger.model_dump())
    save_json(STORY_DIR / "state" / "pending_hooks.json", hooks.model_dump())
    save_json(STORY_DIR / "state" / "chapter_summaries.json", summaries.model_dump())
    save_json(STORY_DIR / "state" / "subplot_board.json", subplots.model_dump())
    save_json(STORY_DIR / "state" / "emotional_arcs.json", emotional_arcs.model_dump())
    save_json(STORY_DIR / "state" / "current_state.json", current_state.model_dump())
    save_project(proj)

    print(f"  State updated for chapter {chapter}")
    print(f"  Characters: {len(char_matrix.characters)}")
    print(f"  Resources: {len(power_ledger.resources)}")
    print(f"  Items: {len(power_ledger.items)}")
    print(f"  Hooks: {len(hooks.hooks)}")
    print(f"  Subplots: {len(subplots.subplots)}")
    return True


def step_snapshot_and_commit(chapter: int) -> bool:
    """Phase 5: Create snapshot and git commit."""
    banner(f"Step 8: Snapshot & Commit — Chapter {chapter}")
    rt_dir = get_runtime_dir(chapter)

    # Create snapshot
    result = subprocess.run(
        [sys.executable, "snapshot_state.py", "create", "--chapter", str(chapter)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  [WARN] Snapshot creation failed: {result.stderr}")
    else:
        print(result.stdout)

    # Copy draft to chapters/vNNN/
    proj = load_project()
    chapters_v_dir = get_chapters_v_dir(proj.current_volume)
    draft_path = rt_dir / "draft.md"
    if draft_path.exists():
        chapters_v_dir.mkdir(parents=True, exist_ok=True)
        chapter_file = chapters_v_dir / f"ch_{chapter:04d}.md"
        chapter_file.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  Draft copied to {chapter_file}")

    # Pre-save commit index entry (with placeholder hash) before git commit.
    # This ensures the index is included in the same commit as the state.
    # If the process crashes after git commit but before the hash update,
    # the entry can be recovered by scanning git log.
    index_path = STORY_DIR / "memory" / "snapshots" / "commit_index.json"
    index_data = load_json(index_path)
    from story_schema import SnapshotEntry, SnapshotIndex
    index = SnapshotIndex(**index_data)
    entry = SnapshotEntry(
        chapter=chapter,
        commit_hash="(pending)",
        timestamp=datetime.now().isoformat(),
        description=f"Chapter {chapter} accepted",
    )
    index.entries.append(entry)
    save_json(index_path, index.model_dump())

    # Git commit (includes the pre-saved index)
    commit_msg = f"chapter {chapter}: accepted"
    commit_hash = git_commit(commit_msg)
    if commit_hash:
        print(f"  Committed: {commit_hash}")
        # Update the entry with the actual commit hash
        entry.commit_hash = commit_hash
        save_json(index_path, index.model_dump())
        return True
    else:
        # Commit failed — remove the pending entry
        index.entries.pop()
        save_json(index_path, index.model_dump())
        return False


def step_index_chapter(chapter: int) -> bool:
    """Phase 7: Index chapter into FTS5 database for retrieval."""
    banner(f"Step 8b: Index Chapter — Chapter {chapter}")
    try:
        result = subprocess.run(
            [sys.executable, "memory_retrieval.py", "index", "--chapter", str(chapter)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"  [WARN] Chapter indexing had issues: {result.stderr}")
            return True  # Non-blocking
    except Exception as e:
        print(f"  [WARN] Chapter indexing failed: {e}")
        return True  # Non-blocking


def step_update_projections(chapter: int) -> bool:
    """Phase 6: Update human-readable projection documents."""
    banner(f"Step 9: Update Projections — Chapter {chapter}")
    try:
        result = subprocess.run(
            [sys.executable, "update_projections.py", "--chapter", str(chapter), "--full"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"  [WARN] Projection update had issues: {result.stderr}")
            return True  # Non-blocking
    except Exception as e:
        print(f"  [WARN] Projection update failed: {e}")
        return True  # Non-blocking


def step_periodic_summary(chapter: int) -> bool:
    """Phase 6: Every 5 chapters, verify state consistency."""
    if chapter % 5 != 0:
        return True  # Skip if not a 5-chapter boundary

    banner(f"Step 10: Periodic Summary Check — Chapter {chapter}")
    # Run full state validation
    result = subprocess.run(
        [sys.executable, "validate_state.py", "--full"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"  [WARN] Periodic validation found issues")
        # Non-blocking for now, but logged
    else:
        print(f"  [PASS] State validation at chapter {chapter}")
    return True


def step_volume_end(volume: int, chapter: int) -> bool:
    """Phase 6: At volume end, generate summary and run compaction."""
    # Check if this chapter is the last in the volume
    proj = load_project()
    import yaml
    vol_path = STORY_DIR / "plans" / f"volume_{volume:03d}.yaml"
    if vol_path.exists():
        with open(vol_path, "r", encoding="utf-8") as f:
            vol_data = yaml.safe_load(f) or {}
        cr = vol_data.get("chapter_range", "")
        if cr and "-" in cr:
            parts = cr.split("-")
            vol_end = int(parts[1])
            if chapter != vol_end:
                return True  # Not volume end
        else:
            return True  # Can't determine volume end
    else:
        return True  # No volume plan

    banner(f"Volume {volume} End Processing — Chapter {chapter}")

    # 1. Generate volume summary
    print("  Generating volume summary...")
    result = subprocess.run(
        [sys.executable, "gen_volume_summary.py", "--volume", str(volume)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  Volume summary generated")
    else:
        print(f"  [WARN] Volume summary failed: {result.stderr}")

    # 2. Run compaction
    print("  Running memory compaction...")
    result = subprocess.run(
        [sys.executable, "run_compaction.py", "--volume", str(volume)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"  [WARN] Compaction failed: {result.stderr}")

    # 3. Update projections one more time
    subprocess.run(
        [sys.executable, "update_projections.py", "--full"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )

    return True


# ---------------------------------------------------------------------------
# Chapter transaction
# ---------------------------------------------------------------------------

def is_chapter_accepted(chapter: int) -> bool:
    """Check if a chapter has already been accepted (has a snapshot)."""
    index_path = STORY_DIR / "memory" / "snapshots" / "commit_index.json"
    if not index_path.exists():
        return False
    index_data = load_json(index_path)
    from story_schema import SnapshotIndex
    index = SnapshotIndex(**index_data)
    return any(e.chapter == chapter for e in index.entries)


def run_chapter_transaction(chapter: int) -> bool:
    """Run the complete transaction for one chapter."""
    banner(f"CHAPTER {chapter} TRANSACTION", char="#")
    start_time = time.time()

    steps = [
        ("Ensure Volume Plan", step_ensure_volume_plan),
        ("Chapter Plan", step_gen_chapter_plan),
        ("Context Assembly", step_assemble_context),
        ("Draft", step_draft_chapter),
        ("Delta Extraction", step_extract_delta),
        ("Webnovel Audit", step_webnovel_audit),
        ("Delta Validation", step_validate_delta),
        ("Apply Delta", step_apply_delta),
        ("Snapshot & Commit", step_snapshot_and_commit),
        ("Index Chapter", step_index_chapter),
        ("Update Projections", step_update_projections),
        ("Periodic Summary", step_periodic_summary),
    ]

    for step_name, step_fn in steps:
        try:
            success = step_fn(chapter)
        except Exception as e:
            print(f"\n  [FATAL] {step_name} raised exception: {e}")
            import traceback
            traceback.print_exc()
            success = False

        if not success:
            elapsed = time.time() - start_time
            print(f"\n  Transaction FAILED at step: {step_name}")
            print(f"  Elapsed: {elapsed:.1f}s")
            return False

    elapsed = time.time() - start_time
    banner(f"CHAPTER {chapter} ACCEPTED", char="#")
    print(f"  Total time: {elapsed:.1f}s")
    return True


def run_multi_chapter(start: int, end: int, resume: bool = False,
                      continue_on_failure: bool = False) -> list[int]:
    """Run transactions for a range of chapters. Returns list of failed chapters."""
    failed = []
    skipped = []
    for ch in range(start, end + 1):
        # Resume: skip chapters that already have snapshots
        if resume and is_chapter_accepted(ch):
            print(f"\n[RESUME] Chapter {ch} already accepted. Skipping.")
            skipped.append(ch)
            continue

        success = run_chapter_transaction(ch)
        if not success:
            failed.append(ch)
            if continue_on_failure:
                print(f"\n[CONTINUE] Chapter {ch} failed. Continuing to next chapter.")
                continue
            else:
                print(f"\n[STOP] Chapter {ch} failed. Stopping.")
                break

        # Check for volume end and run post-processing
        proj = load_project()
        step_volume_end(proj.current_volume, ch)

    if skipped:
        print(f"\nResumed (skipped): {len(skipped)} chapter(s): {skipped}")
    return failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Webnovel long-form pipeline orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python run_webnovel_pipeline.py --chapter 1
  uv run python run_webnovel_pipeline.py --volume 1 --chapters 1-20
  uv run python run_webnovel_pipeline.py --volume-range 1-3
        """,
    )
    parser.add_argument("--chapter", type=int, help="Run transaction for a single chapter")
    parser.add_argument("--volume", type=int, help="Volume number (for multi-chapter runs)")
    parser.add_argument("--chapters", type=str, help="Chapter range, e.g. '1-20'")
    parser.add_argument("--volume-range", type=str, help="Volume range, e.g. '1-3' (runs all chapters in each volume)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without executing")
    parser.add_argument("--audit-warn", action="store_true", help="Treat audit blocking issues as warnings instead of failures")
    parser.add_argument("--resume", action="store_true", help="Skip chapters that already have accepted snapshots")
    parser.add_argument("--continue-on-failure", action="store_true", help="Continue to next chapter on failure instead of stopping")
    args = parser.parse_args()

    global AUDIT_WARN_MODE
    AUDIT_WARN_MODE = args.audit_warn

    if args.chapter:
        if args.dry_run:
            print(f"Would run chapter {args.chapter} transaction")
            return
        if args.resume and is_chapter_accepted(args.chapter):
            print(f"[RESUME] Chapter {args.chapter} already accepted. Skipping.")
            sys.exit(0)
        success = run_chapter_transaction(args.chapter)
        # Run volume end check
        if success:
            proj = load_project()
            step_volume_end(proj.current_volume, args.chapter)
        sys.exit(0 if success else 1)
    elif args.volume and args.chapters:
        parts = args.chapters.split("-")
        start = int(parts[0])
        end = int(parts[1]) if len(parts) > 1 else start
        if args.dry_run:
            print(f"Would run volume {args.volume}, chapters {start}-{end}")
            return
        print(f"Running volume {args.volume}, chapters {start}-{end}")
        failed = run_multi_chapter(start, end, resume=args.resume,
                                   continue_on_failure=args.continue_on_failure)
        if failed:
            print(f"\nFailed chapters: {failed}")
            sys.exit(1)
        else:
            print(f"\nAll chapters {start}-{end} completed successfully!")
    elif args.volume_range:
        parts = args.volume_range.split("-")
        vol_start = int(parts[0])
        vol_end = int(parts[1]) if len(parts) > 1 else vol_start
        if args.dry_run:
            print(f"Would run volumes {vol_start}-{vol_end}")
            return
        print(f"Running volumes {vol_start}-{vol_end}")
        all_failed = []
        for vol in range(vol_start, vol_end + 1):
            import yaml
            vol_path = STORY_DIR / "plans" / f"volume_{vol:03d}.yaml"
            if vol_path.exists():
                with open(vol_path, "r", encoding="utf-8") as f:
                    vol_data = yaml.safe_load(f) or {}
                cr = vol_data.get("chapter_range", "")
                if cr and "-" in cr:
                    ch_parts = cr.split("-")
                    ch_start, ch_end = int(ch_parts[0]), int(ch_parts[1])
                else:
                    ch_start = (vol - 1) * 20 + 1
                    ch_end = ch_start + 19
            else:
                ch_start = (vol - 1) * 20 + 1
                ch_end = ch_start + 19

            print(f"\n{'='*60}")
            print(f"  Volume {vol}: chapters {ch_start}-{ch_end}")
            print(f"{'='*60}\n")

            failed = run_multi_chapter(ch_start, ch_end, resume=args.resume,
                                       continue_on_failure=args.continue_on_failure)
            if failed:
                all_failed.extend(failed)
                if args.continue_on_failure:
                    print(f"\n[CONTINUE] Volume {vol} had failures: {failed}")
                else:
                    print(f"\n[STOP] Volume {vol} failed at chapter(s): {failed}")
                    break

        if all_failed:
            print(f"\nAll failed chapters: {all_failed}")
            sys.exit(1)
        else:
            print(f"\nAll volumes {vol_start}-{vol_end} completed successfully!")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
