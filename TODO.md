# TODO

## reader_panel.py 在 revision 阶段缺少 arc_summary.md

- 位置: `run_pipeline.py` → `run_revision()` 步骤 3 (line 500)
- 问题: `reader_panel.py:166` 直接读取 `arc_summary.md`，但该文件由 `build_arc_summary.py` 在 Phase 4 (export) 才生成。首次运行 revision 时文件不存在，`reader_panel.py` 报错，被 `run_tool(check=False)` 静默吞掉，导致 `reader_panel.json` 不生成，后续的 `parse_panel_consensus()` 返回空列表，整条"读者评审 → 定向修订"链路被跳过。
- 修复方向: 在 revision 阶段调用 `reader_panel.py` 之前，先调用 `build_arc_summary.py` 生成 `arc_summary.md`。

## voice.md Part 2 需要人类参与完成

- 位置: `voice.md` 第 96-160 行（Part 2: 文风标识）
- 现状: Part 2 全部是 `<!-- -->` 注释占位符，从未被填充。
- 说明: 这一部分是**人类参与 + AI 辅助**的协作步骤，不是全自动的。需要人类与 AI 配合，为这本特定小说定制文风：基调、句式节奏、词汇域、对话规范、示范段落、反面示范等。
- 时机: 在 Foundation 阶段的世界观/角色/大纲生成完成后、正式起草之前，由人类介入完成。
- 行动: 在 Foundation 和 Drafting 之间增加一个人工检查点（human checkpoint），提示用户完成 voice.md Part 2。

## voice_fingerprint.py 在 Foundation 阶段被错误调用

- 位置: `run_pipeline.py` → `run_foundation()` 第 270-271 行
- 问题: `voice_fingerprint.py` 的实际功能是统计分析 `chapters/ch_*.md` 的量化文风指标（句长、词频、对话比等），但 Foundation 阶段还没有生成任何章节文件，导致 `IndexError: list index out of range`。PIPELINE.md 第 42 行将其描述为"测试段落 → voice.md 第2部分"，但代码实现与此描述不符——它是一个后验分析工具，不是先验生成工具。
- 影响: `run_tool(check=False)` 静默吞掉了错误，不影响管线继续运行，但属于无效调用。
- 修复方向: 从 Foundation 阶段移除 `voice_fingerprint.py` 调用；将其移至 Drafting 完成后或 Revision 阶段，用于检验章节文风一致性。
