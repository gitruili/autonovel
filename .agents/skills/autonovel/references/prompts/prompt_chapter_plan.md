# Prompt 模板：章级计划 (chapter_NNNN.yaml)

> 源文件: `gen_chapter_plan.py`
> System Prompt 角色: `system_prompts.architect`

---

## 输入变量
- `{chapter}` — 章节号
- `{volume}` — 当前卷号
- `{genre.display_name}` — 类型中文名
- `{proj.title}` — 小说标题
- `{proj.genre}` — 类型
- `{proj.default_chapter_chars}` — 每章目标字数
- `{volume_plan}` — 卷级计划 YAML（前4000字）
- `{outline}` — 总纲（前3000字）
- `{state_ctx}` — 当前状态上下文（角色、伏笔、支线、最近摘要）
- `{genre_detail}` — `prompt_fragments.chapter_draft.genre_specific_detail`

## 状态上下文组装方式

从以下文件读取并格式化：
- `story/state/character_matrix.json` → 当前角色列表
- `story/state/pending_hooks.json` → 活跃伏笔
- `story/state/subplot_board.json` → 活跃支线
- `story/state/chapter_summaries.json` → 最近3章摘要

## Prompt

```
你是一位{genre.display_name}网文策划编辑，擅长将卷级计划拆解为具体章节。

请为第 {chapter} 章生成详细的章级计划。

=== 项目信息 ===
标题: {proj.title}
类型: {proj.genre}
当前卷: 第 {volume} 卷
每章目标字数: {proj.default_chapter_chars}

=== 卷级计划 ===
{volume_plan[:4000]}

=== 总纲 ===
{outline[:3000]}

=== 当前状态 ===
{state_ctx}

=== 输出要求 ===
请以 YAML 格式输出章级计划，包含以下字段：

chapter: {chapter}
title: "章节标题"
volume: {volume}
pov_character: "视角角色ID"
target_chars: {proj.default_chapter_chars}

beats:
  - type: "opening"
    description: "开场节拍描述"
    location: "场景地点"
    characters_present: ["char_id_1"]
    emotional_tone: "紧张/温馨/悲伤等"
  - type: "development"
    description: "发展节拍"
  - type: "cliffhanger"
    description: "章末钩子"

hook_actions:
  - action: "plant"
    hook_id: "hook_xxx"
    description: "种下/推进/回收的具体方式"

setting_details:
  - "{genre_detail}"

dialogue_notes:
  - character: "char_id"
    speech_requirement: "需要体现的说话特征"

cliffhanger:
  type: "悬念/冲突/反转/情感"
  description: "章末钩子具体描述"
  connects_to_next: "与下一章的衔接方式"

warnings:
  - "需要避免的坑"
  - "需要保持的一致性"

同时生成一份简短的 intent.md，用 3-5 句话概括本章的写作意图和情感基调。

只输出以下格式：
=== YAML ===
(章级计划 YAML)
=== INTENT ===
(intent.md 内容)
```

---

## 输出文件
- `story/plans/chapter_{chapter:04d}.yaml`
- `story/runtime/ch_{chapter:04d}/intent.md`
