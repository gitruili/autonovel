#!/usr/bin/env python3
"""
gen_outline_part2.py -- 女频种田网文：大纲续写脚本。
当 gen_outline.py 因输出长度限制未完成全部章节时，本脚本续写剩余章节并追加到 outline.md。
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
        temperature=0.5,
        system=(
            "你是一位正在继续编写大纲的种田网文架构师。"
            "请使用与前述章节完全相同的格式进行编写。\n"
            "每一章都需要包含：核心推进、视角、地点、% 进度、情绪走向、"
            "关键场景、种田进展、情感进展、人际变动、伏笔植入、伏笔回收、"
            "章尾钩子、爽点/虐点、目标字数。\n"
            "确保续写的章节与前面的章节在节奏、伏笔、台阶升级上完美衔接。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
    )

part1 = open(BASE_DIR / 'outline.md').read()

# MYSTERY.md（如果存在）
mystery_path = BASE_DIR / "MYSTERY.md"
mystery = mystery_path.read_text() if mystery_path.exists() else ""

prompt = f"""这是一部女频种田网文大纲的前半部分。
大纲在某一章中途断开了。请从断开的地方继续，完成剩余章节，
然后补全以下台账（如果前半部分未包含）：

1. 种田升级台账
2. 情感线进度台账
3. 伏笔台账
4. 打脸/爽点台账

目前已完成的大纲：
{part1}

{"核心悬念 (仅供参考):" if mystery.strip() else ""}
{mystery}

续写要求：
- 使用与前面完全相同的逐章格式
- 种田线的升级台阶要与前面衔接（不能跳级，也不能重复）
- 情感线的推进要与前面的阶段衔接
- 伏笔的回收要与前面的植入对应
- 打脸/爽点必须有前面的铺垫
- 确保大结局章节有：事业高潮 + 感情确认 + 全部伏笔收束
- 最终章的情绪必须是"圆满+温暖"，但不能太完美——保留一丝"生活还在继续"的余韵
"""

print("正在续写大纲...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# append to outline.md
with open(BASE_DIR / "outline.md", "a", encoding="utf-8") as f:
    f.write("\n" + result)
