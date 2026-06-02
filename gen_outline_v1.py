#!/usr/bin/env python3
"""
gen_outline_v1.py -- 长篇网文：第一卷详细章节大纲生成器。
读取 seed.txt + world.md + characters.md + story/plans/master_plan.yaml + voice.md，
生成第一卷（~20章）的逐章大纲，追加到 outline.md。
"""
import os
import sys
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
    master_plan_yaml = yaml.dump(master_plan, allow_unicode=True, default_flow_style=False)
else:
    print("ERROR: story/plans/master_plan.yaml not found. Run gen_master_outline.py first.", file=sys.stderr)
    sys.exit(1)

# Voice Part 2 only
voice = (BASE_DIR / "voice.md").read_text(encoding="utf-8")
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

# Get V1 info from master plan
v1 = master_plan.get("volumes", [{}])[0] if master_plan.get("volumes") else {}
v1_title = v1.get("title", "第一卷")
v1_arc = v1.get("main_arc", "")
v1_turning = v1.get("key_turning_point", "")
v1_antagonist = v1.get("antagonist", "")
v1_romance = v1.get("romance_phase", "")
v1_tone = v1.get("emotional_tone", "")
v1_hooks_plant = v1.get("foreshadow_planted", [])
v1_hooks_payoff = v1.get("foreshadow_payoff", [])

# Read existing outline.md (master summary)
outline_existing = (BASE_DIR / "outline.md").read_text(encoding="utf-8")

prompt = f"""为这部**百万字长篇**{genre.display_name}网文生成**第一卷**的详细章节大纲。
这是全书的起始卷，目标是快速入戏、建立读者追读习惯。

{tags_context}

全书总纲摘要（已有，不要重复输出）：
{outline_existing[:3000]}

第一卷信息（来自总纲）：
- 卷标题：{v1_title}
- 核心主线：{v1_arc}
- 关键转折：{v1_turning}
- 主要对手：{v1_antagonist}
- 感情阶段：{v1_romance}
- 情绪基调：{v1_tone}
- 需要植入的伏笔：{', '.join(v1_hooks_plant) if v1_hooks_plant else '无'}
- 需要回收的伏笔：{', '.join(v1_hooks_payoff) if v1_hooks_payoff else '无'}

种子概念 (SEED):
{seed}

生活设定集 (WORLD):
{world}

角色注册表 (CHARACTERS):
{characters}

文风标识 (VOICE):
{voice_part2}

---

## 请生成第一卷的详细章节大纲

第一卷约 20 章，每章约 4000 字，总计约 8 万字。

### 逐章大纲格式

针对每一章，请按以下格式输出：

### 第 N 章: [标题]（标题要有网文感，能勾起好奇心）
- **核心推进:** 本章主要推进哪条线？
- **视角:** 女主第三人称有限视角
- **地点:** 具体的场景地点
- **% 进度:** 在全书中的位置（第一卷约占全书 0-8%）
- **情绪走向:** 开头情绪 → 结尾情绪
- **关键场景:** 3-5 个必须发生的具体场景（用一句话描述每个场景）
- **升级进展:** 本章中女主的逆袭/升级有什么具体进展？
- **情感进展:** 本章中女主与男主的关系有什么变化？
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

8. **目标字数约 3500-4500 字/章**：前3章可以略短，高潮章节可以略长。

## 重要提示
- 你的输出上限已解锁至 32,000 Token，**务必在单次回复中一口气写完完整的 20 章大纲，千万不要中途中断**。
- 先输出逐章大纲，最后附上所有的台账。
- 不要重复输出总纲中已有的内容。

"""

print("正在生成第一卷详细大纲...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# Write to volume_001_outline.md
with open(PLANS_DIR / "volume_001_outline.md", "w", encoding="utf-8") as f:
    f.write(result)

# Rebuild compatibility layer outline.md
from outline_utils import rebuild_outline_compatibility_layer
rebuild_outline_compatibility_layer(BASE_DIR)

print(f"\n已保存 volume_001_outline.md 并拼装到 outline.md", file=sys.stderr)
