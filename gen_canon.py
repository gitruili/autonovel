#!/usr/bin/env python3
"""
gen_canon.py -- 设定准则数据库生成器（Foundation 阶段）。
从 world.md + characters.md + seed.txt 中提取所有硬性事实，生成 canon.md。
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
        temperature=0.2,
        system=genre.get_system_prompt("canon_editor"),
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

{genre.get_prompt_fragment("canon", "sections")}

每个类别下：
- 每个条目仅记录一个事实
- 在每个事实后的括号中注明来源（seed.txt / world.md / characters.md）

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
