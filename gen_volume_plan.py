#!/usr/bin/env python3
"""
gen_volume_plan.py — Generate a volume-level plan using LLM.

Usage:
  uv run python gen_volume_plan.py --volume 1
"""

import argparse
import sys
from pathlib import Path

from story_schema import (
    ProjectConfig,
    load_json,
    save_json,
    load_yaml,
    save_yaml,
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

# Default YAML output template — used as fallback when genre config
# does not define volume_plan.yaml_schema.
DEFAULT_YAML_SCHEMA = """=== 输出要求 ===
请以 YAML 格式输出卷级计划，包含以下字段：

```yaml
volume: {volume}
title: "卷标题"
theme: "本卷核心主题"
stage: "舞台环境描述"
chapter_range: "1-20"  # 本卷包含的章节范围
target_chapters: 20
target_words: 80000

# 阶段性成长（开头 vs 结尾的量化对比）
growth:
  position_start: "开头的职位/身份"
  position_end: "结尾的职位/身份"
  wealth_start: "开头的财富/股份状态"
  wealth_end: "结尾的财富/股份状态"
  reputation_start: "开头的声望"
  reputation_end: "结尾的声望"
  romance_start: "开头的感情阶段"
  romance_end: "结尾的感情阶段"

# 本卷主线（五段式结构）
main_arc:
  opening_challenge: "开局挑战描述"
  exploration: "发展与探索描述"
  escalation: "冲突升级描述"
  climax: "高潮事件描述"
  resolution_and_hook: "整合与钩子描述"

# 本卷新元素（至少其一）
new_elements:
  new_resources: ["新人脉/资金/信息"]
  new_projects: ["新项目/新商战"]
  new_enemies: ["新敌人"]

# 本卷关键节点
key_milestones:
  - chapter: 5
    event: "关键事件描述"
    impact: "对主线的影响"
  - chapter: 10
    event: "关键事件描述"
    impact: "对主线的影响"
  # ... 更多节点

# 本卷新增角色
new_characters:
  - id: "char_xxx"
    name: "角色名"
    role: "supporting"
    introduction_chapter: 3
    description: "简要描述"

# 本卷伏笔规划
hooks_to_plant:
  - id: "hook_xxx"
    description: "伏笔描述"
    plant_chapter: 2
    expected_payoff: "后续卷"

# 本卷需要回收的伏笔
hooks_to_resolve:
  - id: "hook_xxx"
    resolve_chapter: 18
    resolution: "回收方式"

# 本卷情感线
emotional_arcs:
  - character_id: "char_xxx"
    arc: "情感变化描述"
    peak_chapter: 15

# 本卷子线
subplots:
  - id: "subplot_xxx"
    name: "子线名"
    description: "子线描述"
    chapters_involved: [3, 5, 8, 12]

# 爽点归因（高潮胜利归因到哪些前期积累）
climax_payoff_sources:
  - "前期积累1"
  - "前期积累2"

# 节奏规划
pacing:
  slow_chapters: [1, 2, 6, 7]  # 日常/铺垫章
  fast_chapters: [5, 10, 15, 20]  # 高潮/冲突章
  cliffhanger_chapters: [5, 10, 15, 19]  # 需要章末钩子的章
```

只输出 YAML，不要其他文字。"""


def load_outline() -> str:
    """Load outline.md content."""
    path = BASE_DIR / "outline.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_world() -> str:
    path = BASE_DIR / "world.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_characters() -> str:
    path = BASE_DIR / "characters.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def gen_volume_plan(volume: int) -> dict:
    """Generate a volume plan using LLM."""
    genre = load_genre_for_project()
    proj = ProjectConfig(**load_json(STORY_DIR / "project.json"))
    outline = load_outline()
    world = load_world()
    characters = load_characters()

    # Load genre-specific volume plan fragments
    split_req = genre.get_prompt_fragment("volume_plan", "split_requirements")
    design_princ = genre.get_prompt_fragment("volume_plan", "design_principles")
    structure_req = genre.get_prompt_fragment("volume_plan", "structure_requirements")
    yaml_schema = genre.get_prompt_fragment("volume_plan", "yaml_schema")
    if not yaml_schema:
        yaml_schema = DEFAULT_YAML_SCHEMA
    yaml_schema = yaml_schema.format(volume=volume)

    # Load existing chapter summaries for context
    summaries_path = STORY_DIR / "state" / "chapter_summaries.json"
    summaries_data = load_json(summaries_path)
    recent_summaries = ""
    if summaries_data.get("summaries"):
        # Get last 5 summaries
        items = sorted(summaries_data["summaries"].items(), key=lambda x: x[0])
        recent = items[-5:] if len(items) > 5 else items
        recent_summaries = "\n".join(
            f"- Ch {v.chapter}: {v.summary}" for _, v in recent
        )

    prompt = f"""你是一位网文策划编辑，擅长规划百万字长篇网文的卷级结构。

请为第 {volume} 卷生成详细的卷级计划。

=== 项目信息 ===
标题: {proj.title or '(未设定)'}
类型: {proj.genre or '(未设定)'}
目标字数: {proj.target_words:,}
目标章节数: {proj.target_chapters}
每章目标字数: {proj.default_chapter_chars}

=== 总纲 ===
{outline if outline else '(未生成)'}

=== 世界设定 ===
{world[:3000] if world else '(未生成)'}

=== 角色 ===
{characters[:3000] if characters else '(未生成)'}

=== 已有章节摘要 ===
{recent_summaries or '(这是第一卷)'}

{split_req}

{design_princ}

{structure_req}

{yaml_schema}"""


    print(f"Generating volume {volume} plan...", file=sys.stderr)
    result = call_text_model(
        model=WRITER_MODEL,
        max_tokens=8000,
        temperature=0.7,
        system="你是一位网文策划编辑。只输出 YAML 格式的内容。",
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

    # Extract YAML from response (handle markdown code blocks)
    yaml_text = result.strip()
    if yaml_text.startswith("```"):
        lines = yaml_text.split("\n")
        # Remove first and last code block markers
        start = 1
        end = len(lines) - 1
        if lines[-1].strip() == "```":
            end = -1
        yaml_text = "\n".join(lines[start:end])

    return yaml_text


def main():
    parser = argparse.ArgumentParser(description="Generate volume-level plan")
    parser.add_argument("--volume", type=int, required=True, help="Volume number")
    args = parser.parse_args()

    yaml_text = gen_volume_plan(args.volume)

    # Save to file
    plan_path = STORY_DIR / "plans" / f"volume_{args.volume:03d}.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(yaml_text, encoding="utf-8")

    print(f"\nVolume plan saved to: {plan_path}")
    # print(yaml_text)


if __name__ == "__main__":
    main()
