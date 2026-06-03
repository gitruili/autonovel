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

    prompt = f"""为这部**百万字长篇**{genre.display_name}网文生成**第 {volume} 卷**的详细章节大纲。
目标字数约 {target_chapters * 4000} 字，共约 {target_chapters} 章。

{tags_context}

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
{voice_part2}

---

## 请生成第 {volume} 卷的详细章节大纲

本卷约 {target_chapters} 章，每章约 4000 字。
如果是全书的起始卷，目标是快速入戏、建立读者追读习惯；如果是后续卷，注意与上一卷的平滑承接和矛盾升级。

### 逐章大纲格式

针对每一章，请按以下格式输出：

### 第 N 章: [标题]（标题要有网文感，能勾起好奇心）
- **核心推进:** 本章主要推进哪条线？
- **视角:** 第三/第一人称有限视角（主要角色）
- **地点:** 具体的场景地点
- **情绪走向:** 开头情绪 → 结尾情绪
- **关键场景:** 3-5 个必须发生的具体场景（用一句话描述每个场景）
- **升级进展:** 本章中主角的逆袭/升级有什么具体进展？
- **情感进展:** 本章中主角的核心感情线/羁绊有什么变化？
- **人际变动:** 本章中人际关系发生了什么变化？
- **伏笔植入:** 本章中埋下了什么线索？
- **伏笔回收:** 本章中回收了之前哪个伏笔？
- **章尾钩子:** 本章结尾留下什么悬念或期待感？
- **爽点/虐点:** 本章是否有情绪爆发点？
- **~目标字数:** 用于控制节奏

---

{genre.get_prompt_fragment("outline", "ledgers")}

---

{genre.get_prompt_fragment("outline", "constraints")}

8. **目标字数约 3500-4500 字/章**：铺垫章节可以略短，高潮章节可以略长。

## 重要提示
- 你的输出上限已解锁至 32,000 Token，**务必在单次回复中一口气写完完整的 {target_chapters} 章大纲，千万不要中途中断**。
- 先输出逐章大纲，最后附上所有的台账。
- 不要重复输出总纲中已有的宏观规划内容，只需输出本卷的详细纲要。

"""

    print(f"正在生成第 {volume} 卷详细大纲...", file=sys.stderr)
    result = call_writer(prompt)
    print(result)

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
