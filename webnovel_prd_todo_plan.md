# Autonovel 百万字网文改造 PRD 与执行计划

## 1. Summary

目标是把现有 `autonovel` 从 8-10 万字中短篇/实体书流水线，升级为可支撑 100 万字以上、300-1000+ 章长篇网文连载的工程化写作系统。

第一版不追求完整 RAG、复杂 Agent 框架或 Web UI，而是先跑通“一章事务闭环”：

```text
章纲生成
  -> 上下文拼装
  -> 正文生成
  -> delta 抽取
  -> 状态校验
  -> 网文审计
  -> 状态应用
  -> 快照
  -> Git commit
```

MVP 成功标准：

- 新流程可生成并验收至少 1 章长篇网文章节。
- 每个 accepted chapter 都有正文、章级合同、上下文、delta、审计报告、状态更新和快照。
- 状态校验能阻断凭空物品、未来信息、错误伏笔回收、资源重复使用。
- 回滚到某个 accepted commit 后，`story/state/` 与 `memory.sqlite` 同步恢复。
- 现有短篇流水线作为 legacy 暂留，但不作为 MVP 验收目标。

## 2. PRD

### 2.1 用户与场景

目标用户：

- 使用 AI 辅助长期连载小说的作者。
- 想把小说生产流程工程化、可审计、可回滚的开发者。
- 需要在数百章规模下维持设定、人物、伏笔、资源账本一致性的创作团队。

核心使用场景：

- 从已有总纲和基础设定开始，持续生成长篇网文章节。
- 每章写作前按当前状态动态拼装上下文，而不是全量塞入所有 Markdown。
- 每章写完后抽取事实变化，并用代码层校验阻断设定崩坏。
- 每卷结束压缩记忆，降低过期信息优先级。
- 需要回滚时，正文、状态、记忆索引同步恢复。

### 2.2 核心需求

- 长篇上下文不能随章节数线性膨胀。
- 世界、角色、伏笔、物品、战力、支线必须可机器校验。
- Markdown 仍保留给人看，但真实状态以 JSON/SQLite 为准。
- 每章必须像数据库事务一样，要么完整 accepted，要么丢弃重试。
- 评估体系既看文学质量，也看网文追读力、章末钩子、爽点兑现、注水比例和伏笔债务。
- 新开发以长篇事务闭环为唯一主线；现有短篇脚本只在可复用时被改造或迁移。

### 2.3 非目标

- 第一版不做 Web UI。
- 第一版不做 embedding/reranker。
- 第一版不主动清理、迁移或删除完整短篇流水线。
- 第一版不生成 1000 章完整大纲。
- 第一版不做多 Provider 复杂路由。
- 第一版不适配美术、有声书、落地页的长篇工作流。

### 2.4 成功指标

- 能执行 `validate_state.py --full` 并通过初始状态校验。
- 能执行 `run_webnovel_pipeline.py --chapter 1` 完成一章事务。
- `story/runtime/ch_0001/` 中产物完整，包括 `context.json`、`draft.md`、`delta.json`、`audit.json`、`trace.json`。
- accepted 后状态文件更新，且 `story/memory/snapshots/` 生成快照。
- `snapshot_state.py restore --commit <ref>` 后，状态与正文一致。

## 3. Public Interfaces And Data Contracts

### 3.1 新目录

```text
story/
├── project.json
├── plans/
├── state/
├── memory/
│   ├── memory.sqlite
│   ├── embeddings/
│   └── snapshots/
├── runtime/
└── projections/
```

章节目录策略：

- 新长篇流程读写 `chapters/v001/ch_0001.md`。
- 旧 `chapters/ch_XX.md` 文件如存在，只作为 legacy 输入或迁移来源。
- 第一版不要求旧章节目录继续可写，也不为旧命名新增回归测试。

### 3.2 新状态文件

新增 `story/project.json`：

- `title`
- `genre`
- `target_words`
- `target_chapters`
- `default_chapter_chars`
- `current_volume`
- `current_chapter`
- `current_chars`
- `phase`
- `status`

新增七个真相文件：

- `story/state/current_state.json`
- `story/state/character_matrix.json`
- `story/state/power_ledger.json`
- `story/state/pending_hooks.json`
- `story/state/chapter_summaries.json`
- `story/state/subplot_board.json`
- `story/state/emotional_arcs.json`

所有重要事实必须具备时序字段：

- `source_chapter`
- `valid_from_chapter`
- `valid_until_chapter`
- `last_seen_chapter`
- `visibility`
- `status`
- `confidence`

### 3.3 新脚本接口

`story_schema.py`

- 定义 Pydantic schema。
- 提供 `count_cn_words(text: str) -> int`。
- 提供基础 JSON load/save helper。

`validate_state.py`

```bash
uv run python validate_state.py --full
uv run python validate_state.py --delta story/runtime/ch_0001/delta.json --chapter 1
```

职责：

- 校验 state JSON schema。
- 校验 delta schema。
- 校验角色知识边界。
- 校验物品、资源、战力账本。
- 校验伏笔新增、推进、回收是否合法。

`gen_volume_plan.py`

```bash
uv run python gen_volume_plan.py --volume 1
```

输出：

- `story/plans/volume_001.yaml`

`gen_chapter_plan.py`

```bash
uv run python gen_chapter_plan.py --chapter 1
```

输出：

- `story/plans/chapter_0001.yaml`
- `story/runtime/ch_0001/intent.md`

`memory_orchestrator.py`

```bash
uv run python memory_orchestrator.py --chapter 1 --out story/runtime/ch_0001/context.json
```

职责：

- 读取章级合同。
- 读取当前卷合同。
- 读取状态切片。
- 读取最近 3-5 章摘要。
- 使用 SQLite FTS5 检索旧摘要或片段。
- 输出 token 预算内的 `context.json`。

`draft_chapter.py`

长篇接口：

```bash
uv run python draft_chapter.py 1 \
  --context story/runtime/ch_0001/context.json \
  --out story/runtime/ch_0001/draft.md
```

新模式职责：

- 不再全量读取 `world.md`、`characters.md`、`outline.md`、`canon.md`。
- 只读取 `context.json`。
- 同步写入 `story/runtime/ch_0001/draft.md` 和 `chapters/v001/ch_0001.md`。
- 旧无 `--context` 调用属于 legacy path，能否继续工作不作为验收目标。

`extract_delta.py`

```bash
uv run python extract_delta.py \
  --chapter 1 \
  --draft story/runtime/ch_0001/draft.md \
  --out story/runtime/ch_0001/delta.json
```

输出 delta 包括：

- `new_facts`
- `character_updates`
- `relationship_updates`
- `power_updates`
- `resource_updates`
- `item_updates`
- `hook_updates`
- `subplot_updates`
- `emotional_arc_updates`
- `chapter_summary`

`webnovel_audit.py`

```bash
uv run python webnovel_audit.py \
  --chapter 1 \
  --draft story/runtime/ch_0001/draft.md \
  --delta story/runtime/ch_0001/delta.json \
  --out story/runtime/ch_0001/audit.json
```

审计维度：

- 章末钩子。
- 上一章承诺兑现。
- 节奏推进。
- 爽点铺垫、代价和反应。
- 注水比例。
- 连贯性。
- 账本合规。
- 伏笔债务变化。
- 卷级进度。

`snapshot_state.py`

```bash
uv run python snapshot_state.py create --chapter 1
uv run python snapshot_state.py restore --commit <ref>
```

职责：

- 创建 `story/memory/snapshots/ch_0001_<timestamp>.zip` 或 commit 关联快照。
- 维护 `story/memory/snapshots/commit_index.json`。
- 恢复 `story/project.json`、`story/state/*.json`、`story/memory/memory.sqlite`、必要 runtime trace。

`run_webnovel_pipeline.py`

长篇编排入口：

```bash
uv run python run_webnovel_pipeline.py --chapter 1
uv run python run_webnovel_pipeline.py --volume 1 --chapters 1-20
```

`run_pipeline.py` 暂不作为长篇入口，保留为 legacy 脚本，后续在长篇闭环稳定后再决定删除、归档或拆出可复用函数。

## 4. Implementation Todo List

### Phase 0: 长篇基线准备

目标：清理会阻塞长篇 MVP 的问题，建立独立长篇入口和目录基线。

任务：

- 新增 `run_webnovel_pipeline.py` 作为长篇编排入口。
- 梳理现有脚本，标记哪些直接复用、哪些改造复用、哪些 legacy 暂留。
- 暂停把旧 `run_pipeline.py` 作为长篇改造目标，避免双模式分支膨胀。
- 新增中文字数统计函数 `count_cn_words()`。
- 替换长篇路径中用于中文正文统计的 `split()` 计数。
- 明确新长篇章节命名为 `chapters/v001/ch_0001.md`。

验收：

- `run_webnovel_pipeline.py --help` 可运行。
- 长篇脚本不会依赖旧 `state.json` 作为真实状态来源。
- 新章节路径、runtime 路径、state 路径被统一定义。
- 中文章节字数统计合理。

### Phase 1: 结构化状态 MVP

目标：让系统能记录长篇状态。

任务：

- 新增 `story/` 目录结构。
- 新增 `story_schema.py`。
- 创建 `story/project.json` 初始文件。
- 创建七个真相文件的初始 JSON。
- 实现 `validate_state.py --full`。
- 将现有 `world.md`、`characters.md`、`canon.md` 的核心内容半自动导入 state。
- 新增 `story/projections/`，保留人类可读 Markdown 投影。

验收：

- 所有 JSON 可通过 schema 校验。
- 可以读取当前章、当前卷、角色、伏笔、账本状态。
- `validate_state.py --full` 在初始状态下通过。

### Phase 2: 章级合同与上下文编排

目标：替换全量上下文注入。

任务：

- 实现 `gen_volume_plan.py`。
- 实现 `gen_chapter_plan.py`。
- 实现 `memory_orchestrator.py` 的无向量版本。
- 使用 SQLite FTS5 建立章节摘要和片段检索。
- 改造 `draft_chapter.py` 支持 `--context` 和 `--out`。
- 旧无 `--context` CLI 暂留为 legacy，不新增兼容性工作。

验收：

- 写一章时不再全量塞入所有设定。
- `context.json` 可审计。
- prompt token 不随章节数线性增长。

### Phase 3: Delta 提取与硬校验

目标：让章节写完后自动沉淀状态。

任务：

- 实现 `extract_delta.py`。
- 在 `story_schema.py` 中实现 `ChapterDelta` schema。
- 实现 delta parse 失败后的单独重试逻辑。
- 实现资源、物品、战力基础校验。
- 实现伏笔新增、推进、回收校验。
- 实现角色知识边界校验。
- 实现 `apply_delta` 逻辑，只允许追加或关闭旧事实，不允许直接覆盖历史事实。

验收：

- 每章生成 `delta.json`。
- 错误 delta 不会写入 state。
- 凭空物品、越级突破、未来信息可被拦截。
- 重大矛盾阻断提交，而不是只写入报告。

### Phase 4: 网文专项审计

目标：把评估从文学质量扩展到连载质量。

任务：

- 新增 `webnovel_audit.py`。
- 扩展 `evaluate.py` 输出，合并网文审计结果。
- 增加章末钩子评分。
- 增加上一章承诺兑现评分。
- 增加注水检测。
- 增加爽点铺垫和代价检测。
- 增加伏笔债务检测。
- 增加卷级进度检测。
- 将账本重大违规设为阻断项。
- 将钩子弱、节奏弱、注水高设为可重写项。

验收：

- 每章输出文学评分和网文评分。
- `audit.json` 包含阻断项和警告项。
- 账本重大违规会导致本章失败。
- 章末钩子弱时可触发章末局部重写。

### Phase 5: 事务提交与快照回滚

目标：保证文本、状态、记忆同步。

任务：

- 实现 `snapshot_state.py create`。
- 实现 `snapshot_state.py restore`。
- 新增 `story/memory/snapshots/commit_index.json`。
- 实现 `run_webnovel_pipeline.py` 的 commit 流程。
- 禁止新长篇流程裸调用 `git reset --hard`。
- 将状态恢复统一封装到 `snapshot_state.py restore`。

建议提交流程：

```text
1. 正文通过评估
2. delta 通过校验
3. 应用 delta 到 story/state/
4. 更新 memory.sqlite
5. 创建预快照
6. git add -A
7. git commit
8. 更新 commit_index.json
9. git add/commit 或 amend
```

验收：

- 回滚到任意 accepted commit 后，state 和 memory 同步恢复。
- 恢复后 `validate_state.py --full` 通过。
- 自动续写不会读取未来事实。

### Phase 6: 长篇章节循环

目标：能连续写 20-50 章并保持状态一致。

任务：

- 扩展 `run_webnovel_pipeline.py` 支持卷/章双层进度。
- 每章运行完整事务。
- 每 5 章运行小结审计。
- 每卷结束运行 `run_compaction.py`。
- 更新 `story/projections/` 中的人类可读投影文档。

验收：

- 连续生成至少 20 章。
- 状态文件可持续增长但不失控。
- 伏笔池和账本没有明显错位。
- prompt 上下文不随章节数线性增长。

### Phase 7: RAG 增强

目标：提升旧剧情召回能力。

任务：

- 为章节摘要和片段建立 SQLite FTS5。
- 增加实体标签：角色、地点、物品、伏笔、支线。
- 加入 embedding。
- 加入 reranker。
- 对检索结果做去重和时序过滤。
- 禁止返回大于当前章节的内容。

验收：

- 第 100 章可正确检索第 20 章埋下的相关伏笔。
- 检索不会返回未来章节信息。
- 检索片段有来源章节和可信度。

### Phase 8: 体验优化

目标：提升长期使用体验。

可选任务：

- 新增 CLI 总入口。
- 新增简单 dashboard。
- 新增守护进程自动连载。
- 新增每日写作报告。
- 新增手动审核界面。
- 新增多题材模板。

## 5. Test Plan

### 5.1 单元测试

- `count_cn_words()`：中文、英文、数字、混合文本计数。
- schema 测试：合法/非法 `project.json`、`ChapterPlan`、`VolumePlan`、`ChapterDelta`。
- delta 校验：凭空新增物品、重复消耗资源、未来章节信息、回收不存在伏笔。
- 伏笔状态流转：`open -> advanced -> resolved` 合法，`resolved -> open` 默认非法。
- 快照测试：创建快照、恢复快照、缺失快照时阻断续写。

### 5.2 集成测试

- `validate_state.py --full` 在空白初始化 story 后通过。
- `gen_volume_plan.py --volume 1` 生成合法 YAML。
- `gen_chapter_plan.py --chapter 1` 生成合法 YAML。
- `memory_orchestrator.py --chapter 1` 生成 token 预算内的 `context.json`。
- `draft_chapter.py 1 --context ... --out ...` 能写入 runtime draft。
- `extract_delta.py` 能从 draft 生成合法 delta。
- `webnovel_audit.py` 能生成 `audit.json`。
- `run_webnovel_pipeline.py --chapter 1` 能完成一章事务并生成 commit/snapshot。

### 5.3 手动验收场景

- 手动制造一个 delta：角色获得不存在的物品，确认校验失败。
- 手动制造一个 delta：角色知道未来章节事实，确认校验失败。
- 手动制造一个 delta：回收不存在的伏笔，确认校验失败。
- 接受一章后恢复到上一章 commit，确认状态、memory、章节正文一致。
- 连续生成 5 章，确认 `pending_hooks.json`、`chapter_summaries.json`、`power_ledger.json` 持续更新。

## 6. Execution Order

推荐执行顺序：

1. Phase 0：建立独立长篇入口和路径基线。
2. Phase 1：建立 `story/` 和 schema。
3. Phase 2：实现 `context.json` 写作路径。
4. Phase 3：实现 delta 和硬校验。
5. Phase 4：实现网文审计。
6. Phase 5：实现事务提交和快照。
7. 用 `run_webnovel_pipeline.py --chapter 1` 跑通一章。
8. 扩展到 5 章。
9. 扩展到 20 章。
10. 再考虑 Phase 7 的 embedding/reranker。

## 7. Risks And Mitigations

### JSON 状态越来越复杂

处理：

- 用 schema 强约束。
- 用 delta 追加更新。
- 定期卷末压缩。
- 投影 Markdown 给人类检查。

### LLM 输出 delta 不稳定

处理：

- 严格 JSON schema。
- parse 失败单独重试 delta，不重写正文。
- 对关键字段使用枚举和 ID。
- 重大不确定项进入人工审核队列。

### RAG 检索污染上下文

处理：

- 默认按章节时序过滤。
- 检索结果必须带 `source_chapter`。
- 禁止返回大于当前章节的内容。
- Composer 对上下文做 token 预算和优先级裁剪。

### 快照体积过大

处理：

- JSON 状态和 SQLite 必须快照。
- embedding 可重建时可不入快照。
- 大文件使用压缩。
- 每卷保留完整快照，每章保留增量快照。

### 评估过严导致无法前进

处理：

- 分清阻断项和警告项。
- 账本、时间线、角色知识边界是阻断项。
- 文风和追读力可通过修订重试。
- 达到最低门槛先前进，每卷再统一修。

## 8. Assumptions

- 现有短篇流水线作为 legacy 暂留，不作为新系统验收目标。
- 第一版使用 JSON + SQLite FTS5，不引入 embedding/reranker。
- 第一轮开发目标是“跑通一章事务闭环”，不是一次性完成 100 万字自动连载系统。
- 旧 Markdown 文档继续保留，但只作为人类可读投影和模型背景摘要。
- 所有 accepted chapter 必须绑定状态快照。
- 重大状态矛盾必须阻断提交。
