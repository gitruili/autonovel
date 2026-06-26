#!/usr/bin/env python3
"""
gen_batch_chapter_plans.py — Generate multiple chapter plans in a single LLM call.

Batch generation gives the LLM cross-chapter visibility, producing more coherent
foreshadowing, pacing, and cliffhanger transitions than one-at-a-time generation.

Usage:
  uv run python gen_batch_chapter_plans.py --start 1 --count 20
  uv run python gen_batch_chapter_plans.py --start 21 --count 10
"""

import argparse
import re
import sys
from pathlib import Path

from story_schema import (
    ChapterSummaries,
    CharacterMatrix,
    PendingHooks,
    ProjectConfig,
    SubplotBoard,
    load_json,
    load_volume_plan,
)
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
load_dotenv(BASE_DIR / ".env")

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
    """Assemble current state context."""
    parts = []

    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    if char_matrix.characters:
        chars_text = "当前角色:\n"
        for cid, char in char_matrix.characters.items():
            chars_text += f"  - {char.name} ({char.role}): {char.personality[:100]}\n"
        parts.append(chars_text)

    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    active_hooks = {k: v for k, v in hooks.hooks.items() if v.status == "active"}
    if active_hooks:
        hooks_text = "活跃伏笔:\n"
        for hid, hook in active_hooks.items():
            hooks_text += f"  - [{hid}] {hook.description} (种于第{hook.planted_chapter}章)\n"
        parts.append(hooks_text)

    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))
    active_subplots = {k: v for k, v in subplots.subplots.items() if v.status == "active"}
    if active_subplots:
        sp_text = "活跃支线:\n"
        for sid, sp in active_subplots.items():
            sp_text += f"  - [{sid}] {sp.name}: {sp.description[:100]}\n"
        parts.append(sp_text)

    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    if summaries.summaries:
        items = sorted(summaries.summaries.items(), key=lambda x: x[0])
        recent = items[-5:] if len(items) > 5 else items
        sum_text = "最近章节摘要:\n"
        for key, s in recent:
            sum_text += f"  - 第{s.chapter}章: {s.summary[:150]}\n"
        parts.append(sum_text)

    return "\n".join(parts) if parts else "(当前状态为空——这是第一批章节)"


def clean_yaml(text: str) -> str:
    """Strip markdown code fences from YAML text."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])
    return text.strip()


def parse_batch_output(result: str, start: int, count: int) -> list[tuple[str, str]]:
    """Parse LLM output into list of (yaml_text, intent_text) tuples.

    Expected format:
      === PLANS ===
      - chapter: N
        ...
      - chapter: N+1
        ...
      === INTENT_N ===
      intent text for chapter N
      === INTENT_N+1 ===
      intent text for chapter N+1
    """
    plans = []

    # Split off intents section
    if "=== PLANS ===" in result:
        plans_section = result.split("=== PLANS ===")[1]
    else:
        plans_section = result

    # Extract all intents
    intents = {}
    intent_pattern = re.compile(r"=== INTENT_(\d+) ===\s*(.*?)(?==== INTENT_\d+ ===|$)", re.DOTALL)
    for match in intent_pattern.finditer(plans_section):
        ch_num = int(match.group(1))
        intent_text = match.group(2).strip()
        intents[ch_num] = intent_text

    # Remove intent markers from plans section to get clean YAML
    yaml_section = re.sub(r"=== INTENT_\d+ ===.*", "", plans_section, flags=re.DOTALL).strip()
    yaml_section = clean_yaml(yaml_section)

    # Split the YAML list into individual chapter plans
    # The YAML is a list starting with "- chapter: N"
    # Split on "- chapter:" pattern at the start of a line
    chapter_blocks = re.split(r"(?=\n- chapter:)", yaml_section)

    # First block might not start with "- chapter:" if the list starts immediately
    first_block = chapter_blocks[0].strip()
    if first_block.startswith("- chapter:"):
        pass  # Already correct
    elif first_block.startswith("chapter:"):
        # First item without leading dash (part of a list after the opening)
        chapter_blocks[0] = "- " + first_block
    else:
        # Try to find the first "- chapter:" in the text
        idx = first_block.find("- chapter:")
        if idx >= 0:
            chapter_blocks = [first_block[idx:]] + ["- " + b.strip() for b in first_block[idx:].split("\n- chapter:") if b.strip()]
            chapter_blocks = [b for b in chapter_blocks if b.strip()]

    for i, block in enumerate(chapter_blocks):
        block = block.strip()
        if not block:
            continue

        # Extract chapter number from the block
        ch_match = re.search(r"chapter:\s*(\d+)", block)
        if not ch_match:
            continue

        ch_num = int(ch_match.group(1))

        # Clean up the YAML: ensure it starts with proper format
        if block.startswith("- "):
            block = block[2:]  # Remove list prefix for individual file

        yaml_text = clean_yaml(block)
        intent_text = intents.get(ch_num, f"第 {ch_num} 章写作意图（自动生成）")

        plans.append((ch_num, yaml_text, intent_text))

    # Fallback: if parsing produced nothing, try treating each "- chapter:" as a separator
    if not plans:
        lines = yaml_section.split("\n")
        current_yaml = []
        current_ch = None

        for line in lines:
            ch_match = re.match(r"^- chapter:\s*(\d+)", line)
            if ch_match:
                if current_ch is not None and current_yaml:
                    yaml_text = "\n".join(current_yaml)
                    intent_text = intents.get(current_ch, f"第 {current_ch} 章写作意图（自动生成）")
                    plans.append((current_ch, yaml_text, intent_text))
                current_ch = int(ch_match.group(1))
                current_yaml = [line[2:]]  # Remove "- " prefix
            elif current_ch is not None:
                current_yaml.append(line)

        if current_ch is not None and current_yaml:
            yaml_text = "\n".join(current_yaml)
            intent_text = intents.get(current_ch, f"第 {current_ch} 章写作意图（自动生成）")
            plans.append((current_ch, yaml_text, intent_text))

    return plans


def gen_batch_plans(start: int, count: int) -> list[tuple[int, str, str]]:
    """Generate batch chapter plans. Returns list of (chapter_num, yaml_text, intent_text)."""
    genre = load_genre_for_project()
    proj = ProjectConfig(**load_json(STORY_DIR / "project.json"))
    volume = proj.current_volume
    end = start + count - 1
    volume_plan = load_volume_plan(volume)
    outline = load_outline()
    voice = load_voice()
    state_ctx = get_state_context(start)

    # Load genre-specific writing fragments
    genre_detail = genre.get_prompt_fragment("chapter_draft", "genre_specific_detail")
    writing_guide = genre.get_prompt_fragment("chapter_draft", "writing_guide")

    detail_block = f"\n=== 题材专属细节 ===\n{genre_detail}" if genre_detail else ""
    guide_block = f"\n=== 写作指南 ===\n{writing_guide}" if writing_guide else ""

    prompt = f"""你是一位网文策划编辑，擅长将卷级计划拆解为连续章节，确保前后章节的连贯性和伏笔节奏。

请为第 {start} 章到第 {end} 章（共 {count} 章）生成详细的章级计划。

=== 项目信息 ===
标题: {proj.title or '(未设定)'}
类型: {proj.genre or '(未设定)'}
当前卷: 第 {volume} 卷
每章目标字数: {proj.default_chapter_chars}

=== 卷级计划 ===
{volume_plan[:6000] if volume_plan else '(未生成卷计划)'}

=== 总纲 ===
{outline[:4000] if outline else '(未生成总纲)'}

=== 当前状态 ===
{state_ctx}

=== 写作规范 ===
{voice[:2000] if voice else '(未设定写作规范)'}{detail_block}{guide_block}

=== 输出要求 ===
请以 YAML 列表格式输出 {count} 个章级计划。关键要求：

1. **前后衔接**：每章的 cliffhanger.connects_to_next 必须与下一章的 opening 自然衔接
2. **伏笔节奏**：合理分配 hook_actions，不要在连续章节重复种下同类伏笔
3. **情绪起伏**：利用卷纲中的 pacing 指引，控制节奏变化（紧张→缓和→高潮）
4. **角色弧线**：确保角色在多章中有渐进式发展，不要突变

每章包含以下字段：

```yaml
- chapter: {start}
  title: "章节标题"
  volume: {volume}
  pov_character: "视角角色ID"
  target_chars: {proj.default_chapter_chars}
  beats:
    - type: "opening"
      description: "开场节拍描述"
      location: "场景地点"
      characters_present: ["char_id_1"]
      emotional_tone: "紧张/温馨/悲伤等"
    - type: "development"
      description: "发展节拍"
      location: "场景地点"
      characters_present: ["char_id_1"]
      emotional_tone: "情绪"
    - type: "conflict"
      description: "冲突节拍"
      location: "场景地点"
      characters_present: ["char_id_1"]
      emotional_tone: "情绪"
    - type: "revelation"
      description: "揭示节拍"
      location: "场景地点"
      characters_present: ["char_id_1"]
      emotional_tone: "情绪"
    - type: "emotion"
      description: "情感节拍"
      location: "场景地点"
      characters_present: ["char_id_1"]
      emotional_tone: "情绪"
    - type: "cliffhanger"
      description: "章末钩子"
      location: "场景地点"
      characters_present: ["char_id_1"]
      emotional_tone: "情绪"
  hook_actions:
    - action: "plant"  # plant | advance | resolve
      hook_id: "hook_xxx"
      description: "种下/推进/回收的具体方式"
  setting_details:
    - "需要展示的设定细节"
  dialogue_notes:
    - character: "char_id"
      speech_requirement: "说话特征"
  cliffhanger:
    type: "悬念/冲突/反转/情感"
    description: "章末钩子具体描述"
    connects_to_next: "与下一章的衔接方式"
  warnings:
    - "需要避免的坑"
```

同时为每章生成 intent.md（3-5句写作意图和情感基调）。

输出格式（严格遵守）：
=== PLANS ===
- chapter: {start}
  title: ...
  ...
- chapter: {start + 1}
  ...
=== INTENT_{start} ===
(第{start}章写作意图)
=== INTENT_{start + 1} ===
(第{start + 1}章写作意图)
...
"""

    print(f"Generating batch chapter plans: Ch.{start}-Ch.{end} ({count} chapters)...", file=sys.stderr)
    result = call_text_model(
        model=WRITER_MODEL,
        max_tokens=16000,
        temperature=0.7,
        system=genre.get_system_prompt("architect"),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
    )

    plans = parse_batch_output(result, start, count)

    if not plans:
        print("[ERROR] Failed to parse any chapter plans from LLM output.", file=sys.stderr)
        print(f"Raw output (first 1000 chars):\n{result[:1000]}", file=sys.stderr)
        return []

    return plans


def main():
    parser = argparse.ArgumentParser(description="Generate batch chapter plans")
    parser.add_argument("--start", type=int, required=True, help="First chapter number")
    parser.add_argument("--count", type=int, default=20, help="Number of chapters to plan (default: 20)")
    args = parser.parse_args()

    plans_dir = STORY_DIR / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)

    # Check which chapters already have plans
    existing = []
    to_generate = []
    for ch in range(args.start, args.start + args.count):
        plan_path = plans_dir / f"chapter_{ch:04d}.yaml"
        intent_path = STORY_DIR / "runtime" / f"ch_{ch:04d}" / "intent.md"
        if plan_path.exists() and intent_path.exists():
            existing.append(ch)
        else:
            to_generate.append(ch)

    if existing:
        print(f"Skipping {len(existing)} chapters with existing plans: {existing}", file=sys.stderr)

    if not to_generate:
        print("All chapter plans already exist. Nothing to do.")
        return 0

    actual_start = to_generate[0]
    actual_count = len(to_generate)

    # If only a few chapters need generation, adjust the batch
    # But we still generate the full range for coherence, then only save the needed ones
    plans = gen_batch_plans(args.start, args.count)

    if not plans:
        return 1

    saved = 0
    skipped = 0
    for ch_num, yaml_text, intent_text in plans:
        if ch_num in existing:
            skipped += 1
            continue

        # Save chapter plan
        plan_path = plans_dir / f"chapter_{ch_num:04d}.yaml"
        plan_path.write_text(yaml_text, encoding="utf-8")

        # Save intent
        rt_dir = STORY_DIR / "runtime" / f"ch_{ch_num:04d}"
        rt_dir.mkdir(parents=True, exist_ok=True)
        intent_path = rt_dir / "intent.md"
        intent_path.write_text(intent_text, encoding="utf-8")

        saved += 1
        print(f"  Saved: chapter_{ch_num:04d}.yaml + intent.md", file=sys.stderr)

    print(f"\nBatch plan complete: {saved} saved, {skipped} skipped (already existed)", file=sys.stderr)
    print(f"Total plans parsed from LLM: {len(plans)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
