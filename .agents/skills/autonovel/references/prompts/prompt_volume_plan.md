# Prompt 模板：卷级计划 (volume_NNN.yaml)

> 源文件: `gen_volume_plan.py`
> System Prompt: `"你是一位网文策划编辑。只输出 YAML 格式的内容。"`

---

## 输入变量
- `{volume}` — 卷号
- `{proj.title}` — 小说标题
- `{proj.genre}` — 类型名
- `{proj.target_words}` — 目标字数
- `{proj.target_chapters}` — 目标章节数
- `{proj.default_chapter_chars}` — 每章目标字数
- `{outline}` — outline.md 内容
- `{world}` — world.md 内容（前3000字）
- `{characters}` — characters.md 内容（前3000字）
- `{recent_summaries}` — 最近5章摘要
- `{split_req}` — `prompt_fragments.volume_plan.split_requirements`
- `{design_princ}` — `prompt_fragments.volume_plan.design_principles`
- `{structure_req}` — `prompt_fragments.volume_plan.structure_requirements`

## Prompt

```
你是一位网文策划编辑，擅长规划百万字长篇网文的卷级结构。

请为第 {volume} 卷生成详细的卷级计划。

=== 项目信息 ===
标题: {proj.title}
类型: {proj.genre}
目标字数: {proj.target_words}
目标章节数: {proj.target_chapters}
每章目标字数: {proj.default_chapter_chars}

=== 总纲 ===
{outline}

=== 世界设定 ===
{world[:3000]}

=== 角色 ===
{characters[:3000]}

=== 已有章节摘要 ===
{recent_summaries or '(这是第一卷)'}

{split_req}

{design_princ}

{structure_req}

=== 输出要求 ===
请以 YAML 格式输出卷级计划，包含以下字段：

volume: {volume}
title: "卷标题"
theme: "本卷核心主题"
stage: "舞台环境描述"
chapter_range: "1-20"
target_chapters: 20
target_words: 80000

growth:
  position_start: "开头的职位/身份"
  position_end: "结尾的职位/身份"
  wealth_start: "开头的财富/股份状态"
  wealth_end: "结尾的财富/股份状态"
  reputation_start: "开头的声望"
  reputation_end: "结尾的声望"
  romance_start: "开头的感情阶段"
  romance_end: "结尾的感情阶段"

main_arc:
  opening_challenge: "开局挑战描述"
  exploration: "发展与探索描述"
  escalation: "冲突升级描述"
  climax: "高潮事件描述"
  resolution_and_hook: "整合与钩子描述"

new_elements:
  new_resources: ["新人脉/资金/信息"]
  new_projects: ["新项目/新商战"]
  new_enemies: ["新敌人"]

key_milestones:
  - chapter: 5
    event: "关键事件描述"
    impact: "对主线的影响"

new_characters:
  - id: "char_xxx"
    name: "角色名"
    role: "supporting"
    introduction_chapter: 3

hooks_to_plant:
  - id: "hook_xxx"
    description: "伏笔描述"
    plant_chapter: 2
    expected_payoff: "后续卷"

hooks_to_resolve:
  - id: "hook_xxx"
    resolve_chapter: 18
    resolution: "回收方式"

emotional_arcs:
  - character_id: "char_xxx"
    arc: "情感变化描述"
    peak_chapter: 15

subplots:
  - id: "subplot_xxx"
    name: "子线名"
    description: "子线描述"
    chapters_involved: [3, 5, 8, 12]

climax_payoff_sources:
  - "前期积累1"

pacing:
  slow_chapters: [1, 2, 6, 7]
  fast_chapters: [5, 10, 15, 20]
  cliffhanger_chapters: [5, 10, 15, 19]

只输出 YAML，不要其他文字。
```

---

## 输出文件
- `story/plans/volume_{volume:03d}.yaml`
