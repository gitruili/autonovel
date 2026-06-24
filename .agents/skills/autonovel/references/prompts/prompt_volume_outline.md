# Prompt 模板：卷级详细大纲 (volume_NNN_outline.md)

> 源文件: `gen_volume_outline.py`
> System Prompt 角色: `system_prompts.architect`

---

## 输入变量
- `{volume}` — 卷号
- `{genre.display_name}` — 类型中文名
- `{tags_context}` — 项目标签上下文
- `{seed}` — seed.txt 内容
- `{world}` — world_brief.md 或 world.md 内容
- `{characters}` — characters_brief.md 或 characters.md 内容
- `{voice_part2}` — voice.md Part 2
- `{outline_existing}` — 已有 outline.md 内容（前4000字）
- `{prev_vol_context}` — 上一卷大纲内容（如有，前3000字）
- `{v_title}` — 卷标题（来自 master_plan.yaml）
- `{v_arc}` — 核心主线
- `{v_turning}` — 关键转折
- `{v_antagonist}` — 主要对手
- `{v_romance}` — 感情阶段
- `{v_tone}` — 情绪基调
- `{v_hooks_plant}` — 需要植入的伏笔
- `{v_hooks_payoff}` — 需要回收的伏笔
- `{target_chapters}` — 本卷章节数
- genre prompt fragments: `volume_plan.terminology`, `volume_plan.design_principles`, `volume_plan.structure_requirements`, `volume_plan.conflict_patterns`, `volume_plan.output_template`, `volume_plan.chapter_output_template`, `outline.ledgers`, `outline.constraints`

## Prompt

```
为这部**百万字长篇**{genre.display_name}网文生成**第 {volume} 卷**的详细章节大纲。
目标字数约 {target_chapters * 4000} 字，共约 {target_chapters} 章。

{tags_context}

{genre.prompt_fragments.volume_plan.terminology}

---

全书总纲与历史卷纲摘要（已有，不要重复输出宏观内容，保持专注在本卷）：
{outline_existing[:4000]}

{prev_vol_context}

本卷信息（来自总纲）：
- 卷标题：{v_title}
- 核心主线：{v_arc}
- 关键转折：{v_turning}
- 主要对手：{v_antagonist}
- 感情阶段：{v_romance}
- 情绪基调：{v_tone}
- 需要植入的伏笔：{v_hooks_plant}
- 需要回收的伏笔：{v_hooks_payoff}

种子概念 (SEED):
{seed}

生活设定集 (WORLD):
{world}

角色注册表 (CHARACTERS):
{characters}

文风标识 (VOICE):
{voice_part2}

---

{genre.prompt_fragments.volume_plan.design_principles}

{genre.prompt_fragments.volume_plan.structure_requirements}

---

{genre.prompt_fragments.volume_plan.conflict_patterns}

---

## 请生成第 {volume} 卷的详细章节大纲

本卷约 {target_chapters} 章，每章约 4000 字。

### 卷纲骨架（先输出本卷宏观骨架）

{genre.prompt_fragments.volume_plan.output_template}

### 逐章大纲（核心输出，每章约 200-300 字）

{genre.prompt_fragments.volume_plan.chapter_output_template}

---

{genre.prompt_fragments.outline.ledgers}

---

{genre.prompt_fragments.outline.constraints}

8. **目标字数约 3500-4500 字/章**

## 重要提示
- 务必一口气写完完整的 {target_chapters} 章大纲，不要中途中断
- 先输出卷纲骨架，再输出逐章大纲，最后附上台账
- 逐章大纲必须使用"编号剧情点 + 情绪标签/爽点类型标签 + 三要素"格式
- 每章至少包含 1 种明确的爽点类型
- 不要重复输出总纲中已有的宏观规划内容
```

---

## 输出文件
- `story/plans/volume_{volume:03d}_outline.md`
- 然后重建 outline.md 兼容层
