#!/usr/bin/env python3
"""
memory_orchestrator.py — Assemble context.json for chapter writing.

Reads chapter plan, volume plan, state, recent summaries, and voice rules,
then outputs a token-budgeted context.json for the writer model.

Usage:
  uv run python memory_orchestrator.py --chapter 1 --out story/runtime/ch_0001/context.json
"""

import argparse
import sys
from pathlib import Path

from story_schema import (
    ChapterContext,
    ChapterSummaries,
    CharacterMatrix,
    ContextBudget,
    CurrentState,
    PendingHooks,
    PowerLedgerFull,
    ProjectConfig,
    SubplotBoard,
    count_cn_words,
    load_json,
    save_json,
    load_yaml,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"


def load_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def truncate_to_budget(text: str, max_chars: int) -> str:
    """Truncate text to approximately max_chars, trying to end at a sentence boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Try to find last sentence boundary
    for sep in ["\n\n", "\n", "。", ".", "！", "!", "？", "?"]:
        idx = truncated.rfind(sep)
        if idx > max_chars * 0.7:  # Don't cut too much
            return truncated[:idx + len(sep)]
    return truncated


def assemble_context(chapter: int, out_path: Path) -> ChapterContext:
    """Assemble context for a chapter."""
    proj = ProjectConfig(**load_json(STORY_DIR / "project.json"))
    budget = ContextBudget()

    # 1. Chapter plan
    plan_path = STORY_DIR / "plans" / f"chapter_{chapter:04d}.yaml"
    chapter_plan = load_file(plan_path)
    chapter_plan = truncate_to_budget(chapter_plan, budget.chapter_plan)

    # 2. Volume contract
    volume = proj.current_volume
    vol_path = STORY_DIR / "plans" / f"volume_{volume:03d}.yaml"
    volume_contract = load_file(vol_path)
    volume_contract = truncate_to_budget(volume_contract, budget.volume_contract)

    # 3. State slice (characters, hooks, subplots, current state)
    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))
    current_state = CurrentState(**load_json(STORY_DIR / "state" / "current_state.json"))
    power_ledger = PowerLedgerFull(**load_json(STORY_DIR / "state" / "power_ledger.json"))

    state_slice = {}
    if char_matrix.characters:
        state_slice["characters"] = {
            cid: {
                "name": c.name,
                "role": c.role,
                "personality": c.personality[:200],
                "speech_pattern": c.speech_pattern[:100],
                "relationships": c.relationships,
            }
            for cid, c in char_matrix.characters.items()
        }
    active_hooks = {k: v.model_dump() for k, v in hooks.hooks.items() if v.status == "active"}
    if active_hooks:
        state_slice["active_hooks"] = active_hooks
    active_subplots = {k: v.model_dump() for k, v in subplots.subplots.items() if v.status == "active"}
    if active_subplots:
        state_slice["active_subplots"] = active_subplots
    if current_state.timeline_position:
        state_slice["current_state"] = current_state.model_dump()
    if power_ledger.resources:
        state_slice["resources"] = {
            rid: r.model_dump() for rid, r in power_ledger.resources.items()
        }
    if power_ledger.items:
        state_slice["items"] = {
            iid: i.model_dump() for iid, i in power_ledger.items.items()
        }

    # 4. Recent summaries (last 3-5 chapters)
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    recent_summaries = []
    if summaries.summaries:
        items = sorted(summaries.summaries.items(), key=lambda x: x[0])
        recent = items[-5:] if len(items) > 5 else items
        for key, s in recent:
            recent_summaries.append({
                "chapter": s.chapter,
                "summary": s.summary,
                "key_events": s.key_events,
                "characters_present": s.characters_present,
            })

    # 5. Previous chapter tail
    prev_chapter_path = BASE_DIR / "chapters" / "v001" / f"ch_{chapter - 1:04d}.md"
    prev_tail = ""
    if prev_chapter_path.exists():
        prev_text = prev_chapter_path.read_text(encoding="utf-8")
        prev_tail = prev_text[-budget.previous_chapter_tail:]
    elif chapter == 1:
        prev_tail = "(第一章——无前文)"

    # 6. Voice rules (anti-slop + voice identity)
    voice = load_file(BASE_DIR / "voice.md")
    voice_rules = truncate_to_budget(voice, budget.voice_rules)

    # 7. Intent
    intent_path = STORY_DIR / "runtime" / f"ch_{chapter:04d}" / "intent.md"
    intent = load_file(intent_path)

    # Build context
    context = ChapterContext(
        chapter=chapter,
        budget=budget,
        chapter_plan=chapter_plan,
        volume_contract=volume_contract,
        state_slice=state_slice,
        recent_summaries=recent_summaries,
        retrieved_fragments=[],  # TODO: Phase 7 RAG
        voice_rules=voice_rules,
        previous_chapter_tail=prev_tail,
        metadata={
            "project_title": proj.title,
            "project_genre": proj.genre,
            "target_chars": proj.default_chapter_chars,
            "intent": intent,
        },
    )

    # Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(out_path, context.model_dump())

    # Print budget summary
    total_chars = sum([
        len(chapter_plan),
        len(volume_contract),
        len(str(state_slice)),
        len(str(recent_summaries)),
        len(voice_rules),
        len(prev_tail),
    ])
    print(f"Context assembled for chapter {chapter}")
    print(f"  Total chars: ~{total_chars:,} / {budget.total_budget:,} budget")
    print(f"  Characters in state: {len(char_matrix.characters)}")
    print(f"  Active hooks: {len([h for h in hooks.hooks.values() if h.status == 'active'])}")
    print(f"  Recent summaries: {len(recent_summaries)}")
    print(f"  Output: {out_path}")

    return context


def main():
    parser = argparse.ArgumentParser(description="Assemble context for chapter writing")
    parser.add_argument("--chapter", type=int, required=True, help="Chapter number")
    parser.add_argument("--out", type=str, required=True, help="Output context.json path")
    args = parser.parse_args()

    out_path = Path(args.out)
    assemble_context(args.chapter, out_path)


if __name__ == "__main__":
    main()
