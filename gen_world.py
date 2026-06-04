#!/usr/bin/env python3
"""
gen_world.py -- 生活设定集生成器（Foundation 阶段）。
读取 seed.txt + voice.md，调用大模型，输出 world.md（时代背景与社会经济设定）。
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
        system=genre.get_system_prompt("world_builder"),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

seed = (BASE_DIR / "seed.txt").read_text(encoding="utf-8")
voice = (BASE_DIR / "voice.md").read_text(encoding="utf-8")

# Extract voice Part 2 only (the novel-specific voice)
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""为这部{genre.display_name}网文构建一份完整的世界观设定集。这是 WORLD.MD 文件——
它是这个故事发生的时代背景、社会规则、商业环境和经济体系的权威参考。
作者写任何一个场景时，都应当能从此文档中找到所需的硬性细节，
不需要临时编造不确定的设定。

种子概念 (SEED):
{seed}

语气标识 (VOICE，此小说的基调):
{voice_part2}

{genre.get_prompt_fragment("world", "requirements")}

{genre.get_prompt_fragment("world", "sections")}

重要提示 (IMPORTANT):
- 务必具体。不要说"公司规模很大"，要给出具体年营收、员工数、估值。
- 所有经济数据必须内部自洽：股权比例、收购价格、交易金额、资产规模——
  这些数字必须前后对得上，不能出现"100亿收购的公司反而不如一个500万的项目值钱"。
- 社会规则（家族规矩、商业潜规则、社交圈层的进入门槛）既要制造压力，
  又要留有缝隙（让主角能用智慧找到突破口）。
- 用简洁、干练的散文体写作。严禁AI废话。
  不要用"丰富多彩""博大精深""源远流长"这类空话。
- 目标字数约为 3000-4000 字。内容密集，严禁注水。
  每一条设定都必须是作者写正文时"查得到、用得上"的硬性细节。
"""

print("正在生成生活设定集...", file=sys.stderr)
print(prompt)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "world.md", "w", encoding="utf-8") as f:
    f.write(result)
