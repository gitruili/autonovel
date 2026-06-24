# Prompt 模板：章节起草 (draft_chapter)

> 源文件: `draft_chapter.py`
> System Prompt 角色: `system_prompts.chapter_writer`

---

## Webnovel Pipeline 模式（从 context.json 构建）

### 输入变量
- `{chapter_num}` — 章节号
- `{title}` — 小说标题
- `{target_chars}` — 目标字数
- `{intent}` — 写作意图
- `{chapter_plan}` — 章级计划内容
- `{volume_contract}` — 卷级计划（前2000字）
- `{previous_chapter_tail}` — 前一章结尾文本
- `{state_text}` — 状态切片（角色、伏笔、资源、物品）
- `{summaries_text}` — 最近章节摘要
- `{voice_rules}` — 语气规则
- `{genre.display_name}` — 类型中文名
- `{genre_craft}` — 类型写作技法参考（从 genres/craft/ 目录加载）
- `{genre_detail}` — `prompt_fragments.chapter_draft.genre_specific_detail`
- `{writing_guide}` — `prompt_fragments.chapter_draft.writing_guide`

### Prompt

```
撰写《{title}》的第 {chapter_num} 章。

=== 写作意图 ===
{intent}

=== 本章计划 ===
{chapter_plan}

=== 卷级计划（参考） ===
{volume_contract[:2000]}

=== 前一章结尾（从此处继续） ===
{previous_chapter_tail}

{state_text}

=== 最近章节摘要 ===
{summaries_text}

=== 语气规则 ===
{voice_rules}

=== 写作指令 ===
1. 章节开头必须输出标题行：`# 第{chapter_num}章 标题`（标题取自章计划中的 title 字段）。
2. 撰写完整的章节。目标字数约 {target_chars} 字。不要截断或总结。
3. 第三人称限制视角，过去时态，紧贴章计划中指定的视角人物。
4. 按顺序完成章计划中所有节拍。
5. 展示感官细节：触觉、嗅觉、听觉融入场景。
6. 对话遵循角色信息中定义的说话模式。
7. 不要使用语气规则中禁用的词汇和句式。
8. 改变句子长度。短句用于情绪冲击，长句用于铺陈日常。
9. 信任读者。不要解释场景的含义，让场景本身产生力量。
10. 从场景中开始这一章，不要以铺陈开始。以一个瞬间结束，而不是总结。
11. 展示之后不要过度解释。信任场景。
12. 对话要像说话，不像书面语。角色会磕绊、打断、话没说完。
13. 场景优于总结。本章至少 70% 的内容应是即时场景。
14. 章尾钩子必须让读者想翻下一章。
15. 禁止使用三元组感官列表（"X、Y和Z"）。合并两个，删掉一个。
16. 禁止"她心想/她暗想"——让想法本身作为独立句子出现。

=== {genre.display_name}写作技法参考 ===
{genre_craft[:3000]}

{writing_guide}

现在开始撰写章节。完整文本，从头到尾。
```

---

## Legacy 模式（文件直接读取）

### 输入变量
- `{title}` — 小说标题
- `{chapter_num}` — 章节号
- `{voice}` — voice.md 全文
- `{world}` — world.md 全文
- `{characters}` — characters.md 全文
- `{outline}` — outline.md 全文
- `{canon}` — canon.md 全文
- `{chapter_outline}` — 本章大纲段落
- `{next_chapter}` — 下一章大纲（前10行）
- `{prev_tail}` — 前一章结尾（后2000字符）

---

## 输出文件
- Webnovel: `chapters/v{volume:03d}/ch_{chapter:04d}.md`
- Legacy: `chapters/ch_{chapter:02d}.md`
