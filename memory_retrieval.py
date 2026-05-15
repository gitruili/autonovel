#!/usr/bin/env python3
"""
memory_retrieval.py — SQLite FTS5-based retrieval for chapter context.

Indexes chapter summaries and draft text fragments with entity tags,
then provides temporal-filtered, deduplicated search results.

Usage:
  uv run python memory_retrieval.py index --chapter 1
  uv run python memory_retrieval.py search --query "角色名" --chapter 5 --limit 10
  uv run python memory_retrieval.py rebuild
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from story_schema import (
    ChapterSummaries,
    CharacterMatrix,
    PendingHooks,
    SubplotBoard,
    load_json,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
DB_PATH = STORY_DIR / "memory" / "memory.sqlite"


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def get_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a connection to the memory SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chapter_summaries (
            chapter INTEGER PRIMARY KEY,
            summary TEXT NOT NULL,
            key_events TEXT,
            characters TEXT,
            indexed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS fragments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter INTEGER NOT NULL,
            fragment_type TEXT NOT NULL,
            text TEXT NOT NULL,
            entities TEXT,
            source_file TEXT,
            indexed_at TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS summaries_fts USING fts5(
            chapter,
            summary,
            key_events,
            characters,
            content='chapter_summaries',
            content_rowid='chapter'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS fragments_fts USING fts5(
            chapter,
            text,
            entities,
            content='fragments',
            content_rowid='id'
        );

        CREATE TABLE IF NOT EXISTS index_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Entity extraction (simple pattern-based)
# ---------------------------------------------------------------------------

def extract_entities(text: str, known_entities: dict[str, str] | None = None) -> list[str]:
    """Extract entity names from text using known entity list and patterns."""
    entities = set()

    # Match against known entity names
    if known_entities:
        for name in known_entities:
            if name in text:
                entities.add(name)

    # Match quoted names (common in Chinese fiction)
    for match in re.finditer(r'[「"\'](.*?)[」"\']', text):
        name = match.group(1).strip()
        if 1 < len(name) <= 10:
            entities.add(name)

    return sorted(entities)


def build_known_entities() -> dict[str, str]:
    """Build a dict of known entity names -> types from state files."""
    entities = {}

    # Characters
    char_path = STORY_DIR / "state" / "character_matrix.json"
    if char_path.exists():
        chars = CharacterMatrix(**load_json(char_path))
        for cid, c in chars.characters.items():
            entities[c.name] = "character"

    # Hooks
    hooks_path = STORY_DIR / "state" / "pending_hooks.json"
    if hooks_path.exists():
        hooks = PendingHooks(**load_json(hooks_path))
        for hid, h in hooks.hooks.items():
            if h.description:
                # Extract key phrases from hook descriptions
                for word in h.description.split():
                    if len(word) >= 2:
                        entities[word] = "hook"

    # Subplots
    subplots_path = STORY_DIR / "state" / "subplot_board.json"
    if subplots_path.exists():
        subplots = SubplotBoard(**load_json(subplots_path))
        for sid, sp in subplots.subplots.items():
            if sp.name:
                entities[sp.name] = "subplot"

    return entities


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def index_chapter(chapter: int, db_path: Path = DB_PATH):
    """Index a chapter's summary and draft fragments."""
    from datetime import datetime

    conn = get_db(db_path)
    known_entities = build_known_entities()
    now = datetime.now().isoformat()

    # Index chapter summary
    summaries_path = STORY_DIR / "state" / "chapter_summaries.json"
    if summaries_path.exists():
        summaries = ChapterSummaries(**load_json(summaries_path))
        key = f"ch_{chapter}"
        if key in summaries.summaries:
            s = summaries.summaries[key]
            key_events_str = "; ".join(s.key_events) if s.key_events else ""
            chars_str = "; ".join(s.characters_present) if s.characters_present else ""
            entities = extract_entities(s.summary + " " + key_events_str, known_entities)

            conn.execute(
                "INSERT OR REPLACE INTO chapter_summaries (chapter, summary, key_events, characters, indexed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (chapter, s.summary, key_events_str, chars_str, now),
            )
            # Update FTS index
            conn.execute("DELETE FROM summaries_fts WHERE chapter = ?", (str(chapter),))
            conn.execute(
                "INSERT INTO summaries_fts (chapter, summary, key_events, characters) VALUES (?, ?, ?, ?)",
                (str(chapter), s.summary, key_events_str, chars_str),
            )
            print(f"  Indexed summary for chapter {chapter}")

    # Index draft fragments (paragraphs)
    draft_path = STORY_DIR / "runtime" / f"ch_{chapter:04d}" / "draft.md"
    if not draft_path.exists():
        # Try chapters/vNNN/ directory
        proj_path = STORY_DIR / "project.json"
        volume = 1
        if proj_path.exists():
            proj_data = load_json(proj_path)
            volume = proj_data.get("current_volume", 1)
        chapters_dir = BASE_DIR / "chapters" / f"v{volume:03d}"
        draft_path = chapters_dir / f"ch_{chapter:04d}.md"

    if draft_path.exists():
        draft_text = draft_path.read_text(encoding="utf-8")
        paragraphs = _split_into_fragments(draft_text)

        # Delete old fragments for this chapter
        conn.execute("DELETE FROM fragments WHERE chapter = ?", (chapter,))
        conn.execute("DELETE FROM fragments_fts WHERE chapter = ?", (str(chapter),))

        for para_type, para_text in paragraphs:
            if len(para_text.strip()) < 20:
                continue
            entities = extract_entities(para_text, known_entities)
            entities_str = " ".join(entities)

            cursor = conn.execute(
                "INSERT INTO fragments (chapter, fragment_type, text, entities, source_file, indexed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (chapter, para_type, para_text.strip(), entities_str, str(draft_path.name), now),
            )
            frag_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO fragments_fts (rowid, chapter, text, entities) VALUES (?, ?, ?, ?)",
                (frag_id, str(chapter), para_text.strip(), entities_str),
            )

        print(f"  Indexed {len(paragraphs)} fragments for chapter {chapter}")

    conn.commit()
    conn.close()


def _split_into_fragments(text: str) -> list[tuple[str, str]]:
    """Split chapter text into typed fragments (scene, dialogue, narration)."""
    fragments = []
    current_type = "narration"

    for paragraph in text.split("\n\n"):
        para = paragraph.strip()
        if not para:
            continue

        # Detect type
        if para.startswith("---") or para.startswith("***"):
            current_type = "scene_break"
            continue
        elif '"' in para or '"' in para or "「" in para:
            current_type = "dialogue"
        else:
            current_type = "narration"

        fragments.append((current_type, para))

    return fragments


def rebuild_index(db_path: Path = DB_PATH):
    """Rebuild the entire FTS index from state files and existing drafts."""
    print("Rebuilding memory index...")

    # Remove old database
    if db_path.exists():
        db_path.unlink()

    conn = get_db(db_path)

    # Index all existing chapter summaries
    summaries_path = STORY_DIR / "state" / "chapter_summaries.json"
    if summaries_path.exists():
        summaries = ChapterSummaries(**load_json(summaries_path))
        for key in summaries.summaries:
            chapter = summaries.summaries[key].chapter
            conn.close()
            index_chapter(chapter, db_path)
            conn = get_db(db_path)

    conn.close()
    print("Index rebuild complete.")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_fragments(
    query: str,
    current_chapter: int,
    limit: int = 10,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Search for relevant fragments, filtered by temporal constraint.

    Only returns results from chapters <= current_chapter.
    Returns list of dicts with: chapter, text, type, entities, relevance.
    """
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    results = []

    # Search summaries
    try:
        rows = conn.execute(
            "SELECT chapter, summary, key_events, characters, "
            "rank AS relevance "
            "FROM summaries_fts "
            "WHERE summaries_fts MATCH ? AND CAST(chapter AS INTEGER) <= ? "
            "ORDER BY rank "
            "LIMIT ?",
            (query, current_chapter, limit),
        ).fetchall()
        for row in rows:
            results.append({
                "chapter": int(row["chapter"]),
                "type": "summary",
                "text": row["summary"],
                "key_events": row["key_events"] or "",
                "entities": row["characters"] or "",
                "relevance": row["relevance"],
            })
    except sqlite3.OperationalError:
        pass  # FTS table might not exist yet

    # Search fragments
    try:
        rows = conn.execute(
            "SELECT f.chapter, f.text, f.fragment_type, f.entities, "
            "ff.rank AS relevance "
            "FROM fragments_fts ff "
            "JOIN fragments f ON f.id = ff.rowid "
            "WHERE fragments_fts MATCH ? AND CAST(ff.chapter AS INTEGER) <= ? "
            "ORDER BY ff.rank "
            "LIMIT ?",
            (query, current_chapter, limit),
        ).fetchall()
        for row in rows:
            results.append({
                "chapter": int(row["chapter"]),
                "type": row["fragment_type"],
                "text": row["text"],
                "entities": row["entities"] or "",
                "relevance": row["relevance"],
            })
    except sqlite3.OperationalError:
        pass  # FTS table might not exist yet

    conn.close()

    # Deduplicate by text similarity (exact match)
    seen = set()
    deduped = []
    for r in results:
        text_hash = hash(r["text"][:200])
        if text_hash not in seen:
            seen.add(text_hash)
            deduped.append(r)

    # Sort by relevance and limit
    deduped.sort(key=lambda x: x["relevance"])
    return deduped[:limit]


def retrieve_for_chapter(
    chapter: int,
    query: str | None = None,
    limit: int = 5,
    max_chars: int = 2000,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Retrieve relevant fragments for a chapter's context.

    If no query is provided, uses the chapter plan or recent summaries as query.
    Returns fragments truncated to max_chars total.
    """
    if not db_path.exists():
        return []

    # Build query from chapter plan if not provided
    if not query:
        plan_path = STORY_DIR / "plans" / f"chapter_{chapter:04d}.yaml"
        if plan_path.exists():
            query = plan_path.read_text(encoding="utf-8")[:500]
        else:
            # Use recent summaries as query
            summaries_path = STORY_DIR / "state" / "chapter_summaries.json"
            if summaries_path.exists():
                summaries = ChapterSummaries(**load_json(summaries_path))
                recent = sorted(summaries.summaries.values(), key=lambda s: s.chapter)[-3:]
                query = " ".join(s.summary for s in recent)
            else:
                return []

    results = search_fragments(query, chapter, limit=limit * 2, db_path=db_path)

    # Truncate to max_chars
    total_chars = 0
    truncated = []
    for r in results:
        text = r["text"]
        if total_chars + len(text) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 100:
                text = text[:remaining] + "..."
                r = {**r, "text": text}
                truncated.append(r)
            break
        truncated.append(r)
        total_chars += len(text)

    return truncated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Memory retrieval via SQLite FTS5")
    sub = parser.add_subparsers(dest="command")

    index_p = sub.add_parser("index", help="Index a chapter")
    index_p.add_argument("--chapter", type=int, required=True)

    search_p = sub.add_parser("search", help="Search fragments")
    search_p.add_argument("--query", type=str, required=True)
    search_p.add_argument("--chapter", type=int, required=True, help="Current chapter (temporal filter)")
    search_p.add_argument("--limit", type=int, default=10)

    sub.add_parser("rebuild", help="Rebuild entire index")

    args = parser.parse_args()

    if args.command == "index":
        index_chapter(args.chapter)
    elif args.command == "search":
        results = search_fragments(args.query, args.chapter, args.limit)
        for r in results:
            print(f"[Ch.{r['chapter']}] ({r['type']}) {r['text'][:100]}...")
            if r['entities']:
                print(f"  Entities: {r['entities']}")
    elif args.command == "rebuild":
        rebuild_index()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
