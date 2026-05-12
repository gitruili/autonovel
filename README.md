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
uv run python seed.py

# 运行完整的流水线
uv run python run_pipeline.py --from-scratch
```

---

## 流水线 (The Pipeline)

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

## 工具 (27 个 Python 脚本)

### 基础构建 (Foundation)
| 工具 | 用途 |
|------|---------|
| `seed.py` | 生成灵感种子 |
| `gen_world.py` | 种子 → 世界观设定集 (world bible) |
| `gen_characters.py` | 种子 + 世界观 → 角色注册表 |
| `gen_outline.py` | 包含节拍(beats)和伏笔的大纲 |
| `gen_outline_part2.py` | 伏笔账本 |
| `gen_canon.py` | 交叉引用硬性事实 |
| `voice_fingerprint.py` | 声音特征分析和发现 |

### 写作 (Drafting)
| 工具 | 用途 |
|------|---------|
| `draft_chapter.py` | 编写单章，带反模式规则 |
| `run_drafts.py` | 批处理顺序章节编写器 |

### 评估 (Evaluation)
| 工具 | 用途 |
|------|---------|
| `evaluate.py` | 机械式AI痕迹(slop)评分器 + LLM 裁判 |
| `adversarial_edit.py` | “删减 500 字”分析 → 分类删减项 |
| `compare_chapters.py` | 一对一 Elo 锦标赛 |
| `reader_panel.py` | 4角色整本小说评估 |
| `review.py` | 带有停止条件的双重角色审查 |

### 修改 (Revision)
| 工具 | 用途 |
|------|---------|
| `gen_brief.py` | 根据反馈自动生成修改简报 |
| `gen_revision.py` | 根据修改简报重写一章 |
| `apply_cuts.py` | 批处理对抗性删减应用器 |

### 美术与封面 (Art & Cover)
| 工具 | 用途 |
|------|---------|
| `gen_art.py` | 美术流水线：风格、策展、装饰图案、矢量化 |
| `gen_art_directions.py` | 生成多样化的美术方向以供策展 |
| `gen_cover_composite.py` | 在封面图上叠加文本 |
| `gen_cover_print.py` | 准备打印的全幅封面（符合 Lulu/KDP 规范） |

### 有声书 (Audiobook)
| 工具 | 用途 |
|------|---------|
| `gen_audiobook_script.py` | 解析章节为带说话人归属的脚本 |
| `gen_audiobook.py` | 通过 ElevenLabs 生成多声部音频 |

### 编排 (Orchestration)
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
