#!/usr/bin/env python3
"""
snapshot_state.py — Create and restore story state snapshots.

Usage:
  uv run python snapshot_state.py create --chapter 1
  uv run python snapshot_state.py restore --commit <ref>
"""

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from story_schema import (
    SnapshotEntry,
    SnapshotIndex,
    load_json,
    save_json,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
SNAPSHOTS_DIR = STORY_DIR / "memory" / "snapshots"
INDEX_PATH = SNAPSHOTS_DIR / "commit_index.json"


# ---------------------------------------------------------------------------
# Create snapshot
# ---------------------------------------------------------------------------

def create_snapshot(chapter: int) -> str:
    """Create a snapshot of current state. Returns snapshot path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_name = f"ch_{chapter:04d}_{timestamp}.zip"
    snapshot_path = SNAPSHOTS_DIR / snapshot_name

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(snapshot_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Include project.json
        proj_path = STORY_DIR / "project.json"
        if proj_path.exists():
            zf.write(proj_path, "story/project.json")

        # Include all state files
        state_dir = STORY_DIR / "state"
        if state_dir.exists():
            for f in state_dir.glob("*.json"):
                zf.write(f, f"story/state/{f.name}")

        # Include memory.sqlite if exists
        sqlite_path = STORY_DIR / "memory" / "memory.sqlite"
        if sqlite_path.exists():
            zf.write(sqlite_path, "story/memory/memory.sqlite")

        # Include runtime trace for this chapter
        rt_dir = STORY_DIR / "runtime" / f"ch_{chapter:04d}"
        if rt_dir.exists():
            for f in rt_dir.iterdir():
                if f.is_file():
                    zf.write(f, f"story/runtime/ch_{chapter:04d}/{f.name}")

        # Include commit index
        if INDEX_PATH.exists():
            zf.write(INDEX_PATH, "story/memory/snapshots/commit_index.json")

    print(f"  Snapshot created: {snapshot_path}")
    print(f"  Size: {snapshot_path.stat().st_size:,} bytes")
    return str(snapshot_path)


# ---------------------------------------------------------------------------
# Restore snapshot
# ---------------------------------------------------------------------------

def restore_snapshot(commit_ref: str) -> bool:
    """Restore state from a snapshot associated with the given commit."""
    # Load commit index
    if not INDEX_PATH.exists():
        print(f"  [ERROR] Commit index not found: {INDEX_PATH}")
        return False

    index_data = load_json(INDEX_PATH)
    index = SnapshotIndex(**index_data)

    # Find entry matching commit
    entry = None
    for e in index.entries:
        if e.commit_hash.startswith(commit_ref):
            entry = e
            break

    if not entry:
        print(f"  [ERROR] No snapshot found for commit: {commit_ref}")
        return False

    snapshot_path = Path(entry.snapshot_path)
    if not snapshot_path.exists():
        # Try to find by chapter
        chapter = entry.chapter
        candidates = list(SNAPSHOTS_DIR.glob(f"ch_{chapter:04d}_*.zip"))
        if candidates:
            snapshot_path = candidates[-1]  # Latest
        else:
            print(f"  [ERROR] Snapshot file not found: {snapshot_path}")
            return False

    print(f"  Restoring from: {snapshot_path}")
    print(f"  Chapter: {entry.chapter}, Commit: {entry.commit_hash}")

    # Git checkout to that commit
    result = subprocess.run(
        ["git", "checkout", entry.commit_hash, "--", "."],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  [WARN] Git checkout had issues: {result.stderr}")

    # Also restore from zip if git checkout didn't bring everything back
    if snapshot_path.exists():
        with zipfile.ZipFile(snapshot_path, "r") as zf:
            # Extract state files
            for name in zf.namelist():
                if name.startswith("story/"):
                    target = BASE_DIR / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(target, "wb") as dst:
                        dst.write(src.read())
        print(f"  State files restored from snapshot")

    print(f"  Restore complete. Run 'uv run python validate_state.py --full' to verify.")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Create and restore story state snapshots")
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create", help="Create a snapshot")
    create_p.add_argument("--chapter", type=int, required=True, help="Chapter number")

    restore_p = sub.add_parser("restore", help="Restore from a snapshot")
    restore_p.add_argument("--commit", type=str, required=True, help="Commit hash to restore")

    args = parser.parse_args()

    if args.command == "create":
        snapshot_path = create_snapshot(args.chapter)
        # Update commit index (will be done by pipeline after git commit)
    elif args.command == "restore":
        success = restore_snapshot(args.commit)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
