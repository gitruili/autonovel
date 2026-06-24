# Prompt 模板：角色注册表 (characters.md)

> 源文件: `gen_characters.py` / `gen_characters_lf.py`
> System Prompt 角色: `system_prompts.character_designer`

---

## 短篇模式

### 输入变量
- `{genre.display_name}` — 类型中文名
- `{seed}` — seed.txt 内容
- `{world}` — world.md 内容
- `{voice_part2}` — voice.md 的 Part 2 部分
- `{genre.prompt_fragments.characters.requirements}` — 类型专属角色要求
- `{genre.prompt_fragments.characters.role_types}` — 类型专属角色类型

### Prompt

```
为这部{genre.display_name}网文构建一份完整的角色注册表（Character Registry）。
这是 CHARACTERS.MD —— 它是关于故事中每个人物的权威参考，
包括他们是谁、想要什么、怎么说话、藏着什么秘密。

种子概念 (SEED):
{seed}

生活设定集 (WORLD，这些角色生活的时代与社会):
{world}

文风标识 (VOICE，本小说的基调):
{voice_part2}

{genre.prompt_fragments.characters.requirements}

---

{genre.prompt_fragments.characters.role_types}

---

## 每个主要角色的输出模板

### [角色名]（[身份/定位]）

**外貌与身体**
- 姓名、年龄、身高、身份
- 外貌速写（3-4 句，具体、有画面感，不用套话）
- 声线/嗓音特征
- 衣着风格
- 标志性外貌细节

**驱动力链条**
- 处境 (SITUATION)：她/他目前的具体困境
- 欲望 (WANT)：她/他最想达到的外部目标
- 需求 (NEED)：她/他真正需要但不自知的东西
- 谎言 (LIE)：她/他心底的错误信念
- 弧光 (ARC)：从故事开头到结尾，这条信念链如何变化

**性格与行为**
- 性格核心（2-3 个关键词 + 解释）
- 底线/逆鳞（触碰了会爆发的点）
- 行事风格（先想还是先做？先信任还是先防备？）
- 身体习惯/小动作（至少 2 个）

**说话方式**
- 6 维度描述
- 3 句示例对话（分别展示日常、生气、心软三种状态）
- 口头禅（至少 1 句）
- 如果有口头禅，解释这句口头禅的来源或意义

**背景与羁绊**
- 家庭关系
- 关键过去事件（至少 1 个塑造性格的事件）
- 人脉关系

**能力与资源**
- 金手指/核心优势及局限
- 专业技能/教育背景
- 资产状况

**秘密**
- 至少 1 个读者不会立刻知道的事
- 这个秘密如果暴露，会怎么改变故事走向？

**关系网**
- 与每个相关角色的关系
- 哪些关系会在故事中发生转变？

**主题作用**
- 这个角色体现了故事的什么主题？

---

## 重要提示

- 主角的设定必须是最详尽的
- 角色必须互相咬合。一个角色的 WANT 应该与另一个角色的 WANT 冲突
- 配角设计铁律：每个配角的设定必须扎根于与主角的关系
- 对手不能纯坏——她们有自己的焦虑和处境
- 男主必须有自己的困境
- 对话要有身份感
- 每个角色的秘密必须是"一旦暴露就会改变至少一条关系线"的级别
- 目标字数约为 3000-4000 字
```

---

## 长篇模式

### 额外输入变量
- `{tags_context}` — 项目标签上下文

### 结构差异
长篇模式的角色注册表需要三层体系：

1. **核心角色（5-7人）** — 贯穿全书，最详细档案 + 长篇弧光规划
2. **卷级角色（15-25人）** — 分批登场/退场，标注登场卷号
3. **反派轮换表** — 4-6 层反派

### 输出格式
需要包含 HTML 注释标记（用于后续自动更新）：
- `<!-- CORE_PROFILES_START -->` / `<!-- CORE_PROFILES_END -->`
- `<!-- EARLY_PROFILES_START -->` / `<!-- EARLY_PROFILES_END -->`
- `<!-- ROLE_INDEX_START -->` / `<!-- ROLE_INDEX_END -->`
- `<!-- SPECIAL_CHARACTERS_START -->` / `<!-- SPECIAL_CHARACTERS_END -->`
- `<!-- SPECIAL_ROLES_START -->` / `<!-- SPECIAL_ROLES_END -->`
- `<!-- VILLAIN_ROSTER_START -->` / `<!-- VILLAIN_ROSTER_END -->`
- `<!-- APPEARANCE_PLAN_START -->` / `<!-- APPEARANCE_PLAN_END -->`

### 输出顺序
1. 核心角色详细档案
2. 卷1-3 角色详细档案
3. 角色索引表（卷4+角色，用表格）
4. 特殊人物
5. 特殊角色（非人物）
6. 反派轮换表
7. 角色登场计划表（YAML 格式）

---

## 输出文件
- `characters.md`（覆盖写入）
