#!/usr/bin/env python3
"""
extract_delta.py — Extract chapter delta (state changes) from a draft.

Usage:
  uv run python extract_delta.py --chapter 1 --draft story/runtime/ch_0001/draft.md --out story/runtime/ch_0001/delta.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from story_schema import (
    ChapterDelta,
    ChapterSummaries,
    CharacterMatrix,
    PendingHooks,
    PowerLedgerFull,
    SubplotBoard,
    load_json,
    save_json,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)


def get_existing_ids() -> dict:
    """Load existing entity IDs for the prompt."""
    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    power_ledger = PowerLedgerFull(**load_json(STORY_DIR / "state" / "power_ledger.json"))
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))

    return {
        "character_ids": list(char_matrix.characters.keys()),
        "character_names": {c.name: cid for cid, c in char_matrix.characters.items()},
        "resource_ids": list(power_ledger.resources.keys()),
        "item_ids": list(power_ledger.items.keys()),
        "hook_ids": list(hooks.hooks.keys()),
        "active_hook_ids": [k for k, v in hooks.hooks.items() if v.status == "active"],
        "subplot_ids": list(subplots.subplots.keys()),
        "power_levels": {cid: max((l.level_rank for l in power_ledger.levels if l.character_id == cid), default=0)
                        for cid in char_matrix.characters},
    }


def extract_delta(chapter: int, draft_path: Path, out_path: Path) -> ChapterDelta:
    """Extract delta from chapter draft using LLM."""
    draft_text = draft_path.read_text(encoding="utf-8")
    existing = get_existing_ids()

    # Load recent context for the LLM
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    recent_summaries = ""
    if summaries.summaries:
        items = sorted(summaries.summaries.items(), key=lambda x: x[0])
        recent = items[-3:] if len(items) > 3 else items
        for key, s in recent:
            recent_summaries += f"- Ch {s.chapter}: {s.summary[:150]}\n"

    prompt = f"""你是一位小说状态分析师。请从以下章节正文中提取所有状态变化（delta）。

=== 第 {chapter} 章正文 ===
{draft_text[:12000]}

=== 当前已知实体 ===
角色ID: {existing['character_ids']}
角色名映射: {json.dumps(existing['character_names'], ensure_ascii=False)}
物品ID: {existing['item_ids']}
资源ID: {existing['resource_ids']}
伏笔ID: {existing['active_hook_ids']}
支线ID: {existing['subplot_ids']}

=== 已有角色战力等级 ===
{json.dumps(existing['power_levels'], ensure_ascii=False)}

=== 最近章节摘要 ===
{recent_summaries or '(第一章)'}

=== 输出要求 ===
请以 JSON 格式输出 delta，严格遵循以下结构：

{{
  "chapter": {chapter},
  "new_facts": [
    {{"fact": "事实描述", "category": "world|plot|character", "importance": "low|medium|high"}}
  ],
  "character_updates": [
    {{"id": "已有角色ID或新角色名", "new_character": false, "field": "更新的字段", "value": "新值"}}
  ],
  "relationship_updates": [
    {{"from": "角色ID", "to": "角色ID", "relationship": "关系描述", "type": "family|friend|enemy|romantic|professional"}}
  ],
  "power_updates": [
    {{"character_id": "角色ID", "level_name": "等级名", "new_rank": 1, "special_abilities": ["能力"]}}
  ],
  "resource_updates": [
    {{"action": "create|update|consume", "id": "资源ID(更新时)", "name": "资源名", "category": "currency|material|food|tool", "quantity": 数量, "unit": "单位", "owner": "角色ID"}}
  ],
  "item_updates": [
    {{"action": "create|transfer|destroy|upgrade", "id": "物品ID(操作时)", "name": "物品名", "description": "描述", "item_type": "weapon|armor|accessory|artifact|consumable|misc", "rarity": "common|uncommon|rare|epic|legendary", "owner": "角色ID", "new_owner": "角色ID(transfer时)"}}
  ],
  "hook_updates": [
    {{"action": "create|advance|resolve", "id": "伏笔ID(操作时)", "description": "伏笔描述", "hook_type": "setup|advance|payoff", "related_characters": ["角色ID"]}}
  ],
  "subplot_updates": [
    {{"action": "create|update", "id": "支线ID(更新时)", "name": "支线名", "description": "描述", "status": "active|resolved|paused", "related_characters": ["角色ID"]}}
  ],
  "emotional_arc_updates": [
    {{"action": "create|update", "id": "情感弧ID(更新时)", "character_id": "角色ID", "emotion": "情感", "intensity": 0.5, "trigger": "触发原因"}}
  ],
  "chapter_summary": {{
    "title": "章节标题",
    "summary": "200字以内的章节摘要",
    "key_events": ["关键事件1", "关键事件2"],
    "characters_present": ["角色ID列表"],
    "locations": ["地点列表"],
    "word_count": 字数,
    "emotional_tone": "情感基调"
  }}
}}

注意事项：
1. 只提取本章实际发生的变化，不要推测。
2. 新角色用 name 字段标识，设 new_character=true。
3. 对已有实体的更新必须使用正确的 ID。
4. 伏笔回收必须引用已存在的伏笔 ID。
5. 战力提升不能跳级（当前等级+1）。
6. 只输出 JSON，不要其他文字。"""

    print(f"Extracting delta from chapter {chapter}...", file=sys.stderr)
    result = call_text_model(
        model=WRITER_MODEL,
        max_tokens=8000,
        temperature=0.3,
        system="你是一位小说状态分析专家。只输出 JSON 格式，不要其他文字。",
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

    # Parse JSON
    json_text = result.strip()
    if json_text.startswith("```"):
        lines = json_text.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        json_text = "\n".join(lines[start:end])

    try:
        delta_data = json.loads(json_text)
        delta = ChapterDelta(**delta_data)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  [ERROR] Failed to parse delta JSON: {e}", file=sys.stderr)
        print(f"  Raw output:\n{result[:500]}", file=sys.stderr)
        # Create minimal delta with error info
        delta = ChapterDelta(
            chapter=chapter,
            chapter_summary={
                "title": "解析失败",
                "summary": f"Delta 提取失败: {e}",
                "key_events": [],
                "characters_present": [],
                "locations": [],
                "word_count": 0,
                "emotional_tone": "error",
            },
        )

    # Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(out_path, delta.model_dump())

    print(f"  Delta saved to: {out_path}", file=sys.stderr)
    print(f"  New facts: {len(delta.new_facts)}", file=sys.stderr)
    print(f"  Character updates: {len(delta.character_updates)}", file=sys.stderr)
    print(f"  Hook updates: {len(delta.hook_updates)}", file=sys.stderr)
    print(f"  Resource updates: {len(delta.resource_updates)}", file=sys.stderr)

    return delta


def main():
    parser = argparse.ArgumentParser(description="Extract chapter delta from draft")
    parser.add_argument("--chapter", type=int, required=True, help="Chapter number")
    parser.add_argument("--draft", type=str, required=True, help="Path to draft.md")
    parser.add_argument("--out", type=str, required=True, help="Output delta.json path")
    args = parser.parse_args()

    draft_path = Path(args.draft)
    out_path = Path(args.out)

    if not draft_path.exists():
        print(f"Error: Draft not found: {draft_path}", file=sys.stderr)
        sys.exit(1)

    extract_delta(args.chapter, draft_path, out_path)


if __name__ == "__main__":
    main()
