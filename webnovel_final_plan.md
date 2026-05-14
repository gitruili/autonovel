# autonovel 百万字长篇网文改造最终实施方案

## 1. 改造目标

将现有 `autonovel` 从面向 8-10 万字中短篇/实体书的一次性生成流水线，升级为可支撑 100 万字以上、300-1000+ 章长篇网文连载的工程化写作系统。

核心目标：

1. 解决长篇写作中的上下文爆炸问题。
2. 防止中后期设定崩塌、吃书、战力崩坏、物品账本错乱。
3. 支持总纲、卷纲、章纲分级规划，而不是一次性生成全书大纲。
4. 保留现有 `autonovel` 的生成、评估、修改、保留/丢弃循环。
5. 建立文本、记忆、状态、索引、快照一致的长篇回滚机制。
6. 将静态 Markdown 设定文档升级为“机器可校验状态 + 人类可读投影”的双层体系。

## 2. 总体原则

### 2.1 不推倒重写

当前工程已经具备完整的基础构建、写作、评估、修改、导出流水线。改造应优先在现有脚本上扩展，而不是重写成另一个系统。

保留内容：

- `llm_client.py` 的多模型调用抽象。
- `draft_chapter.py` 的章节生成能力。
- `evaluate.py` 的机械 AI 痕迹检测和 LLM 裁判。
- `run_pipeline.py` 的阶段编排、失败重试和 Git 提交策略。
- `adversarial_edit.py`、`gen_brief.py`、`gen_revision.py` 的修订闭环。
- `reader_panel.py`、`review.py` 的整书审查能力。

### 2.2 Markdown 不废弃，但降级

现有 `world.md`、`characters.md`、`outline.md`、`canon.md` 继续保留，但定位调整为：

- 给人类阅读和编辑的投影文档。
- 给模型提供稳定风格和背景说明的摘要材料。
- 不再作为唯一真实状态来源。

机器事实转入结构化 JSON 和 SQLite：

- 角色状态。
- 资源账本。
- 战力体系。
- 伏笔池。
- 章节摘要。
- 支线进度。
- 情感弧线。

### 2.3 评估体系只扩展，不替换

现有 `evaluate.py` 已经覆盖：

- 文风一致性。
- 节拍覆盖。
- 角色语气。
- 伏笔植入。
- 连贯性。
- canon 合规。
- AI 痕迹检测。

长篇网文改造时不应替换这些能力，而应新增网文专项审计：

- 章末钩子强度。
- 追读力。
- 爽点兑现。
- 注水比例。
- 伏笔债务。
- 卷级进度。
- 资源/物品/战力账本合规。
- 角色信息边界。

### 2.4 每章是一个事务

一章只有在以下内容全部完成后，才允许被视为 accepted：

1. 正文写入。
2. 章节摘要生成。
3. 状态 delta 提取。
4. delta 通过 schema 校验。
5. 资源、战力、伏笔、角色状态通过一致性校验。
6. 写作质量和网文质量通过评估门槛。
7. SQLite 记忆索引更新。
8. Git commit 与状态快照绑定。

如果任一步失败，本章应被丢弃或重写，不允许半提交。

## 3. 目标目录结构

```text
autonovel/
├── chapters/
│   ├── v001/
│   │   ├── ch_0001.md
│   │   ├── ch_0002.md
│   │   └── ...
│   └── v002/
│       └── ...
│
├── story/
│   ├── project.json
│   ├── plans/
│   │   ├── master_plan.yaml
│   │   ├── volume_001.yaml
│   │   ├── volume_002.yaml
│   │   ├── chapter_0001.yaml
│   │   └── chapter_0002.yaml
│   │
│   ├── state/
│   │   ├── current_state.json
│   │   ├── character_matrix.json
│   │   ├── power_ledger.json
│   │   ├── pending_hooks.json
│   │   ├── chapter_summaries.json
│   │   ├── subplot_board.json
│   │   └── emotional_arcs.json
│   │
│   ├── memory/
│   │   ├── memory.sqlite
│   │   ├── embeddings/
│   │   └── snapshots/
│   │       ├── commit_index.json
│   │       └── <commit_hash>.zip
│   │
│   ├── runtime/
│   │   └── ch_0001/
│   │       ├── intent.md
│   │       ├── context.json
│   │       ├── draft.md
│   │       ├── delta.json
│   │       ├── audit.json
│   │       └── trace.json
│   │
│   └── projections/
│       ├── world.md
│       ├── characters.md
│       ├── canon.md
│       ├── hooks.md
│       └── volume_001_summary.md
│
├── memory_orchestrator.py
├── gen_master_plan.py
├── gen_volume_plan.py
├── gen_chapter_plan.py
├── extract_delta.py
├── validate_state.py
├── webnovel_audit.py
├── run_compaction.py
└── run_pipeline.py
```

## 4. 核心数据层设计

### 4.1 `project.json`

记录书籍级元信息和当前进度。

```json
{
  "title": "示例书名",
  "genre": "xianxia_business",
  "target_words": 1000000,
  "target_chapters": 400,
  "default_chapter_chars": 3000,
  "current_volume": 1,
  "current_chapter": 1,
  "current_chars": 0,
  "phase": "drafting",
  "status": "active"
}
```

### 4.2 七个真相文件

#### `current_state.json`

记录世界当前状态：

- 当前时间。
- 当前地点。
- 主要势力状态。
- 当前公开信息。
- 各地点可用资源。
- 当前卷主矛盾进度。

#### `character_matrix.json`

记录角色状态和关系网络：

- 角色基础信息。
- 当前地点。
- 当前身份。
- 当前目标。
- 与其他角色的关系。
- 角色已知信息边界。
- 说话习惯。
- 最近出场章节。

#### `power_ledger.json`

记录战力、境界、资源、物品：

- 境界体系。
- 主角和重要角色的能力等级。
- 法宝、丹药、银钱、产业、技能。
- 获得来源。
- 消耗记录。
- 损坏、转移、丢失、死亡状态。

#### `pending_hooks.json`

记录伏笔和悬念：

- 伏笔内容。
- 创建章节。
- 最近推进章节。
- 预计回收区间。
- 当前状态：`open`、`advanced`、`resolved`、`stale`、`dropped`。
- 与角色、地点、支线的关联。

#### `chapter_summaries.json`

记录每章摘要：

- 章节标题。
- 核心事件。
- 场景列表。
- 角色变化。
- 资源变化。
- 新增事实。
- 新增伏笔。
- 回收伏笔。
- 章末钩子。

#### `subplot_board.json`

记录支线进度：

- 支线名称。
- 当前阶段。
- 最近推进章节。
- 关联角色。
- 必须回收的承诺。
- 停滞风险。

#### `emotional_arcs.json`

记录情感弧线：

- 主角情绪状态。
- 关键关系变化。
- 情感债务。
- 冲突升级点。
- 和解/决裂/信任变化。

### 4.3 时序字段

所有重要事实都应带时序字段，避免模型在第 200 章写作时读取第 300 章才知道的信息。

推荐字段：

```json
{
  "id": "fact_000001",
  "content": "角色甲知道角色乙隐藏身份",
  "source_chapter": 87,
  "valid_from_chapter": 87,
  "valid_until_chapter": null,
  "last_seen_chapter": 92,
  "visibility": ["角色甲"],
  "status": "active",
  "confidence": 1.0
}
```

## 5. 分级规划体系

### 5.1 全书总纲

`gen_master_plan.py` 生成 `story/plans/master_plan.yaml`。

总纲只规划宏观结构，不展开所有章节。

应包含：

- 题材。
- 卖点。
- 主角长期目标。
- 核心金手指或能力规则。
- 世界底层规则。
- 全书主要阶段。
- 大反派或终极矛盾。
- 重要伏笔。
- 禁止写法。

### 5.2 卷级合同

`gen_volume_plan.py` 生成 `story/plans/volume_XXX.yaml`。

每卷建议 30-80 章，不建议 100 章以上，避免卷级规划过粗。

卷级合同字段：

```yaml
volume: 1
title: 第一卷标题
target_chapters: 50
target_chars: 150000
main_conflict: 本卷主矛盾
opening_hook: 开卷钩子
midpoint_reversal: 中段反转
finale: 卷末高潮
next_volume_hook: 下一卷钩子
new_characters: []
returning_characters: []
power_progression: []
resource_progression: []
hooks_to_create: []
hooks_to_resolve: []
subplot_plan: []
anti_patterns: []
```

卷级规划要求：

- 前 3 章建立本卷明确冲突。
- 每 5 章至少一个阶段性推进。
- 中段必须有一次失败、反转或代价。
- 卷末 3 章集中爆发。
- 卷末必须留下下一卷动力。

### 5.3 章级合同

`gen_chapter_plan.py` 生成 `story/plans/chapter_XXXX.yaml`。

章级合同字段：

```yaml
chapter: 67
volume: 3
title: 章节标题
goal: 本章核心推进
target_chars: 3500
viewpoint: 视角人物
required_beats:
  - 必须完成的剧情节拍
continuity_requirements:
  - 必须衔接的前文状态
power_or_resource_changes:
  - 预期的境界、物品、资源变化
hooks_to_advance:
  - 本章必须推进的伏笔
hooks_to_create:
  - 本章允许新增的伏笔
hooks_to_resolve:
  - 本章必须回收的伏笔
forbidden_moves:
  - 本章禁止突然突破、禁止新神器、禁止角色知道未来事实
ending_hook: 章末钩子目标
```

## 6. 记忆编排系统

### 6.1 目标

将写作前的上下文注入从“全量加载所有 Markdown”改为“按优先级动态拼装相关上下文”。

### 6.2 上下文优先级

每章写作前，`memory_orchestrator.py` 按以下优先级拼装上下文：

1. 世界底层硬规则。
2. 当前题材和文风规则。
3. 当前章合同。
4. 当前卷目标和本卷主矛盾。
5. 核心角色当前状态。
6. 当前场景相关角色关系。
7. 最近 3-5 章摘要。
8. 本章涉及的伏笔和支线。
9. 本章涉及的资源、物品、战力账本。
10. 检索出的旧章节片段。

### 6.3 Token 预算

推荐每章上下文预算：

- 总纲和世界硬规则：1000-1500 token。
- 卷级合同：1000 token。
- 章级合同：1000 token。
- 最近章节摘要：1500-2500 token。
- 角色和状态切片：1500-2500 token。
- 伏笔/账本切片：1000-1500 token。
- 检索旧章节片段：2000-3000 token。

总量控制在 8000-12000 token 内，除非模型上下文窗口和成本允许扩展。

### 6.4 检索策略

第一阶段先使用低成本方案：

- SQLite FTS5。
- 关键词检索。
- 章节摘要检索。
- 角色、地点、物品、伏笔 ID 过滤。

第二阶段再引入：

- 向量 embedding。
- reranker。
- 混合检索。

不要在最初阶段直接引入复杂 RAG 服务，否则会增加调试难度。

## 7. 每章写作管线

### 7.1 最小可用管线

第一版采用 6 步：

```text
plan -> compose -> draft -> extract_delta -> validate -> evaluate_and_commit
```

#### `plan`

读取总纲、卷纲、当前状态，生成章级合同。

输出：

- `story/plans/chapter_XXXX.yaml`
- `story/runtime/ch_XXXX/intent.md`

#### `compose`

读取章级合同和状态库，编译写作上下文。

输出：

- `story/runtime/ch_XXXX/context.json`

#### `draft`

调用写作模型生成正文。

输出：

- `story/runtime/ch_XXXX/draft.md`
- `chapters/vXXX/ch_XXXX.md`

#### `extract_delta`

从正文中抽取事实变化。

输出：

- `story/runtime/ch_XXXX/delta.json`

delta 内容包括：

- 新事实。
- 角色状态变化。
- 资源变化。
- 物品变化。
- 伏笔新增、推进、回收。
- 支线推进。
- 情感弧线变化。

#### `validate`

对 delta 和正文做硬校验。

检查：

- JSON schema 是否有效。
- 角色是否知道不该知道的信息。
- 物品是否凭空出现。
- 已消耗资源是否重复使用。
- 境界突破是否满足前置条件。
- 时间线是否倒错。
- 伏笔回收是否对应已有伏笔。

#### `evaluate_and_commit`

运行原有文学质量评估和新增网文审计。

通过后：

- 应用 delta。
- 更新 SQLite 记忆库。
- 创建快照。
- Git commit。

失败后：

- 丢弃本次正文。
- 保留 runtime trace 供调试。
- 进入下一次尝试。

### 7.2 完整管线

成熟后扩展为：

```text
Planner
  -> Composer
  -> Writer
  -> Observer
  -> Reflector
  -> Validator
  -> Auditor
  -> Reviser
  -> Snapshotter
  -> Committer
```

不要一开始就做完整多 Agent。先把状态闭环跑通，再拆分角色。

## 8. 评估与审计体系

### 8.1 保留现有评估

继续使用：

- 机械 AI 痕迹检测。
- 禁用词检测。
- 句式单一检测。
- 展示而非讲述检测。
- LLM 文学裁判。
- reader panel。
- review loop。

### 8.2 新增网文专项评估

新增 `webnovel_audit.py`，或将以下维度并入 `evaluate.py`。

#### 章级维度

- `chapter_hook_score`：章末钩子是否具体、有风险、有下章动力。
- `promise_payoff_score`：本章是否兑现上一章承诺。
- `pacing_score`：是否推进明确，是否拖沓。
- `cool_point_score`：爽点是否有铺垫、代价和反应。
- `filler_ratio`：无推进段落比例。
- `continuity_score`：是否和上一章状态一致。
- `ledger_compliance`：资源、物品、战力是否符合账本。
- `hook_debt_delta`：本章新增和偿还伏笔是否健康。

#### 卷级维度

- 本卷主矛盾是否推进。
- 小高潮间隔是否过长。
- 支线是否长期停滞。
- 反派或阻力是否足够成长。
- 主角成长是否过快或过慢。
- 卷末是否能自然导向下一卷。

### 8.3 机械检测不要奖励套路词

不要用“震惊”“突破”“究竟”等词作为钩子强度依据。真正应检测：

- 是否留下具体未解决问题。
- 是否存在明确风险。
- 是否和下一章合同连接。
- 是否推进旧伏笔。
- 是否制造新的选择压力。
- 是否避免无意义吊胃口。

### 8.4 中文字数统计

当前英文式 `split()` 不适合中文。新增统一字数统计：

```python
def count_cn_words(text: str) -> int:
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    ascii_words = len(re.findall(r"[A-Za-z0-9]+", text))
    return chinese_chars + ascii_words
```

所有章节目标字数、注水比例、总字数统计都使用这个函数。

## 9. 状态更新与 delta 机制

### 9.1 delta 文件格式

每章生成一个 `delta.json`：

```json
{
  "chapter": 67,
  "new_facts": [],
  "character_updates": [],
  "relationship_updates": [],
  "power_updates": [],
  "resource_updates": [],
  "item_updates": [],
  "hook_updates": [],
  "subplot_updates": [],
  "emotional_arc_updates": [],
  "chapter_summary": {}
}
```

### 9.2 delta 应用原则

1. 所有更新必须可追溯到章节。
2. 不允许覆盖历史事实，只能追加新版本或关闭旧版本。
3. 事实更新必须带 `valid_from_chapter`。
4. 角色知识必须区分“读者知道”和“角色知道”。
5. 模型输出的 delta 必须经过代码层 schema 校验。
6. 重大矛盾必须阻断提交，而不是只写入评估报告。

## 10. Git 与状态快照回滚

### 10.1 问题

长篇系统引入 SQLite、JSON 状态和向量索引后，仅靠 `git reset --hard` 回滚正文是不够的。

如果正文回滚到第 120 章，但记忆库和状态文件仍保留第 121-130 章事实，后续写作会出现：

- 角色提前知道未来信息。
- 已死亡角色仍被认为活着。
- 已消耗物品重新出现。
- 已回收伏笔再次被当成 open。
- 模型基于不存在的剧情续写。

### 10.2 快照策略

每次 accepted chapter commit 前，创建状态快照：

```text
story/memory/snapshots/<commit_hash>.zip
```

快照内容：

- `story/project.json`
- `story/state/*.json`
- `story/memory/memory.sqlite`
- `story/memory/embeddings/`
- `story/plans/*.yaml`
- 必要的 runtime trace

同时维护：

```json
{
  "a1b2c3d": {
    "chapter": 67,
    "snapshot": "story/memory/snapshots/a1b2c3d.zip",
    "created_at": "2026-05-14T12:00:00+08:00"
  }
}
```

### 10.3 提交流程

```text
1. 正文通过评估
2. delta 通过校验
3. 应用 delta 到 story/state/
4. 更新 memory.sqlite
5. 创建临时快照
6. git add -A
7. git commit
8. 获取 commit hash
9. 将快照命名为 commit hash
10. 更新 commit_index.json
11. 再次 git add/commit 或 amend
```

实现时可以采用两种方式：

方案 A：commit 后生成快照，再 `git commit --amend`。  
方案 B：先生成预快照，用章节号命名，commit 后更新 index。  

建议第一版采用方案 B，逻辑更简单。

### 10.4 回滚流程

封装 `restore_commit(ref)`，禁止直接裸调用 `git reset --hard`。

```text
1. 解析目标 commit
2. git reset --hard <commit>
3. 读取 commit_index.json
4. 找到对应 snapshot
5. 恢复 story/state/
6. 恢复 memory.sqlite
7. 恢复 embeddings/
8. 运行 validate_state.py --full
```

如果找不到快照，必须警告并停止自动续写。

## 11. 卷末压缩机制

### 11.1 触发时机

每卷结束后运行 `run_compaction.py`。

### 11.2 压缩内容

- 将本卷所有章节摘要合并为卷级摘要。
- 将已解决伏笔标记为 `resolved`。
- 将长期不再出现的地点、角色、物品降级为低优先级。
- 将死亡、退场、失效内容标记为 `inactive` 或 `outdated`。
- 提炼下一卷必须继承的硬事实。
- 更新人类可读投影文档。

### 11.3 压缩原则

压缩不是删除。旧章节原文、摘要、状态仍在数据库中可检索，只是默认上下文优先级降低。

## 12. 脚本改造计划

### 12.1 新增脚本

#### `story_schema.py`

定义所有 Pydantic schema：

- ProjectState
- ChapterPlan
- VolumePlan
- CharacterState
- PowerLedger
- Hook
- ChapterDelta
- ChapterSummary

#### `memory_orchestrator.py`

负责：

- 检索相关章节。
- 读取真相文件。
- 按优先级拼装上下文。
- 输出 `context.json`。

#### `gen_master_plan.py`

生成全书总纲。

#### `gen_volume_plan.py`

生成卷级合同。

#### `gen_chapter_plan.py`

生成章级合同。

#### `extract_delta.py`

从正文抽取结构化状态变化。

#### `validate_state.py`

校验状态一致性和账本合法性。

#### `webnovel_audit.py`

执行网文专项评估。

#### `run_compaction.py`

执行卷末压缩。

#### `snapshot_state.py`

创建和恢复状态快照。

### 12.2 改造脚本

#### `draft_chapter.py`

从全量加载 Markdown 改为读取 `context.json`。

保留：

- 写作模型调用。
- 文风规则。
- 禁用模式。
- 章尾钩子要求。

新增：

- 章级合同注入。
- 状态切片注入。
- 检索片段注入。
- 中文字数目标。

#### `evaluate.py`

保留现有评估，新增：

- 中文字数统计。
- 网文审计结果合并。
- 账本违规降分。
- 伏笔债务提示。

#### `run_pipeline.py`

将章节循环改为事务状态机：

```text
for chapter:
  generate_plan
  compose_context
  draft
  extract_delta
  validate_delta
  evaluate
  apply_delta
  update_memory
  snapshot
  commit
```

失败重试：

- 写作失败：重试。
- delta 提取失败：重试或单独修 delta。
- schema 失败：阻断。
- 账本违规：重写。
- 文学评分低：重写或修订。
- 钩子弱：局部重写章末。

## 13. 实施路线图

### Phase 0：清理和准备

目标：建立可改造基线。

任务：

1. 整理当前分支，确认现有流水线可运行。
2. 新增 `story/` 目录。
3. 新增中文字符统计工具。
4. 明确章节文件命名从 `ch_01.md` 升级为 `ch_0001.md` 的兼容策略。
5. 保持旧流程仍可运行。

验收：

- 旧 `run_pipeline.py` 不受影响。
- 新目录存在但不参与旧流程。

### Phase 1：结构化状态 MVP

目标：让系统能记录长篇状态。

任务：

1. 新增 `story_schema.py`。
2. 创建 7 个真相文件的初始 JSON。
3. 实现 `validate_state.py --full`。
4. 实现 `project.json`。
5. 将现有 `world.md`、`characters.md`、`canon.md` 的核心内容人工或半自动导入 state。

验收：

- 所有 JSON 可通过 schema 校验。
- 可以读取当前章、当前卷、角色、伏笔、账本状态。

### Phase 2：章级合同与上下文编排

目标：替换全量上下文注入。

任务：

1. 实现 `gen_volume_plan.py`。
2. 实现 `gen_chapter_plan.py`。
3. 实现 `memory_orchestrator.py` 的无向量版本。
4. 改造 `draft_chapter.py` 支持 `--context story/runtime/ch_XXXX/context.json`。
5. 保留旧 CLI 兼容。

验收：

- 写一章时不再全量塞入所有设定。
- `context.json` 可审计。
- prompt token 明显下降。

### Phase 3：delta 提取与硬校验

目标：让章节写完后自动沉淀状态。

任务：

1. 实现 `extract_delta.py`。
2. 实现 delta schema。
3. 实现资源、物品、战力基础校验。
4. 实现伏笔新增、推进、回收校验。
5. 实现角色知识边界校验。

验收：

- 每章生成 `delta.json`。
- 错误 delta 不会写入 state。
- 凭空物品、越级突破、未来信息可被拦截。

### Phase 4：网文审计扩展

目标：把评估从文学质量扩展到连载质量。

任务：

1. 新增 `webnovel_audit.py`。
2. 扩展 `evaluate.py` 输出。
3. 增加章末钩子评分。
4. 增加注水检测。
5. 增加伏笔债务检测。
6. 增加卷级进度检测。

验收：

- 每章输出文学评分和网文评分。
- 账本重大违规会导致本章失败。
- 章末钩子弱时可触发章末重写。

### Phase 5：事务提交与快照回滚

目标：保证文本、状态、记忆同步。

任务：

1. 实现 `snapshot_state.py create`。
2. 实现 `snapshot_state.py restore`。
3. 改造 `run_pipeline.py` 的 commit 流程。
4. 禁止章节管线裸调用 `git reset --hard`。
5. 增加 `commit_index.json`。

验收：

- 回滚到任意 accepted commit 后，state 和 memory 同步恢复。
- 恢复后 `validate_state.py --full` 通过。
- 自动续写不会读取未来事实。

### Phase 6：长篇章节循环

目标：能连续写 20-50 章并保持状态一致。

任务：

1. 改造 `run_pipeline.py` 支持卷/章双层进度。
2. 每章运行完整事务。
3. 每 5 章运行小结审计。
4. 每卷结束运行 `run_compaction.py`。

验收：

- 连续生成至少 20 章。
- 状态文件可持续增长但不失控。
- 伏笔池和账本没有明显错位。
- prompt 上下文不随章节数线性增长。

### Phase 7：RAG 增强

目标：提升旧剧情召回能力。

任务：

1. 为章节摘要和片段建立 SQLite FTS5。
2. 增加实体标签：角色、地点、物品、伏笔、支线。
3. 加入 embedding。
4. 加入 reranker。
5. 对检索结果做去重和时序过滤。

验收：

- 第 100 章可正确检索第 20 章埋下的相关伏笔。
- 检索不会返回未来章节信息。
- 检索片段有来源章节和可信度。

### Phase 8：体验优化

目标：提升长期使用体验。

可选任务：

1. 新增 CLI 总入口。
2. 新增简单 dashboard。
3. 新增守护进程自动连载。
4. 新增每日写作报告。
5. 新增手动审核界面。
6. 新增多题材模板。

## 14. 优先级排序

必须优先做：

1. 结构化状态。
2. 章级合同。
3. 上下文编排。
4. delta 提取。
5. 状态校验。
6. 快照回滚。

可以稍后做：

1. 向量 RAG。
2. Web UI。
3. 多 Provider 复杂路由。
4. 自动通知。
5. 美术、有声书和落地页的长篇适配。

不建议第一阶段做：

1. 一次性重构全部脚本。
2. 一开始就引入复杂 Agent 框架。
3. 一开始就做 1000 章大纲。
4. 只靠 prompt 要求模型不崩设定。
5. 只靠 LLM 审查账本，不做代码层校验。

## 15. 风险与处理

### 15.1 JSON 状态越来越复杂

处理：

- 用 schema 强约束。
- 用 delta 追加更新。
- 定期卷末压缩。
- 投影 Markdown 给人类检查。

### 15.2 LLM 输出 delta 不稳定

处理：

- 严格 JSON schema。
- parse 失败单独重试 delta，不重写正文。
- 对关键字段使用枚举和 ID。
- 重大不确定项进入人工审核队列。

### 15.3 RAG 检索污染上下文

处理：

- 默认按章节时序过滤。
- 检索结果必须带 source_chapter。
- 禁止返回大于当前章节的内容。
- Composer 对上下文做 token 预算和优先级裁剪。

### 15.4 快照体积过大

处理：

- JSON 状态和 SQLite 必须快照。
- embedding 可重建时可不入快照。
- 大文件使用压缩。
- 每卷保留完整快照，每章保留增量快照。

### 15.5 评估过严导致无法前进

处理：

- 分清阻断项和警告项。
- 账本、时间线、角色知识边界是阻断项。
- 文风和追读力可通过修订重试。
- 达到最低门槛先前进，每卷再统一修。

## 16. 最终形态

改造完成后，单章生产应是：

```text
读取项目状态
  -> 生成章级合同
  -> 编译相关上下文
  -> 写作正文
  -> 抽取事实变化
  -> 校验状态和账本
  -> 评估文学质量和网文追读力
  -> 必要时局部修订
  -> 应用状态变化
  -> 更新记忆索引
  -> 创建快照
  -> Git commit
```

卷末生产应是：

```text
汇总本卷章节
  -> 压缩卷级摘要
  -> 清理伏笔和支线状态
  -> 降级过期实体
  -> 生成下一卷规划
  -> 继续章级循环
```

系统最终应具备：

- 百万字级别的上下文控制能力。
- 长期角色、伏笔、物品、战力一致性。
- 可回滚、可审计、可恢复的写作状态。
- 保留现有自动评估和自动修订优势。
- 支持长期连载的卷/章节奏管理。

## 17. 第一轮实际开发建议

第一轮不要追求完整系统，建议只做一个可验证闭环：

1. 新建 `story/` 状态目录。
2. 实现 7 个 JSON 真相文件的最小 schema。
3. 让 `draft_chapter.py` 从 `context.json` 写一章。
4. 让 `extract_delta.py` 生成 `delta.json`。
5. 让 `validate_state.py` 拦截资源和伏笔错误。
6. 让 `run_pipeline.py` 对一章执行完整事务。
7. accepted 后创建快照和 commit。
8. 手动回滚一次，确认状态同步恢复。

只要这个闭环跑通，后续扩展到 20 章、100 章、1000 章就是工程迭代问题，而不是架构问题。
