# AUTONOVEL：可复现的小说流水线

## 概述

本文档记录了从灵感种子生成、起草到修改小说的完整自动化流水线。该流程衍生自《The Second Son of the House of Bells》（7.5万字，23章，5个修改周期）的创作过程。

目标：用户提供一个灵感种子。其他一切全部自动化。

---

## Master 分支（框架层）

Master 分支不包含任何特定于故事的内容。它是可复用的基础。

```
框架层 (FRAMEWORK) (可复用，流水线从不修改):
  README.md            -- 项目概述
  WORKFLOW.md          -- 供人类参考的步骤指南
  PIPELINE.md          -- 本文件（自动化规范）
  program.md           -- 每个阶段的智能体指令
  CRAFT.md             -- 写作技巧教育（情节、角色、世界观、散文）
  ANTI-SLOP.md         -- 词汇级别的 AI 痕迹检测
  ANTI-PATTERNS.md     -- 结构级别的 AI 模式检测

模板层 (TEMPLATES) (空壳，在各个分支上按小说填充):
  voice.md             -- 第1部分（护栏）是永久的；第2部分为空
  world.md             -- 仅包含章节标题
  characters.md        -- 仅包含结构模板
  outline.md           -- 仅包含结构模板
  canon.md             -- 空白，带有说明
  MYSTERY.md           -- 空白模板
  state.json           -- {phase: "foundation", iteration: 0, debts: []}

工具 (TOOLS) (流水线机器):
  基础构建 (Foundation):
    seed.py              -- 生成 10 个灵感种子
    gen_world.py         -- 种子 → world.md
    gen_characters.py    -- 种子 + 世界观 → characters.md
    gen_outline.py       -- 种子 + 世界观 + 角色 → outline.md (第1部分)
    gen_outline_part2.py -- 大纲 + 角色 → 伏笔账本
    gen_canon.py         -- 世界观 + 角色 → canon.md (硬事实)
    voice_fingerprint.py -- 测试段落 → voice.md 第2部分

  写作 (Drafting):
    draft_chapter.py     -- 编写单章，带反模式规则
    run_drafts.py        -- 批处理顺序章节编写器

  评估 (Evaluation):
    evaluate.py          -- 机械式AI痕迹评分器 + LLM 裁判
                            模式: --phase=foundation, --chapter=N, --full

  修改 (Revision):
    adversarial_edit.py  -- “删减 500 字”裁判 → 分类后的删减列表
    compare_chapters.py  -- 一对一 Elo 锦标赛
    reader_panel.py      -- 4角色的整本小说评估
    gen_revision.py      -- 根据修改简报重写章节
    build_arc_summary.py -- 根据章节重新生成 arc_summary.md
    build_outline.py     -- 根据章节重新生成 outline.md

  导出 (Export):
    typeset/novel.tex    -- LaTeX 模板（EB Garamond，平装本）
    typeset/build_tex.py -- chapters/*.md → chapters_content.tex

  编排器 (Orchestrator):
    run_pipeline.py      -- 新增：全自动的流水线运行器

配置 (CONFIG):
  .env.example           -- API 密钥模板
  pyproject.toml         -- Python 依赖项 (httpx, dotenv)
  .python-version
  .gitignore
```

---

## 每一本小说的专属分支（生成的）

以下所有内容均在一个分支上自动创建。

```
  seed.txt               -- 选定的灵感种子
  world.md               -- 填充完毕的世界观设定集
  characters.md          -- 填充完毕的角色注册表
  outline.md             -- 填充完毕的章节大纲 + 伏笔账本
  voice.md Part 2        -- 发现的叙事声音标识
  canon.md               -- 积累的硬事实
  MYSTERY.md             -- 核心谜团（仅限作者）
  chapters/ch_*.md       -- 散文内容
  state.json             -- 当前阶段、分数、债务
  results.tsv            -- 实验日志（记录每次保留/丢弃）
  arc_summary.md         -- 供评审团评估的章节摘要
  edit_logs/*.json       -- 对抗性删减、评审结果、锦标赛
  eval_logs/*.json       -- 完整的评估结果
  briefs/*.md            -- 修改简报（gen_revision.py 的输入）
  typeset/novel.pdf      -- 排版完成的 PDF
```

---

## 完整的流水线 (THE PIPELINE)

### 阶段 0：准备工作 (Phase 0: Setup)

```
输入:  seed.txt（用户提供或通过 seed.py 生成）
输出:  创建分支，配置 .env

1. git checkout -b autonovel/<tag>
2. 验证 `.env` 是否有选定提供商的密钥
   （`ANTHROPIC_API_KEY` 或 `MINIMAX_API_KEY`）
3. 验证 seed.txt 是否存在且足够具体
   （具有世界差异性、核心冲突、代价/限制、感官钩子）
```

### 阶段 1：基础构建 (Phase 1: Foundation)

```
输入:  seed.txt
输出:  world.md, characters.md, outline.md, voice.md, canon.md, MYSTERY.md
退出条件:   foundation_score > 7.5 AND lore_score > 7.0

循环：
  1. gen_world.py        → world.md（传说、魔法系统、地理、阵营）
  2. gen_characters.py   → characters.md（创伤/渴望/需求/谎言、语言习惯、滑块）
  3. gen_outline.py      → outline.md 第 1 部分（节拍、章节结构）
  4. gen_outline_part2.py → outline.md 第 2 部分（伏笔账本）
  5. 叙事声音发现：用不同的语域写5段测试段落，
     选择最好的一个，用示例和反面示例填充 voice.md 的第 2 部分
  6. 定义 MYSTERY.md（读者将要发现的核心秘密）
  7. gen_canon.py        → canon.md（交叉引用所有硬事实）
  8. evaluate.py --phase=foundation
  9. 如果分数提高 → git commit。如果下降 → git reset --hard HEAD~1。
  10. 找出最弱的维度 → 下一次迭代针对该维度进行优化。

关键经验：
  - 基础构建通常需要 5-15 次迭代
  - 评估器将设定关联性的权重定为 40% — 魔法必须
    影响政治，历史必须解释阵营，地理必须
    塑造文化
  - 每次迭代都进行跨层一致性检查
  - 在退出基础构建阶段之前，正典(canon)应具有 400+ 个条目
  - 声音发现是一个独立的子循环：编写测试段落，
    评估，选择，完善
```

### 阶段 2：初稿写作 (Phase 2: First Draft)

```
输入:  所有基础构建文档
输出:  chapters/ch_01.md 到 ch_NN.md
退出条件:   起草完所有章节，且所有得分 > 6.0

按照大纲顺序处理每一章：
  1. 加载上下文窗口：
     - voice.md（完整）
     - world.md（完整）
     - characters.md（完整）
     - 本章的大纲条目
     - 上一章的最后约 1000 字
     - 下一章的大纲（用于保持连贯性）
  2. draft_chapter.py → chapters/ch_NN.md
  3. evaluate.py --chapter=NN
  4. 如果得分 > 6.0 → 保留并提交。如果 < 6.0 → 丢弃，重试（最多 5 次）。
  5. 从评估输出中提取新的正典条目 → 追加到 canon.md 中
  6. 记录到 results.tsv 中

草稿完成后的清理：
  7. 跨所有章节运行机械式 AI 痕迹检查 (evaluate.py 正则扫描)
  8. 修复在前几章中发现的反复出现的 AI 模式
     （这些模式会累积 — 在修改阶段之前解决它们）
  9. 将 state.json 的 phase 更新为 "revision"

关键经验：
  - 前进的进度优先于完美。6.0 分已经足够好了。
  - 第 1-6 章的得分往往高于 7-24 章（新鲜感衰减）。
    在第 6 章之后，在写作提示词中添加反模式规则。
  - 批处理后半部分（第 11 章以上）—— 速度更快，且质量
    足够稳定。
  - 机械式扫除通常会发现约 200 个第一级禁用词、
    破折号滥用以及句子长度单一等情况。
  - 总写作时间：25 章约需 8-16 小时的 API 调用时间。
```

### 阶段 3：修改 (Phase 3: Revision)

这是真正提升质量的阶段。3-6 个周期，每个周期都有特定的侧重点。当连续 2 个周期的分数陷入平台期时停止。

```
周期 1：基线与诊断 (CYCLE 1: BASELINE & DIAGNOSIS)

  1. adversarial_edit.py all
     → 为所有章节生成 edit_logs/chNN_cuts.json
     → 发现系统性模式（预期过度解释 OVER-EXPLAIN 会在 30-35% 左右）
  2. compare_chapters.py
     → 生成 edit_logs/tournament_results.json (Elo 排名)
  3. 应用排名靠前的删减项：
     侧重于 OVER-EXPLAIN（过度解释）+ REDUNDANT（冗余）（两者合计占所有删减的 55-60%）
     目标：包含 >17% 冗杂内容的章节
     方法：基于引用的自动化匹配移除
     预期删减约 2000-3000 字（小说总量的 3-4%）
  4. reader_panel.py
     → 生成 edit_logs/reader_panel.json
     4 种角色：编辑、类型读者、作家、第一读者
     各自回答：动力丧失点、当之无愧的结局、建议删减的章节、
       缺失的场景、最单薄的角色、最好的场景、最差的场景、
       是否推荐、让你难忘的桥段、下一本书等问题。
  5. 识别共识项（3/4 或 4/4 一致同意）：
     这些就是修改的优先级。
  6. Git 提交："Cycle 1: adversarial + panel baseline"
```

```
周期 2-3：结构化修改 (CYCLE 2-3: STRUCTURAL REVISIONS)（解决评审团共识）

  对于每个共识项，按优先级顺序进行：
    a. 建议删减的候选 (CUT CANDIDATE)（4/4 一致）：
       编写压缩简报 → gen_revision.py
       目标：删减章节的 40-60% 字数
       保留：评审团指出的 2-3 个必要的节拍
       警告：不要过度压缩。1700 字对于任何一章来说都太单薄了。
       最佳区间：压缩后的章节 2200-3000 字。

    b. 缺失的场景 (MISSING SCENE)（4/4 一致）：
       为目标章节编写扩展简报 → gen_revision.py
       或者：如果场景 <400 字，则进行外科手术式修补
       关键点：简报必须说明要保留什么（现有的好素材）
       以及要添加什么（缺失的节拍）

    c. 角色单薄 (THIN CHARACTER)（4/4 一致）：
       找出 1-2 个该角色出场的现有场景
       添加一个 POV 角色捕捉到的私密/毫无防备的时刻
       连接到 characters.md 中该角色的背景故事
       不要添加新场景 — 而是深化现有场景

    d. 场景薄弱 (WEAK SCENE)（3/4 一致）：
       编写戏剧化简报 → gen_revision.py
       改变信息是如何到达的，而不是信息本身是什么
       将“阅读文档” → 改为调查/冲突
       将“听取简报” → 改为带阻力的冲突

    e. 一致性/时间线 (CONSISTENCY / TIMELINE)：
       寻找矛盾之处（年份、年龄、事件顺序）
       在 canon.md + 所有源文件 + 章节引用中进行修复
       会出现 10年/12年 的区分错误。要做好准备。

    f. 重新编号章节 (CHAPTER RENUMBERING)：
       如果合并/删除了章节，所有的内部标题都需要更新
       使用脚本，不要手动修改

  每次结构更改后：
    对受影响的章节运行 evaluate.py --chapter=N
    如果有改进则保留，否则丢弃
    带有详细信息的 Git 提交

  evaluate.py --full → 获取整本小说的评分
  Git 提交："Cycle N: structural revisions from panel"
```

```
周期 4-5：针对性改进 (CYCLE 4-5: TARGETED IMPROVEMENTS)（解决评估的指引）

  evaluate.py --full 输出：
    - 最弱的维度 weakest_dimension（通常是节奏 pacing_curve）
    - 最弱的章节 weakest_chapter
    - 最佳建议 top_suggestion（具体的修复方案）
    - 各维度的分数和评论

  常见的模式和修复：
    a. 节奏 (PACING)（这始终是个顽固的低分项）：
       - 第二幕调查的节奏重复 →
         压缩最弱的调查章节，使场景类型多样化
       - 第三幕太紧凑 → 扩展召集盟友和高潮部分
       - 揭露秘密过快 → 在不同揭露之间添加呼吸式的节拍
       警告：修复一段节奏往往会暴露下一段。对于由 LLM 评估的小说来说，Pacing=7 可能是
       一个结构的上限。

    b. 章节太短 (CHAPTER TOO SHORT)，无法承载其结构重要性：
       编写扩展简报 → gen_revision.py
       目标：增加 +800-1500 字
       侧重于：物理上的积聚、恐惧感、带有持续时间的寂静
       简报应具体说明要扩展什么节拍，而不仅仅是“让它更长”

    c. 跨章节重复的短语 (REPEATED PHRASES)：
       在所有章节中搜索该短语
       保留最有影响力的一处，修改其余的
       常见的 AI 重复情况：开场描写、情感公式、
       "[X] 做 [Y] 的方式" (the way [X] did [Y])、三段式列表

    d. 未解决的线索 (UNRESOLVED THREADS)：
       检查 outline.md 中的伏笔账本
       在埋下线索但从未收尾的地方添加解决节拍
       外科手术式的修补，而不是全盘重写

  修复之后：
    evaluate.py --full → 检查分数是否有所提高
    如果 weakest_chapter 变了 → 之前的修复有效
    如果在 2 个周期后分数不变 → 停止，因为边际收益递减
```

```
周期 6：润色 (CYCLE 6: POLISH)（最后一遍过）

  1. adversarial_edit.py all → 获取重写章节的全新删减数据
  2. 在第 2-5 个周期中被重写的章节中应用删减
  3. AI 痕迹清理：对重写的章节逐章执行 evaluate.py
  4. reader_panel.py → 最终验证
  5. 重新生成基础文档
```

```
阶段 3b：OPUS 审查循环 (PHASE 3b: OPUS REVIEW LOOP)（深度的散文级打磨）

  在自动化修改循环之后，切换到审查模型进行最终的质量提升。
  这个评估才会真正捕捉到散文问题、结构性
  重复、角色单薄和伦理漏洞。

  工具: review.py
  模型: 配置的审查模型 (`AUTONOVEL_REVIEW_MODEL`)
  提示词: "阅读下面的小说。首先作为文学评论家审查它
    （就像报纸上的书评），然后作为小说教授审查它。
    在后一份评论中，对于你发现的任何缺陷给出具体的、可操作的
    建议。公平但诚实。你并非*必须*找出缺陷。"

  循环（最多 4 轮）：
    1. review.py --output reviews.md
       将完整手稿发送给审查模型。获取双重角色的评价。
    2. review.py --parse
       提取可操作项、严重程度、类型。
       对条目进行分类：major(重大)/moderate(中等)/minor(次要)，qualified(有保留)/unqualified(无条件)。
    3. 停止条件 (STOPPING CONDITION)：
       如果满足以下条件则停止：没有留下重大的无条件项目
       如果满足以下条件则停止：>50% 的项目是有保留/婉转的
       如果满足以下条件则停止：发现的问题数 ≤2
       这些信号意味着审查者已经找不出真正的问题了。
    4. 解决首要问题：
       - gen_brief.py --auto → 选择最弱的一章，生成简报
       - gen_revision.py → 根据简报重写这一章
       - 对模式问题的机械修复（apply_cuts.py）
       - 用于针对性添加的外科手术式修补
    5. 提交，重复。

  来自《Bells》创作过程的关键经验（6 轮审查）：
    - 同样的问题会反复浮现直到被修复为止（中段的节奏、
      口头禅、角色深度）。这就是需要采取行动的信号。
    - 当评价的语言从“这部小说有问题”转变为
      “这些是野心带来的代价”时 → 停止修改。
    - 审查者总是会挑出点毛病。停止条件是看严重程度和有无保留意见，而不是零缺陷。
    - 持续存在于 3+ 轮次中的项目可能在小说的声音/方法论上是结构性的，而不是错误。要学会接受它们。
    - 审查者的项目严重程度就是指南针：
      多个重大问题 → 需要结构性工作
      少量重大，一些中等 → 针对性修改，再来 2-3 轮
      全部是中等/轻微 → 仅打磨，再来 1-2 轮
      大部分是有保留的批评 → 完成，准备发布
```

### 阶段 4：导出 (Phase 4: Export)

```
  1. 规范化章节标题（统一 # 级别、格式）
  2. typeset/build_tex.py → chapters_content.tex
  3. 编辑 typeset/novel.tex:
     - 设置书名、作者名
     - 选择卷首语（从小说正文中选，不要剧透）
     - 设置页尾文字
  4. tectonic novel.tex → novel.pdf
  5. Git 提交: "Export: [书名] — [字数] words"
```

---

## 关键经验 (来自《Bells》的创作过程)

### 评估器奖励什么
  - 如果种子具有强大的核心疑问，主题连贯性很早就会达到上限（10 分）。将魔法系统**作为**主题来构建。
  - 如果你从不打破 POV 并且保持写作词汇库的原生性，声音一致性（9 分）就能保持。
  - 伏笔（9 分）需要一个从基础构建延续到起草阶段的账本。每一个埋点都需要回收。

### 评估器惩罚什么
  - 节奏（7 分）是结构上的顽疾。调查类的章节
    （走访-获知-受阻）会重复一种评估器能捕捉到的节拍。
    修复了一段，它就会发现下一段。除非你重构情节，否则请接受 7 分作为可能的上限。
  - 过度解释（OVER-EXPLAIN）是排名第一的 AI 写作模式（占对抗性删减的约 32%）。
    叙述者总在解释场景已经展示过的内容。积极地删掉它们。
  - 冗余（REDUNDANT）排名第二（约 26%）。同一个见解被重申 3-4 次。一次就足够了。

### 读者评审团能捕捉而评估器不能捕捉到的问题
  - “YES 清单”——当盟友毫无摩擦地全部同意时
  - 关键角色之间缺乏情感场景
  - 角色“更像机制而不是人”
  - 场景需要更混乱、更人性化、更少刻意编排的感觉
  - “起作用的”场景与“鲜活的”场景之间的区别

### 危险模式
  - 过度压缩：将一章删减到低于 1800 字会使它成为新的
    最弱章节。压缩章节的最佳区间是 2200-3000 字。
  - 扩展膨胀：gen_revision.py 增加的字数通常比简报要求的超出约 30%。
    目标为 3200 字的简报将产生 3800-4200 字的内容。
  - 盲目追求分数：在第 4 周期之后，修复一个分数通常会导致另一个分数下降。
    当我们过度压缩第 11 章时，情节弧的分数经历了 9→8→9。
  - 评估器会轮换“最弱章节”——盲目追逐它就像在打地鼠。
    轮换 2 次后即可停止。

### 时间预估
  阶段 1 (基础构建):    2-4 小时 API 时间, 5-15 次迭代
  阶段 2 (初稿写作):    8-16 小时 API 时间, 23-30 章
  阶段 3 (修改阶段):    4-8 小时 API 时间, 3-6 次循环
  阶段 4 (最终导出):    30 分钟
  总计:                    产出一部 7.5 万字的小说大约需要 15-30 小时 API 时间

---

## 为实现全面自动化还需要构建什么 (WHAT NEEDS BUILDING FOR FULL AUTOMATION)

### 已经存在的（在分支上，需要合并到 master）：
  - gen_revision.py
  - reader_panel.py
  - build_arc_summary.py
  - build_outline.py
  - voice_fingerprint.py
  - typeset/novel.tex + build_tex.py

### 需要构建的：
  1. run_pipeline.py — 运行所有阶段的编排器
     - 阶段 1：循环进行基础生成 + 评估
     - 阶段 2：带有重试逻辑的顺序写作
     - 阶段 3：带有自动生成简报功能的修改循环
     - 阶段 4：导出
     - 平台期检测（当跨 2 个周期的 Δ < 0.5 时停止）
     - 根据评审团反馈 + 评估指引自动编写简报

  2. gen_brief.py — 根据结构化反馈自动生成修改简报
     输入: 评审团 JSON + 评估 JSON + 章节文本
     输出: 一份适合 gen_revision.py 的修改简报 (.md)
     这是关键的自动化缺口——目前简报都是手写的。

  3. apply_cuts.py — 批处理删减应用器
     输入: edit_logs/chNN_cuts.json
     输出: 打了补丁的章节文件
     根据删减类型（OVER-EXPLAIN, REDUNDANT）进行过滤
     优雅地处理引用匹配失败的情况

  4. 清理 master 分支：
     - 从分支合并工具（gen_revision, reader_panel 等）
     - 从模板文件中剥离特定于故事的内容
     - 添加 .env.example
     - 更新 WORKFLOW.md 以引用 PIPELINE.md
     - 更新 README.md，包含完整的自动化故事

---

## 编排器 (run_pipeline.py 规范)

```python
# 完整自动化流水线的伪代码

def run_pipeline(seed_path, tag="run1"):
    setup(tag, seed_path)
    
    # 第 1 阶段
    while state.foundation_score < 7.5 or state.lore_score < 7.0:
        weakest = evaluate_foundation()
        improve_layer(weakest)
        score = evaluate_foundation()
        if score > state.foundation_score:
            commit(f"foundation: improve {weakest}")
            state.foundation_score = score
        else:
            reset()
    
    state.phase = "drafting"
    
    # 第 2 阶段
    for ch in range(1, state.chapters_total + 1):
        for attempt in range(5):
            draft_chapter(ch)
            score = evaluate_chapter(ch)
            if score > 6.0:
                commit(f"drafting: ch {ch} score {score}")
                break
            else:
                reset()
        mechanical_slop_pass(ch)
    
    state.phase = "revision"
    
    # 第 3 阶段
    prev_score = 0
    for cycle in range(1, 7):
        # 诊断
        cuts = adversarial_edit_all()
        apply_top_cuts(cuts, types=["OVER-EXPLAIN", "REDUNDANT"])
        panel = run_reader_panel()
        
        # 结构化修复
        for item in panel.consensus_items():
            brief = generate_brief(item, panel, cuts)
            revise_chapter(item.chapter, brief)
            if evaluate_chapter(item.chapter) > previous:
                commit(f"cycle {cycle}: {item.type}")
            else:
                reset()
        
        # 完整评估
        score = evaluate_full()
        if abs(score - prev_score) < 0.5 and cycle >= 3:
            break  # 陷入平台期
        prev_score = score
        
        # 根据评估进行针对性修复
        fix_eval_callouts(score.top_suggestion)
        slop_pass(rewritten_chapters)
        
        commit(f"Cycle {cycle} complete: score {score}")
    
    # 第 4 阶段
    rebuild_docs()
    typeset()
    export()
```

---

*此流水线源自 60+ 次提交、5 个修改周期、2 次读者评审团讨论、2 次对抗性编辑，以及智能体耗时约 20 小时创作出一部 7.5 万字的奇幻小说。*
