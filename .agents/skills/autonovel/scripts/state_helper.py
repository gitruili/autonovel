#!/usr/bin/env python3
"""
state_helper.py — 无 LLM 依赖的状态读写辅助工具。
供 Antigravity Skill 调用，快速查看/更新项目状态。

用法:
  uv run python .agents/skills/autonovel/scripts/state_helper.py status
  uv run python .agents/skills/autonovel/scripts/state_helper.py context --chapter 5
"""
import argparse
import io
import json
import sys

# Fix Windows GBK encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent  # .agents/skills/autonovel/scripts/ → project root
STORY_DIR = BASE_DIR / "story"
STATE_DIR = STORY_DIR / "state"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_status():
    """打印当前项目状态摘要。"""
    proj_path = STORY_DIR / "project.json"
    if not proj_path.exists():
        print("❌ 未找到 story/project.json — 请先初始化项目")
        return

    proj = load_json(proj_path)
    print("=" * 60)
    print(f"  📖 {proj.get('title', '(未命名)')}")
    print(f"  📁 类型: {proj.get('genre', '未设定')}")
    print(f"  📊 目标: {proj.get('target_words', 0):,} 字 / {proj.get('target_chapters', 0)} 章")
    print(f"  📝 已写: {proj.get('current_chars', 0):,} 字")
    print(f"  📌 当前: 卷{proj.get('current_volume', 0)} 章{proj.get('current_chapter', 0)}")
    print(f"  🔄 阶段: {proj.get('phase', '未知')} | 状态: {proj.get('status', '未知')}")
    print("=" * 60)

    # State files
    if STATE_DIR.exists():
        chars = load_json(STATE_DIR / "character_matrix.json")
        hooks = load_json(STATE_DIR / "pending_hooks.json")
        subplots = load_json(STATE_DIR / "subplot_board.json")
        summaries = load_json(STATE_DIR / "chapter_summaries.json")

        char_count = len(chars.get("characters", {}))
        active_hooks = sum(
            1 for h in hooks.get("hooks", {}).values()
            if isinstance(h, dict) and h.get("status") == "active"
        )
        active_subplots = sum(
            1 for s in subplots.get("subplots", {}).values()
            if isinstance(s, dict) and s.get("status") == "active"
        )
        summary_count = len(summaries.get("summaries", {}))

        print(f"  👤 角色: {char_count}")
        print(f"  🎣 活跃伏笔: {active_hooks}")
        print(f"  📖 活跃支线: {active_subplots}")
        print(f"  📝 章节摘要: {summary_count}")

    # Check foundation files
    print("\n  --- 设定文件 ---")
    for name in ["seed.txt", "world.md", "characters.md", "outline.md",
                  "canon.md", "voice.md", "world_brief.md", "characters_brief.md"]:
        path = BASE_DIR / name
        status = f"✅ {path.stat().st_size:,} bytes" if path.exists() else "❌ 缺失"
        print(f"  {name}: {status}")

    # Check plans
    plans_dir = STORY_DIR / "plans"
    if plans_dir.exists():
        plan_files = list(plans_dir.glob("*.yaml")) + list(plans_dir.glob("*.md"))
        if plan_files:
            print(f"\n  --- 计划文件 ({len(plan_files)}) ---")
            for f in sorted(plan_files)[:10]:
                print(f"  {f.name}: {f.stat().st_size:,} bytes")


def cmd_context(chapter: int):
    """为指定章节组装上下文摘要（不调用 LLM）。"""
    proj = load_json(STORY_DIR / "project.json")
    volume = proj.get("current_volume", 1)

    print(f"\n=== 第 {chapter} 章上下文 (卷{volume}) ===\n")

    # Characters
    chars = load_json(STATE_DIR / "character_matrix.json")
    if chars.get("characters"):
        print("--- 当前角色 ---")
        for cid, c in chars["characters"].items():
            if isinstance(c, dict):
                print(f"  - {c.get('name', cid)} ({c.get('role', '?')}): {c.get('personality', '')[:80]}")

    # Active hooks
    hooks = load_json(STATE_DIR / "pending_hooks.json")
    active_hooks = {
        k: v for k, v in hooks.get("hooks", {}).items()
        if isinstance(v, dict) and v.get("status") == "active"
    }
    if active_hooks:
        print("\n--- 活跃伏笔 ---")
        for hid, h in active_hooks.items():
            print(f"  - [{hid}] {h.get('description', '')} (种于第{h.get('planted_chapter', '?')}章)")

    # Active subplots
    subplots = load_json(STATE_DIR / "subplot_board.json")
    active_sp = {
        k: v for k, v in subplots.get("subplots", {}).items()
        if isinstance(v, dict) and v.get("status") == "active"
    }
    if active_sp:
        print("\n--- 活跃支线 ---")
        for sid, s in active_sp.items():
            print(f"  - [{sid}] {s.get('name', '')}: {s.get('description', '')[:100]}")

    # Recent summaries
    summaries = load_json(STATE_DIR / "chapter_summaries.json")
    if summaries.get("summaries"):
        items = sorted(summaries["summaries"].items(), key=lambda x: x[0])
        recent = items[-5:] if len(items) > 5 else items
        print("\n--- 最近章节摘要 ---")
        for key, s in recent:
            if isinstance(s, dict):
                print(f"  - 第{s.get('chapter', '?')}章: {s.get('summary', '')[:150]}")

    # Volume plan
    vol_plan_path = STORY_DIR / "plans" / f"volume_{volume:03d}.yaml"
    if vol_plan_path.exists():
        print(f"\n--- 卷{volume}计划 ---")
        print(f"  {vol_plan_path.name}: {vol_plan_path.stat().st_size:,} bytes")

    # Chapter plan
    ch_plan_path = STORY_DIR / "plans" / f"chapter_{chapter:04d}.yaml"
    if ch_plan_path.exists():
        print(f"\n--- 第{chapter}章计划 ---")
        content = ch_plan_path.read_text(encoding="utf-8")
        print(content[:500])

    # Previous chapter tail
    prev_paths = [
        BASE_DIR / "chapters" / f"v{volume:03d}" / f"ch_{chapter-1:04d}.md",
        BASE_DIR / "chapters" / f"ch_{chapter-1:02d}.md",
    ]
    for pp in prev_paths:
        if pp.exists():
            tail = pp.read_text(encoding="utf-8")[-500:]
            print(f"\n--- 前一章结尾 ---")
            print(tail)
            break


def cmd_files():
    """列出所有章节文件。"""
    chapters_dir = BASE_DIR / "chapters"
    if not chapters_dir.exists():
        print("chapters/ 目录不存在")
        return

    total_chars = 0
    for md in sorted(chapters_dir.rglob("*.md")):
        size = md.stat().st_size
        text = md.read_text(encoding="utf-8")
        cn_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        total_chars += cn_chars
        print(f"  {md.relative_to(chapters_dir)}: {cn_chars:,} 中文字 ({size:,} bytes)")

    print(f"\n  总计: {total_chars:,} 中文字")


def main():
    parser = argparse.ArgumentParser(description="Autonovel 状态辅助工具")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="查看项目状态摘要")

    ctx = sub.add_parser("context", help="查看指定章节的上下文")
    ctx.add_argument("--chapter", type=int, required=True, help="章节号")

    sub.add_parser("files", help="列出所有章节文件")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "context":
        cmd_context(args.chapter)
    elif args.command == "files":
        cmd_files()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
