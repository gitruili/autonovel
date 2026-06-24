# Prompt 模板：事实库 (canon.md)

> 源文件: `gen_canon.py`
> System Prompt 角色: `system_prompts.canon_editor`

---

## 输入变量
- `{seed}` — seed.txt 内容
- `{world}` — world.md 内容
- `{characters}` — characters.md 内容
- `{genre.prompt_fragments.canon.sections}` — 类型专属 canon 分类

## Prompt

```
请将这些策划文档中的每一个硬性事实提取到一个结构化的设定准则数据库（Canon Database）中。
"硬性事实"是指作者绝不能违反的任何内容：姓名、年龄、经济数据、地理、关系、已发生的事件、
金手指规则、社会规则、商业规则等。

源文档：

=== SEED.TXT ===
{seed}

=== WORLD.MD ===
{world}

=== CHARACTERS.MD ===
{characters}

将输出格式化为 CANON.MD，包含以下类别：

{genre.prompt_fragments.canon.sections}

每个类别下：
- 每个条目仅记录一个事实
- 在每个事实后的括号中注明来源（seed.txt / world.md / characters.md）

规则：
- 每个要点仅包含一个事实。简洁、具体、可核对。
- 在每个事实后的括号中注明来源。
- 目标条数至少为 80-120 条。要详尽无遗。
- 如果两个文档提供的细节略有不同，请注明差异。
- 绝不编造事实。仅记录明确陈述的内容。
- 特别注意经济数据的交叉验证。
```

---

## 输出文件
- `canon.md`（覆盖写入）
