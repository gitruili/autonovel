#!/usr/bin/env python3
"""
gen_outline.py -- 章节大纲生成器（Foundation 阶段）。
读取 seed.txt + world.md + characters.md + MYSTERY.md + voice.md，
调用大模型，输出 outline.md。
题材结构、约束条件、台账模板均从 genre config 动态读取。
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
        temperature=0.5,
        system=genre.get_system_prompt("architect"),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
        include_beta=True,
    )

seed = (BASE_DIR / "seed.txt").read_text(encoding="utf-8")
world = (BASE_DIR / "world.md").read_text(encoding="utf-8")
characters = (BASE_DIR / "characters.md").read_text(encoding="utf-8")

# MYSTERY.md（如果存在）
mystery_path = BASE_DIR / "MYSTERY.md"
mystery = mystery_path.read_text(encoding="utf-8") if mystery_path.exists() else ""

# Voice Part 2 only
voice = (BASE_DIR / "voice.md").read_text(encoding="utf-8")
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

# --- 题材专属结构、约束、台账（从 genre config 动态读取）---
outline_structure = genre.get_prompt_fragment("outline", "structure")
outline_constraints = genre.get_prompt_fragment("outline", "constraints")
outline_ledgers = genre.get_prompt_fragment("outline", "ledgers")

# 兜底：如果 genre config 未定义，使用通用结构
if not outline_structure:
    outline_structure = """### 整体结构

请根据本作品的核心线索（事业线 + 感情线 + 家庭/权力线）规划全书的起承转合，
确保每一幕都有明确的目标、冲突和高潮。"""
if not outline_constraints:
    outline_constraints = """1. 事业线不能断：不能连续 3 章以上没有事业/升级内容的推进。
2. 情感线自然推进：男女主感情发展必须有合理过程，不能跳跃。
3. 打脸必须有铺垫：每个打脸/逆袭场景之前，必须有至少 1-2 章的铺垫。
4. 章尾钩子必须有：每一章的结尾都必须留下悬念或期待感。
5. 节奏张弛有度：不能连续 3 章以上都是高强度冲突。
6. 配角不是工具人：反派每次出场不能只是"来找麻烦"。
7. 金手指使用有节制：金手指不能每章都用，不能每次都完美解决问题。"""
if not outline_ledgers:
    outline_ledgers = """### 事业/升级台账
| 台阶 | 内容 | 起始章 | 完成章 | 标志性事件 | 身份/地位变化 |

### 情感线进度台账
| 阶段 | 描述 | 章节范围 | 标志性名场面 |

### 伏笔台账
| 线索 | 植入 (章) | 强化 (章) | 回收 (章) | 类型 |

### 打脸/爽点台账
| 爽点 | 章节 | 被打脸的人 | 爽点描述 | 铺垫章节 |"""

prompt = f"""为这部{genre.display_name}网文构建一份完整的章节大纲。
目标：20-24 章，总字数约 8-10 万字（每章约 3,500-4,500 字）。

种子概念 (SEED):
{seed}

{"核心悬念 (MYSTERY，仅供架构师参考，读者将逐渐发现):" if mystery.strip() else ""}
{mystery}

生活设定集 (WORLD):
{world}

角色注册表 (CHARACTERS):
{characters}

文风标识 (VOICE):
{voice_part2}

---

## 大纲构建要求

{outline_structure}

---

### 逐章大纲格式

针对每一章，提供：

### 第 N 章: [标题]（标题要有网文感，能勾起好奇心）
- **核心推进:** 本章主要推进哪条线？（事业线 / 情感线 / 权力线 / 悬念线 / 人际线）
- **视角:** 第三人称有限视角
- **地点:** 具体的场景地点
- **% 进度:** 在全书中所处的位置
- **情绪走向:** 开头情绪 → 结尾情绪
- **关键场景:** 3-5 个必须发生的具体场景（用一句话描述每个场景）
- **事业/地位进展:** 本章中女主的事业、地位、资产有什么具体进展？（如本章无此内容则写"无"）
- **情感进展:** 本章中女主与男主的关系有什么变化？（如本章无情感内容则写"无"）
- **人际变动:** 本章中人际关系发生了什么变化？谁的态度转变了？
- **伏笔植入:** 本章中埋下了什么线索？
- **伏笔回收:** 本章中回收了之前哪个伏笔？
- **章尾钩子:** 本章结尾留下什么悬念或期待感？（这是读者继续看下一章的理由）
- **爽点/虐点:** 本章是否有打脸、心动、委屈、感动等情绪爆发点？如有，用一句话描述
- **~目标字数:** 用于控制节奏

---

{outline_ledgers}

---

## 约束条件

{outline_constraints}
"""

print("正在生成章节大纲...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "outline.md", "w", encoding="utf-8") as f:
    f.write(result)
