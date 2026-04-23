#!/usr/bin/env python3
"""
One-shot characters.md generator for foundation phase.
Reads seed.txt + voice.md + world.md + CRAFT.md, calls writer model.
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
            "你是一位文学创作领域的角色设计师，深谙创伤/欲望/需求/谎言（Wound/Want/Need/Lie）框架、山德森三滑块理论（Sanderson's three sliders）以及对话辨识度理论。 "
            "你创作的角色应当像真实的人一样，拥有矛盾性、秘密和具有辨识度的说话方式。 "
            "你从不使用 AI 废话词汇。你使用简洁、直白的散文体写作。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

seed = (BASE_DIR / "seed.txt").read_text()
world = (BASE_DIR / "world.md").read_text()

# Voice Part 2 only
voice = (BASE_DIR / "voice.md").read_text()
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""为此奇幻小说构建一份完整的角色注册表（Character Registry）。这是 CHARACTERS.MD —— 
它是关于故事中“谁”存在的权威参考，包括他们的驱动力、说话方式以及携带的秘密。

种子概念 (SEED CONCEPT):
{seed}

世界设定集 (WORLD BIBLE，这些角色所处的世界):
{world}

语气标识 (VOICE IDENTITY，小说的基调):
{voice_part2}

角色创作要求 (CHARACTER CRAFT REQUIREMENTS):

### 山德森三滑块 (Sanderson's Three Sliders)
每个角色都有三个独立的拨盘 (0-10):
  主动性 (PROACTIVITY) —— 他们是驱动剧情还是被动反应？
  好感度 (LIKABILITY) —— 读者会产生共情吗？
  能力值 (COMPETENCE) —— 他们擅长自己所做的事吗？
规则：引人入胜的角色通常在至少两个维度上表现突出，或在一个维度表现突出且在其他维度有明显成长。

### 创伤 / 欲望 / 需求 / 谎言框架 (Wound / Want / Need / Lie)
因果链条：
  往事 (GHOST，背景事件) -> 创伤 (WOUND，持续的情感损伤) -> 谎言 (LIE，为了应对创伤而产生的错误信念)
    -> 欲望 (WANT，受谎言驱动的外部目标) -> 需求 (NEED，内心深处的真相，与谎言对立)
规则：欲望与需求必须处于矛盾状态。谎言可以用一句话表述，真相则是它的直接对立面。

### 对话辨识度 (8 个维度)
1. 词汇量水平  2. 句子长度  3. 缩写/正式程度
4. 语言癖好  5. 提问与陈述的比例  6. 插话模式
7. 隐喻领域  8. 直接与间接程度
测试：去掉对话标签（如“某某说”），读者是否仍能分辨出是谁在说话？

请至少包含以下角色来构建注册表：

1. **Cass Bellwright** (主角，视角人物)
   - 完整的“往事/创伤/欲望/需求/谎言”链条
   - 带有理由的三滑块分值
   - 弧光类型 (正向/负向/平淡)
   - 详细的说话模式 (8 个维度)
   - 身体习惯和下意识的小动作
   - 至少 2 个秘密
   - 核心关系图谱

2. **Eddan Bellwright** (父亲)
   - 与 Cass 同等的深度
   - 他与被封存的日志、颤抖的双手的关系
   - 他知道什么，以及他在隐藏什么

3. **Perin Bellwright** (兄弟) 
   - 尽管他在故事的大部分时间里不在场，但他需要完整的深度
   - 关于 Corda 合约究竟发生了什么
   - 他的“缺席式存在”

4. **Maret Corda** (对手)
   - 不是坏人 —— 而是利益与 Cass 冲突的人
   - 她自己的“往事/创伤/欲望/需求/谎言”（她应当是可以被理解的）

5. **Rector Suvaine** (学院院长)
   - 制度上的对手 —— 体系的化身
   - 她相信自己是在保护 Cantamura

6. **Torvald Hess** (Compact 领袖)
   - 体系之外的视角
   - 他在主题上代表了什么

7. **至少 1-2 个额外角色** 
   - 比如 Cass 在学院的同龄人/朋友？
   - House of Corda 中认识 Perin 的人？
   - 一位忠诚度动摇的宫廷歌手？

每个角色需包含：
- 姓名、年龄、角色定位
- 往事/创伤/欲望/需求/谎言链条（针对主要角色）
- 三滑块分值（主动性/好感度/能力值）及分值理由
- 弧光类型及轨迹
- 说话模式（全部 8 个维度，并附带示例文句）
- 身体外观（具体，而非通用化描述）
- 身体习惯和下意识的小动作
- 秘密（读者不会立即知道的事）
- 核心关系（与其他角色的关联）
- 主题作用（这个角色体现了什么问题？）

重要提示 (IMPORTANT):
- 角色必须互相关联。他们的欲望应当互相冲突。
- 每个秘密都应该是那种一旦揭开就会改变剧情走向的事。
- 说话模式必须足够独特，以通过“去标签化”测试。
- 为 Cass 赋予与其天赋相关的习惯（如疼痛、不断的倾听）。
- 父亲颤抖的手应当指向某些具体的事情。
- Maret Corda 应当像 Cass 一样丰满 —— 一个相称的对手。
- 目标字数约为 3000-4000 字。内容密集，严禁注水。
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "characters.md", "w", encoding="utf-8") as f:
    f.write(result)

