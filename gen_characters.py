#!/usr/bin/env python3
"""
gen_characters.py -- 角色注册表生成器（Foundation 阶段）。
读取 seed.txt + voice.md + world.md，调用大模型，输出 characters.md。
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project

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
        system=genre.get_system_prompt("character_designer"),
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

prompt = f"""为这部{genre.display_name}网文构建一份完整的角色注册表（Character Registry）。
这是 CHARACTERS.MD —— 它是关于故事中每个人物的权威参考，
包括他们是谁、想要什么、怎么说话、藏着什么秘密。

种子概念 (SEED):
{seed}

生活设定集 (WORLD，这些角色生活的时代与社会):
{world}

文风标识 (VOICE，本小说的基调):
{voice_part2}

{genre.get_prompt_fragment("characters", "requirements")}

---

{genre.get_prompt_fragment("characters", "role_types")}

---

## 每个主要角色的输出模板

### [角色名]（[身份/定位]）

**基本信息**
- 姓名、年龄、身份
- 外貌速写（3-4 句，具体、有画面感，不用套话）

**驱动力链条**
- 处境 (SITUATION)：她/他目前的具体困境
- 欲望 (WANT)：她/他最想达到的外部目标
- 需求 (NEED)：她/他真正需要但不自知的东西
- 谎言 (LIE)：她/他心底的错误信念
- 弧光 (ARC)：从故事开头到结尾，这条信念链如何变化

**性格与行为**
- 性格核心（2-3 个关键词 + 解释）
- 底线/逆鳞（触碰了会爆发的点）
- 身体习惯/小动作（至少 2 个）

**说话方式**
- 6 维度描述
- 3 句示例对话（分别展示日常、生气、心软三种状态）
- 口头禅（如有）

**秘密**
- 至少 1 个读者不会立刻知道的事
- 这个秘密如果暴露，会怎么改变故事走向？

**关系网**
- 与每个相关角色的关系（用一句话概括）
- 哪些关系会在故事中发生转变？

**主题作用**
- 这个角色体现了故事的什么主题？

---

## 重要提示

- 角色必须互相咬合。一个角色的 WANT 应该与另一个角色的 WANT 冲突。
- 对手不能纯坏——她们有自己的焦虑和处境，只是处理方式令人发指。
- 男主必须有自己的困境，且他的困境和主角的故事线有交集。
- 对话要有"时代感"——村妇不会说"赋能"，书生不会说"搞定"。
  但也不要写成文言文，要像人说话。
- 每个角色的秘密必须是那种"一旦暴露就会改变至少一条关系线"的级别。
- 目标字数约为 3000-4000 字。内容密集，严禁注水。
"""

print("正在生成角色注册表...", file=sys.stderr)
print(prompt)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "characters.md", "w", encoding="utf-8") as f:
    f.write(result)
