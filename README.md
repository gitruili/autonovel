# autonovel

一个用于自动撰写、修改、排版、配图和配音完整小说的自动化流水线。从灵感种子到可供打印的PDF、ePub、有声书和落地页——全部由AI智能体生成。

灵感来源于 [karpathy/autoresearch](https://github.com/karpathy/autoresearch)：同样的“修改-评估-保留/丢弃”循环，应用于小说创作。

**第一部生成的小说：** *《The Second Son of the House of Bells》* —
19章，79,456字。
参见 `autonovel/bells` 分支。

文本堆栈支持直接使用 Anthropic 或通过与 Anthropic 兼容的端点使用 MiniMax。默认的示例配置指向 MiniMax 中国 (`https://api.minimaxi.com/anthropic`)。

### 已知限制
- **MiniMax Token 限制**：当使用 MiniMax 模型（如 `MiniMax-M2.5-highspeed`）时，输出 token 限制通常上限为 4096。如果在一次请求中要求生成超过 2-3 个条目，高度详细的提示词（如当前的 `seed.py`）可能会导致输出被截断。如果看到截断的输出，请减小 `--count` 参数。

---

## 快速开始

```bash
# 克隆并设置
git clone <repo-url> && cd autonovel
cp .env.example .env    # 添加你的 API 密钥

# 安装依赖
uv sync

# 可选：在完整运行之前验证配置的提供商
uv run python smoke_llm.py

# 生成灵感种子（或在 seed.txt 中自己写一个）
uv run python autonovel_cli.py generate seed

# 将喜欢的构思复制到 seed.txt，然后生成设定文件
uv run python autonovel_cli.py generate foundation

# 运行完整的流水线
uv run python run_pipeline.py --from-scratch
```

---

## 网文长篇流水线使用说明

### 统一 CLI 入口

所有操作通过 `autonovel_cli.py` 统一入口：

```bash
uv run python autonovel_cli.py <命令> [参数]
```

### 1. 初始化项目

```bash
# 查看可用题材
uv run python autonovel_cli.py genres

# 初始化项目（题材名用中文，如 种田文、年代文 等）
uv run python autonovel_cli.py init --title "我的小说" --genre "种田文" --tags "穿越,大女主,萌娃" --words 1000000 --chapters 500
uv run python autonovel_cli.py init --title "我的小说" --genre "年代文" --tags "穿越,年代,甜宠" --words 1000000 --chapters 500
```

这会在 `story/` 下创建完整的目录结构和空状态文件。

`--genre` 支持的题材可通过 `autonovel_cli.py genres` 查看。当前支持的题材：
- **种田文** — 女主从低起点起步，凭知识或勤劳一步步积累财富、改善生活。核心是建设与成长的爽感。
- **年代文** — 故事设定在1950s-1990s中国，女主穿越/重生到特定历史时期，抓住时代机遇逆袭翻身。
- **总裁豪门** — 现代都市总裁豪门言情，包含契约婚姻、马甲大佬、商战、豪门恩怨等经典元素。

新题材需在 `genres/` 目录下添加 YAML 配置文件。

`--tags` 支持的类型标签（可组合，逗号分隔）：
穿越、重生、大女主、无cp、萌娃、团宠、穿书、系统、空间、美食、医术、经商、年代、古言、现言、赶山、赶海、脑洞、甜宠、宫斗、宅斗

标签会注入到种子生成、世界观、角色、总纲等所有 prompt 中，引导 LLM 按类型组合要求创作。

### 2. 准备素材

**方式一：自动生成（推荐）**

```bash
# 1. 生成种子构思（3个创意供挑选）
uv run python autonovel_cli.py generate seed

# 2. 将喜欢的构思复制到 seed.txt，然后生成设定文件
uv run python autonovel_cli.py generate foundation
```

也可以基于已有想法扩展：`generate seed --riff "穿越古代当渔娘" --count 5`

**长篇模式（30万-200万字）**：当 `project.json` 的 `target_chapters >= 100` 时，
`generate seed` 和 `generate foundation` 自动切换为长篇管线：

```bash
# 长篇种子（含长篇支撑力提示）
uv run python autonovel_cli.py generate seed --long-form

# 自定义目标字数（自动计算卷数和章数）
uv run python autonovel_cli.py generate seed --target-words 500000   # 50万字
uv run python autonovel_cli.py generate seed --target-words 800000   # 80万字

# 市场调研驱动（推荐：带入榜单分析报告，让 AI 结合市场趋势生成脑洞）
uv run python autonovel_cli.py generate seed --long-form --count 5 --batch-size 5 --target-words 1000000 --market-research reports/7mao.md

# 自定义每批数量和最大 token 数（防止输出截断）
uv run python autonovel_cli.py generate seed --long-form --count 5 --batch-size 2 --max-tokens 48000

# 长篇 foundation（7步：世界草稿→总纲→世界观→角色→摘要→正典→状态初始化）
# 自动运行 evaluate.py --phase=foundation-lf 进行质量评估，结果写入 story/foundation_eval.json
uv run python autonovel_cli.py generate foundation

# 如果中途报错中断，可以使用 --start-step 从指定步骤继续（例如从第4步继续）
uv run python autonovel_cli.py generate foundation --start-step 4
```

长篇管线自动生成 `story/plans/master_plan.yaml`（结构化总纲）并初始化全部 7 个状态 JSON 文件，
foundation 完成后即可直接运行 `plan volume` 和 `run --chapter`。

`voice.md` 已随项目模板提供（Part 1 为通用规则，Part 2 可按需微调）。

**方式二：手动创建**

在项目根目录创建以下文件（模板已存在，填入你的内容）：

| 文件 | 说明 |
|------|------|
| `outline.md` | 总纲（卷、章级节拍） |
| `world.md` | 世界观设定（物价、地理、礼法） |
| `characters.md` | 角色档案（性格、说话方式、关系） |
| `voice.md` | 语气定义（禁用词、风格规则） |

### 3. 生成卷计划

```bash
uv run python autonovel_cli.py plan volume --volume 1
```

输出 `story/plans/volume_001.yaml`，定义本卷的章节范围和剧情走向。

### 4. 逐章生成

```bash
# 单章
uv run python autonovel_cli.py run --chapter 1

# 批量（第1卷前20章）
uv run python autonovel_cli.py run --volume 1 --chapters 1-20

# 多卷
uv run python autonovel_cli.py run --volume-range 1-3

# 断点续写（跳过已完成的章节）
uv run python autonovel_cli.py run --volume 1 --chapters 1-20 --resume

# 失败继续（不因单章失败而中断）
uv run python autonovel_cli.py run --volume 1 --chapters 1-20 --continue-on-failure
```

#### 批量章纲生成（推荐）

逐章生成时，每章的章纲是独立生成的，前后章节之间靠状态机传递上下文。
批量章纲模式在一次 LLM 调用中生成多章章纲，让模型在单次推理中保持跨章连贯性——
伏笔的埋/收节奏、情节起伏、钩子衔接都会更自然。

```bash
# 默认生成 20 章章纲
uv run python autonovel_cli.py plan batch --start 1

# 自定义数量
uv run python autonovel_cli.py plan batch --start 21 --count 10

# 之后正常跑流水线，会自动使用已生成的章纲
uv run python autonovel_cli.py run --volume 1 --chapters 1-20
```

已存在的章纲文件不会被覆盖，可安全重复运行。

每章执行 11 步事务闭环：
1. 生成章纲 → 2. 拼装上下文 → 3. 撰写正文 → 4. 抽取 delta → 5. 网文审计 → 6. 校验 delta → 7. 应用状态 → 8. 快照提交 → 9. FTS5 索引 → 10. 更新投影 → 11. 周期校验

### 5. 查看状态

```bash
# 仪表盘（进度、角色、伏笔、状态健康）
uv run python autonovel_cli.py status

# 写作报告（章节字数、钩子债务、支线进度）
uv run python autonovel_cli.py report

# 状态校验
uv run python autonovel_cli.py validate
```

### 6. 回滚

```bash
# 查看快照列表
ls story/memory/snapshots/

# 恢复到某个 commit
uv run python autonovel_cli.py snapshot restore --commit <hash>
```

### 7. FTS5 检索管理

```bash
# 索引单章
uv run python autonovel_cli.py index --chapter 1

# 重建全部索引
uv run python autonovel_cli.py rebuild
```

### 审计模式

默认模式下，账本违规（凭空物品、越级突破、未来信息）会阻断提交。开发调试时可降级为警告：

```bash
uv run python autonovel_cli.py run --chapter 1 --audit-warn
```

### 状态文件说明

所有状态存储在 `story/state/` 下，以 JSON 格式保存，由 Pydantic 强校验：

| 文件 | 内容 |
|------|------|
| `character_matrix.json` | 角色信息、关系、性格 |
| `current_state.json` | 时间线位置、近期事件 |
| `pending_hooks.json` | 伏笔债务（植入/推进/回收） |
| `chapter_summaries.json` | 每章摘要和关键事件 |
| `power_ledger.json` | 战力等级、资源、物品账本 |
| `subplot_board.json` | 支线追踪 |
| `emotional_arcs.json` | 角色情感弧 |

每条记录带有时序字段：`source_chapter`、`valid_from_chapter`、`valid_until_chapter`，确保续写时不会读取未来信息。

---

## 短篇流水线 (Legacy Pipeline)

适用于 8-10 万字中短篇。通过 `run_pipeline.py --from-scratch` 运行，读取 `voice.md`、`world.md`、`characters.md`、`outline.md`、`canon.md` 直接构建。

### 第一阶段：基础构建 (Phase 1: Foundation)
根据灵感种子构建世界观、角色、大纲、叙事声音和正典(canon)。
循环直到 `基础得分 (foundation_score) > 7.5`。

### 第二阶段：初稿写作 (Phase 2: First Draft)
按顺序编写每一章。评估每一章。如果 `得分 > 6.0` 则保留，否则重试。追求前进的进度而非完美。

### 第三阶段 (a)：自动修改 (Phase 3a: Automated Revision)
对抗性编辑 → 应用删减 → 读者评审团 → 生成修改简报 → 重写章节。当得分稳定时，平台期检测机制将停止循环。

### 第三阶段 (b)：审查循环 (Phase 3b: Review Loop)
将完整的手稿发送给配置的审查模型进行双重角色审查（文学评论家 + 小说教授）。解析可操作的建议。修复首要问题。重复此过程，直到审查者找不到主要的无条件缺陷。

### 第四阶段：导出 (Phase 4: Export)
重新生成文档，在 LaTeX 中进行排版，生成配图，制作有声书脚本，构建 ePub，创建落地页。

完整的技术规范请参见 [PIPELINE.md](PIPELINE.md)。

---

## 工具

### 网文长篇流水线

| 工具 | 用途 |
|------|------|
| `autonovel_cli.py` | 统一 CLI 入口（status, run, validate, plan, generate, report 等 14 个子命令） |
| `run_webnovel_pipeline.py` | 章节事务编排器（11 步闭环） |
| `story_schema.py` | 所有状态的 Pydantic schema、`count_cn_words()`、JSON/YAML 工具函数 |
| `validate_state.py` | 状态校验（`--full` 全量 / `--delta` 增量） |
| `gen_volume_plan.py` | 生成卷计划 YAML |
| `gen_chapter_plan.py` | 生成章计划 YAML + intent.md |
| `gen_batch_chapter_plans.py` | 批量生成章计划（单次 LLM 调用，跨章连贯） |
| `memory_orchestrator.py` | 拼装 context.json（token 预算内） |
| `memory_retrieval.py` | SQLite FTS5 索引和检索 |
| `draft_chapter.py` | 撰写单章（支持 `--context` 新路径 / 无参 legacy 路径） |
| `extract_delta.py` | 从正文中抽取状态变化 delta |
| `webnovel_audit.py` | 网文专项审计（钩子、注水、账本合规） |
| `snapshot_state.py` | 状态快照创建/恢复 |
| `run_compaction.py` | 卷末记忆压缩 |
| `gen_volume_summary.py` | 卷级摘要生成 |
| `update_projections.py` | 人类可读投影文档 |

### 短篇流水线 (Legacy)

#### 基础构建 (Foundation) — 短篇
| 工具 | 用途 |
|------|---------|
| `seed.py` | 生成灵感种子（8-10万字/20-24章） |
| `gen_world.py` | 种子 → 世界观设定集 |
| `gen_characters.py` | 种子 + 世界观 → 角色注册表 |
| `gen_outline.py` | 包含节拍和伏笔的24章大纲 |
| `gen_outline_part2.py` | 伏笔账本 |
| `gen_canon.py` | 交叉引用硬性事实 |
| `voice_fingerprint.py` | 声音特征分析和发现 |

#### 基础构建 (Foundation) — 长篇（30万-200万字）
| 工具 | 用途 |
|------|---------|
| `seed_lf.py` | 长篇种子（含长篇支撑力提示，支持 `--target-words`、`--market-research`、`--batch-size`、`--max-tokens`） |
| `gen_world_sketch.py` | 轻量世界观草稿（5个核心参数，~300-500字） |
| `gen_master_outline.py` | 全书总纲（master_plan.yaml + master_summary.md） |
| `gen_world_lf.py` | 长篇世界观（核心设定 + 扩展路线图，根据总纲一次到位） |
| `gen_characters_lf.py` | 长篇角色（三层体系：核心/卷级/反派轮换，根据总纲一次到位） |
| `gen_briefs.py` | 浓缩摘要层（生成防截断的高密度设定上下文） |
| `gen_canon.py` | 设定准则数据库（交叉引用硬性事实） |
| `gen_volume_outline.py` | 单卷详细大纲（按卷生成 ~20章逐章细纲） |
| `init_state.py` | 状态初始化（7个 JSON state 文件） |

#### 写作 (Drafting)
| 工具 | 用途 |
|------|---------|
| `draft_chapter.py` | 编写单章，带反模式规则 |
| `run_drafts.py` | 批处理顺序章节编写器 |

#### 评估 (Evaluation)
| 工具 | 用途 |
|------|---------|
| `evaluate.py` | 机械式AI痕迹(slop)评分器 + LLM 裁判（`--phase=foundation-lf` 评估长篇 foundation） |
| `adversarial_edit.py` | “删减 500 字”分析 → 分类删减项 |
| `compare_chapters.py` | 一对一 Elo 锦标赛 |
| `reader_panel.py` | 4角色整本小说评估 |
| `review.py` | 带有停止条件的双重角色审查 |

#### 修改 (Revision)
| 工具 | 用途 |
|------|---------|
| `gen_brief.py` | 根据反馈自动生成修改简报 |
| `gen_revision.py` | 根据修改简报重写一章 |
| `apply_cuts.py` | 批处理对抗性删减应用器 |

#### 美术与封面 (Art & Cover)
| 工具 | 用途 |
|------|---------|
| `gen_art.py` | 美术流水线：风格、策展、装饰图案、矢量化 |
| `gen_art_directions.py` | 生成多样化的美术方向以供策展 |
| `gen_cover_composite.py` | 在封面图上叠加文本 |
| `gen_cover_print.py` | 准备打印的全幅封面（符合 Lulu/KDP 规范） |

#### 有声书 (Audiobook)
| 工具 | 用途 |
|------|---------|
| `gen_audiobook_script.py` | 解析章节为带说话人归属的脚本 |
| `gen_audiobook.py` | 通过 ElevenLabs 生成多声部音频 |

#### 编排 (Orchestration)
| 工具 | 用途 |
|------|---------|
| `run_pipeline.py` | 完整的流水线编排器（种子 → 完成的小说） |
| `build_arc_summary.py` | 根据章节重新生成情节弧摘要 |
| `build_outline.py` | 根据章节重新生成大纲 |

---

## 文件结构

```
框架层 (FRAMEWORK) (可复用，在 master 分支):
  program.md             — 每个阶段的智能体指令
  CRAFT.md               — 写作技巧教育（情节、角色、世界观、散文）
  ANTI-SLOP.md           — 词汇级别的 AI 痕迹检测
  ANTI-PATTERNS.md       — 结构级别的 AI 模式检测
  PIPELINE.md            — 完整的自动化规范
  WORKFLOW.md            — 供人类参考的步骤指南

模板层 (TEMPLATES) (每个小说的分支上填充):
  voice.md               — 第一部分：护栏。第二部分：每本小说的专属声音
  world.md               — 世界观设定集模板
  characters.md          — 角色注册表模板
  outline.md             — 章节大纲模板
  canon.md               — 硬事实数据库
  MYSTERY.md             — 核心谜团（仅限作者）
  state.json             — 流水线状态追踪器

排版层 (TYPESETTING):
  typeset/novel.tex      — LaTeX 模板（EB Garamond 字体，平装本）
  typeset/build_tex.py   — 章节 → 带有矢量装饰的 LaTeX
  typeset/epub_*          — ePub 元数据、CSS 和前置内容

美术层 (ART):
  audiobook_voices.json  — 角色 → ElevenLabs 声音映射
  landing/index.html     — 响应式落地页模板

配置层 (CONFIG):
  .env.example           — API 密钥 (Anthropic, fal.ai, ElevenLabs)
  pyproject.toml         — Python 依赖
```

---

## 工作原理

小说由五个共同演进的层构成：

```
  第5层:  voice.md          — 我们怎么写 (HOW)
  第4层:  world.md          — 有什么 (WHAT)
  第3层:  characters.md     — 谁来做 (WHO)
  第2层:  outline.md        — 发生什么 (WHAT HAPPENS)
  第1层:  chapters/ch_NN.md — 实际的文字内容 (THE ACTUAL PROSE)
  交叉切面: canon.md        — 什么是真实的 (WHAT IS TRUE)
```

变更既会向下传播（设定更改 → 大纲更改 → 章节修改），也会向上传播（写作时发现空白 → 更新设定 → 检查下游）。流水线在 `state.json` 中追踪这些传播债务。

### 两个免疫系统

1. **机械系统** (`evaluate.py`，无 LLM)：正则表达式扫描禁用词、虚构类陈词滥调、违反“展示而非讲述”(show-don't-tell)规则的情况、句子长度单一性。

2. **LLM 裁判** (`evaluate.py`，单独的模型)：对散文质量、声音的一致性、角色的独特性、节拍覆盖率进行评分。

### 审查循环

在自动修改周期结束后，完整的手稿会被发送给配置的审查模型，并附带以下提示词：

> "阅读下面的小说。首先作为文学评论家审查它，然后作为小说教授审查它。对于你发现的任何缺陷，请给出具体的、可操作的建议。公平但诚实。你并非*必须*找出缺陷。"

双重角色审查能捕捉到自动化工具无法捕捉的问题：散文层面的重复、角色单薄、伦理漏洞、结构单调。循环将一直持续，直到审查者提出的主要都是带有保留意见的修饰性批评，而不是真正的问题。

---

## API 密钥

流水线使用三种外部服务：

| 服务 | 密钥 | 用途 |
|---------|-----|----------|
| Anthropic | `ANTHROPIC_API_KEY` | 当 `AUTONOVEL_LLM_PROVIDER=anthropic` 时用于写作、评估、审查 |
| MiniMax | `MINIMAX_API_KEY` | 当 `AUTONOVEL_LLM_PROVIDER=minimax` 时用于写作、评估、审查 |
| fal.ai | `FAL_KEY` | 封面图和装饰生成 (Nano Banana 2) |
| ElevenLabs | `ELEVENLABS_API_KEY` | 多声部有声书生成 |

将 `.env.example` 复制为 `.env` 并填入你的密钥。核心流水线只需要一个文本模型提供商的密钥即可。美术和有声书是可选的。

---

## 创作历史

第一部小说《The Second Son of the House of Bells》是通过这条流水线创作出来的：

- **基础构建：** 世界观设定集、8个角色、24章大纲、声音发现
- **写作：** 24章，75,698字，带评估的顺序写作
- **修改：** 6次自动循环 + 6轮审查
- **结构：** 24章 → 通过4次合并精简为19章
- **美术：** 亚麻油毡版画封面 (Nano Banana 2)，19个木刻风格章节装饰（已矢量化）
- **有声书：** 19章被解析为 4,179 个带说话人属性的片段
- **最终：** 79,456字，6轮审查，解决所有首要问题

---

## 灵感来源

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — 自主的研究循环
- Brandon Sanderson 的写作讲座（魔法定律、角色滑块）
- K.M. Weiland 的 *《Creating Character Arcs》*
- Blake Snyder 的 *《Save the Cat》*
- Ursula K. Le Guin 的 "From Elfland to Poughkeepsie"
- [slop-forensics](https://github.com/sam-paech/slop-forensics) 和 [EQ-Bench Slop Score](https://eqbench.com/slop-score.html)
