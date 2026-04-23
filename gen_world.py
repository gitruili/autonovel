#!/usr/bin/env python3
"""
One-shot world.md generator for foundation phase.
Reads seed.txt + voice.md, calls the writer model, outputs world.md content.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)

def call_writer(prompt, max_tokens=16000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.7,
        system=(
            "你是一位奇幻世界构建师，深谙山德森定律（Sanderson's Laws）、勒古恩（Le Guin）的散文哲学以及桌面角色扮演游戏（TTRPG）级别的设定设计。 "
            "你编写的世界设定集具有具体性、关联性，并能暗示出文字之外的深度。 "
            "你从不使用 AI 废话词汇（如：delve, tapestry, myriad, tapestry, shimmer 等）。 "
            "你用简洁、直白的散文体写作。每一条规则都有代价。每一个文化细节都暗含历史。 "
            "每一个地点都有其独特的感官特征。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

seed = (BASE_DIR / "seed.txt").read_text()
voice = (BASE_DIR / "voice.md").read_text()

# Extract voice Part 2 only (the novel-specific voice)
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""为此奇幻小说构建一份完整的世界设定集。这是 WORLD.MD 文件 —— 
它是这个世界中存在的一切事物的权威参考。作者应当能仅凭此文档解决任何世界观构建方面的问题。

种子概念 (SEED CONCEPT):
{seed}

语气标识 (VOICE IDENTITY，此小说的基调和语域):
{voice_part2}

创作要求 (CRAFT REQUIREMENTS，来自 CRAFT.md —— 请遵循这些要求):
- 魔法系统需要有明确的规则（HARD RULES），且必须符合山德森第二定律，包含“代价”和“局限性”
- 局限性在叙事中的重要性必须大于或等于能力本身
- 追踪魔法对社会、经济、法律和宗教的影响
- 至少深入探讨 2-3 个魔法带来的社会影响
- 历史必须产生驱动剧情的“现状矛盾”（PRESENT-DAY TENSIONS），而不仅仅是背景
- 地理描述必须具体且具有感官细节（不要通用的奇幻设定）
- 冰山原则：暗示的内容要多于直接陈述的内容
- 关联性：牵一发而动全身，各元素之间紧密交织

请按以下章节组织文档：

## 宇宙观与历史 (Cosmology & History)
重大事件的时间线。聚焦于产生现状矛盾的事件。
包括创世神话、关键转折点以及对剧情有影响的近期事件。

## 魔法系统 (Magic System)
### 硬规则 (律法)
具体、可测试的规则。音程如何作用，序列如何绑定。
违反规则会发生什么。必须突出显示代价和局限性。

### 软魔法 (Cass 的天赋)
他感知到了什么，它是如何运作的，对他个人而言具体的代价是什么。
这应该是神秘的，但具有前后一致的内部逻辑。

### 社会影响
魔法律法如何塑造：政体、商业、教育、阶级结构、犯罪、家庭生活、童年、衰老、残疾？

## 地理 (Geography)
Cantamura 的物理布局、各区域划分、天然大剧院的声学特性。
邻近地区（至少 2-3 个）。为每个地点提供感官特征。

## 派系与政治 (Factions & Politics)
谁掌握权力，谁渴求权力，谁被权力压迫。
至少包含 3-4 个利益冲突的派系。

## 动物 / 植物 / 自然界 (Bestiary / Flora / Natural World)
Cantamura 及其周边的自然世界有什么独特之处？

## 文化细节 (Cultural Details)
习俗、禁忌、节日、食物、服饰、成年礼。
让日常生活感到真实的具体细节。

## 内部一致性规则 (Internal Consistency Rules)
作者不可违反的硬性约束。这个世界中声音的物理特性。
什么是可能的，什么是不可能的。

重要提示 (IMPORTANT):
- 务必具体。不要说“城市有分区”，要命名它们，描述它们，赋予它们感官特征。
- 每一条规则在说明的同时，都必须注明其代价或局限。
- 每个章节包含 2-3 个未解释的事实，暗示更深层的系统（冰山深度）。
- 事实必须互联：魔法应当影响政治，地理应当影响文化，历史应当解释当前的派系冲突。
- 使用简洁、直白的散文体写作。严禁 AI 废话。不要用“丰富多彩的画卷（rich tapestry）”，不要用“深入探索（delving）”。
- 世界应当让人感到真实且有生活气息，而不是虚构出来的。思考：早餐闻起来是什么味道？孩子们玩什么？老人如何抱怨？
- 目标字数约为 3000-4000 字。内容密集，严禁注水。
"""

print("Calling writer model...", file=sys.stderr)
# print(prompt, file=sys.stderr)
result = call_writer(prompt)
print(result)
# save to file
with open(BASE_DIR / "world.md", "w", encoding="utf-8") as f:
    f.write(result)
