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

def call_writer(prompt, max_tokens=16000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.5,
        system=genre.get_system_prompt("architect"),
        messages=[{"role": "user", "content": prompt}],
        timeout=900,
        include_beta=True,
    )

seed = (BASE_DIR / "seed.txt").read_text()
world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()
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
voice = (BASE_DIR / "voice.md").read_text()
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
outline_existing = (BASE_DIR / "outline.md").read_text()

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
{world[:6000]}

角色注册表 (CHARACTERS):
{characters[:6000]}

文风标识 (VOICE):
{voice_part2}

---

## 请生成第一卷的详细章节大纲

第一卷约 20 章，每章约 4000 字，总计约 8 万字。

### 逐章大纲格式

针对每一章，请按以下格式输出：

### 第 N 章: [标题]（标题要有网文感，能勾起好奇心）
- **核心推进:** 本章主要推进哪条线？（种田线 / 情感线 / 人际线 / 悬念线）
- **视角:** 女主第三人称有限视角
- **地点:** 具体的场景地点
- **% 进度:** 在全书中的位置（第一卷约占全书 0-8%）
- **情绪走向:** 开头情绪 → 结尾情绪
- **关键场景:** 3-5 个必须发生的具体场景（用一句话描述每个场景）
- **种田进展:** 本章中女主的经营/产业有什么具体进展？
- **情感进展:** 本章中女主与男主的关系有什么变化？
- **人际变动:** 本章中人际关系发生了什么变化？
- **伏笔植入:** 本章中埋下了什么线索？
- **伏笔回收:** 本章中回收了之前哪个伏笔？
- **章尾钩子:** 本章结尾留下什么悬念或期待感？
- **爽点/虐点:** 本章是否有情绪爆发点？
- **~目标字数:** 用于控制节奏

---

### 种田升级台账（第一卷范围）
| 台阶 | 内容 | 起始章 | 完成章 | 标志性事件 | 经济变化 |

### 情感线进度台账（第一卷范围）
| 阶段 | 描述 | 章节范围 | 标志性名场面 |

### 伏笔台账（第一卷范围）
| 线索 | 植入 (章) | 强化 (章) | 预计回收 (卷) | 类型 |

### 打脸/爽点台账（第一卷范围）
| 爽点 | 章节 | 被打脸的人 | 爽点描述 | 铺垫章节 |

---

## 约束条件

1. **种田线不能断**：第一卷必须有种田线的明确进展（至少从"无"到"第一台阶"）。
2. **情感线自然推进**：前5章只能有"初见"，不能有心动。第一卷结束时最多到"好奇"阶段。
3. **经济逻辑自洽**：每一笔收入和支出必须符合 world.md 中的物价体系。
4. **打脸必须有铺垫**：每个打脸场景之前，必须有至少1-2章的"被欺负"铺垫。
5. **章尾钩子必须有**：每一章的结尾都必须留下悬念或期待感。
6. **节奏张弛有度**：不能连续3章以上都是高强度冲突。至少有2-3章是"温馨日常"。
7. **第一卷结尾必须有钩子**：最后1-2章要留下悬念，驱动读者追第二卷。
8. **目标字数约 3500-4500 字/章**：前3章可以略短，高潮章节可以略长。

## 重要提示
- 只输出第一卷的20章大纲，不要输出其他卷
- 先输出逐章大纲，再输出4个台账
- 不要重复输出总纲中已有的内容
"""

print("正在生成第一卷详细大纲...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# Append to outline.md
with open(BASE_DIR / "outline.md", "a", encoding="utf-8") as f:
    f.write("\n\n---\n\n")
    f.write(result)

print(f"\n已追加到 outline.md", file=sys.stderr)
