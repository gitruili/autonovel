# Prompt 模板：章节修订 (gen_revision)

> 源文件: `gen_revision.py`
> System Prompt 角色: `system_prompts.revision_writer`

---

## 输入变量
- `{title}` — 小说标题
- `{ch_num}` — 章节号
- `{brief}` — 修订任务书内容（来自 briefs/*.md）
- `{voice}` — voice.md 全文
- `{characters}` — characters.md 全文
- `{world}` — world.md 全文
- `{prev_tail}` — 前一章结尾（后2000字符）
- `{next_head}` — 下一章开头（前1500字符）
- `{old_text}` — 现有草稿全文

## Prompt

```
重写《{title}》的第 {ch_num} 章。

=== 修订任务书 REVISION BRIEF (请严格遵循此文档进行修改) ===
{brief}

=== 语气定义 VOICE DEFINITION ===
{voice}

=== 角色信息 CHARACTER REGISTRY ===
{characters}

=== 世界设定集 WORLD BIBLE ===
{world}

=== 前一章结尾 (用于保持连贯性) ===
{prev_tail}

=== 下一章开头 (结尾应顺滑过渡到这里) ===
{next_head}

=== 现有草稿 (作为原材料——保留好的部分，剪掉坏的部分) ===
{old_text}

=== 避免的负面模式 (ANTI-PATTERN RULES) ===
- 禁止使用三元组感官列表 (例如: 看到X，听到Y，闻到Z)
- 每一章中"不由自主地"或类似词汇不得出现超过一次
- 禁止"她心想/她暗想"——让想法本身作为独立的句子融入叙事
- 禁止过度解释（如果动作或对话已经展示了，就不要再用旁白解释一遍）
- 每章最多 2 个小节分隔符(---)，仅在真正的时空跳转时使用
- 必须包含至少一个令人惊喜/符合人设但打破常规的瞬间
- 至少 70% 的内容必须是即时场景（带对话和动作），而不是干巴巴的叙述总结
- 对话要像真正的说话：带有地方特色、有潜台词，而不是书面语或演讲
- 绝不使用烂俗 AI 网文词汇：\"不禁\"、\"映入眼帘\"、\"心中涌起暖流\"、\"美眸\"等

现在，请写出完整的修订章节。
```

---

## 输出文件
- 覆盖写入原章节文件路径
