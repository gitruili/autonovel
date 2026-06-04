#!/usr/bin/env python3
"""
update_projections.py — Update human-readable projection documents.

Generates Markdown files in story/projections/ that summarize the current
state of the story for human review. Run after each chapter or volume.

Usage:
  uv run python update_projections.py --chapter 5
  uv run python update_projections.py --full
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from story_schema import (
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
PROJECTIONS_DIR = STORY_DIR / "projections"


def write_md(path: Path, lines: list[str]):
    """Write lines to a markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_characters_projection():
    """Update characters.md projection."""
    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    if not char_matrix.characters:
        return

    lines = ["# 角色档案", f"", f"*更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*", ""]

    for cid, char in sorted(char_matrix.characters.items(), key=lambda x: x[0]):
        lines.append(f"## {char.name} (`{cid}`)")
        lines.append(f"- **角色定位:** {char.role}")
        if char.age:
            lines.append(f"- **年龄:** {char.age}")
        if char.gender:
            lines.append(f"- **性别:** {char.gender}")
        if char.personality:
            lines.append(f"- **性格:** {char.personality}")
        if char.speech_pattern:
            lines.append(f"- **说话方式:** {char.speech_pattern}")
        if char.motivation:
            lines.append(f"- **动机:** {char.motivation}")
        if char.arc_summary:
            lines.append(f"- **弧光:** {char.arc_summary}")
        if char.relationships:
            lines.append(f"- **关系网:**")
            for other, rel in char.relationships.items():
                lines.append(f"  - {other}: {rel}")
        lines.append(f"- **首次出现:** 第{char.source_chapter}章 | **最后出现:** 第{char.last_seen_chapter}章")
        lines.append("")

    write_md(PROJECTIONS_DIR / "characters.md", lines)


def update_hooks_projection():
    """Update pending hooks projection."""
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    if not hooks.hooks:
        return

    lines = ["# 伏笔追踪", f"", f"*更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*", ""]

    active = {k: v for k, v in hooks.hooks.items() if v.status == "active"}
    resolved = {k: v for k, v in hooks.hooks.items() if v.status == "resolved"}

    if active:
        lines.append("## 活跃伏笔")
        lines.append("")
        for hid, hook in sorted(active.items(), key=lambda x: x[1].planted_chapter):
            urgency_icon = {"low": "🔵", "normal": "⚪", "high": "🟡", "critical": "🔴"}.get(hook.urgency, "⚪")
            lines.append(f"### {urgency_icon} {hook.description}")
            lines.append(f"- **ID:** `{hid}`")
            lines.append(f"- **类型:** {hook.hook_type}")
            lines.append(f"- **种于:** 第{hook.planted_chapter}章")
            if hook.expected_payoff_chapter:
                lines.append(f"- **预期回收:** 第{hook.expected_payoff_chapter}章")
            if hook.related_characters:
                lines.append(f"- **相关角色:** {', '.join(hook.related_characters)}")
            lines.append("")

    if resolved:
        lines.append("## 已回收伏笔")
        lines.append("")
        for hid, hook in sorted(resolved.items(), key=lambda x: x[1].valid_until_chapter or 0):
            lines.append(f"- ~~{hook.description}~~ (回收于第{hook.valid_until_chapter}章)")
        lines.append("")

    lines.append(f"**统计:** 活跃 {len(active)} | 已回收 {len(resolved)}")
    write_md(PROJECTIONS_DIR / "hooks.md", lines)


def update_power_projection():
    """Update power ledger projection."""
    ledger = PowerLedgerFull(**load_json(STORY_DIR / "state" / "power_ledger.json"))

    lines = ["# 战力与资源账本", f"", f"*更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*", ""]

    if ledger.power_system:
        lines.append(f"## 力量体系: {ledger.power_system}")
        if ledger.level_names:
            lines.append(f"**等级序列:** {' → '.join(ledger.level_names)}")
        lines.append("")

    if ledger.levels:
        lines.append("## 战力记录")
        lines.append("")
        for level in sorted(ledger.levels, key=lambda x: (x.character_id, x.level_rank)):
            lines.append(f"- **{level.character_id}**: {level.level_name} (Rank {level.level_rank})"
                        f" — 突破于第{level.breakthrough_chapter}章")
        lines.append("")

    if ledger.resources:
        lines.append("## 资源")
        lines.append("")
        for rid, res in sorted(ledger.resources.items()):
            if res.status == "active":
                lines.append(f"- **{res.name}** ({res.category}): {res.quantity} {res.unit}"
                            f" | 持有者: {res.owner or '无'}")
        lines.append("")

    if ledger.items:
        lines.append("## 物品")
        lines.append("")
        for iid, item in sorted(ledger.items.items()):
            if item.status == "active":
                lines.append(f"- **{item.name}** ({item.rarity} {item.item_type})"
                            f" | 持有者: {item.owner or '无'}"
                            f" | 获得于第{item.acquired_chapter}章")
        lines.append("")

    write_md(PROJECTIONS_DIR / "power_ledger.md", lines)


def update_subplots_projection():
    """Update subplots projection."""
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))
    if not subplots.subplots:
        return

    lines = ["# 支线追踪", f"", f"*更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*", ""]

    active = {k: v for k, v in subplots.subplots.items() if v.status == "active"}
    other = {k: v for k, v in subplots.subplots.items() if v.status != "active"}

    if active:
        lines.append("## 活跃支线")
        lines.append("")
        for sid, sp in sorted(active.items()):
            tension_icon = {"building": "📈", "climax": "🔥", "resolution": "📉"}.get(sp.tension_level, "📊")
            lines.append(f"### {tension_icon} {sp.name}")
            lines.append(f"- **ID:** `{sid}`")
            lines.append(f"- **描述:** {sp.description}")
            lines.append(f"- **张力:** {sp.tension_level}")
            if sp.related_characters:
                lines.append(f"- **相关角色:** {', '.join(sp.related_characters)}")
            if sp.chapters_involved:
                lines.append(f"- **涉及章节:** {sp.chapters_involved}")
            lines.append("")

    if other:
        lines.append("## 已结束支线")
        lines.append("")
        for sid, sp in sorted(other.items()):
            lines.append(f"- **{sp.name}** ({sp.status}): {sp.description[:100]}")
        lines.append("")

    write_md(PROJECTIONS_DIR / "subplots.md", lines)


def update_state_snapshot():
    """Update current state snapshot."""
    current = CurrentState(**load_json(STORY_DIR / "state" / "current_state.json"))
    proj = ProjectConfig(**load_json(STORY_DIR / "project.json"))

    lines = [
        "# 当前状态快照",
        "",
        f"*更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## 项目进度",
        f"- **当前章节:** 第{proj.current_chapter}章",
        f"- **当前卷:** 第{proj.current_volume}卷",
        f"- **累计字数:** {proj.current_chars:,}",
        f"- **目标字数:** {proj.target_words:,}",
        f"- **进度:** {proj.current_chars / proj.target_words * 100:.1f}%",
        "",
        "## 时间线",
        f"- **当前位置:** {current.timeline_position or '(未设定)'}",
        f"- **当前地点:** {current.current_location or '(未设定)'}",
        "",
    ]

    if current.active_plot_threads:
        lines.append("## 活跃剧情线")
        for t in current.active_plot_threads:
            lines.append(f"- {t}")
        lines.append("")

    if current.recent_events:
        lines.append("## 最近事件")
        for evt in current.recent_events[-10:]:
            lines.append(f"- **第{evt.get('chapter', '?')}章:** {evt.get('event', '')[:150]}")
        lines.append("")

    write_md(PROJECTIONS_DIR / "current_state.md", lines)


def update_emotional_arcs_projection():
    """Update emotional arcs projection."""
    arcs = EmotionalArcs(**load_json(STORY_DIR / "state" / "emotional_arcs.json"))
    if not arcs.arcs:
        return

    lines = ["# 情感弧追踪", f"", f"*更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*", ""]

    active = {k: v for k, v in arcs.arcs.items() if v.end_chapter is None}
    completed = {k: v for k, v in arcs.arcs.items() if v.end_chapter is not None}

    if active:
        lines.append("## 进行中")
        lines.append("")
        for aid, arc in sorted(active.items()):
            bar = "█" * int(arc.intensity * 10) + "░" * (10 - int(arc.intensity * 10))
            lines.append(f"- **{arc.character_id}** — {arc.emotion} [{bar}] {arc.intensity:.0%}")
            if arc.trigger:
                lines.append(f"  - 触发: {arc.trigger}")
            lines.append(f"  - 起始: 第{arc.start_chapter}章")
        lines.append("")

    if completed:
        lines.append("## 已完成")
        lines.append("")
        for aid, arc in sorted(completed.items()):
            lines.append(f"- **{arc.character_id}** — {arc.emotion}"
                        f" (第{arc.start_chapter}-{arc.end_chapter}章)")
        lines.append("")

    write_md(PROJECTIONS_DIR / "emotional_arcs.md", lines)


def update_all_projections(chapter: int | None = None):
    """Update all projection documents."""
    PROJECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    update_characters_projection()
    print("  Updated: projections/characters.md")

    update_hooks_projection()
    print("  Updated: projections/hooks.md")

    update_power_projection()
    print("  Updated: projections/power_ledger.md")

    update_subplots_projection()
    print("  Updated: projections/subplots.md")

    update_state_snapshot()
    print("  Updated: projections/current_state.md")

    update_emotional_arcs_projection()
    print("  Updated: projections/emotional_arcs.md")


def main():
    parser = argparse.ArgumentParser(description="Update projection documents")
    parser.add_argument("--chapter", type=int, help="Chapter number (for logging)")
    parser.add_argument("--full", action="store_true", help="Update all projections")
    args = parser.parse_args()

    if args.chapter or args.full:
        print(f"Updating projections...")
        update_all_projections(args.chapter)
        print("Projections updated.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
