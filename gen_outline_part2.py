#!/usr/bin/env python3
"""Generate remaining chapters + foreshadowing ledger."""
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
            "你是一位正在继续编写大纲的小说架构师。请使用与前述章节完全相同的格式进行编写。 "
            "每一章都需要包含：POV（视角）、地点、救猫咪节拍、% 进度、情感弧光、尝试-失败循环、情节节拍、伏笔植入、伏笔回收、角色变动、谎言、目标字数。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
    )

part1 = open('/tmp/outline_output.md').read()
mystery = (BASE_DIR / "MYSTERY.md").read_text()

prompt = f"""这是《钟鸣之家次子》（The Second Son of the House of Bells）24 章大纲的前 17 章。
大纲在第 17 章中途断开了。请从断开的地方继续，然后完成第 18-24 章，最后编写伏笔台账（Foreshadowing Ledger）。

目前已完成的大纲：
{part1}

核心悬念 (仅供参考):
{mystery}

剩余所需的结构：

第 17 章 (补全它): 与 Maret 的对峙 —— 她揭露了关于虚空（void）的真相
第 18 章: 灵魂暗夜 (Dark Night of the Soul) —— Cass 消化他所学到的东西
第 19 章: 突破进入第三幕 (Break Into Three) —— 新的信息或视角改变了一切
第 20-21 章: 集结力量，制定计划
第 22 章: 钟楼高潮 —— Cass 回答了那个问题
第 23 章: 余波与结局
第 24 章: 最终画面 (与开场画面相呼应)

然后编写：

## 伏笔台账 (Foreshadowing Ledger)

| # | 线索 | 植入 (章节) | 强化 (章节) | 回收 (章节) | 类型 |
|---|--------|-------------|-----------------|-------------|------|

至少包含 15 条线索。类型包括：实物、对话、行动、象征、结构。
“植入”到“回收”之间必须至少间隔 3 章。

请记住：
- 高潮部分使用第四个选项：Cass 将“问题”放大到可听见的范围，以便全城都能听到并自行回答。
- 这并不会直接解救 Perin（稳定性陷阱 —— 并非所有事情都能圆满解决）。
- 到高潮部分时，Cass 的谎言必须被彻底击碎。
- 最终画面应当与第 1 章的开场画面形成镜像，但要展示出转化后的状态。
- 后半部分至少要有一个安静的章节。
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "outline_part2.md", "w", encoding="utf-8") as f:
    f.write(result)
