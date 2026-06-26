#!/usr/bin/env python3
"""
gen_chapter_plan.py — Generate chapter-level plan using LLM.

Usage:
  uv run python gen_chapter_plan.py --chapter 1
"""

import argparse
import sys
from pathlib import Path

from outline_utils import (
    extract_chapter_outline,
    load_volume_outline_for_chapter,
)
from story_schema import (
    ChapterSummaries,
    CharacterMatrix,
    PendingHooks,
    ProjectConfig,
    SubplotBoard,
    load_json,
    load_volume_plan,
    save_json,
)
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
load_dotenv(BASE_DIR / ".env")

genre = load_genre_for_project()

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)


def load_outline() -> str:
    path = BASE_DIR / "outline.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_voice() -> str:
    path = BASE_DIR / "voice.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def get_state_context(chapter: int) -> str:
    """Assemble current state context for the chapter plan."""
    parts = []

    # Characters
    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    if char_matrix.characters:
        chars_text = "当前角色:\n"
        for cid, char in char_matrix.characters.items():
            chars_text += f"  - {char.name} ({char.role}): {char.personality[:100]}\n"
        parts.append(chars_text)

    # Pending hooks
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    active_hooks = {k: v for k, v in hooks.hooks.items() if v.status == "active"}
    if active_hooks:
        hooks_text = "活跃伏笔:\n"
        for hid, hook in active_hooks.items():
            hooks_text += f"  - [{hid}] {hook.description} (种于第{hook.planted_chapter}章)\n"
        parts.append(hooks_text)

    # Subplots
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))
    active_subplots = {k: v for k, v in subplots.subplots.items() if v.status == "active"}
    if active_subplots:
        sp_text = "活跃支线:\n"
        for sid, sp in active_subplots.items():
            sp_text += f"  - [{sid}] {sp.name}: {sp.description[:100]}\n"
        parts.append(sp_text)

    # Recent summaries
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    if summaries.summaries:
        items = sorted(summaries.summaries.items(), key=lambda x: x[0])
        recent = items[-3:] if len(items) > 3 else items
        sum_text = "最近章节摘要:\n"
        for key, s in recent:
            sum_text += f"  - 第{s.chapter}章: {s.summary[:150]}\n"
        parts.append(sum_text)

    return "\n".join(parts) if parts else "(当前状态为空——这是第一章)"


def gen_chapter_plan(chapter: int) -> tuple[str, str]:
    """Generate chapter plan and intent. Returns (yaml_text, intent_text)."""
    proj = ProjectConfig(**load_json(STORY_DIR / "project.json"))
    volume = proj.current_volume
    volume_plan = load_volume_plan(volume)
    outline = load_outline()
    voice = load_voice()
    state_ctx = get_state_context(chapter)

    # Extract the narrative outline entry for this chapter from the corresponding
    # volume outline file; fall back to the combined outline.md if unavailable.
    chapter_outline_detail = ""
    vol_outline_text, _ = load_volume_outline_for_chapter(chapter, BASE_DIR)
    if vol_outline_text:
        chapter_outline_detail = extract_chapter_outline(vol_outline_text, chapter)
    if not chapter_outline_detail:
        chapter_outline_detail = extract_chapter_outline(outline, chapter)

    genre_detail = genre.get_prompt_fragment("chapter_draft", "genre_specific_detail") or "题材专属细节要具体有质感，参考世界设定集中的相关描写。"

    prompt = f"""你是一位{genre.display_name}网文策划编辑，擅长将卷级计划拆解为具体章节。

请为第 {chapter} 章生成详细的章级计划。

=== 项目信息 ===
标题: {proj.title or '(未设定)'}
类型: {proj.genre or '(未设定)'}
当前卷: 第 {volume} 卷
每章目标字数: {proj.default_chapter_chars}

=== 卷级计划 ===
{volume_plan[:4000] if volume_plan else '(未生成卷计划)'}

=== 总纲 ===
{outline[:2000] if outline else '(未生成总纲)'}

=== 本章在卷纲中的定位（叙事细纲） ===
{chapter_outline_detail or '(无逐章细纲)'}

=== 当前状态 ===
{state_ctx}

=== 输出要求 ===
请以 YAML 格式输出章级计划，包含以下字段：

```yaml
chapter: {chapter}
title: "章节标题"
volume: {volume}
pov_character: "视角角色ID"
target_chars: {proj.default_chapter_chars}

# 本章节拍（按顺序完成）
beats:
  - type: "opening"  # opening | development | conflict | revelation | emotion | cliffhanger
    description: "开场节拍描述"
    location: "场景地点"
    characters_present: ["char_id_1"]
    emotional_tone: "紧张/温馨/悲伤等"
  - type: "development"
    description: "发展节拍"
    # ... 更多节拍
  - type: "cliffhanger"
    description: "章末钩子"

# 本章伏笔操作
hook_actions:
  - action: "plant"  # plant | advance | resolve
    hook_id: "hook_xxx"
    description: "种下/推进/回收的具体方式"
  - action: "advance"
    hook_id: "hook_yyy"
    description: "推进方式"

# 本章需要展示的设定
setting_details:
  - "{genre_detail[:60]}"

# 本章对话要点
dialogue_notes:
  - character: "char_id"
    speech_requirement: "需要体现的说话特征"

# 章末钩子要求
cliffhanger:
  type: "悬念/冲突/反转/情感"
  description: "章末钩子具体描述"
  connects_to_next: "与下一章的衔接方式"

# 注意事项
warnings:
  - "需要避免的坑"
  - "需要保持的一致性"
```

同时生成一份简短的 intent.md，用 3-5 句话概括本章的写作意图和情感基调。

只输出以下格式：
=== YAML ===
(章级计划 YAML)
=== INTENT ===
(intent.md 内容)"""

    print(f"Generating chapter {chapter} plan...", file=sys.stderr)
    result = call_text_model(
        model=WRITER_MODEL,
        max_tokens=6000,
        temperature=0.7,
        system=genre.get_system_prompt("architect"),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

    # Parse output
    yaml_text = ""
    intent_text = ""

    if "=== YAML ===" in result and "=== INTENT ===" in result:
        parts = result.split("=== INTENT ===")
        yaml_part = parts[0].replace("=== YAML ===", "").strip()
        intent_part = parts[1].strip()

        # Clean code blocks
        if yaml_part.startswith("```"):
            lines = yaml_part.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            yaml_part = "\n".join(lines[start:end])

        yaml_text = yaml_part
        intent_text = intent_part
    else:
        # Fallback: treat entire output as YAML
        yaml_text = result.strip()
        if yaml_text.startswith("```"):
            lines = yaml_text.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            yaml_text = "\n".join(lines[start:end])
        intent_text = f"第 {chapter} 章写作意图（自动生成失败，请手动填写）"

    return yaml_text, intent_text


def main():
    parser = argparse.ArgumentParser(description="Generate chapter-level plan")
    parser.add_argument("--chapter", type=int, required=True, help="Chapter number")
    args = parser.parse_args()

    yaml_text, intent_text = gen_chapter_plan(args.chapter)

    # Save chapter plan
    plan_path = STORY_DIR / "plans" / f"chapter_{args.chapter:04d}.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(yaml_text, encoding="utf-8")

    # Save intent
    rt_dir = STORY_DIR / "runtime" / f"ch_{args.chapter:04d}"
    rt_dir.mkdir(parents=True, exist_ok=True)
    intent_path = rt_dir / "intent.md"
    intent_path.write_text(intent_text, encoding="utf-8")

    print(f"\nChapter plan saved to: {plan_path}")
    print(f"Intent saved to: {intent_path}")
    print(f"\n--- Plan ---\n{yaml_text[:500]}...")


if __name__ == "__main__":
    main()
