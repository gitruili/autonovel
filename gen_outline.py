#!/usr/bin/env python3
"""Generate outline.md from seed + world + characters + mystery + craft."""
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
            "你是一位小说架构师，深谙《救猫咪》（Save the Cat）节拍、山德森（Sanderson）情节设计原则、丹·哈蒙（Dan Harmon）的故事圆环以及 MICE 商数（MICE Quotient）。 "
            "你构建的大纲应当足以让作者直接进行初稿撰写，而无需在过程中即兴设计结构。 "
            "每一章都包含节拍、情感弧光和尝试-失败循环（try-fail cycle）类型。 "
            "你从不使用 AI 废话词汇。你使用简洁、直白的散文体写作。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
        include_beta=True,
    )

seed = (BASE_DIR / "seed.txt").read_text()
world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()
mystery = (BASE_DIR / "MYSTERY.md").read_text()
craft = (BASE_DIR / "CRAFT.md").read_text()

# Voice Part 2 only
voice = (BASE_DIR / "voice.md").read_text()
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""为此奇幻小说构建一份完整的章节大纲。目标：22-26 章，
总字数约 80,000 字（每章约 3,000-4,000 字）。

种子概念 (SEED CONCEPT):
{seed}

核心悬念 (THE CENTRAL MYSTERY，仅供作者参考 —— 读者将逐渐发现):
{mystery}

世界设定集 (WORLD BIBLE):
{world}

角色注册表 (CHARACTER REGISTRY):
{characters}

语气标识 (VOICE，基调和语域):
{voice_part2}

创作参考 (CRAFT REFERENCE，需遵循的结构):
{craft}

请按以下要求构建大纲：

## 幕后结构 (Act Structure)
规划第一幕 (0-23%)、第二幕第一部分 (23-50%)、第二幕第二部分 (50-77%)、第三幕 (77-100%)。
注明小说关键节点的百分比标记。

## 逐章大纲 (Chapter-by-Chapter Outline)

针对每一章，提供：
### 第 N 章: [标题]
- **POV:** (始终为 Cass，第三人称限制视角)
- **地点:** 具体的区域/地点
- **救猫咪节拍:** 本章服务的节拍（开场画面、铺垫、催化剂等）
- **% 进度:** 在小说中所处的位置
- **情感弧光:** 初始情感 → 结束情感
- **尝试-失败循环:** 是-但是 (Yes-but) / 否-而且 (No-and) / 否-但是 (No-but) / 是-而且 (Yes-and)
- **情节节拍:** 3-5 个必须发生的具体场景节拍
- **伏笔植入 (Plants):** 本章中植入的伏笔元素
- **伏笔回收 (Payoffs):** 在本章得到回收的伏笔元素
- **角色变动:** 到本章结束时，Cass（或其他角色）发生了什么变化
- **谎言:** Cass 的谎言（“如果我精通这套体制，我就能从内部解决问题”）在本章中是如何被强化或挑战的
- **~目标字数:** 用于控制节奏

## 伏笔台账 (Foreshadowing Ledger)

一个跟踪所有植入线索的表格：
| 线索 | 植入 (章节) | 强化 (章节) | 回收 (章节) | 类型 |

至少包含 15 条线索。类型包括：实物、对话、行动、象征、结构。

核心情节架构：

第一幕 (约 1-6 章): 建立 Cass 的世界、他的痛苦、他的天赋、学院以及他的家庭。
尽早植入悬念（上锁的房间、禁忌之钟、父亲的颤抖）。
催化剂：某些事迫使 Cass 去调查 Perin 的合约。

第二幕第一部分 (约 7-12 章): 调查阶段。Cass 深入挖掘 Corda 合约，遇到 Maret，与 Torvald 和 Lenne 结盟，开始更清晰地听到谐波。
中点 (Midpoint): Cass 了解到了一个改变他行动方式的部分真相（虚假的胜利或失败）。

第二幕第二部分 (约 13-18 章): 压力增大。Maret 对 Bellwrights 采取行动。
父亲的秘密开始浮出水面。Cass 的谎言越来越难以为继。
跌入谷底 (All Is Lost): Cass 与父亲对峙并得知了全部真相。

第三幕 (约 19-24 章): Cass 理解了那个问题。必须选择如何回答。
高潮戏将利用已确立的“律法”音程展开。
结局展示他选择后的余波。

约束条件：
- 高潮部分必须能利用已确立的“律法”音程在机械逻辑上得到解决。
- Cass 的调查应当感觉像是一个叠加在成长小说弧光上的悬念/推理情节。
- 稳定性陷阱：坏事必须保持糟糕的状态。并非所有事情都能圆满解决。
- Perin 必须在某个时刻亲自现身（而不仅仅是在记忆或信件中）。
- 至少有 3 章应该是“安静”的 —— 聚焦于角色、低动作量、情感丰富。
- 改变尝试-失败循环的类型：60% 以上应该是“是-但是”或“否-而且”。
- 伏笔台账中的“植入”到“回收”之间必须至少间隔 3 章。
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "outline.md", "w", encoding="utf-8") as f:
    f.write(result) 
