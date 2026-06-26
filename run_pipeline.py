#!/usr/bin/env python3
"""
run_pipeline.py — 全自动小说生产管线编排器。

运行完整的 autonovel 流水线：从种子概念到最终完稿。
管理状态、Git 提交、自动评估以及失败重试逻辑。

用法:
  python run_pipeline.py                    # 从当前状态继续运行
  python run_pipeline.py --from-scratch     # 从 seed.txt 开始全新的运行
  python run_pipeline.py --phase foundation # 仅运行设定阶段
  python run_pipeline.py --phase drafting   # 仅运行起草阶段
  python run_pipeline.py --phase revision   # 仅运行修订阶段
  python run_pipeline.py --phase export     # 仅运行导出阶段
  python run_pipeline.py --max-cycles 4     # 限制修订循环次数
"""

import argparse
import json
import os
import re
import subprocess
import sys
import yaml
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "state.json"
RESULTS_FILE = BASE_DIR / "results.tsv"
CHAPTERS_DIR = BASE_DIR / "chapters"
BRIEFS_DIR = BASE_DIR / "briefs"
EDIT_LOGS_DIR = BASE_DIR / "edit_logs"
EVAL_LOGS_DIR = BASE_DIR / "eval_logs"

FOUNDATION_THRESHOLD = 7.5
CHAPTER_THRESHOLD = 6.0
MAX_FOUNDATION_ITERS = 20
MAX_CHAPTER_ATTEMPTS = 5
MIN_REVISION_CYCLES = 3
MAX_REVISION_CYCLES = 6
PLATEAU_DELTA = 0.3

PHASE_ORDER = ["foundation", "drafting", "revision", "export"]


# ---------------------------------------------------------------------------
# Helpers: state management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load pipeline state from state.json, creating defaults if missing."""
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return default_state()


def default_state() -> dict:
    return {
        "phase": "foundation",
        "current_focus": "planning",
        "iteration": 0,
        "foundation_score": 0.0,
        "lore_score": 0.0,
        "chapters_drafted": 0,
        "chapters_total": 0,
        "novel_score": 0.0,
        "revision_cycle": 0,
        "debts": [],
    }


def save_state(state: dict):
    """Write state to state.json."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Helpers: logging
# ---------------------------------------------------------------------------

def log_result(commit: str, phase: str, score, word_count: int,
               status: str, description: str):
    """Append a row to results.tsv."""
    header = "commit\tphase\tscore\tword_count\tstatus\tdescription\n"
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text(header, encoding="utf-8")
    elif RESULTS_FILE.stat().st_size == 0:
        RESULTS_FILE.write_text(header, encoding="utf-8")
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{commit}\t{phase}\t{score}\t{word_count}\t{status}\t{description}\n")


def banner(text: str, char: str = "=", width: int = 60):
    """Print a visible phase/step banner."""
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


def step(text: str):
    """Print a step indicator."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {text}")


# ---------------------------------------------------------------------------
# Helpers: subprocess execution
# ---------------------------------------------------------------------------

def run_tool(cmd: str, timeout: int = 600, check: bool = False) -> subprocess.CompletedProcess:
    """
    Run a tool as a subprocess, capturing output.
    Uses shell=True so callers can pass full command strings.
    Returns CompletedProcess; never raises unless check=True.
    """
    # Enforce a safe minimum timeout for reasoning models
    timeout = max(timeout, 1800)
    step(f"RUN: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(BASE_DIR),
        )
        if result.returncode != 0:
            print(f"    WARN: exit code {result.returncode}")
            stderr_preview = (result.stderr or "")[:300]
            if stderr_preview:
                print(f"    stderr: {stderr_preview}")
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr)
        return result
    except subprocess.TimeoutExpired:
        print(f"    ERROR: timed out after {timeout}s")
        # Return a fake CompletedProcess for graceful handling
        fake = subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="TIMEOUT")
        return fake


def uv_run(script: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Shorthand for 'uv run python <script>' from project root."""
    return run_tool(f"uv run python {script}", timeout=timeout)


# ---------------------------------------------------------------------------
# Helpers: git operations
# ---------------------------------------------------------------------------

def git_add_commit(message: str) -> str:
    """Stage all changes and commit. Returns short hash or empty string."""
    run_tool("git add -A")
    result = run_tool(f'git commit -m "{message}" --allow-empty')
    if result.returncode == 0:
        hash_result = run_tool("git rev-parse --short HEAD")
        commit_hash = hash_result.stdout.strip()
        step(f"GIT COMMIT: {commit_hash} — {message}")
        return commit_hash
    else:
        step("GIT: nothing to commit or commit failed")
        return ""


def git_reset_hard(ref: str = "HEAD~1"):
    """Hard reset to discard bad changes."""
    step(f"GIT RESET: {ref}")
    run_tool(f"git reset --hard {ref}")


def git_short_hash() -> str:
    """Get current HEAD short hash."""
    r = run_tool("git rev-parse --short HEAD")
    return r.stdout.strip() if r.returncode == 0 else "unknown"


# ---------------------------------------------------------------------------
# Helpers: score parsing
# ---------------------------------------------------------------------------

def parse_score(stdout: str, key: str = "overall_score") -> float:
    """
    Parse a score from evaluate.py YAML-like stdout output.
    Looks for lines like 'overall_score: 8.0' or 'novel_score: 7.5'.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith(f"{key}:"):
            val = line.split(":", 1)[1].strip()
            try:
                return float(val)
            except ValueError:
                continue
    return -1.0


def parse_lore_score(stdout: str) -> float:
    """Parse lore_score from foundation evaluation output."""
    return parse_score(stdout, "lore_score")


def count_words_in_chapters() -> int:
    """Sum word count across all chapter files."""
    total = 0
    if CHAPTERS_DIR.exists():
        for f in CHAPTERS_DIR.glob("ch_*.md"):
            total += len(f.read_text(encoding="utf-8").split())
    return total


def is_long_form() -> bool:
    """Check if project.json indicates a long-form novel (>= 100 chapters)."""
    proj_path = BASE_DIR / "story" / "project.json"
    if not proj_path.exists():
        return False
    try:
        with open(proj_path, encoding="utf-8") as f:
            proj = json.load(f)
        return proj.get("target_chapters", 0) >= 100
    except Exception:
        return False


def count_chapter_files() -> int:
    """Count the number of chapter files."""
    if not CHAPTERS_DIR.exists():
        return 0
    return len(list(CHAPTERS_DIR.glob("ch_*.md")))


def get_total_chapters(state: dict) -> int:
    """Determine total chapter count from state, project.json, or master_plan.yaml.

    No longer scans outline.md for chapter headings, because outline.md is now a
    stable whole-book master outline (master_summary.md) and does not contain
    per-volume chapter details.
    """
    if state.get("chapters_total", 0) > 0:
        return state["chapters_total"]

    # Try project.json target_chapters
    proj_path = BASE_DIR / "story" / "project.json"
    if proj_path.exists():
        try:
            proj_data = json.loads(proj_path.read_text(encoding="utf-8"))
            target = proj_data.get("target_chapters") or proj_data.get("chapters_total")
            if target:
                return int(target)
        except (json.JSONDecodeError, ValueError):
            pass

    # Try master_plan.yaml volumes chapter_range
    master_plan_path = BASE_DIR / "story" / "plans" / "master_plan.yaml"
    if master_plan_path.exists():
        try:
            master = yaml.safe_load(master_plan_path.read_text(encoding="utf-8"))
            volumes = master.get("volumes", [])
            if volumes:
                last_range = volumes[-1].get("chapter_range", "")
                if "-" in last_range:
                    return int(last_range.split("-")[-1])
        except (yaml.YAMLError, ValueError, AttributeError):
            pass

    return 24  # sensible default


# ---------------------------------------------------------------------------
# PHASE 1 — FOUNDATION
# ---------------------------------------------------------------------------

def run_foundation(state: dict) -> dict:
    """
    Build planning documents (world, characters, outline, voice, canon).
    Auto-detects long-form mode when story/project.json has >= 100 chapters.
    Loop until foundation_score > threshold or max iterations reached.
    """
    banner("阶段 1: 设定基石 (FOUNDATION)", "=")

    best_score = state.get("foundation_score", 0.0)
    iteration = state.get("iteration", 0)
    long_form = is_long_form()

    if long_form:
        step("检测到长篇模式 (>=100章)，启用全书总纲 + 长篇角色 + 反哺工具链")

    for i in range(iteration + 1, MAX_FOUNDATION_ITERS + 1):
        banner(f"设定迭代 {i}", "-")
        state["iteration"] = i

        # 1. 生成规划文档
        step("正在生成世界观设定集...")
        uv_run("gen_world.py", timeout=300)

        if long_form:
            step("正在生成长篇角色注册表（含反派轮换+登场计划）...")
            uv_run("gen_characters_lf.py", timeout=600)
        else:
            step("正在生成角色注册表...")
            uv_run("gen_characters.py", timeout=300)

        if long_form:
            step("正在生成全书总纲（master_plan + master_summary）...")
            uv_run("gen_master_outline.py", timeout=900)
        else:
            step("正在生成大纲 (第一部分)...")
            uv_run("gen_outline.py", timeout=300)

            step("正在生成大纲 (第二部分 — 伏笔)...")
            uv_run("gen_outline_part2.py", timeout=300)

        if long_form:
            step("正在反哺更新 foundation 设定（world Part B + characters 后半部）...")
            uv_run("backfill_foundation.py", timeout=600)

        step("正在生成事实库 (Canon)...")
        uv_run("gen_canon.py", timeout=300)

        step("正在提取文风指纹...")
        uv_run("voice_fingerprint.py", timeout=300)

        # 2. 评估 — 长篇用 foundation-lf，短篇用 foundation
        eval_phase = "foundation-lf" if long_form else "foundation"
        step(f"正在评估设定质量（{eval_phase} 模式）...")
        eval_result = uv_run(f"evaluate.py --phase={eval_phase}", timeout=300)
        score = parse_score(eval_result.stdout, "overall_score")
        lore = parse_lore_score(eval_result.stdout)

        step(f"设定得分: {score}  (逻辑一致性: {lore}, 此前最高分: {best_score})")

        # 3. 保留或丢弃
        if score > best_score:
            commit_hash = git_add_commit(
                f"foundation iter {i}: score {score} (lore {lore})")
            log_result(commit_hash, "foundation", score, 0, "keep",
                       f"第 {i} 次迭代: 分数从 {best_score} 提升至 {score}")
            best_score = score
            state["foundation_score"] = score
            state["lore_score"] = lore
            save_state(state)
        else:
            step(f"分数未提升 ({score} <= {best_score})，丢弃本次改动")
            git_reset_hard("HEAD")
            log_result("discarded", "foundation", score, 0, "discard",
                       f"第 {i} 次迭代: 无提升 ({score} <= {best_score})")

        # 4. Check exit condition
        if best_score >= FOUNDATION_THRESHOLD:
            step(f"Foundation score {best_score} >= {FOUNDATION_THRESHOLD} — PASSED")
            break
    else:
        step(f"WARNING: max iterations ({MAX_FOUNDATION_ITERS}) reached "
             f"with score {best_score}")

    # Determine total chapters from outline
    total = get_total_chapters(state)
    state["chapters_total"] = total
    state["phase"] = "drafting"
    state["current_focus"] = "chapter_drafting"
    save_state(state)

    banner(f"FOUNDATION COMPLETE — score {best_score}, {total} chapters planned")
    return state


# ---------------------------------------------------------------------------
# PHASE 2 — DRAFTING
# ---------------------------------------------------------------------------

def run_drafting(state: dict) -> dict:
    """
    Draft each chapter sequentially, evaluating and retrying as needed.
    """
    banner("阶段 2: 初稿起草 (DRAFTING)", "=")

    total = get_total_chapters(state)
    start_chapter = state.get("chapters_drafted", 0) + 1

    CHAPTERS_DIR.mkdir(exist_ok=True)

    for ch in range(start_chapter, total + 1):
        banner(f"Drafting Chapter {ch}/{total}", "-")
        drafted = False

        for attempt in range(1, MAX_CHAPTER_ATTEMPTS + 1):
            step(f"尝试 {attempt}/{MAX_CHAPTER_ATTEMPTS}")

            # 起草
            draft_result = uv_run(f"draft_chapter.py {ch}", timeout=600)
            if draft_result.returncode != 0:
                step(f"起草失败 (退出码 {draft_result.returncode})，正在重试...")
                continue

            # 检查文件
            ch_file = CHAPTERS_DIR / f"ch_{ch:02d}.md"
            if not ch_file.exists() or ch_file.stat().st_size < 100:
                step("章节文件缺失或内容太少，正在重试...")
                continue

            word_count = len(ch_file.read_text(encoding="utf-8").split())
            step(f"已起草 {word_count} 字")

            # 评估
            eval_result = uv_run(f"evaluate.py --chapter={ch}", timeout=300)
            score = parse_score(eval_result.stdout, "overall_score")
            step(f"第 {ch} 章 得分: {score}")

            if score >= CHAPTER_THRESHOLD:
                commit_hash = git_add_commit(
                    f"ch{ch:02d}: score {score}, {word_count}w")
                log_result(commit_hash, f"ch{ch:02d}", score, word_count,
                           "keep", f"第 {ch} 章 (第 {attempt} 次尝试)")
                state["chapters_drafted"] = ch
                save_state(state)
                drafted = True
                break
            else:
                step(f"得分 {score} < {CHAPTER_THRESHOLD}，丢弃本次起草")
                log_result("discarded", f"ch{ch:02d}", score, word_count,
                           "discard", f"第 {ch} 章 第 {attempt} 次尝试")
                # Remove the bad chapter file so next attempt starts fresh
                if ch_file.exists():
                    run_tool(f"git checkout -- chapters/ch_{ch:02d}.md 2>/dev/null || true")

        if not drafted:
            step(f"WARNING: Chapter {ch} failed all {MAX_CHAPTER_ATTEMPTS} attempts, "
                 f"keeping last attempt and moving on")
            # Keep whatever we have and commit it
            ch_file = CHAPTERS_DIR / f"ch_{ch:02d}.md"
            if ch_file.exists():
                word_count = len(ch_file.read_text(encoding="utf-8").split())
                commit_hash = git_add_commit(
                    f"ch{ch:02d}: best-effort after {MAX_CHAPTER_ATTEMPTS} attempts")
                log_result(commit_hash, f"ch{ch:02d}", "?", word_count,
                           "forced", f"Chapter {ch}: kept after max attempts")
                state["chapters_drafted"] = ch
                save_state(state)

    # All chapters drafted
    state["phase"] = "revision"
    state["current_focus"] = "full_novel"
    state["chapters_drafted"] = total
    state["revision_cycle"] = 0
    save_state(state)

    total_words = count_words_in_chapters()
    banner(f"DRAFTING COMPLETE — {total} chapters, {total_words} words")
    return state


# ---------------------------------------------------------------------------
# PHASE 3 — REVISION
# ---------------------------------------------------------------------------

def parse_panel_consensus(panel_path: Path) -> list[dict]:
    """
    Parse reader_panel.json to find chapters with consensus issues.
    Returns list of dicts: {chapter, question, flagged_by, details}
    sorted by number of readers who flagged (descending).
    """
    if not panel_path.exists():
        return []
    with open(panel_path, encoding="utf-8") as f:
        data = json.load(f)

    items = []

    # Look at disagreements — these are flagged by some but not all readers
    for d in data.get("disagreements", []):
        items.append({
            "chapter": d.get("chapter", 0),
            "question": d.get("question", ""),
            "flagged_by": d.get("flagged_by", []),
            "count": len(d.get("flagged_by", [])),
        })

    # Also scan readers for direct chapter mentions in key questions
    readers = data.get("readers", {})
    chapter_mentions = {}  # ch_num -> count of readers mentioning it

    for reader_key, answers in readers.items():
        for question in ["momentum_loss", "cut_candidate", "worst_scene",
                         "thinnest_character", "missing_scene"]:
            answer = answers.get(question, "")
            if not isinstance(answer, str):
                continue
            chs = re.findall(r'Ch(?:apter)?\s*(\d+)', answer, re.IGNORECASE)
            for ch_str in chs:
                ch_num = int(ch_str)
                key = (ch_num, question)
                if key not in chapter_mentions:
                    chapter_mentions[key] = {"chapter": ch_num, "question": question,
                                             "flagged_by": [], "count": 0}
                chapter_mentions[key]["flagged_by"].append(reader_key)
                chapter_mentions[key]["count"] += 1

    # Merge and deduplicate
    seen = set()
    for item in items:
        seen.add((item["chapter"], item["question"]))
    for key, item in chapter_mentions.items():
        if key not in seen:
            items.append(item)

    # Sort by count descending, take unique chapters
    items.sort(key=lambda x: -x["count"])

    # Deduplicate by chapter (keep highest-count issue per chapter)
    seen_chapters = set()
    unique = []
    for item in items:
        if item["chapter"] not in seen_chapters and item["chapter"] > 0:
            seen_chapters.add(item["chapter"])
            unique.append(item)

    return unique[:5]  # top 3-5 consensus items


def run_revision(state: dict, max_cycles: int = MAX_REVISION_CYCLES) -> dict:
    """
    Revision phase: adversarial editing, reader panel, targeted revisions.
    """
    banner("阶段 3: 自动化修订 (REVISION)", "=")

    BRIEFS_DIR.mkdir(exist_ok=True)
    EDIT_LOGS_DIR.mkdir(exist_ok=True)

    prev_score = state.get("novel_score", 0.0)
    start_cycle = state.get("revision_cycle", 0) + 1
    max_cycles = min(max_cycles, MAX_REVISION_CYCLES)

    for cycle in range(start_cycle, max_cycles + 1):
        banner(f"修订循环 {cycle}/{max_cycles}", "-")

        # -- 步骤 1: 对抗性编辑 pass --
        step("正在对所有章节运行对抗性编辑分析...")
        uv_run("adversarial_edit.py all", timeout=900)

        # -- 步骤 2: 应用机械性剪裁 --
        apply_cuts = BASE_DIR / "apply_cuts.py"
        if apply_cuts.exists():
            step("正在应用机械剪裁 (OVER-EXPLAIN, REDUNDANT)...")
            run_tool("uv run python apply_cuts.py all "
                     "--types OVER-EXPLAIN REDUNDANT --min-fat 15", timeout=300)
        else:
            step("未找到 apply_cuts.py，跳过机械剪裁")

        # -- 步骤 3: 读者评审团 --
        step("正在运行虚拟读者评审团评估...")
        uv_run("reader_panel.py", timeout=600)

        # -- Step 4: Parse panel consensus --
        panel_path = EDIT_LOGS_DIR / "reader_panel.json"
        consensus_items = parse_panel_consensus(panel_path)

        if consensus_items:
            step(f"Found {len(consensus_items)} consensus items:")
            for item in consensus_items:
                print(f"    Ch {item['chapter']}: {item['question']} "
                      f"(flagged by {item['count']} readers)")
        else:
            step("No strong consensus items found from panel")

        # -- Step 5: Targeted revisions for consensus items --
        for idx, item in enumerate(consensus_items):
            ch_num = item["chapter"]
            question = item["question"]
            banner(f"  Revising Ch {ch_num} ({question}) [{idx+1}/{len(consensus_items)}]", ".")

            # Snapshot the current chapter score for comparison
            pre_eval = uv_run(f"evaluate.py --chapter={ch_num}", timeout=300)
            pre_score = parse_score(pre_eval.stdout, "overall_score")

            # Generate revision brief
            brief_file = BRIEFS_DIR / f"ch{ch_num:02d}_cycle{cycle}_{question}.md"
            gen_brief = BASE_DIR / "gen_brief.py"
            if gen_brief.exists():
                step(f"Generating brief for Ch {ch_num}...")
                run_tool(f"uv run python gen_brief.py --panel {ch_num}", timeout=300)
                # gen_brief.py may write to briefs/ — find the most recent brief
                brief_candidates = sorted(
                    BRIEFS_DIR.glob(f"ch{ch_num:02d}*.md"),
                    key=lambda p: p.stat().st_mtime, reverse=True)
                if brief_candidates:
                    brief_file = brief_candidates[0]
            else:
                # Create a minimal brief from the panel data
                step(f"gen_brief.py not found, creating minimal brief for Ch {ch_num}...")
                brief_content = (
                    f"# Revision Brief: Chapter {ch_num}\n\n"
                    f"## Issue: {question}\n\n"
                    f"Panel consensus identified this chapter for revision.\n"
                    f"Focus: address the {question.replace('_', ' ')} issue.\n"
                    f"Preserve existing voice, character work, and essential beats.\n"
                )
                brief_file.write_text(brief_content, encoding="utf-8")

            if not brief_file.exists():
                step(f"No brief file found for Ch {ch_num}, skipping")
                continue

            # Run revision
            step(f"Revising Ch {ch_num} with brief {brief_file.name}...")
            uv_run(f"gen_revision.py {ch_num} {brief_file}", timeout=600)

            # Evaluate revised chapter
            post_eval = uv_run(f"evaluate.py --chapter={ch_num}", timeout=300)
            post_score = parse_score(post_eval.stdout, "overall_score")

            ch_file = CHAPTERS_DIR / f"ch_{ch_num:02d}.md"
            word_count = len(ch_file.read_text(encoding="utf-8").split()) if ch_file.exists() else 0

            step(f"Ch {ch_num}: {pre_score} -> {post_score}")

            if post_score >= pre_score:
                commit_hash = git_add_commit(
                    f"revision cycle {cycle}: ch{ch_num:02d} "
                    f"{question} {pre_score}->{post_score}")
                log_result(commit_hash, f"rev-ch{ch_num:02d}", post_score,
                           word_count, "keep",
                           f"Cycle {cycle}: {question} improved {pre_score}->{post_score}")
            else:
                step(f"Revision made it worse ({post_score} < {pre_score}), reverting")
                git_reset_hard("HEAD")
                log_result("reverted", f"rev-ch{ch_num:02d}", post_score,
                           word_count, "discard",
                           f"Cycle {cycle}: {question} regressed {pre_score}->{post_score}")

        # -- Step 6: Full novel evaluation --
        step("Running full novel evaluation...")
        full_eval = uv_run("evaluate.py --full", timeout=600)
        novel_score = parse_score(full_eval.stdout, "novel_score")

        if novel_score < 0:
            # Fallback: try overall_score
            novel_score = parse_score(full_eval.stdout, "overall_score")

        total_words = count_words_in_chapters()
        step(f"Novel score: {novel_score}  (prev: {prev_score}, words: {total_words})")

        # Commit cycle results
        commit_hash = git_add_commit(
            f"revision cycle {cycle} complete: novel_score {novel_score}")
        log_result(commit_hash, f"revision-cycle-{cycle}", novel_score,
                   total_words, "cycle",
                   f"Cycle {cycle}: novel_score {prev_score}->{novel_score}")

        state["novel_score"] = novel_score
        state["revision_cycle"] = cycle
        save_state(state)

        # -- Step 7: Plateau detection --
        if cycle >= MIN_REVISION_CYCLES and abs(novel_score - prev_score) < PLATEAU_DELTA:
            step(f"Plateau detected (delta {abs(novel_score - prev_score):.2f} "
                 f"< {PLATEAU_DELTA}) after {cycle} cycles — stopping")
            break

        prev_score = novel_score

    # =========================================================
    # PHASE 3b: OPUS REVIEW LOOP (deep, prose-level refinement)
    # =========================================================
    review_py = BASE_DIR / "review.py"
    if review_py.exists():
        banner("PHASE 3b: OPUS REVIEW LOOP", "=")
        
        max_review_rounds = 4
        for rnd in range(1, max_review_rounds + 1):
            banner(f"Opus Review Round {rnd}/{max_review_rounds}", "-")
            
            # Step 1: Generate the review
            step("Sending manuscript to Opus for review...")
            review_result = uv_run(
                f"review.py --output reviews.md", timeout=900)
            
            # Step 2: Parse the review
            step("Parsing review...")
            parse_result = run_tool(
                "uv run python review.py --parse", timeout=60)
            print(parse_result.stdout if parse_result else "")
            
            # Step 3: Check stopping condition
            review_logs = sorted(
                (EDIT_LOGS_DIR).glob("*_review.json"), reverse=True)
            if review_logs:

                review_data = json.loads(review_logs[0].read_text(encoding="utf-8"))
                stars = review_data.get("stars", 0) or 0
                total_items = review_data.get("total_items", 0)
                major_items = review_data.get("major_items", 0)
                qualified = review_data.get("qualified_items", 0)
                
                step(f"Stars: {stars}, Items: {total_items} "
                     f"({major_items} major, {qualified} qualified)")
                
                # Stop if: ≥4★, no major unqualified items, or >half qualified
                if stars >= 4.5 and major_items == 0:
                    step("★★★★½ with no major items — novel is ready.")
                    break
                if stars >= 4 and total_items > 0 and qualified / total_items > 0.5:
                    step(f"★{'★' * int(stars)} with majority qualified items — novel is ready.")
                    break
            
            # Step 4: Generate briefs from review items and fix
            step("Generating revision briefs from review...")
            gen_brief_py = BASE_DIR / "gen_brief.py"
            if gen_brief_py.exists():
                # Auto mode: picks weakest chapter, cross-references all sources
                run_tool("uv run python gen_brief.py --auto", timeout=300)
                
                # Find any generated briefs and apply the top one
                recent_briefs = sorted(
                    BRIEFS_DIR.glob("*_auto.md"),
                    key=lambda p: p.stat().st_mtime, reverse=True)
                if recent_briefs:
                    brief = recent_briefs[0]
                    # Extract chapter number from filename
                    ch_match = re.search(r'ch(\d+)', brief.name)
                    if ch_match:
                        ch_num = int(ch_match.group(1))
                        step(f"Revising Ch {ch_num} from review brief...")
                        uv_run(f"gen_revision.py {ch_num} {brief}", timeout=600)
                        git_add_commit(
                            f"review round {rnd}: revise ch{ch_num:02d} from Opus feedback")
            
            # Step 5: Mechanical fixes from review
            # Run slop pass on any mentioned patterns
            step("Running mechanical cleanup pass...")
            apply_cuts_py = BASE_DIR / "apply_cuts.py"
            if apply_cuts_py.exists():
                run_tool(
                    "uv run python apply_cuts.py all --types OVER-EXPLAIN REDUNDANT --min-fat 15",
                    timeout=300)
                git_add_commit(f"review round {rnd}: mechanical cleanup")
            
            step(f"Review round {rnd} complete.")
        
        banner("OPUS REVIEW LOOP COMPLETE")
    
    state["phase"] = "export"
    state["current_focus"] = "export"
    save_state(state)

    banner(f"REVISION COMPLETE — {state.get('revision_cycle', 0)} cycles, "
           f"novel_score {state.get('novel_score', 0)}")
    return state


# ---------------------------------------------------------------------------
# PHASE 4 — EXPORT
# ---------------------------------------------------------------------------

def run_export(state: dict) -> dict:
    """
    Build final deliverables: outline, arc summary, manuscript, PDF.
    """
    banner("阶段 4: 导出 (EXPORT)", "=")

    # 1. Rebuild outline from chapters
    build_outline = BASE_DIR / "build_outline.py"
    if build_outline.exists():
        step("Rebuilding outline from chapters...")
        uv_run("build_outline.py", timeout=300)

    # 2. Build arc summary
    build_arc = BASE_DIR / "build_arc_summary.py"
    if build_arc.exists():
        step("Building arc summary...")
        uv_run("build_arc_summary.py", timeout=300)

    # 3. Concatenate chapters into manuscript.md
    step("Building manuscript.md...")
    manuscript = BASE_DIR / "manuscript.md"
    chapter_files = sorted(CHAPTERS_DIR.glob("ch_*.md"))

    parts = []
    for ch_file in chapter_files:
        text = ch_file.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)

    if parts:
        manuscript.write_text("\n\n---\n\n".join(parts, encoding="utf-8") + "\n")
        word_count = sum(len(p.split()) for p in parts)
        step(f"Manuscript: {len(parts)} chapters, {word_count} words")
    else:
        step("WARNING: no chapter files found for manuscript")

    # 4. Build LaTeX
    build_tex = BASE_DIR / "typeset" / "build_tex.py"
    if build_tex.exists():
        step("Building LaTeX content...")
        run_tool(f"uv run python typeset/build_tex.py", timeout=120)

        # 5. Typeset with tectonic (if available)
        novel_tex = BASE_DIR / "typeset" / "novel.tex"
        if novel_tex.exists():
            tectonic_check = run_tool("which tectonic", timeout=10)
            if tectonic_check.returncode == 0:
                step("Typesetting PDF with tectonic...")
                result = run_tool("tectonic typeset/novel.tex", timeout=300)
                if result.returncode == 0:
                    step("PDF generated: typeset/novel.pdf")
                else:
                    step("WARNING: tectonic typesetting failed")
            else:
                step("tectonic not found, skipping PDF generation")
    else:
        step("typeset/build_tex.py not found, skipping LaTeX")

    # 6. Final commit
    commit_hash = git_add_commit("export: manuscript, outline, arc summary, PDF")
    total_words = count_words_in_chapters()
    log_result(commit_hash, "export", state.get("novel_score", "?"),
               total_words, "export", "Final export")

    state["phase"] = "complete"
    state["current_focus"] = "done"
    save_state(state)

    banner(f"EXPORT COMPLETE — {len(chapter_files)} chapters, {total_words} words")
    return state


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(args):
    """Run the full pipeline or a specific phase."""

    # Load or initialize state
    if args.from_scratch:
        banner("STARTING FROM SCRATCH")
        seed_file = BASE_DIR / "seed.txt"
        if not seed_file.exists():
            print("ERROR: seed.txt not found. Cannot start from scratch without a seed.")
            sys.exit(1)
        state = default_state()
        save_state(state)
    else:
        state = load_state()

    # Ensure directories exist
    CHAPTERS_DIR.mkdir(exist_ok=True)
    BRIEFS_DIR.mkdir(exist_ok=True)
    EDIT_LOGS_DIR.mkdir(exist_ok=True)
    EVAL_LOGS_DIR.mkdir(exist_ok=True)

    # Apply max_cycles override
    max_cycles = args.max_cycles if args.max_cycles else MAX_REVISION_CYCLES

    # Determine which phases to run
    if args.phase:
        # Single phase mode
        phases = [args.phase]
    else:
        # Run from current state onward
        current = state.get("phase", "foundation")
        if current == "complete":
            print("Pipeline already complete. Use --from-scratch to restart "
                  "or --phase to run a specific phase.")
            return
        try:
            start_idx = PHASE_ORDER.index(current)
        except ValueError:
            start_idx = 0
        phases = PHASE_ORDER[start_idx:]

    banner(f"AUTONOVEL PIPELINE — phases: {', '.join(phases)}")
    print(f"  State: phase={state.get('phase')}, "
          f"foundation_score={state.get('foundation_score', 0)}, "
          f"chapters={state.get('chapters_drafted', 0)}/{state.get('chapters_total', '?')}, "
          f"novel_score={state.get('novel_score', 0)}")

    start_time = datetime.now()

    for phase in phases:
        try:
            if phase == "foundation":
                state = run_foundation(state)
            elif phase == "drafting":
                state = run_drafting(state)
            elif phase == "revision":
                state = run_revision(state, max_cycles=max_cycles)
            elif phase == "export":
                state = run_export(state)
            else:
                print(f"Unknown phase: {phase}")
                sys.exit(1)
        except KeyboardInterrupt:
            banner("INTERRUPTED — state saved")
            save_state(state)
            sys.exit(130)
        except Exception as e:
            print(f"\n  FATAL ERROR in {phase}: {e}")
            save_state(state)
            raise

    elapsed = datetime.now() - start_time
    hours = elapsed.total_seconds() / 3600

    banner("PIPELINE COMPLETE")
    print(f"  Time:       {hours:.1f} hours")
    print(f"  Phase:      {state.get('phase')}")
    print(f"  Foundation: {state.get('foundation_score', 0)}")
    print(f"  Chapters:   {state.get('chapters_drafted', 0)}/{state.get('chapters_total', '?')}")
    print(f"  Words:      {count_words_in_chapters()}")
    print(f"  Novel:      {state.get('novel_score', 0)}")
    print(f"  Cycles:     {state.get('revision_cycle', 0)}")


def main():
    parser = argparse.ArgumentParser(
        description="Autonovel pipeline orchestrator — seed to finished novel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python run_pipeline.py                     # resume from current state
  python run_pipeline.py --from-scratch      # start fresh from seed.txt
  python run_pipeline.py --phase foundation  # run only foundation
  python run_pipeline.py --phase drafting    # run only drafting
  python run_pipeline.py --phase revision    # run only revision
  python run_pipeline.py --phase export      # run only export
  python run_pipeline.py --max-cycles 4      # limit revision to 4 cycles
""")

    parser.add_argument(
        "--from-scratch", action="store_true",
        help="Reset state and start from seed.txt")
    parser.add_argument(
        "--phase", choices=PHASE_ORDER,
        help="Run only a specific phase")
    parser.add_argument(
        "--max-cycles", type=int, default=None,
        help=f"Maximum revision cycles (default: {MAX_REVISION_CYCLES})")

    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
