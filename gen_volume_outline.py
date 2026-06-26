#!/usr/bin/env python3
"""
gen_volume_outline.py -- 长篇网文：单卷详细章节大纲生成器。
读取 seed.txt + world.md + characters.md + story/plans/master_plan.yaml + voice.md，
生成指定卷（~20章）的逐章大纲，追加到 outline.md。

Usage:
  uv run python gen_volume_outline.py --volume 1
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project
from story_schema import load_project_tags

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
PLANS_DIR = STORY_DIR / "plans"
load_dotenv(BASE_DIR / ".env")

genre = load_genre_for_project()

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)

def call_writer(prompt, max_tokens=32000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.5,
        system=genre.get_system_prompt("architect"),
        messages=[{"role": "user", "content": prompt}],
        timeout=900,
        include_beta=True,
    )

def main():
    parser = argparse.ArgumentParser(description="Generate volume-level detailed chapter outline")
    parser.add_argument("--volume", type=int, required=True, help="Volume number")
    args = parser.parse_args()
    volume = args.volume

    seed = (BASE_DIR / "seed.txt").read_text(encoding="utf-8")
    world_path = BASE_DIR / "world_brief.md"
    if not world_path.exists(): world_path = BASE_DIR / "world.md"
    world = world_path.read_text(encoding="utf-8")

    char_path = BASE_DIR / "characters_brief.md"
    if not char_path.exists(): char_path = BASE_DIR / "characters.md"
    characters = char_path.read_text(encoding="utf-8")
    _, tags_context = load_project_tags()

    # Load master plan
    import yaml
    master_plan_path = PLANS_DIR / "master_plan.yaml"
    if master_plan_path.exists():
        with open(master_plan_path, "r", encoding="utf-8") as f:
            master_plan = yaml.safe_load(f)
    else:
        print("ERROR: story/plans/master_plan.yaml not found. Run gen_master_outline.py first.", file=sys.stderr)
        return 1

    # Voice Part 2 only
    voice = (BASE_DIR / "voice.md").read_text(encoding="utf-8")
    voice_lines = voice.split('\n')
    part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
    voice_part2 = '\n'.join(voice_lines[part2_start:])

    # Get Volume info from master plan
    volumes_list = master_plan.get("volumes", [])
    if volume - 1 < len(volumes_list):
        vol_info = volumes_list[volume - 1]
    else:
        print(f"ERROR: Volume {volume} not found in master_plan.yaml.", file=sys.stderr)
        return 1

    v_title = vol_info.get("title", f"第{volume}卷")
    v_arc = vol_info.get("main_arc", "")
    v_turning = vol_info.get("key_turning_point", "")
    v_antagonist = vol_info.get("antagonist", "")
    v_romance = vol_info.get("romance_phase", "")
    v_tone = vol_info.get("emotional_tone", "")
    v_hooks_plant = vol_info.get("foreshadow_planted", [])
    v_hooks_payoff = vol_info.get("foreshadow_payoff", [])

    # Read existing outline.md (master summary + previous volumes)
    outline_existing = ""
    outline_path = BASE_DIR / "outline.md"
    if outline_path.exists():
        outline_existing = outline_path.read_text(encoding="utf-8")

    # If generating volume > 1, try to load previous volume's structure
    prev_vol_context = ""
    if volume > 1:
        prev_vol_md = PLANS_DIR / f"volume_{volume-1:03d}_outline.md"
        if prev_vol_md.exists():
            prev_vol_context = f"上一卷详细细纲参考（用于承接剧情）：\n{prev_vol_md.read_text(encoding='utf-8')[:3000]}\n...\n"

    target_chapters = 20
    chapter_range = vol_info.get("chapter_range", "")
    if chapter_range and "-" in chapter_range:
        parts = chapter_range.split("-")
        ch_start = int(parts[0])
        ch_end = int(parts[1])
        target_chapters = ch_end - ch_start + 1

    # Pre-load genre prompt fragments; conditionally skip empty ones
    # so prompts don't contain dangling section headers/separators.
    term_frag = genre.get_prompt_fragment("volume_plan", "terminology")
    dp_frag = genre.get_prompt_fragment("volume_plan", "design_principles")
    sr_frag = genre.get_prompt_fragment("volume_plan", "structure_requirements")
    cp_frag = genre.get_prompt_fragment("volume_plan", "conflict_patterns")
    ot_frag = genre.get_prompt_fragment("volume_plan", "output_template")
    cot_frag = genre.get_prompt_fragment("volume_plan", "chapter_output_template")
    lgr_frag = genre.get_prompt_fragment("outline", "ledgers")
    cnstr_frag = genre.get_prompt_fragment("outline", "constraints")

    # Build conditional sections — skip the surrounding markers if empty
    term_block = f"\n{term_frag}\n\n---" if term_frag else ""
    dp_sr_block = f"\n{dp_frag}\n\n{sr_frag}\n\n---" if (dp_frag or sr_frag) else ""
    cp_block = f"\n{cp_frag}\n\n---" if cp_frag else ""
    ot_block = f"\n\n### 卷纲骨架（先输出本卷宏观骨架）\n\n{ot_frag}" if ot_frag else ""
    cot_block = f"\n\n### 逐章大纲（核心输出，每章约 200-300 字）\n\n{cot_frag}" if cot_frag else ""
    lgr_block = f"\n{lgr_frag}\n\n---" if lgr_frag else ""
    cnstr_block = f"\n{cnstr_frag}" if cnstr_frag else ""

    prompt = f"""为这部**百万字长篇**{genre.display_name}网文生成**第 {volume} 卷**的详细章节大纲。
目标字数约 {target_chapters * 4000} 字，共约 {target_chapters} 章。

{tags_context}{term_block}

全书总纲与历史卷纲摘要（已有，不要重复输出宏观内容，保持专注在本卷）：
{outline_existing[:4000]}

{prev_vol_context}

本卷信息（来自总纲）：
- 卷标题：{v_title}
- 核心主线：{v_arc}
- 关键转折：{v_turning}
- 主要对手：{v_antagonist}
- 感情阶段：{v_romance}
- 情绪基调：{v_tone}
- 需要植入的伏笔：{', '.join(v_hooks_plant) if v_hooks_plant else '无'}
- 需要回收的伏笔：{', '.join(v_hooks_payoff) if v_hooks_payoff else '无'}

种子概念 (SEED):
{seed}

生活设定集 (WORLD):
{world}

角色注册表 (CHARACTERS):
{characters}

文风标识 (VOICE):
{voice_part2}{dp_sr_block}{cp_block}

## 请生成第 {volume} 卷的详细章节大纲

本卷约 {target_chapters} 章，每章约 4000 字。
如果是全书的起始卷，目标是快速入戏、建立读者追读习惯；如果是后续卷，注意与上一卷的平滑承接和矛盾升级。
{ot_block}{cot_block}{lgr_block}{cnstr_block}

8. **目标字数约 3500-4500 字/章**：铺垫章节可以略短，高潮章节可以略长。

## 重要提示
- 你的输出上限已解锁至 32,000 Token，**务必在单次回复中一口气写完完整的 {target_chapters} 章大纲，千万不要中途中断**。
- 先输出卷纲骨架（舞台环境/阶段目标/阶段成长/剧情概要），再输出逐章大纲，最后附上所有的台账。
- 逐章大纲必须使用"编号剧情点 + 情绪标签/爽点类型标签 + 三要素（发生了什么/为什么好看/推动什么）"的格式，不能使用旧的"关键场景: 3-5 个"格式。
- 每章至少包含 1 种明确的爽点类型。从冲突设计脚手架中选择合适的商战策略或情感推拉策略注入剧情。
- 每 3-5 章埋一个"炸弹"（远期威胁或近期危机），在 Hook 中暗示。
- 不要重复输出总纲中已有的宏观规划内容，只需输出本卷的详细纲要。

"""

    print(f"正在生成第 {volume} 卷详细大纲...", file=sys.stderr)
    result = call_writer(prompt)
    # print(result)

    # Write to volume_NNN_outline.md
    out_file = PLANS_DIR / f"volume_{volume:03d}_outline.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result)

    # Rebuild compatibility layer outline.md
    from outline_utils import rebuild_outline_compatibility_layer
    rebuild_outline_compatibility_layer(BASE_DIR)

    print(f"\n已保存 {out_file.name} 并拼装到 outline.md", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
