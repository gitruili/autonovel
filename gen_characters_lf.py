#!/usr/bin/env python3
"""
gen_characters_lf.py -- 长篇网文：角色注册表生成器（Foundation 阶段）。
读取 seed.txt + voice.md + world.md，调用大模型，输出 characters.md。
三层角色体系：核心角色（全卷在线）、卷级角色（分批登场）、反派轮换表。
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project
from story_schema import load_project_tags

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
        timeout=600,
    )

seed = (BASE_DIR / "seed.txt").read_text()
world = (BASE_DIR / "world.md").read_text()
_, tags_context = load_project_tags()

# Voice Part 2 only
voice = (BASE_DIR / "voice.md").read_text()
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""为这部**百万字长篇**{genre.display_name}网文构建一份完整的角色注册表。
这是 CHARACTERS.MD —— 它是关于故事中每个人物的权威参考。

百万字长篇的角色体系与短篇不同：角色需要分批登场、分批退场，
不能一次性把30个角色全部推到读者面前。

{tags_context}

种子概念 (SEED):
{seed}

生活设定集 (WORLD，这些角色生活的时代与社会):
{world}

文风标识 (VOICE):
{voice_part2}

---

{genre.get_prompt_fragment("characters", "role_types")}

---

## 角色体系架构

### 第一层：核心角色（始终在线，5-7 人）
这些角色贯穿全书每一卷。需要最详细的档案。

### 第二层：卷级角色（分批登场，15-25 人）
每个角色标注"登场卷号"和"退场卷号"（可为null表示长期留存）。
卷1-3 角色需要详细档案；卷4+ 角色只需简要档案。

### 第三层：反派轮换表
4-6 层反派，每层在不同卷号登场和退场。
每层反派不是"更大的坏人"，而是不同类型的威胁。

---

## 核心角色塑造要求

{genre.get_prompt_fragment("characters", "requirements")}

---

## 角色清单

### 第一层：核心角色（详细档案）

#### 1. 女主（主角，视角人物）—— 最高优先级
必须包含：
- 基本信息：姓名、年龄、身份、外貌（具体，不用套话）
- 穿越/重生前的身份与关键技能（如有）
- 驱动力链条：SITUATION → WANT → NEED → LIE → ARC
- 性格核心：底线、最怕什么、最擅长什么
- 说话方式（6 维度 + 3 句示例对话）
- 身体习惯和下意识小动作
- 至少 2 个秘密
- 金手指的使用习惯和心理
- **长篇弧光规划**：5-8 个阶段的弧光变化（对应多卷升级线的每个引擎）

#### 2. 男主 —— 高优先级
同上详细度，加：
- 真实身份（如有隐藏身份）
- 被女主吸引的具体原因
- 他的短板/缺陷
- **长篇弧光规划**

#### 3. 核心伙伴（2-3 人）—— 高优先级
始终在线的配角（如小叔子、忠仆、闺蜜等）。
每个需要完整档案 + 长篇弧光规划。

### 第二层：卷级角色

#### 卷1-3 角色（详细档案）
故事初期登场的角色，需要与核心角色同等详细度的档案。
包括：初期反派、初期助力、初期NPC。

#### 卷4+ 角色（简要档案）
后续卷才登场的角色，只需：
  - 姓名、身份、登场卷号、退场卷号（可为null）
  - 核心动机（一句话）
  - 与女主的关系（一句话）
  - 为什么在这个时间点登场（剧情驱动力）

请用表格形式列出卷4+角色：
| 角色ID | 姓名 | 身份 | 登场卷号 | 退场卷号 | 核心动机 | 与女主关系 |

### 第三层：反派轮换表

请用表格形式列出反派轮换：
| 层级 | 活跃卷号 | 反派名称 | 反派类型 | 核心动机 | 退场方式 | 对女主的威胁类型 |

反派类型参考：利益争夺型、权力压制型、理念冲突型、情感纠葛型、制度性压迫型
威胁类型参考：生存威胁、商业威胁、名誉威胁、人身安全、政治迫害

---

## 角色登场计划表

请用 YAML 格式列出每卷的活跃角色：
```yaml
volume_1_active: [char_女主id, char_男主id, char_核心伙伴1, char_核心伙伴2, char_卷1反派, ...]
volume_2_active: [char_女主id, char_男主id, char_核心伙伴1, char_核心伙伴2, char_新角色, ...]
volume_3_active: [...]
# ... 直到 volume_25
```

不需要列出全部25卷——列出前5卷（详细）和后续卷的大致规划即可。

---

## 每个核心角色的输出模板

### [角色名]（[身份/定位]）

**基本信息**
- 姓名、年龄、身份
- 外貌速写（3-4 句，具体、有画面感）

**驱动力链条**
- 处境 (SITUATION)
- 欲望 (WANT)
- 需求 (NEED)
- 谎言 (LIE)
- 弧光 (ARC)

**长篇弧光规划**
- 阶段1（卷1-3）：...
- 阶段2（卷4-7）：...
- 阶段3（卷8-12）：...
- ...（根据角色重要性，2-6个阶段）

**性格与行为**
- 性格核心
- 底线/逆鳞
- 身体习惯/小动作

**说话方式**
- 6 维度描述
- 3 句示例对话（日常、生气、心软）

**秘密**
- 至少 1 个
- 暴露后的影响

**关系网**
- 与每个相关角色的关系
- 哪些关系会转变？

**主题作用**

---

## 重要提示

- 核心角色不超过 7 人——百万字也不能角色太多，读者记不住
- 卷级角色每卷新增 2-4 人即可，不能一次性涌入大量新角色
- 反派轮换要自然——老反派退场和新反派登场之间要有过渡
- 角色的秘密必须是"一旦暴露就会改变至少一条关系线"的级别
- 所有角色的时代感必须与 WORLD 设定一致
- 目标字数：核心角色 ~3000 字 + 卷级角色 ~1500 字 + 反派轮换表 ~500 字 = 总计 ~5000 字
"""

print("正在生成长篇角色注册表...", file=sys.stderr)
result = call_writer(prompt)
print(result)

# save to file
with open(BASE_DIR / "characters.md", "w", encoding="utf-8") as f:
    f.write(result)

print(f"\n已保存到 characters.md ({len(result)} 字符)", file=sys.stderr)
