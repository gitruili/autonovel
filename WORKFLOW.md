# 工作流 (WORKFLOW)

运行 autonovel 的详细步骤指南。

有关完整的技术流水线规范，请参阅 [PIPELINE.md](PIPELINE.md)。

---

## 快速开始

```bash
# 1. 设置
cd ~/autonovel
cp .env.example .env   # 添加你的 Anthropic 或 MiniMax API 密钥

# 2. 查看可用题材并初始化项目
uv run python autonovel_cli.py genres
uv run python autonovel_cli.py init --title "我的小说" --genre "种田文"

# 3a. 方式一：生成灵感种子（AI 生成多个概念供选择）
uv run python autonovel_cli.py generate seed

# 3b. 方式二：长篇脑洞生成（推荐，支持市场调研+自动分批）
uv run python autonovel_cli.py generate seed --long-form --count 5 --target-words 1000000 --market-research reports/7mao.md

# 3c. 方式三：提供你自己的脑洞（自动评价+优化+保存到 seed.txt）
uv run python autonovel_cli.py generate seed --input-file concept.txt

# 4. 生成设定文件（seed.txt 已就绪时）
uv run python autonovel_cli.py generate foundation

# (可选) 如果生成设定文件时由于某些原因中断，可指定步骤继续（例如从第5步继续）：
uv run python autonovel_cli.py generate foundation --start-step 5

# 5. 运行完整的流水线
uv run python run_pipeline.py --from-scratch
```

流水线将：
1. 构建世界观、角色、大纲和叙事声音（阶段 1）
2. 顺序起草所有章节（阶段 2）
3. 通过自动循环 + 审查循环进行修改（阶段 3）
4. 导出为手稿、PDF、ePub（阶段 4）

---

## 单独运行各个阶段

```bash
# 仅运行基础构建
uv run python run_pipeline.py --phase foundation

# 仅运行写作
uv run python run_pipeline.py --phase drafting

# 仅运行修改（带最大循环限制）
uv run python run_pipeline.py --phase revision --max-cycles 5

# 仅运行导出
uv run python run_pipeline.py --phase export
```

---

## 手动工具

### 评估 (Evaluation)
```bash
uv run python evaluate.py --phase=foundation   # 对规划文档评分
uv run python evaluate.py --chapter=5           # 对某一章评分
uv run python evaluate.py --full                # 对整本小说评分
```

### 修改 (Revision)
```bash
uv run python adversarial_edit.py all           # 在所有章节中寻找可删减部分
uv run python apply_cuts.py all --types OVER-EXPLAIN REDUNDANT
uv run python reader_panel.py                   # 4个角色的评估
uv run python review.py                         # 双重角色审查
uv run python gen_brief.py --auto               # 自动生成修改简报
uv run python gen_revision.py 5 briefs/ch05.md  # 根据简报重写章节
```

### 美术 (Art) (需要 FAL_KEY)
```bash
uv run python gen_art.py style                  # 派生视觉风格
uv run python gen_art.py curate cover --n=6     # 生成封面的多个变体
uv run python gen_art.py pick cover 3           # 选择第 3 个变体
uv run python gen_art.py ornaments-all          # 生成章节装饰图案
uv run python gen_art.py vectorize              # 转换为 SVG → PDF
uv run python gen_cover_print.py art/cover.png --canvas-width 11.889 --canvas-height 8.75 --spine-width 0.639
```

### 有声书 (Audiobook) (需要 ELEVENLABS_API_KEY)
```bash
uv run python gen_audiobook_script.py           # 解析所有章节
uv run python gen_audiobook.py --list-voices    # 浏览声音
uv run python gen_audiobook.py --test 1         # 测试第一章
uv run python gen_audiobook.py                  # 生成所有章节
uv run python gen_audiobook.py --assemble       # 拼接音频
```

### 导出 (Export)
```bash
uv run python build_outline.py                  # 重新构建大纲
uv run python build_arc_summary.py              # 重新构建情节摘要
python3 typeset/build_tex.py && cd typeset && tectonic novel.tex  # PDF
```

---

## 三个循环 (The Three Loops)

```
内部循环 (INNER LOOP) (智能体负责，彻夜运行):
  修改 → 评估 → 保留/丢弃 → 重复

外部循环 (OUTER LOOP) (你负责，当你查看时):
  阅读结果 → 引导 program.md / evaluate.py / 各个层级文件
  → 让智能体再次运行

审查循环 (REVIEW LOOP) (在自动修改之后):
  发送给审查模型 → 解析审查结果 → 修复首要问题 → 重复
  → 当没有留下重大的无条件缺陷时停止
```

你不是在写小说。你是在编写**写小说**的系统。
