#!/usr/bin/env python3
"""
gen_volume_summary.py — Generate volume-level summary from chapter summaries.

Aggregates chapter summaries within a volume into a structured volume summary.
Used at volume boundaries and for periodic review.

Usage:
  uv run python gen_volume_summary.py --volume 1
  uv run python gen_volume_summary.py --volume 1 --chapters 1-20
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from story_schema import (
    ChapterSummaries,
    CharacterMatrix,
    PendingHooks,
    ProjectConfig,
    SubplotBoard,
    VolumeSummary,
    load_json,
    save_json,
    save_yaml,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)


def get_chapter_range_for_volume(volume: int) -> tuple[int, int]:
    """Determine chapter range for a given volume."""
    vol_path = STORY_DIR / "plans" / f"volume_{volume:03d}.yaml"
    if vol_path.exists():
        import yaml
        with open(vol_path, "r", encoding="utf-8") as f:
            vol_data = yaml.safe_load(f) or {}
        cr = vol_data.get("chapter_range", "")
        if cr and "-" in cr:
            parts = cr.split("-")
            return int(parts[0]), int(parts[1])
        tc = vol_data.get("target_chapters", 20)
        start = (volume - 1) * tc + 1
        return start, start + tc - 1
    # Default: 20 chapters per volume
    start = (volume - 1) * 20 + 1
    return start, start + 19


def load_volume_plan(volume: int) -> str:
    path = STORY_DIR / "plans" / f"volume_{volume:03d}.yaml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def gen_volume_summary(volume: int, chapter_start: int | None = None,
                       chapter_end: int | None = None) -> VolumeSummary:
    """Generate a volume summary from chapter summaries."""
    proj = ProjectConfig(**load_json(STORY_DIR / "project.json"))

    # Determine chapter range
    if chapter_start and chapter_end:
        start, end = chapter_start, chapter_end
    else:
        start, end = get_chapter_range_for_volume(volume)

    # Load chapter summaries
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    volume_summaries = []
    for ch in range(start, end + 1):
        key = f"ch_{ch}"
        if key in summaries.summaries:
            s = summaries.summaries[key]
            volume_summaries.append({
                "chapter": s.chapter,
                "title": s.title,
                "summary": s.summary,
                "key_events": s.key_events,
                "characters_present": s.characters_present,
                "word_count": s.word_count,
                "emotional_tone": s.emotional_tone,
            })

    if not volume_summaries:
        print(f"  [WARN] No chapter summaries found for volume {volume} (chapters {start}-{end})")
        return VolumeSummary(volume=volume, chapter_range=f"{start}-{end}")

    # Load state context
    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))

    active_hooks = {k: v for k, v in hooks.hooks.items() if v.status == "active"}
    resolved_hooks = {k: v for k, v in hooks.hooks.items() if v.status == "resolved"}

    char_list = []
    for cid, c in char_matrix.characters.items():
        char_list.append(f"  - {c.name} ({c.role}): {c.personality[:100]}")

    hook_list_planted = [f"  - [{k}] {v.description}" for k, v in hooks.hooks.items()
                         if v.planted_chapter >= start]
    hook_list_resolved = [f"  - [{k}] {v.description}" for k, v in resolved_hooks.items()
                          if v.valid_until_chapter and v.valid_until_chapter >= start]
    hook_list_unresolved = [f"  - [{k}] {v.description}" for k, v in active_hooks.items()]

    subplot_list = []
    for sid, sp in subplots.subplots.items():
        subplot_list.append(f"  - [{sid}] {sp.name}: {sp.status}")

    volume_plan = load_volume_plan(volume)

    total_words = sum(s.get("word_count", 0) for s in volume_summaries)

    prompt = f"""你是一位网文编辑，擅长总结卷级剧情。请根据以下章节摘要生成第 {volume} 卷的卷级总结。

=== 章节范围 ===
第 {start} 章 到 第 {end} 章

=== 卷级计划 ===
{volume_plan[:3000] if volume_plan else '(无卷级计划)'}

=== 章节摘要 ===
{json.dumps(volume_summaries, ensure_ascii=False, indent=2)[:6000]}

=== 当前角色 ===
{chr(10).join(char_list[:20]) if char_list else '(无)'}

=== 本卷种下的伏笔 ===
{chr(10).join(hook_list_planted[:20]) if hook_list_planted else '(无)'}

=== 本卷回收的伏笔 ===
{chr(10).join(hook_list_resolved[:20]) if hook_list_resolved else '(无)'}

=== 未解决的伏笔 ===
{chr(10).join(hook_list_unresolved[:20]) if hook_list_unresolved else '(无)'}

=== 支线状态 ===
{chr(10).join(subplot_list[:20]) if subplot_list else '(无)'}

=== 输出要求 ===
请以 YAML 格式输出卷级总结，包含以下字段：

```yaml
volume: {volume}
title: "卷标题"
theme: "本卷核心主题"
chapter_range: "{start}-{end}"
total_words: {total_words}
main_arc_summary: "本卷主线剧情总结（300-500字）"
key_events:
  - "关键事件1"
  - "关键事件2"
  # ... 5-10个关键事件
character_developments:
  - character: "角色名"
    development: "角色发展描述"
hooks_planted:
  - "伏笔描述"
hooks_resolved:
  - "伏笔回收描述"
unresolved_hooks:
  - "未解决伏笔描述"
subplots_status:
  - name: "支线名"
    status: "active/resolved/paused"
    summary: "支线进展"
emotional_arcs_summary:
  - "角色情感弧总结"
pacing_notes: "本卷节奏总结"
next_volume_setup: "为下一卷铺设的基础"
```

只输出 YAML，不要其他文字。"""

    print(f"Generating volume {volume} summary...", file=sys.stderr)
    result = call_text_model(
        model=WRITER_MODEL,
        max_tokens=6000,
        temperature=0.3,
        system="你是一位网文编辑。只输出 YAML 格式的内容。",
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

    # Parse YAML
    yaml_text = result.strip()
    if yaml_text.startswith("```"):
        lines = yaml_text.split("\n")
        start_idx = 1
        end_idx = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        yaml_text = "\n".join(lines[start_idx:end_idx])

    import yaml
    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            data = {}
    except Exception as e:
        print(f"  [WARN] YAML parse failed: {e}", file=sys.stderr)
        data = {}

    # Build VolumeSummary with fallbacks
    summary = VolumeSummary(
        volume=volume,
        title=data.get("title", f"第{volume}卷"),
        theme=data.get("theme", ""),
        chapter_range=f"{start}-{end}",
        total_words=total_words,
        main_arc_summary=data.get("main_arc_summary", ""),
        key_events=data.get("key_events", []),
        character_developments=data.get("character_developments", []),
        hooks_planted=data.get("hooks_planted", []),
        hooks_resolved=data.get("hooks_resolved", []),
        unresolved_hooks=data.get("unresolved_hooks", []),
        subplots_status=data.get("subplots_status", []),
        emotional_arcs_summary=data.get("emotional_arcs_summary", []),
        pacing_notes=data.get("pacing_notes", ""),
        next_volume_setup=data.get("next_volume_setup", ""),
    )

    return summary


def main():
    parser = argparse.ArgumentParser(description="Generate volume-level summary")
    parser.add_argument("--volume", type=int, required=True, help="Volume number")
    parser.add_argument("--chapters", type=str, help="Chapter range, e.g. '1-20'")
    args = parser.parse_args()

    chapter_start = chapter_end = None
    if args.chapters:
        parts = args.chapters.split("-")
        chapter_start = int(parts[0])
        chapter_end = int(parts[1]) if len(parts) > 1 else chapter_start

    summary = gen_volume_summary(args.volume, chapter_start, chapter_end)

    # Save as YAML
    out_path = STORY_DIR / "plans" / f"volume_{args.volume:03d}_summary.yaml"
    save_yaml(out_path, summary.model_dump())

    # Also save to projections
    proj_path = STORY_DIR / "projections" / f"volume_{args.volume:03d}_summary.md"
    proj_path.parent.mkdir(parents=True, exist_ok=True)
    md_lines = [
        f"# 第{args.volume}卷总结",
        f"",
        f"**章节范围:** {summary.chapter_range}",
        f"**总字数:** {summary.total_words:,}",
        f"**主题:** {summary.theme}",
        f"",
        f"## 主线剧情",
        summary.main_arc_summary,
        f"",
        f"## 关键事件",
    ]
    for evt in summary.key_events:
        md_lines.append(f"- {evt}")
    md_lines.append("")
    md_lines.append("## 角色发展")
    for dev in summary.character_developments:
        if isinstance(dev, dict):
            md_lines.append(f"- **{dev.get('character', '?')}**: {dev.get('development', '')}")
        else:
            md_lines.append(f"- {dev}")
    md_lines.append("")
    md_lines.append("## 伏笔状态")
    md_lines.append("### 本卷种下")
    for h in summary.hooks_planted:
        md_lines.append(f"- {h}")
    md_lines.append("### 本卷回收")
    for h in summary.hooks_resolved:
        md_lines.append(f"- {h}")
    md_lines.append("### 未解决")
    for h in summary.unresolved_hooks:
        md_lines.append(f"- {h}")
    md_lines.append("")
    md_lines.append("## 下卷铺垫")
    md_lines.append(summary.next_volume_setup)

    proj_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\nVolume summary saved to: {out_path}")
    print(f"Projection saved to: {proj_path}")
    print(f"  Chapters: {summary.chapter_range}")
    print(f"  Total words: {summary.total_words:,}")
    print(f"  Key events: {len(summary.key_events)}")
    print(f"  Hooks planted: {len(summary.hooks_planted)}")
    print(f"  Hooks resolved: {len(summary.hooks_resolved)}")


if __name__ == "__main__":
    main()
