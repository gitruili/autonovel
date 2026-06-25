#!/usr/bin/env python3
"""
gen_world_lf.py -- 长篇网文：生活设定集生成器（Foundation 阶段）。
读取 seed.txt，调用大模型，输出 world.md。
Part A: 核心设定（V1-3 范围，~3000词）
Part B: 扩展路线图（~2000词）
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project
from story_schema import load_project_tags

BASE_DIR = Path(__file__).parent
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
        temperature=0.7,
        system=genre.get_system_prompt("world_builder"),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
    )

seed = (BASE_DIR / "seed.txt").read_text(encoding="utf-8")
_, tags_context = load_project_tags()

prompt = f"""为这部**百万字长篇**{genre.display_name}网文构建一份完整的生活设定集。
这份文档分三部分：Part 0 是世界观速查表（结构化核心信息），Part A 是核心设定（卷1-3 立即需要的），Part B 是扩展路线图（后续卷需要的）。

{tags_context}

种子概念 (SEED):
{seed}

{genre.get_prompt_fragment("world", "requirements")}

---

## 输出顺序要求 (非常重要)

为了确保核心结构信息不被截断，请**严格按照以下顺序**输出：

# Part 0: 世界观速查表
提供给下游脚本快速读取的核心变量，必须用紧凑的表格形式展现：
1. **基础设定参数**：时代背景、核心货币体系（如铜钱/银子，或元/万/亿，必须与类型相符）、科技/文明阶段。
2. **扩展路线速查表**：预估在第几卷解锁的新地图或新阶层（3-4个条目）。
3. **金手指/系统速查表**（如有）：能力限制、核心代价、随卷号升级的方向。

---

# Part A: 核心设定（卷1-3 范围）

这是故事开始时立即需要的详细设定。作者写前60章时，都应当能从此部分找到所需的硬性细节。

{genre.get_prompt_fragment("world", "sections")}

## 关键 NPC 与势力
有影响力的人物及其利益诉求、关系网。

## 内部一致性规则（作者不可违反）
10-15 条硬性约束。

---

# Part B: 扩展路线图（卷4+ 的世界扩展规划）

这是百万字长篇独有的部分。随着故事推进，世界必须同步扩展。
每一个扩展锚点都要具体到可以直接用于写作的程度。

请按以下结构组织：

## 地理扩展锚点
定义 4-6 个后续会解锁的地点，每个标注"解锁卷号"：
  - 地点名称
  - 解锁卷号（大约在第几卷登场）
  - 与初始地点的距离和交通方式
  - 该地点的核心特征（规模、人口、经济水平、权力结构）
  - 该地点独有的规则或环境
  - 女主为什么需要去这里（剧情驱动力）

## 势力/层级扩展
定义 3-4 个后续卷会登场的新势力或层级：
  - 名称
  - 登场卷号
  - 类型
  - 与女主的关系（潜在助力/阻碍/中立）
  - 核心诉求
  - 女主与该势力/层级的博弈方式

## 世界观伏笔锚点
3-5 条世界级别的悬念，从卷1埋下、后续卷才揭示：
  - 伏笔内容
  - 埋设方式（自然融入日常描写，不能刻意）
  - 揭示卷号
  - 揭示后对剧情的影响

---

重要提示 (IMPORTANT):
- Part A 的详细度与短篇 world.md 完全一致——具体数字、具体规则、可直接用于写作
- Part B 的每个锚点也要具体——不能只说"后续会去某地"，要给出具体的名字、规模、环境差异
- 所有数据必须内部自洽
- 用简洁、干练的散文体写作。严禁AI废话
- Part A 目标 ~3000 字，Part B 目标 ~2000 字，总计 ~5000 字
- 两部分之间用明确的分隔线隔开
"""

print("正在生成长篇生活设定集...", file=sys.stderr)
result = call_writer(prompt)
# print(result)

# save to file
with open(BASE_DIR / "world.md", "w", encoding="utf-8") as f:
    f.write(result)

print(f"\n已保存到 world.md ({len(result)} 字符)", file=sys.stderr)
