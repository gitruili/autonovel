#!/usr/bin/env python3
"""
run_compaction.py — Compact memory at volume boundaries.

Archives old chapter summaries, compresses resolved hooks/subplots,
and reduces state file size for long-running stories.

Usage:
  uv run python run_compaction.py --volume 1
  uv run python run_compaction.py --volume 1 --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from story_schema import (
    ChapterSummaries,
    CompactionRecord,
    PendingHooks,
    SubplotBoard,
    EmotionalArcs,
    load_json,
    save_json,
    save_yaml,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
load_dotenv(BASE_DIR / ".env")


def get_volume_chapter_range(volume: int) -> tuple[int, int]:
    """Get chapter range for a volume."""
    import yaml
    vol_path = STORY_DIR / "plans" / f"volume_{volume:03d}.yaml"
    if vol_path.exists():
        with open(vol_path, "r", encoding="utf-8") as f:
            vol_data = yaml.safe_load(f) or {}
        cr = vol_data.get("chapter_range", "")
        if cr and "-" in cr:
            parts = cr.split("-")
            return int(parts[0]), int(parts[1])
    start = (volume - 1) * 20 + 1
    return start, start + 19


def compact_summaries(volume: int, chapter_start: int, chapter_end: int,
                      keep_recent: int = 5, dry_run: bool = False) -> tuple[int, int, list[int]]:
    """Compact chapter summaries for a volume.

    Keeps the last `keep_recent` summaries in full detail.
    Older summaries get their key_events and characters_present trimmed.
    Returns (before_count, after_count).
    """
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    before_count = len(summaries.summaries)

    archived = []
    for ch in range(chapter_start, chapter_end + 1):
        key = f"ch_{ch}"
        if key in summaries.summaries:
            s = summaries.summaries[key]
            # Trim older summaries: keep summary text, remove detailed lists
            if s.chapter <= chapter_end - keep_recent:
                s.key_events = s.key_events[:3] if s.key_events else []
                s.characters_present = s.characters_present[:5] if s.characters_present else []
                archived.append(ch)

    after_count = len(summaries.summaries)

    if not dry_run:
        save_json(STORY_DIR / "state" / "chapter_summaries.json", summaries.model_dump())

    return before_count, after_count, archived


def compact_resolved_hooks(volume: int, chapter_end: int, dry_run: bool = False) -> list[str]:
    """Remove fully resolved hooks that are well past their payoff chapter."""
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    compressed = []

    to_remove = []
    for hook_id, hook in hooks.hooks.items():
        if (hook.status == "resolved" and
            hook.valid_until_chapter is not None and
            hook.valid_until_chapter < chapter_end - 5):
            to_remove.append(hook_id)
            compressed.append(hook_id)

    for hook_id in to_remove:
        del hooks.hooks[hook_id]

    if not dry_run and to_remove:
        save_json(STORY_DIR / "state" / "pending_hooks.json", hooks.model_dump())

    return compressed


def compact_resolved_subplots(volume: int, chapter_end: int, dry_run: bool = False) -> list[str]:
    """Trim resolved subplots."""
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))
    compressed = []

    for sid, sp in subplots.subplots.items():
        if sp.status == "resolved":
            # Keep name and status, trim details
            sp.chapters_involved = sp.chapters_involved[:5] if sp.chapters_involved else []
            compressed.append(sid)

    if not dry_run and compressed:
        save_json(STORY_DIR / "state" / "subplot_board.json", subplots.model_dump())

    return compressed


def compact_emotional_arcs(volume: int, chapter_end: int, dry_run: bool = False) -> list[str]:
    """Remove completed emotional arcs."""
    arcs = EmotionalArcs(**load_json(STORY_DIR / "state" / "emotional_arcs.json"))
    compressed = []

    to_remove = []
    for arc_id, arc in arcs.arcs.items():
        if (arc.end_chapter is not None and
            arc.end_chapter < chapter_end - 5):
            to_remove.append(arc_id)
            compressed.append(arc_id)

    for arc_id in to_remove:
        del arcs.arcs[arc_id]

    if not dry_run and to_remove:
        save_json(STORY_DIR / "state" / "emotional_arcs.json", arcs.model_dump())

    return compressed


def run_compaction(volume: int, chapter_start: int | None = None,
                   chapter_end: int | None = None, dry_run: bool = False) -> CompactionRecord:
    """Run full compaction for a volume."""
    if chapter_start is None or chapter_end is None:
        chapter_start, chapter_end = get_volume_chapter_range(volume)

    print(f"Compacting volume {volume} (chapters {chapter_start}-{chapter_end})")
    if dry_run:
        print("  [DRY RUN] No changes will be made")

    # 1. Compact summaries
    before, after, archived = compact_summaries(
        volume, chapter_start, chapter_end, dry_run=dry_run
    )
    print(f"  Summaries: {before} -> {after} (archived {len(archived)} chapter details)")

    # 2. Compact resolved hooks
    compressed_hooks = compact_resolved_hooks(volume, chapter_end, dry_run=dry_run)
    print(f"  Resolved hooks removed: {len(compressed_hooks)}")

    # 3. Compact resolved subplots
    compressed_subplots = compact_resolved_subplots(volume, chapter_end, dry_run=dry_run)
    print(f"  Resolved subplots trimmed: {len(compressed_subplots)}")

    # 4. Compact emotional arcs
    compressed_arcs = compact_emotional_arcs(volume, chapter_end, dry_run=dry_run)
    print(f"  Completed emotional arcs removed: {len(compressed_arcs)}")

    # Build record
    record = CompactionRecord(
        volume=volume,
        timestamp=datetime.now().isoformat(),
        chapters_compacted=chapter_end - chapter_start + 1,
        summaries_before=before,
        summaries_after=after,
        archived_summaries=archived,
        compressed_hooks=compressed_hooks,
        compressed_subplots=compressed_subplots,
        notes=f"Compaction for volume {volume}, chapters {chapter_start}-{chapter_end}",
    )

    # Save compaction record
    if not dry_run:
        record_path = STORY_DIR / "memory" / f"compaction_{volume:03d}.json"
        save_json(record_path, record.model_dump())
        print(f"  Compaction record saved to: {record_path}")

    return record


def main():
    parser = argparse.ArgumentParser(description="Compact memory at volume boundaries")
    parser.add_argument("--volume", type=int, required=True, help="Volume number")
    parser.add_argument("--chapters", type=str, help="Chapter range, e.g. '1-20'")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without modifying files")
    args = parser.parse_args()

    chapter_start = chapter_end = None
    if args.chapters:
        parts = args.chapters.split("-")
        chapter_start = int(parts[0])
        chapter_end = int(parts[1]) if len(parts) > 1 else chapter_start

    record = run_compaction(args.volume, chapter_start, chapter_end, dry_run=args.dry_run)

    print(f"\nCompaction complete for volume {args.volume}")
    print(f"  Chapters compacted: {record.chapters_compacted}")
    print(f"  Summaries: {record.summaries_before} -> {record.summaries_after}")
    print(f"  Archived summary details: {len(record.archived_summaries)}")
    print(f"  Compressed hooks: {len(record.compressed_hooks)}")
    print(f"  Compressed subplots: {len(record.compressed_subplots)}")


if __name__ == "__main__":
    main()
