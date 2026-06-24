# Prompt 模板：全书总纲 (master_plan.yaml + master_summary.md)

> 源文件: `gen_master_outline.py`
> System Prompt 角色: `system_prompts.architect_lf`
> 仅长篇模式使用

---

## 输入变量
- `{genre.display_name}` — 类型中文名
- `{tags_context}` — 项目标签上下文
- `{seed}` — seed.txt 内容
- `{world}` — world_brief.md 或 world.md 内容
- `{characters}` — characters_brief.md 或 characters.md 内容
- `{voice_part2}` — voice.md Part 2
- `{target_words}` — 目标总字数（通常 1,000,000）
- `{target_chapters}` — 目标总章数（通常 500）
- `{words_per_chapter}` — 每章字数
- `{total_volumes}` — 总卷数（通常 25）
- `{chapters_per_volume}` — 每卷章数（通常 20）
- `{title}` — 小说标题
- `{genre_name}` — 类型名
- `{volume_design_principles}` — 类型专属卷设计原则

## Prompt

```
为这部**百万字长篇**{genre.display_name}网文构建一份全书总纲。
总纲是整部书的骨架——它定义了25卷的宏观走向，但不细化到每一章。

{tags_context}

种子概念 (SEED):
{seed}

生活设定集 (WORLD):
{world}

角色注册表 (CHARACTERS):
{characters}

文风标识 (VOICE):
{voice_part2}

---

## 目标参数
- 总字数：{target_words} 字
- 总章数：{target_chapters} 章
- 每章字数：约 {words_per_chapter} 字
- 总卷数：{total_volumes} 卷
- 每卷章数：约 {chapters_per_volume} 章

---

## 请输出两部分内容

### 第一部分：YAML 格式的结构化总纲

请严格按以下 YAML 结构输出：

title: "{title}"
genre: "{genre_name}"
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
    emotional_tone: "本卷的情绪基调"
  # 共 {total_volumes} 卷

romance_arc:
  - phase: 1
    volumes: "1-3"
    description: "阶段描述"
    key_scenes: ["名场面1", "名场面2"]
  # 共 6 个阶段

antagonist_rotation:
  - tier: 1
    volumes: "1-3"
    antagonists: ["反派1（身份）"]
    threat_type: "威胁类型"
    defeat_method: "退场方式"
  # 共 4-6 层

economy_milestones:
  - volume: 1
    milestone: "经济里程碑描述"
    income_level: "日/月/年收入量级"
  # 每5卷一个里程碑

long_foreshadows:
  - id: "lf_001"
    plant_volume: 1
    payoff_volume: 18
    description: "伏笔内容"
  # 3-5条超长线伏笔

### 第二部分：人类可读的 Markdown 摘要

# 《{title}》全书总纲

## 核心主线
[一句话核心矛盾]

## 卷级概览
### 第1卷：[标题]（第1-{chapters_per_volume}章）
**舞台环境**：...
**阶段目标**：...
**阶段成长**：...
**剧情概要**：...
...（为 {total_volumes} 卷每一卷都详细展开）

---

## 约束条件

1. 卷间节奏张弛有度
2. 资源/实力升级必须合理
3. 反派退场要有逻辑
4. 感情线不能太快——前3卷（60章）不能确认关系
5. 伏笔回收要自然
6. 每卷要有独立的小高潮
7. 卷间衔接要有钩子

{volume_design_principles}

---

## 重要提示
- 先输出 YAML 部分，再输出 Markdown 部分
- YAML 部分必须是合法的 YAML 格式
- Markdown 部分应该尽可能详尽，充分展示每一卷的剧情脉络
```

---

## 输出文件
- `story/plans/master_plan.yaml`（YAML 部分）
- `story/plans/master_summary.md`（Markdown 部分）
- 然后运行 `uv run python -c "from outline_utils import rebuild_outline_compatibility_layer; rebuild_outline_compatibility_layer(Path('.'))"` 重建 outline.md
