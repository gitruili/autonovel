#!/usr/bin/env python3
"""
gen_canon.py -- 女频种田网文：设定准则数据库生成器（Foundation 阶段）。
从 world.md + characters.md + seed.txt 中提取所有硬性事实，生成 canon.md。
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
            "你是一位负责种田网文设定文档的连续性编辑，专门提取其中的硬性事实。"
            "你为人严谨、详尽，绝不编造源材料中没有的事实。"
            "每一条条目都必须能够追溯到原始文档中的具体陈述。"
            "你尤其擅长核查经济数据（物价、收入、成本）和时间线的一致性。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()
seed = (BASE_DIR / "seed.txt").read_text()

prompt = f"""请将这些策划文档中的每一个硬性事实提取到一个结构化的设定准则数据库（Canon Database）中。
"硬性事实"是指作者绝不能违反的任何内容：姓名、年龄、物价、地理、关系、已发生的事件、
金手指规则、社会礼法、季节农时等。

源文档：

=== SEED.TXT ===
{seed}

=== WORLD.MD ===
{world}

=== CHARACTERS.MD ===
{characters}

将输出格式化为 CANON.MD，包含以下类别：

## 经济与物价
- 货币换算、核心物价、税赋、商业规则
- 每个条目仅记录一个事实

## 地理与环境
- 地点、距离、气候、物产、布局
- 每个条目仅记录一个事实

## 时间线
- 故事发生的时代、关键事件的时间、角色的年龄
- 季节与农时的对应关系

## 金手指规则
- 金手指的能力、局限性、冷却期、使用条件
- 必须完整列出所有限制

## 角色事实
- 姓名、年龄、身份、外貌、说话特征、关系
- 每个条目仅记录一个事实（不要写成段落）

## 社会礼法
- 婚姻、分家、女性地位、立女户条件
- 官府法律、打官司流程

## 民俗与日常
- 饮食习惯、服饰规矩、节日习俗、忌讳
- 邻里人情规矩

## 内部一致性规则
- world.md 中列出的所有硬性约束
- 这些是"红线"——写正文时绝不可违反

规则：
- 每个要点仅包含一个事实。简洁、具体、可核对。
- 在每个事实后的括号中注明来源（seed.txt / world.md / characters.md）。
- 目标条数至少为 80-120 条。要详尽无遗。
- 如果两个文档提供的细节略有不同，请注明差异。
- 绝不编造事实。仅记录明确陈述的内容。
- 特别注意经济数据的交叉验证：收入、支出、物价、工钱是否自洽？
"""

print("正在生成设定准则数据库...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "canon.md", "w", encoding="utf-8") as f:
    f.write(result)
