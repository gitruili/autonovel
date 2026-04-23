#!/usr/bin/env python3
"""
Generate canon.md by extracting all hard facts from world.md + characters.md.
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
        temperature=0.2,
        system=(
            "你是一位负责奇幻小说策划文档的连续性编辑，专门提取其中的硬性事实（hard facts）。 "
            "你为人严谨、详尽，绝不编造源材料中没有的事实。 "
            "每一条条目都必须能够追溯到原始文档中的具体陈述。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()
seed = (BASE_DIR / "seed.txt").read_text()

prompt = f"""请将这些策划文档中的每一个硬性事实提取到一个结构化的设定准则数据库（Canon Database）中。
“硬性事实”是指作者绝不能违反的任何内容：姓名、年龄、日期、物理描述、魔法系统规则、地理、关系、已发生的事件。

源文档：

=== SEED.TXT ===
{seed}

=== WORLD.MD ===
{world}

=== CHARACTERS.MD ===
{characters}

将输出格式化为 CANON.MD，包含以下类别：

## 地理 (Geography)
- 关于地点、距离、物理属性的具体事实

## 时间线 (Timeline)
- 带有日期的事件、年龄、持续时间

## 魔法系统规则 (Magic System Rules)
- 律法的硬性规则（音程、代价、局限性）
- Cass 的天赋细节

## 角色事实 (Character Facts)
- 年龄、物理描述、习惯、关系
- 每个条目仅记录一个事实（不要写成段落）

## 政治 / 派系 (Political / Factional)
- 谁控制什么、联盟、冲突、合约

## 文化 (Cultural)
- 习俗、禁忌、法律、节日、饮食、服饰

## 故事中已确立的内容 (Established In-Story)
- 故事背景中已经发生的事件
- Perin 合约、扩张战争（Expansion Wars）等

规则：
- 每个要点仅包含一个事实。简洁、具体、可核对。
- 在每个事实后的括号中注明来源（world.md 或 characters.md）。
- 目标条数至少为 80-120 条。要详尽无遗。
- 如果两个文档提供的细节略有不同，请注明差异。
- 绝不编造事实。仅记录明确陈述的内容。
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "canon.md", "w", encoding="utf-8") as f:
    f.write(result)
