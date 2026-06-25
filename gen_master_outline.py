#!/usr/bin/env python3
"""
gen_master_outline.py -- 长篇网文：全书总纲生成器（Foundation 阶段）。

这是长篇设定的核心"蓝图"脚本：
1. 它读取前期的基础设定（seed.txt + world_brief.md + characters_brief.md）。
2. 它从 project.json 动态计算全书卷数（通常为25卷）。
3. 它生成全书宏观走向（master_plan.yaml + master_summary.md）。
4. （注：在它生成后，backfill_foundation.py 会根据它的25卷蓝图，去反哺补全 world.md 和 characters.md 的后半段设定空白）。
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project
from story_schema import load_project_tags

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
PLANS_DIR = STORY_DIR / "plans"
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
        system=genre.get_system_prompt("architect_lf"),
        messages=[{"role": "user", "content": prompt}],
        timeout=900,
        include_beta=True,
    )

seed = (BASE_DIR / "seed.txt").read_text(encoding="utf-8")
world_path = BASE_DIR / "world_brief.md"
if not world_path.exists(): world_path = BASE_DIR / "world.md"
world = world_path.read_text(encoding="utf-8")

char_path = BASE_DIR / "characters_brief.md"
if not char_path.exists(): char_path = BASE_DIR / "characters.md"
characters = char_path.read_text(encoding="utf-8")
_, tags_context = load_project_tags()

# Read project config for targets
import json
proj_path = STORY_DIR / "project.json"
if proj_path.exists():
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = json.load(f)
    target_words = proj.get("target_words", 1_000_000)
    target_chapters = proj.get("target_chapters", 500)
    title = proj.get("title", "")
    genre_name = proj.get("genre", genre.display_name)
else:
    target_words = 1_000_000
    target_chapters = 500
    title = ""
    genre_name = genre.display_name

words_per_chapter = target_words // target_chapters
chapters_per_volume = 20
total_volumes = target_chapters // chapters_per_volume

# Load genre-specific volume design principles
volume_design_principles = genre.get_prompt_fragment("master_outline", "volume_design_principles")

prompt = f"""为这部**百万字长篇**{genre.display_name}网文构建一份全书总纲。
总纲是整部书的骨架——它定义了25卷的宏观走向，但不细化到每一章。

{tags_context}

种子概念 (SEED):
{seed}

生活设定集 (WORLD):
{world}

角色注册表 (CHARACTERS):
{characters}

---

## 目标参数
- 总字数：{target_words:,} 字
- 总章数：{target_chapters} 章
- 每章字数：约 {words_per_chapter} 字
- 总卷数：{total_volumes} 卷
- 每卷章数：约 {chapters_per_volume} 章

---

## 请输出两部分内容

### 第一部分：YAML 格式的结构化总纲

请严格按以下 YAML 结构输出（这是机器可读的格式，必须严格遵守）：

```yaml
title: "{title}"
genre: "{genre_name}"
tags: {json.dumps(proj.get("tags", []), ensure_ascii=False) if 'proj' in locals() and isinstance(proj, dict) else "[]"}
total_volumes: {total_volumes}
total_chapters: {target_chapters}
target_words: {target_words}

core_conflict: "一句话概括全书核心矛盾"

volumes:
  - volume: 1
    title: "卷标题（有网文感，4-8字）"
    chapter_range: "1-{chapters_per_volume}"
    main_arc: "本卷的核心剧情线（一句话）"
    key_turning_point: "本卷最关键的一个转折事件"
    antagonist: "本卷的主要对手（名字+身份）"
    romance_phase: "本卷感情线的阶段描述"
    foreshadow_planted: ["伏笔1", "伏笔2"]
    foreshadow_payoff: ["回收的伏笔（如有）"]
    emotional_tone: "本卷的情绪基调（如：紧张求生/温馨日常/虐心低谷/爽快逆袭）"
  - volume: 2
    ...
  # 共 {total_volumes} 卷

romance_arc:
  - phase: 1
    volumes: "1-3"
    description: "阶段描述"
    key_scenes: ["名场面1", "名场面2"]
  - phase: 2
    ...
  # 共 6 个阶段

antagonist_rotation:
  - tier: 1
    volumes: "1-3"
    antagonists: ["反派1（身份）", "反派2（身份）"]
    threat_type: "威胁类型"
    defeat_method: "退场方式"
  - tier: 2
    ...
  # 共 4-6 层

economy_milestones:
  - volume: 1
    milestone: "经济里程碑描述"
    income_level: "日/月/年收入量级"
  - volume: 5
    ...
  - volume: 10
    ...
  # 每5卷一个里程碑

long_foreshadows:
  - id: "lf_001"
    plant_volume: 1
    payoff_volume: 18
    description: "伏笔内容"
  - id: "lf_002"
    ...
  # 3-5条超长线伏笔
```

### 第二部分：人类可读的 Markdown 摘要

这部分写成 outline.md 的开头，供作者和其他脚本快速参考。
格式如下：

```markdown
# 《{title}》全书总纲

## 核心主线
[一句话核心矛盾]

## 卷级概览

### 第1卷：[标题]（第1-{chapters_per_volume}章）
**舞台环境**：[本卷主要活动区域]
**阶段目标**：[本卷女主要达成的核心目标]
**阶段成长**：
- 资产/权力：[量化的变化]
- 势力/人脉：[新增的底牌]
- 情感：[感情阶段]
**剧情概要**：
1. [开局挑战描述]
2. [发展与探索描述]
3. [冲突升级描述]
4. [高潮解决描述]
5. [整合与钩子描述]

...（请为这 {total_volumes} 卷中的每一卷都详细展开上述结构，不要偷懒缩略，充分展示每一卷的细节和爽点！）

## 感情线总规划
[6个阶段的简要描述]

## 反派轮换总规划
[4-6层反派的简要描述]

## 经济升级里程碑
| 卷号 | 里程碑 | 收入量级 |

## 超长线伏笔
| 编号 | 埋设卷号 | 回收卷号 | 内容 |
```

---

## 约束条件

1. **卷间节奏张弛有度**：不能连续3卷都是高强度冲突。至少每3-4卷有一卷"温馨日常"基调。
2. **资源/实力升级必须合理**：不论是经济、战力还是权势，从底层到顶层的每一级跳跃都要有具体的剧情事件支撑。
3. **反派退场要有逻辑**：反派不能"突然就输了"，每层反派的退场方式要与其类型匹配。
4. **感情线不能太快**：前3卷（60章）不能确认关系，要给读者足够的"磕糖"过程。
5. **伏笔回收要自然**：超长线伏笔回收时，读者应该有"原来如此！"而不是"这谁记得住"的感觉。
6. **每卷要有独立的小高潮**：每卷最后2-3章必须有一个本卷级别的高潮事件，让读者觉得"这一卷值了"。
7. **卷间衔接要有钩子**：每卷结尾要留下至少一个悬念，驱动读者追下一卷。

---

{volume_design_principles}

---

## 重要提示
- 先输出 YAML 部分（用 ```yaml 和 ``` 包裹），再输出 Markdown 部分
- YAML 部分必须是合法的 YAML 格式
- Markdown 部分应该尽可能详尽，不受字数限制，充分展示每一卷的剧情脉络。
- 你的输出上限已解锁至 32,000 Token，务必一口气写完 {total_volumes} 卷的详尽大纲，中途不要中断！
- 不要在 YAML 和 Markdown 之间添加额外说明文字
"""

print("正在生成全书总纲...", file=sys.stderr)
result = call_writer(prompt)
# print(result)

# Parse the result: split YAML and Markdown parts
# The LLM should output YAML first (in ```yaml block), then Markdown
yaml_content = ""
md_content = ""

import re

# Try to extract YAML block
yaml_match = re.search(r'```yaml\s*\n(.*?)```', result, re.DOTALL)
if yaml_match:
    yaml_content = yaml_match.group(1).strip()
    # Everything after the YAML block is the Markdown part
    md_start = result.find('```', yaml_match.end() + 1)
    if md_start == -1:
        md_content = result[yaml_match.end():].strip()
    else:
        md_content = result[yaml_match.end():].strip()
else:
    # Fallback: try to split by a clear separator
    # The YAML should come first, Markdown after
    parts = result.split('---', 1)
    if len(parts) == 2:
        yaml_content = parts[0].strip()
        md_content = parts[1].strip()
    else:
        # Last resort: treat the whole thing as both
        yaml_content = result
        md_content = result

# Clean up markdown content - remove leading ``` lines
md_content = re.sub(r'^```\w*\s*\n', '', md_content)
md_content = re.sub(r'\n```\s*$', '', md_content)

# Save YAML
PLANS_DIR.mkdir(parents=True, exist_ok=True)
with open(PLANS_DIR / "master_plan.yaml", "w", encoding="utf-8") as f:
    f.write(yaml_content)

# Save master_summary.md
with open(PLANS_DIR / "master_summary.md", "w", encoding="utf-8") as f:
    f.write(md_content)

# Rebuild compatibility layer outline.md
from outline_utils import rebuild_outline_compatibility_layer
rebuild_outline_compatibility_layer(BASE_DIR)

print(f"\n已保存 master_plan.yaml ({len(yaml_content)} 字符)", file=sys.stderr)
print(f"已保存 master_summary.md ({len(md_content)} 字符) 并重新拼装 outline.md", file=sys.stderr)
