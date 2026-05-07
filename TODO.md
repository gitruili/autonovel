# TODO

## reader_panel.py 在 revision 阶段缺少 arc_summary.md

- 位置: `run_pipeline.py` → `run_revision()` 步骤 3 (line 500)
- 问题: `reader_panel.py:166` 直接读取 `arc_summary.md`，但该文件由 `build_arc_summary.py` 在 Phase 4 (export) 才生成。首次运行 revision 时文件不存在，`reader_panel.py` 报错，被 `run_tool(check=False)` 静默吞掉，导致 `reader_panel.json` 不生成，后续的 `parse_panel_consensus()` 返回空列表，整条"读者评审 → 定向修订"链路被跳过。
- 修复方向: 在 revision 阶段调用 `reader_panel.py` 之前，先调用 `build_arc_summary.py` 生成 `arc_summary.md`。
