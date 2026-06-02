#!/usr/bin/env python3
"""
autonovel_cli.py — Unified CLI entry point for the autonovel system.

Usage:
  uv run python autonovel_cli.py status
  uv run python autonovel_cli.py init --title "My Novel" --genre "古言"
  uv run python autonovel_cli.py generate foundation
  uv run python autonovel_cli.py run --chapter 1
  uv run python autonovel_cli.py run --volume 1 --chapters 1-20
  uv run python autonovel_cli.py validate
  uv run python autonovel_cli.py plan volume --volume 1
  uv run python autonovel_cli.py plan chapter --chapter 1
  uv run python autonovel_cli.py plan batch --start 1 --count 20
  uv run python autonovel_cli.py report
  uv run python autonovel_cli.py snapshot create --chapter 1
  uv run python autonovel_cli.py snapshot restore --commit <ref>
  uv run python autonovel_cli.py compact --volume 1
  uv run python autonovel_cli.py index --chapter 1
  uv run python autonovel_cli.py rebuild
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
STATE_DIR = STORY_DIR / "state"


def _run_script(script: str, args: list[str]) -> int:
    """Run a Python script with given arguments."""
    result = subprocess.run(
        [sys.executable, script] + args,
        cwd=BASE_DIR,
        text=True,
    )
    return result.returncode


# ---------------------------------------------------------------------------
# status — terminal dashboard
# ---------------------------------------------------------------------------

def cmd_status(args):
    """Show project status dashboard."""
    from story_schema import (
        ProjectConfig, CharacterMatrix, PendingHooks, SubplotBoard,
        ChapterSummaries, PowerLedgerFull, EmotionalArcs,
        count_cn_words, load_json,
    )

    proj_path = STORY_DIR / "project.json"
    if not proj_path.exists():
        print("[ERROR] No project.json found. Run 'autonovel init' first.")
        return 1

    proj = ProjectConfig(**load_json(proj_path))

    # Project info
    print("=" * 60)
    print(f"  {proj.title or '(untitled)'} — {proj.genre or '(no genre)'}")
    print("=" * 60)
    print(f"  Target: {proj.target_words:,} words / {proj.target_chapters} chapters")
    print(f"  Chapter target: {proj.default_chapter_chars} chars")
    print(f"  Phase: {proj.phase} | Status: {proj.status}")
    print()

    # Progress
    pct = (proj.current_chars / proj.target_words * 100) if proj.target_words > 0 else 0
    bar_len = 30
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"  Progress: [{bar}] {pct:.1f}%")
    print(f"  Volume: {proj.current_volume} | Chapter: {proj.current_chapter}")
    print(f"  Words written: {proj.current_chars:,}")
    print()

    # State summary
    char_matrix = CharacterMatrix(**load_json(STORY_DIR / "state" / "character_matrix.json"))
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    power = PowerLedgerFull(**load_json(STORY_DIR / "state" / "power_ledger.json"))
    arcs = EmotionalArcs(**load_json(STORY_DIR / "state" / "emotional_arcs.json"))

    active_hooks = [h for h in hooks.hooks.values() if h.status == "active"]
    active_subplots = [s for s in subplots.subplots.values() if s.status == "active"]

    print(f"  Characters: {len(char_matrix.characters)}")
    print(f"  Active hooks: {len(active_hooks)}")
    print(f"  Active subplots: {len(active_subplots)}")
    print(f"  Resources: {len(power.resources)} | Items: {len(power.items)}")
    print(f"  Power levels: {len(power.levels)}")
    print(f"  Emotional arcs: {len(arcs.arcs)}")
    print(f"  Chapter summaries: {len(summaries.summaries)}")
    print()

    # Recent chapters
    if summaries.summaries:
        recent = sorted(summaries.summaries.values(), key=lambda s: s.chapter)[-5:]
        print("  Recent chapters:")
        for s in recent:
            events = "; ".join(s.key_events[:2]) if s.key_events else ""
            print(f"    Ch.{s.chapter}: {s.summary[:60]}...")
            if events:
                print(f"           Events: {events[:60]}")
        print()

    # Active hooks detail
    if active_hooks:
        print("  Active hooks:")
        for h in active_hooks[:5]:
            print(f"    [{h.id}] {h.description[:60]}")
        if len(active_hooks) > 5:
            print(f"    ... and {len(active_hooks) - 5} more")
        print()

    # State file health
    state_files = [
        "current_state.json", "character_matrix.json", "power_ledger.json",
        "pending_hooks.json", "chapter_summaries.json", "subplot_board.json",
        "emotional_arcs.json",
    ]
    missing = [f for f in state_files if not (STORY_DIR / "state" / f).exists()]
    if missing:
        print(f"  [WARN] Missing state files: {', '.join(missing)}")
    else:
        print("  All state files present.")

    # Snapshot count
    snap_dir = STORY_DIR / "memory" / "snapshots"
    if snap_dir.exists():
        snaps = list(snap_dir.glob("ch_*.zip"))
        print(f"  Snapshots: {len(snaps)}")

    print()
    return 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def cmd_validate(args):
    """Run state validation."""
    script_args = []
    if args.full:
        script_args.append("--full")
    elif args.delta:
        script_args.extend(["--delta", args.delta, "--chapter", str(args.chapter)])
    return _run_script("validate_state.py", script_args)


# ---------------------------------------------------------------------------
# run — pipeline execution
# ---------------------------------------------------------------------------

def cmd_run(args):
    """Run the webnovel pipeline."""
    script_args = []
    if args.chapter:
        script_args.extend(["--chapter", str(args.chapter)])
    if args.volume:
        script_args.extend(["--volume", str(args.volume)])
    if args.chapters:
        script_args.extend(["--chapters", args.chapters])
    if args.volume_range:
        script_args.extend(["--volume-range", args.volume_range])
    if args.dry_run:
        script_args.append("--dry-run")
    if args.audit_warn:
        script_args.append("--audit-warn")
    if args.resume:
        script_args.append("--resume")
    if args.continue_on_failure:
        script_args.append("--continue-on-failure")
    return _run_script("run_webnovel_pipeline.py", script_args)


# ---------------------------------------------------------------------------
# plan — generate plans
# ---------------------------------------------------------------------------

def cmd_plan_volume(args):
    """Generate a volume plan."""
    return _run_script("gen_volume_plan.py", ["--volume", str(args.volume)])


def cmd_plan_chapter(args):
    """Generate a chapter plan."""
    return _run_script("gen_chapter_plan.py", ["--chapter", str(args.chapter)])


def cmd_plan_batch(args):
    """Generate batch chapter plans."""
    script_args = ["--start", str(args.start), "--count", str(args.count)]
    return _run_script("gen_batch_chapter_plans.py", script_args)


def cmd_plan(args):
    """Plan subcommand dispatcher."""
    if args.plan_type == "volume":
        return cmd_plan_volume(args)
    elif args.plan_type == "chapter":
        return cmd_plan_chapter(args)
    elif args.plan_type == "batch":
        return cmd_plan_batch(args)
    else:
        print("Usage: autonovel plan volume --volume N  OR  autonovel plan chapter --chapter N  OR  autonovel plan batch --start N --count M")
        return 1


# ---------------------------------------------------------------------------
# draft
# ---------------------------------------------------------------------------

def cmd_draft(args):
    """Draft a single chapter."""
    script_args = [str(args.chapter)]
    if args.context:
        script_args.extend(["--context", args.context])
    if args.out:
        script_args.extend(["--out", args.out])
    return _run_script("draft_chapter.py", script_args)


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

def cmd_audit(args):
    """Audit a chapter."""
    script_args = [
        "--chapter", str(args.chapter),
        "--draft", args.draft,
        "--delta", args.delta,
        "--out", args.out,
    ]
    return _run_script("webnovel_audit.py", script_args)


# ---------------------------------------------------------------------------
# delta
# ---------------------------------------------------------------------------

def cmd_delta(args):
    """Extract delta from a draft."""
    script_args = [
        "--chapter", str(args.chapter),
        "--draft", args.draft,
        "--out", args.out,
    ]
    return _run_script("extract_delta.py", script_args)


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------

def cmd_snapshot(args):
    """Create or restore snapshots."""
    if args.action == "create":
        return _run_script("snapshot_state.py", ["create", "--chapter", str(args.chapter)])
    elif args.action == "restore":
        return _run_script("snapshot_state.py", ["restore", "--commit", args.commit])
    else:
        print("Usage: autonovel snapshot create --chapter N  OR  autonovel snapshot restore --commit REF")
        return 1


# ---------------------------------------------------------------------------
# compact
# ---------------------------------------------------------------------------

def cmd_compact(args):
    """Compact memory at volume boundaries."""
    script_args = ["--volume", str(args.volume)]
    if args.chapters:
        script_args.extend(["--chapters", args.chapters])
    if args.dry_run:
        script_args.append("--dry-run")
    return _run_script("run_compaction.py", script_args)


# ---------------------------------------------------------------------------
# index / rebuild
# ---------------------------------------------------------------------------

def cmd_index(args):
    """Index a chapter into FTS5 database."""
    return _run_script("memory_retrieval.py", ["index", "--chapter", str(args.chapter)])


def cmd_rebuild(args):
    """Rebuild the entire FTS5 index."""
    return _run_script("memory_retrieval.py", ["rebuild"])


# ---------------------------------------------------------------------------
# report — writing progress report
# ---------------------------------------------------------------------------

def cmd_report(args):
    """Generate a writing progress report."""
    from story_schema import (
        ProjectConfig, ChapterSummaries, PendingHooks, SubplotBoard,
        PowerLedgerFull, EmotionalArcs, load_json,
    )

    proj_path = STORY_DIR / "project.json"
    if not proj_path.exists():
        print("[ERROR] No project.json found.")
        return 1

    proj = ProjectConfig(**load_json(proj_path))
    summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
    hooks = PendingHooks(**load_json(STORY_DIR / "state" / "pending_hooks.json"))
    subplots = SubplotBoard(**load_json(STORY_DIR / "state" / "subplot_board.json"))
    power = PowerLedgerFull(**load_json(STORY_DIR / "state" / "power_ledger.json"))
    arcs = EmotionalArcs(**load_json(STORY_DIR / "state" / "emotional_arcs.json"))

    print("=" * 60)
    print(f"  Writing Report: {proj.title or '(untitled)'}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Overall progress
    pct = (proj.current_chars / proj.target_words * 100) if proj.target_words > 0 else 0
    print(f"\n  Overall: {proj.current_chars:,} / {proj.target_words:,} words ({pct:.1f}%)")
    print(f"  Chapters: {proj.current_chapter} / {proj.target_chapters}")
    print(f"  Volume: {proj.current_volume}")

    # Per-chapter word counts
    if summaries.summaries:
        print(f"\n  Chapter Details:")
        print(f"  {'Ch':>4}  {'Words':>6}  {'Key Events'}")
        print(f"  {'---':>4}  {'-----':>6}  ----------")
        for key in sorted(summaries.summaries.keys()):
            s = summaries.summaries[key]
            events = "; ".join(s.key_events[:2]) if s.key_events else ""
            # Try to get word count from draft
            draft_path = STORY_DIR / "runtime" / f"ch_{s.chapter:04d}" / "draft.md"
            words = 0
            if draft_path.exists():
                from story_schema import count_cn_words
                words = count_cn_words(draft_path.read_text(encoding="utf-8"))
            print(f"  {s.chapter:>4}  {words:>6}  {events[:50]}")

    # Hook debt
    active_hooks = [h for h in hooks.hooks.values() if h.status == "active"]
    resolved_hooks = [h for h in hooks.hooks.values() if h.status == "resolved"]
    print(f"\n  Hook Debt: {len(active_hooks)} active, {len(resolved_hooks)} resolved")
    if active_hooks:
        for h in active_hooks[:5]:
            age = proj.current_chapter - h.planted_chapter if h.planted_chapter else 0
            print(f"    [{h.id}] planted ch.{h.planted_chapter} (age: {age}) — {h.description[:40]}")

    # Subplot status
    active_sp = [s for s in subplots.subplots.values() if s.status == "active"]
    resolved_sp = [s for s in subplots.subplots.values() if s.status == "resolved"]
    print(f"\n  Subplots: {len(active_sp)} active, {len(resolved_sp)} resolved")

    # Resource summary
    if power.resources:
        print(f"\n  Resources:")
        for rid, r in list(power.resources.items())[:5]:
            print(f"    {r.name}: {r.quantity} {r.unit}")

    # Emotional arcs
    if arcs.arcs:
        print(f"\n  Emotional Arcs: {len(arcs.arcs)}")
        for aid, a in list(arcs.arcs.items())[:3]:
            print(f"    [{aid}] {a.arc_type}: {a.description[:40]}")

    print()
    return 0


# ---------------------------------------------------------------------------
# genres — list available genre configurations
# ---------------------------------------------------------------------------

def cmd_genres(args):
    """List available genre configurations."""
    from genres.genre_registry import list_available_genres

    genres = list_available_genres()
    if not genres:
        print("No genre configurations found.")
        return 1

    print(f"Available genres ({len(genres)}):\n")
    for g in genres:
        print(f"  {g['display_name']}")
        if g['description']:
            print(f"    {g['description']}")
    print(f"\nUsage: uv run python autonovel_cli.py init --title \"书名\" --genre \"{genres[0]['display_name']}\"")
    return 0


# ---------------------------------------------------------------------------
# init — initialize a new story project
# ---------------------------------------------------------------------------

def cmd_init(args):
    """Initialize a new story project."""
    from story_schema import ProjectConfig, save_json

    if (STORY_DIR / "project.json").exists() and not args.force:
        print("[ERROR] project.json already exists. Use --force to overwrite.")
        return 1

    # Create directory structure
    dirs = [
        STORY_DIR / "plans",
        STORY_DIR / "state",
        STORY_DIR / "memory" / "snapshots",
        STORY_DIR / "memory" / "embeddings",
        STORY_DIR / "runtime",
        STORY_DIR / "projections",
        BASE_DIR / "chapters" / "v001",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Create project.json
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    proj = ProjectConfig(
        title=args.title or "",
        genre=args.genre or "",
        tags=tags,
        target_words=args.words or 1000000,
        target_chapters=args.chapters or 500,
        default_chapter_chars=args.chars or 4000,
    )
    save_json(STORY_DIR / "project.json", proj.model_dump())

    # Create empty state files
    empty_states = {
        "current_state.json": {"timeline_position": "", "recent_events": []},
        "character_matrix.json": {"characters": {}},
        "power_ledger.json": {"levels": [], "resources": {}, "items": {}},
        "pending_hooks.json": {"hooks": {}},
        "chapter_summaries.json": {"summaries": {}},
        "subplot_board.json": {"subplots": {}},
        "emotional_arcs.json": {"arcs": {}},
    }
    for filename, default in empty_states.items():
        path = STORY_DIR / "state" / filename
        if not path.exists():
            save_json(path, default)

    # Create empty commit index
    index_path = STORY_DIR / "memory" / "snapshots" / "commit_index.json"
    if not index_path.exists():
        save_json(index_path, {"entries": []})

    print(f"Story project initialized at {STORY_DIR}")
    if args.title:
        print(f"  Title: {args.title}")
    if tags:
        print(f"  Tags: {', '.join(tags)}")
    print(f"  Target: {proj.target_words:,} words / {proj.target_chapters} chapters")
    print(f"\nNext steps:")
    print(f"  1. Create seed.txt with your story concept, then run:")
    print(f"     uv run python autonovel_cli.py generate foundation")
    print(f"  2. Run: uv run python autonovel_cli.py plan volume --volume 1")
    print(f"  3. Run: uv run python autonovel_cli.py run --chapter 1")
    return 0


# ---------------------------------------------------------------------------
# generate — generate foundation material files
# ---------------------------------------------------------------------------

def cmd_generate(args):
    """Generate seed concepts or foundation material files."""
    if args.gen_type == "seed":
        # Route to seed_input.py if user provides their own concept
        if getattr(args, 'input', None) or getattr(args, 'input_file', None):
            seed_input_args = []
            if args.input:
                seed_input_args += ["--input", args.input]
            if args.input_file:
                seed_input_args += ["--input-file", args.input_file]
            if getattr(args, 'auto_accept', False):
                seed_input_args.append("--auto-accept")
            return _run_script("seed_input.py", seed_input_args)

        seed_args = []
        if args.count:
            seed_args += ["--count", str(args.count)]
        if args.riff:
            seed_args += ["--riff", args.riff]
        if hasattr(args, 'target_words') and args.target_words:
            seed_args += ["--target-words", str(args.target_words)]
        for research_path in getattr(args, 'market_research', []) or []:
            seed_args += ["--market-research", research_path]
        # Use long-form seed generator if --long-form flag, --target-words, or project targets 500+ chapters
        long_form = getattr(args, 'long_form', False)
        if not long_form and hasattr(args, 'target_words') and args.target_words:
            long_form = True
        if not long_form and getattr(args, 'market_research', None):
            long_form = True
        if not long_form:
            proj_path = STORY_DIR / "project.json"
            if proj_path.exists():
                from story_schema import ProjectConfig, load_json
                proj = ProjectConfig(**load_json(proj_path))
                long_form = proj.target_chapters >= 100
        script = "seed_lf.py" if long_form else "seed.py"
        return _run_script(script, seed_args)

    if args.gen_type != "foundation":
        print(f"[ERROR] Unknown generate type: {args.gen_type}")
        return 1

    seed_path = Path(args.seed) if args.seed else BASE_DIR / "seed.txt"
    if not seed_path.exists():
        print(f"[ERROR] Seed file not found: {seed_path}")
        print(f"  Run 'uv run python autonovel_cli.py generate seed' to generate concepts,")
        print(f"  then save your chosen concept to seed.txt.")
        return 1

    # Check voice.md exists (generators read it)
    voice_path = BASE_DIR / "voice.md"
    if not voice_path.exists():
        print(f"[ERROR] voice.md not found. It ships with the project template.")
        return 1

    # Determine short-form vs long-form based on project config
    proj_path = STORY_DIR / "project.json"
    long_form = False
    if proj_path.exists():
        from story_schema import ProjectConfig, load_json
        proj = ProjectConfig(**load_json(proj_path))
        long_form = proj.target_chapters >= 100

    if long_form:
        steps = [
            ("gen_world_lf.py", "世界观设定集 (world.md)"),
            ("gen_characters_lf.py", "角色注册表 (characters.md)"),
            ("gen_master_outline.py", "全书总纲 (master_plan.yaml + outline.md)"),
            ("gen_outline_v1.py", "第一卷详细大纲 (outline.md)"),
            ("gen_outline_v1_part2.py", "第一卷大纲续写 (outline.md)"),
            ("gen_canon.py", "设定准则数据库 (canon.md)"),
            ("init_state.py", "状态初始化 (story/state/*.json)"),
        ]
    else:
        steps = [
            ("gen_world.py", "世界观设定集 (world.md)"),
            ("gen_characters.py", "角色注册表 (characters.md)"),
            ("gen_outline.py", "章节大纲 (outline.md)"),
            ("gen_outline_part2.py", "伏笔追加 (outline.md part 2)"),
        ]

    print("=" * 60)
    mode_label = "长篇 FOUNDATION (100万字+)" if long_form else "生成设定基石 (FOUNDATION)"
    print(f"  {mode_label}")
    print("=" * 60)
    print(f"  Seed: {seed_path}")
    print()

    for i, (script, desc) in enumerate(steps, 1):
        print(f"[{i}/{len(steps)}] 正在生成 {desc}...")
        rc = _run_script(script, [])
        if rc != 0:
            print(f"[ERROR] {script} failed with exit code {rc}")
            return rc
        print(f"[{i}/{len(steps)}] {desc} 完成")
        print()

    print("=" * 60)
    print("  设定基石生成完成!")
    print("=" * 60)
    generated = ["world.md", "characters.md", "outline.md"]
    if long_form:
        generated += ["story/plans/master_plan.yaml", "canon.md"]
    for f in generated:
        path = BASE_DIR / f
        if path.exists():
            size = path.stat().st_size
            print(f"  ✓ {f} ({size:,} bytes)")
        else:
            print(f"  ✗ {f} (missing!)")

    if long_form:
        print()
        print("状态文件:")
        for sf in ["character_matrix.json", "pending_hooks.json", "subplot_board.json",
                    "current_state.json", "power_ledger.json", "chapter_summaries.json",
                    "emotional_arcs.json"]:
            path = STATE_DIR / sf
            if path.exists():
                print(f"  ✓ {sf}")
            else:
                print(f"  ✗ {sf} (missing!)")

    # Evaluate foundation quality (long-form only)
    if long_form:
        print()
        print("=" * 60)
        print("  评估设定基石质量...")
        print("=" * 60)
        try:
            from evaluate import evaluate_foundation_lf
            eval_result = evaluate_foundation_lf()
            # Save eval result
            eval_path = STORY_DIR / "foundation_eval.json"
            with open(eval_path, "w", encoding="utf-8") as f:
                json.dump(eval_result, f, indent=2, ensure_ascii=False)
            # Print summary
            overall = eval_result.get("overall_score", "N/A")
            lore = eval_result.get("lore_score", "N/A")
            weakest = eval_result.get("weakest_dimension", "N/A")
            improvements = eval_result.get("top_3_improvements", [])
            print(f"  总分: {overall}/10  逻辑一致性: {lore}/10")
            print(f"  最弱维度: {weakest}")
            if improvements:
                print("  改进建议:")
                for j, imp in enumerate(improvements, 1):
                    print(f"    {j}. {imp}")
            print(f"\n  详细报告: {eval_path}")
        except Exception as e:
            print(f"  [WARN] 评估失败: {e}")
            print("  基石文件已生成，可手动运行: uv run python evaluate.py --phase=foundation-lf")

    print()
    print("Next steps:")
    print("  1. Review and edit the generated files")
    print("  2. Run: uv run python autonovel_cli.py plan volume --volume 1")
    print("  3. Run: uv run python autonovel_cli.py run --chapter 1")
    return 0


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="autonovel",
        description="Autonovel — AI-powered long-form webnovel writing system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python autonovel_cli.py status
  uv run python autonovel_cli.py init --title "My Novel" --genre "古言"
  uv run python autonovel_cli.py generate foundation
  uv run python autonovel_cli.py run --chapter 1
  uv run python autonovel_cli.py run --volume 1 --chapters 1-20 --resume
  uv run python autonovel_cli.py validate
  uv run python autonovel_cli.py plan volume --volume 1
  uv run python autonovel_cli.py plan chapter --chapter 1
  uv run python autonovel_cli.py plan batch --start 1 --count 20
  uv run python autonovel_cli.py report
  uv run python autonovel_cli.py snapshot create --chapter 1
  uv run python autonovel_cli.py compact --volume 1
  uv run python autonovel_cli.py index --chapter 1
  uv run python autonovel_cli.py rebuild
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status
    subparsers.add_parser("status", help="Show project status dashboard")

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate state files")
    p_validate.add_argument("--full", action="store_true", help="Full validation")
    p_validate.add_argument("--delta", type=str, help="Delta file to validate")
    p_validate.add_argument("--chapter", type=int, help="Chapter number for delta validation")

    # run
    p_run = subparsers.add_parser("run", help="Run the webnovel pipeline")
    p_run.add_argument("--chapter", type=int, help="Single chapter to run")
    p_run.add_argument("--volume", type=int, help="Volume number")
    p_run.add_argument("--chapters", type=str, help="Chapter range, e.g. '1-20'")
    p_run.add_argument("--volume-range", type=str, help="Volume range, e.g. '1-3'")
    p_run.add_argument("--dry-run", action="store_true", help="Show what would run")
    p_run.add_argument("--audit-warn", action="store_true", help="Treat audit failures as warnings")
    p_run.add_argument("--resume", action="store_true", help="Skip accepted chapters")
    p_run.add_argument("--continue-on-failure", action="store_true", help="Continue on failure")

    # plan
    p_plan = subparsers.add_parser("plan", help="Generate plans")
    p_plan.add_argument("plan_type", choices=["volume", "chapter", "batch"], help="Plan type")
    p_plan.add_argument("--volume", type=int, help="Volume number")
    p_plan.add_argument("--chapter", type=int, help="Chapter number")
    p_plan.add_argument("--start", type=int, help="First chapter number (for batch)")
    p_plan.add_argument("--count", type=int, default=20, help="Number of chapters to plan (for batch, default: 20)")

    # draft
    p_draft = subparsers.add_parser("draft", help="Draft a single chapter")
    p_draft.add_argument("chapter", type=int, help="Chapter number")
    p_draft.add_argument("--context", type=str, help="Path to context.json")
    p_draft.add_argument("--out", type=str, help="Output draft path")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit a chapter")
    p_audit.add_argument("--chapter", type=int, required=True)
    p_audit.add_argument("--draft", type=str, required=True)
    p_audit.add_argument("--delta", type=str, required=True)
    p_audit.add_argument("--out", type=str, required=True)

    # delta
    p_delta = subparsers.add_parser("delta", help="Extract delta from draft")
    p_delta.add_argument("--chapter", type=int, required=True)
    p_delta.add_argument("--draft", type=str, required=True)
    p_delta.add_argument("--out", type=str, required=True)

    # snapshot
    p_snap = subparsers.add_parser("snapshot", help="Create/restore snapshots")
    p_snap.add_argument("action", choices=["create", "restore"])
    p_snap.add_argument("--chapter", type=int, help="Chapter number (for create)")
    p_snap.add_argument("--commit", type=str, help="Commit hash (for restore)")

    # compact
    p_compact = subparsers.add_parser("compact", help="Compact memory at volume boundaries")
    p_compact.add_argument("--volume", type=int, required=True)
    p_compact.add_argument("--chapters", type=str, help="Chapter range")
    p_compact.add_argument("--dry-run", action="store_true")

    # index
    p_index = subparsers.add_parser("index", help="Index a chapter into FTS5")
    p_index.add_argument("--chapter", type=int, required=True)

    # rebuild
    subparsers.add_parser("rebuild", help="Rebuild entire FTS5 index")

    # report
    subparsers.add_parser("report", help="Generate writing progress report")

    # genres
    subparsers.add_parser("genres", help="List available genre configurations")

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new story project")
    p_init.add_argument("--title", type=str, help="Story title")
    p_init.add_argument("--genre", type=str, help="Genre name in Chinese (e.g. 种田文, 霸总). Use 'genres list' to see available genres.")
    p_init.add_argument("--words", type=int, help="Target word count")
    p_init.add_argument("--chapters", type=int, help="Target chapter count")
    p_init.add_argument("--chars", type=int, help="Chars per chapter")
    p_init.add_argument("--tags", type=str, help="Comma-separated genre tags, e.g. '穿越,大女主,萌娃'")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing project")

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate seed concepts or foundation files")
    p_gen.add_argument("gen_type", choices=["seed", "foundation"], help="What to generate")
    p_gen.add_argument("--seed", type=str, help="Path to seed file (default: seed.txt)")
    p_gen.add_argument("--count", type=int, help="Number of seed concepts to generate (default: 3)")
    p_gen.add_argument("--riff", type=str, help="Expand on an existing idea")
    p_gen.add_argument("--long-form", action="store_true",
                       help="Generate long-form seed concepts (500+ chapters)")
    p_gen.add_argument("--target-words", type=int, default=None,
                       help="Target total word count for long-form seed (e.g. 500000 for 50万字, default: 1000000)")
    p_gen.add_argument("--market-research", action="append", default=[],
                       help="Path to an external ranking/market research Markdown file for long-form seed generation; repeatable")
    p_gen.add_argument("--input", type=str, default=None,
                       help="Provide your own concept text (evaluate + optimize)")
    p_gen.add_argument("--input-file", type=str, default=None,
                       help="Path to a file containing your concept")
    p_gen.add_argument("--auto-accept", action="store_true",
                       help="Skip confirmation prompt when using --input/--input-file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "status": cmd_status,
        "validate": cmd_validate,
        "run": cmd_run,
        "plan": cmd_plan,
        "draft": cmd_draft,
        "audit": cmd_audit,
        "delta": cmd_delta,
        "snapshot": cmd_snapshot,
        "compact": cmd_compact,
        "index": cmd_index,
        "rebuild": cmd_rebuild,
        "report": cmd_report,
        "init": cmd_init,
        "generate": cmd_generate,
        "genres": cmd_genres,
    }

    handler = dispatch.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
