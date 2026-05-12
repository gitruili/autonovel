#!/usr/bin/env python3
"""
Auto-generate revision briefs from reader panel feedback, evaluation results,
or adversarial cuts.

Usage:
  python gen_brief.py --panel 12    # brief from panel feedback for ch 12
  python gen_brief.py --eval 12     # brief from eval callouts for ch 12
  python gen_brief.py --cuts 12     # brief from adversarial cuts for ch 12
  python gen_brief.py --auto        # auto-detect weakest chapter and generate
"""
import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
CHAPTERS_DIR = BASE_DIR / "chapters"
EDIT_LOGS_DIR = BASE_DIR / "edit_logs"
EVAL_LOGS_DIR = BASE_DIR / "eval_logs"
BRIEFS_DIR = BASE_DIR / "briefs"
VOICE_PATH = BASE_DIR / "voice.md"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def chapter_path(ch: int) -> Path:
    return CHAPTERS_DIR / f"ch_{ch:02d}.md"


def chapter_text(ch: int) -> str:
    p = chapter_path(ch)
    if not p.exists():
        sys.exit(f"ERROR: chapter file not found: {p}")
    return p.read_text(encoding="utf-8")


def chapter_title(text: str) -> str:
    """Extract the chapter title from the first line of the md file."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            # strip leading hashes and any "Chapter N/One/Two/..." prefix
            title = re.sub(r"^#+\s*", "", line)
            title = re.sub(
                r"^Chapter\s+(?:\d+|[A-Z][a-z]+(?:-[A-Z][a-z]+)*)\s*[:—–-]*\s*",
                "", title, flags=re.I
            )
            return title.strip() if title.strip() else "Untitled"
    return "Untitled"


def word_count(text: str) -> int:
    return len(text.split())


def extract_voice_rules() -> list[str]:
    """Pull the key guardrail / voice rules from voice.md Part 1 + Part 2."""
    if not VOICE_PATH.exists():
        return ["(voice.md not found)"]
    voice = VOICE_PATH.read_text(encoding="utf-8")

    rules: list[str] = []

    # 核心语气与写作规则（自动附加到所有 Brief 中）
    rules.append("拒绝空洞的情感形容词（如'心中一动'、'暗暗吃惊'），用具体的身体反应和动作代替")
    rules.append("展示之后不要过度解释")
    rules.append("禁止使用三元组感官列表")
    rules.append("至少 70% 的内容必须在场景中（有对话、有动作、有环境互动），而不是干巴巴的叙述总结")
    rules.append("对话要像真正的人类说话：有潜台词，有打断，带有地方或阶级特色，不要冗长的书面语演讲")
    rules.append("改变句子长度。短句用于情绪冲击，长句用于铺陈日常")
    rules.append("比喻和意象必须来自角色的生活经验（如手工艺、种田、算账），严禁使用奇幻或现代词汇")
    rules.append("每一笔经济账必须算清楚，物价要有质感，符合设定")
    rules.append("不要使用'不禁'、'映入眼帘'、'美眸'等烂俗 AI 网文词汇")

    return rules


def latest_full_eval() -> Path | None:
    """Find the most recent *_full.json in eval_logs/."""
    if not EVAL_LOGS_DIR.exists():
        return None
    fulls = sorted(EVAL_LOGS_DIR.glob("*_full.json"))
    return fulls[-1] if fulls else None


def latest_chapter_eval(ch: int) -> Path | None:
    """Find the most recent per-chapter eval for ch N."""
    if not EVAL_LOGS_DIR.exists():
        return None
    pattern = f"*_ch{ch:02d}.json"
    matches = sorted(EVAL_LOGS_DIR.glob(pattern))
    # Also try without zero-pad
    matches += sorted(EVAL_LOGS_DIR.glob(f"*_ch{ch}.json"))
    matches = sorted(set(matches))
    return matches[-1] if matches else None


def load_panel() -> dict | None:
    p = EDIT_LOGS_DIR / "reader_panel.json"
    if not p.exists():
        return None
    return load_json(p)


def load_cuts(ch: int) -> dict | None:
    p = EDIT_LOGS_DIR / f"ch{ch:02d}_cuts.json"
    if not p.exists():
        return None
    return load_json(p)


# ---------------------------------------------------------------------------
# panel feedback extraction
# ---------------------------------------------------------------------------

def panel_mentions_for_chapter(panel: dict, ch: int) -> dict:
    """Extract all reader comments that mention this chapter."""
    readers = panel.get("readers", {})
    disagreements = panel.get("disagreements", [])

    mentions: dict[str, list[str]] = {
        "momentum_loss": [],
        "worst_scene": [],
        "cut_candidate": [],
        "best_scene": [],
        "thinnest_character": [],
        "missing_scene": [],
        "earned_ending": [],
    }

    # Use word-boundary regex so "Chapter 2" doesn't match "Chapter 21"
    ch_re = re.compile(
        rf"\b(?:Chapter|Ch\.?)\s*{ch}\b", re.I
    )

    for reader_name, reader_data in readers.items():
        for key in mentions:
            text = reader_data.get(key, "")
            if ch_re.search(text):
                mentions[key].append(f"[{reader_name}] {text}")

    # Also check disagreements for this chapter
    flagged_issues: list[str] = []
    for d in disagreements:
        if d.get("chapter") == ch:
            q = d.get("question", "")
            flagged = d.get("flagged_by", [])
            count = len(flagged)
            flagged_issues.append(
                f"{q}: flagged by {count}/4 readers ({', '.join(flagged)})"
            )

    return {
        "mentions": mentions,
        "flagged_issues": flagged_issues,
    }


# ---------------------------------------------------------------------------
# brief generators
# ---------------------------------------------------------------------------

def build_panel_brief(ch: int) -> str:
    panel = load_panel()
    if panel is None:
        sys.exit("ERROR: edit_logs/reader_panel.json not found")

    text = chapter_text(ch)
    title = chapter_title(text)
    wc = word_count(text)
    info = panel_mentions_for_chapter(panel, ch)
    mentions = info["mentions"]
    flagged = info["flagged_issues"]
    voice_rules = extract_voice_rules()

    # Determine brief type from dominant issue
    negative_keys = ["momentum_loss", "worst_scene", "cut_candidate"]
    neg_count = sum(len(mentions[k]) for k in negative_keys)
    if len(mentions["cut_candidate"]) > 0:
        brief_type = "COMPRESS"
    elif len(mentions["worst_scene"]) > 0:
        brief_type = "DRAMATIZE"
    elif len(mentions["momentum_loss"]) > 0:
        brief_type = "TIGHTEN"
    else:
        brief_type = "REVISE"

    # Build PROBLEM section
    problem_parts: list[str] = []
    if flagged:
        problem_parts.append(
            "Panel disagreement flags for this chapter:\n"
            + "\n".join(f"- {f}" for f in flagged)
        )
    for key in negative_keys:
        if mentions[key]:
            problem_parts.append(f"### {key.replace('_', ' ').title()}")
            for m in mentions[key]:
                # Truncate very long quotes to ~400 chars for readability
                if len(m) > 500:
                    m = m[:500] + "..."
                problem_parts.append(m)

    if not problem_parts:
        problem_parts.append(
            f"No specific negative feedback for Chapter {ch} from the reader panel. "
            "Consider cross-referencing with --eval or --cuts for targeted feedback."
        )

    # Build WHAT TO KEEP section
    keep_parts: list[str] = []
    if mentions["best_scene"]:
        for m in mentions["best_scene"]:
            if len(m) > 500:
                m = m[:500] + "..."
            keep_parts.append(m)
    # Check cuts file for tightest_passage
    cuts_data = load_cuts(ch)
    if cuts_data and cuts_data.get("tightest_passage"):
        keep_parts.append(
            f'Tightest passage (from adversarial edit): "{cuts_data["tightest_passage"]}"'
        )
    # Check per-chapter eval for strongest sentences
    ch_eval_path = latest_chapter_eval(ch)
    if ch_eval_path:
        ch_eval = load_json(ch_eval_path)
        strongest = ch_eval.get("three_strongest_sentences", [])
        if strongest:
            keep_parts.append("Strongest sentences (from eval):")
            for s in strongest:
                keep_parts.append(f'- "{s}"')

    if not keep_parts:
        keep_parts.append(
            f"(No specific 'best' mentions for Chapter {ch}. "
            "Review the chapter for its strongest passages before revising.)"
        )

    # Build WHAT TO CHANGE section
    change_parts: list[str] = []
    change_num = 1

    # From momentum_loss
    for m in mentions["momentum_loss"]:
        # Extract actionable suggestion if present
        change_parts.append(
            f"{change_num}. **Pacing**: Address momentum loss identified by panel — "
            "tighten or restructure the scenes that drag."
        )
        change_num += 1
        break  # one entry is enough

    # From worst_scene
    for m in mentions["worst_scene"]:
        # Try to extract the fix suggestion — look for "Fix:" or "The fix is"
        fix_match = re.search(
            r"(?:The fix(?:\s+is\s*\w*)?|Fix)\s*[:—]\s*(.+)",
            m, re.I | re.DOTALL
        )
        if fix_match:
            # Take up to ~300 chars of the fix suggestion
            raw_fix = fix_match.group(1).strip()
            fix_text = (raw_fix[:300] + "...") if len(raw_fix) > 300 else raw_fix
            fix_text = fix_text.rstrip(".")
        else:
            # Fall back to the full worst_scene comment, truncated
            raw = m.split("]", 1)[-1].strip() if "]" in m else m
            fix_text = (raw[:300] + "...") if len(raw) > 300 else raw
        change_parts.append(f"{change_num}. **Dramatize**: {fix_text}")
        change_num += 1
        break

    # From cut_candidate
    for m in mentions["cut_candidate"]:
        change_parts.append(
            f"{change_num}. **Compress**: Panel identifies this chapter as a cut candidate. "
            "Fold essential beats into fewer words; eliminate repeated exposition."
        )
        change_num += 1
        break

    # From thinnest_character
    if mentions["thinnest_character"]:
        change_parts.append(
            f"{change_num}. **Deepen character**: Panel flags thin characterization in this chapter. "
            "Add interiority, physical specificity, or a complicating moment."
        )
        change_num += 1

    # From missing_scene
    if mentions["missing_scene"]:
        change_parts.append(
            f"{change_num}. **Add missing beat**: Panel identifies a scene gap near this chapter."
        )
        for m in mentions["missing_scene"]:
            snippet = m[:300] + "..." if len(m) > 300 else m
            change_parts.append(f"   {snippet}")
        change_num += 1

    if not change_parts:
        change_parts.append(
            "No specific changes derived from panel. "
            "Consider combining with --eval or --cuts for concrete revision items."
        )

    # Determine word count target
    if brief_type == "COMPRESS":
        target_wc = int(wc * 0.55)
        target_note = f"~{target_wc} words (compress from current {wc})"
    elif brief_type == "DRAMATIZE":
        target_wc = wc  # restructure, not expand
        target_note = f"~{target_wc} words (restructure, roughly same length)"
    elif brief_type == "TIGHTEN":
        target_wc = int(wc * 0.85)
        target_note = f"~{target_wc} words (tighten from current {wc})"
    else:
        target_note = f"~{wc} words (current length, unless changes dictate otherwise)"

    # Assemble
    brief = f"# Revision Brief: Chapter {ch} — {title} ({brief_type})\n\n"
    brief += "## PROBLEM\n"
    brief += "\n\n".join(problem_parts) + "\n\n"
    brief += "## WHAT TO KEEP\n"
    brief += "\n".join(keep_parts) + "\n\n"
    brief += "## WHAT TO CHANGE\n"
    brief += "\n".join(change_parts) + "\n\n"
    brief += "## VOICE RULES\n"
    brief += "\n".join(f"- {r}" for r in voice_rules) + "\n\n"
    brief += "## TARGET\n"
    brief += target_note + "\n"

    return brief


def build_eval_brief(ch: int) -> str:
    # Try per-chapter eval first, fall back to full eval
    ch_eval_path = latest_chapter_eval(ch)
    full_eval_path = latest_full_eval()

    if ch_eval_path is None and full_eval_path is None:
        sys.exit(f"ERROR: no eval logs found for chapter {ch}")

    text = chapter_text(ch)
    title = chapter_title(text)
    wc = word_count(text)
    voice_rules = extract_voice_rules()

    problem_parts: list[str] = []
    keep_parts: list[str] = []
    change_parts: list[str] = []
    change_num = 1

    # Per-chapter eval data
    if ch_eval_path:
        ch_eval = load_json(ch_eval_path)

        # Overall score and weakest dimension
        overall = ch_eval.get("overall_score", "?")
        weakest_dim = ch_eval.get("weakest_dimension", "unknown")
        problem_parts.append(
            f"Per-chapter eval score: **{overall}/10**. "
            f"Weakest dimension: **{weakest_dim}**."
        )

        # Collect weakest moments from each dimension
        dim_keys = [
            "voice_adherence", "beat_coverage", "character_voice",
            "plants_seeded", "prose_quality", "continuity",
            "canon_compliance", "lore_integration", "engagement",
        ]
        for dk in dim_keys:
            dim = ch_eval.get(dk)
            if not dim or not isinstance(dim, dict):
                continue
            score = dim.get("score", "?")
            weakest = dim.get("weakest_moment", "")
            fix = dim.get("fix", "")
            if score != "?" and int(score) <= 7 and weakest:
                problem_parts.append(
                    f"**{dk.replace('_', ' ').title()}** ({score}/10): {weakest}"
                )
                if fix:
                    change_parts.append(f"{change_num}. [{dk}] {fix}")
                    change_num += 1

        # Top 3 revisions
        top_revs = ch_eval.get("top_3_revisions", [])
        for rev in top_revs:
            change_parts.append(f"{change_num}. {rev}")
            change_num += 1

        # AI patterns detected
        ai_patterns = ch_eval.get("ai_patterns_detected", [])
        if ai_patterns:
            problem_parts.append("**AI patterns detected:**")
            for pat in ai_patterns:
                problem_parts.append(f"- {pat}")

        # Strongest sentences
        strongest = ch_eval.get("three_strongest_sentences", [])
        if strongest:
            keep_parts.append("Strongest sentences (eval):")
            for s in strongest:
                keep_parts.append(f'- "{s}"')

        # Three weakest sentences for reference
        weakest_sents = ch_eval.get("three_weakest_sentences", [])
        if weakest_sents:
            problem_parts.append("**Weakest sentences:**")
            for s in weakest_sents:
                problem_parts.append(f'- "{s}"')

    # Full eval data — add context if this chapter is flagged
    if full_eval_path:
        full_eval = load_json(full_eval_path)
        weakest_ch = full_eval.get("weakest_chapter")
        top_sug = full_eval.get("top_suggestion", "")
        novel_score = full_eval.get("novel_score", "?")

        if weakest_ch == ch:
            problem_parts.insert(0,
                f"**This is the novel's weakest chapter** per full eval "
                f"(novel score: {novel_score}/10)."
            )
        if top_sug and (weakest_ch == ch or ch_eval_path is None):
            change_parts.append(
                f"{change_num}. [full eval top suggestion] {top_sug}"
            )
            change_num += 1

        # Pacing curve note if it mentions this chapter
        pacing = full_eval.get("pacing_curve", {})
        pacing_note = pacing.get("note", "")
        ch_re = re.compile(rf"\b(?:Chapter|Ch\.?)\s*{ch}\b", re.I)
        if ch_re.search(pacing_note):
            problem_parts.append(f"**Pacing note (full eval):** {pacing_note}")

    # Tightest passage from cuts
    cuts_data = load_cuts(ch)
    if cuts_data and cuts_data.get("tightest_passage"):
        keep_parts.append(
            f'Tightest passage (adversarial edit): "{cuts_data["tightest_passage"]}"'
        )

    if not keep_parts:
        keep_parts.append("(Review chapter for strongest passages before revising.)")

    if not change_parts:
        change_parts.append("(No specific revision items from eval. Check --panel or --cuts.)")

    # Determine type from eval
    if ch_eval_path:
        ch_eval = load_json(ch_eval_path)
        overall = ch_eval.get("overall_score", 10)
        if overall <= 5:
            brief_type = "REWRITE"
        elif overall <= 7:
            brief_type = "FIX"
        else:
            brief_type = "POLISH"
    else:
        brief_type = "FIX"

    target_note = f"~{wc} words (current length: {wc}; adjust based on revision scope)"

    brief = f"# Revision Brief: Chapter {ch} — {title} ({brief_type})\n\n"
    brief += "## PROBLEM\n"
    brief += "\n\n".join(problem_parts) + "\n\n"
    brief += "## WHAT TO KEEP\n"
    brief += "\n".join(keep_parts) + "\n\n"
    brief += "## WHAT TO CHANGE\n"
    brief += "\n".join(change_parts) + "\n\n"
    brief += "## VOICE RULES\n"
    brief += "\n".join(f"- {r}" for r in voice_rules) + "\n\n"
    brief += "## TARGET\n"
    brief += target_note + "\n"

    return brief


def build_cuts_brief(ch: int) -> str:
    cuts_data = load_cuts(ch)
    if cuts_data is None:
        sys.exit(f"ERROR: edit_logs/ch{ch:02d}_cuts.json not found")

    text = chapter_text(ch)
    title = chapter_title(text)
    wc = word_count(text)
    voice_rules = extract_voice_rules()

    cuts = cuts_data.get("cuts", [])
    total_cuttable = cuts_data.get("total_cuttable_words", 0)
    tightest = cuts_data.get("tightest_passage", "")
    loosest = cuts_data.get("loosest_passage", "")
    fat_pct = cuts_data.get("overall_fat_percentage", 0)
    verdict = cuts_data.get("one_sentence_verdict", "")

    # Categorize cuts by type
    cut_types: dict[str, list[dict]] = {}
    for c in cuts:
        t = c.get("type", "OTHER")
        cut_types.setdefault(t, []).append(c)

    # Determine dominant pattern
    type_counts = {t: len(cs) for t, cs in cut_types.items()}
    dominant = max(type_counts, key=type_counts.get) if type_counts else "MIXED"

    brief_type = "TIGHTEN"

    # PROBLEM
    problem_parts: list[str] = []
    problem_parts.append(
        f"Adversarial edit found **{total_cuttable} cuttable words** "
        f"({fat_pct}% fat) across {len(cuts)} passages."
    )
    if verdict:
        problem_parts.append(f"Verdict: {verdict}")

    problem_parts.append(f"\nDominant cut pattern: **{dominant}** ({type_counts.get(dominant, 0)} instances)")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        if t != dominant:
            problem_parts.append(f"- {t}: {count} instances")

    if loosest:
        problem_parts.append(f'\n**Loosest passage:**\n> {loosest}')

    # WHAT TO KEEP
    keep_parts: list[str] = []
    if tightest:
        keep_parts.append(f'**Tightest passage** (do not touch):\n> {tightest}')

    # Also pull strongest sentences from eval if available
    ch_eval_path = latest_chapter_eval(ch)
    if ch_eval_path:
        ch_eval = load_json(ch_eval_path)
        strongest = ch_eval.get("three_strongest_sentences", [])
        if strongest:
            keep_parts.append("\nStrongest sentences (from eval):")
            for s in strongest:
                keep_parts.append(f'- "{s}"')

    if not keep_parts:
        keep_parts.append("(Review chapter for strongest passages before revising.)")

    # WHAT TO CHANGE — specific numbered items from each cut
    change_parts: list[str] = []
    change_num = 1

    # Group by type for clarity
    for cut_type in ["REDUNDANT", "OVER-EXPLAIN", "FAT", "TELL", "GENERIC", "OTHER"]:
        type_cuts = cut_types.get(cut_type, [])
        if not type_cuts:
            continue
        change_parts.append(f"\n### {cut_type} ({len(type_cuts)} cuts)")
        for c in type_cuts:
            quote = c.get("quote", "")
            reason = c.get("reason", "")
            action = c.get("action", "CUT")
            rewrite = c.get("rewrite")

            # Truncate very long quotes
            if len(quote) > 200:
                quote = quote[:200] + "..."

            entry = f'{change_num}. `"{quote}"`\n'
            entry += f"   Reason: {reason}\n"
            if action == "REWRITE" and rewrite:
                entry += f'   → Rewrite as: "{rewrite}"'
            elif action == "CUT":
                entry += "   → Cut entirely"
            change_parts.append(entry)
            change_num += 1

    # Word count target
    target_wc = wc - total_cuttable
    target_note = (
        f"~{target_wc} words (cut ~{total_cuttable} from current {wc}). "
        f"Tighten {fat_pct}% fat without losing the chapter's strongest beats."
    )

    brief = f"# Revision Brief: Chapter {ch} — {title} ({brief_type})\n\n"
    brief += "## PROBLEM\n"
    brief += "\n".join(problem_parts) + "\n\n"
    brief += "## WHAT TO KEEP\n"
    brief += "\n".join(keep_parts) + "\n\n"
    brief += "## WHAT TO CHANGE\n"
    brief += "\n".join(change_parts) + "\n\n"
    brief += "## VOICE RULES\n"
    brief += "\n".join(f"- {r}" for r in voice_rules) + "\n\n"
    brief += "## TARGET\n"
    brief += target_note + "\n"

    return brief


def build_auto_brief() -> tuple[int, str]:
    """Auto-detect weakest chapter and build a combined brief."""
    full_eval_path = latest_full_eval()
    if full_eval_path is None:
        sys.exit("ERROR: no *_full.json found in eval_logs/")

    full_eval = load_json(full_eval_path)
    ch = full_eval.get("weakest_chapter")
    if ch is None:
        sys.exit("ERROR: full eval does not contain 'weakest_chapter'")

    print(f"Auto-detected weakest chapter: {ch}", file=sys.stderr)
    print(f"  Source: {full_eval_path.name}", file=sys.stderr)

    top_sug = full_eval.get("top_suggestion", "")
    weakest_dim = full_eval.get("weakest_dimension", "")
    novel_score = full_eval.get("novel_score", "?")

    text = chapter_text(ch)
    title = chapter_title(text)
    wc = word_count(text)
    voice_rules = extract_voice_rules()

    problem_parts: list[str] = []
    keep_parts: list[str] = []
    change_parts: list[str] = []
    change_num = 1

    # Full eval context
    problem_parts.append(
        f"**Weakest chapter in the novel** (novel score: {novel_score}/10, "
        f"weakest dimension: {weakest_dim})."
    )
    if top_sug:
        problem_parts.append(f"**Top suggestion from full eval:** {top_sug}")

    # Per-dimension notes from full eval that mention this chapter
    dim_keys = [
        "arc_completion", "pacing_curve", "theme_coherence",
        "foreshadowing_resolution", "world_consistency", "voice_consistency",
        "overall_engagement",
    ]
    ch_re = re.compile(rf"\b(?:Chapters?|Ch\.?)\s*{ch}\b", re.I)
    for dk in dim_keys:
        dim = full_eval.get(dk, {})
        note = dim.get("note", "")
        if ch_re.search(note):
            score = dim.get("score", "?")
            problem_parts.append(f"**{dk.replace('_', ' ').title()}** ({score}/10): {note}")

    # Per-chapter eval
    ch_eval_path = latest_chapter_eval(ch)
    if ch_eval_path:
        ch_eval = load_json(ch_eval_path)
        overall = ch_eval.get("overall_score", "?")
        problem_parts.append(f"\nPer-chapter eval score: **{overall}/10**")

        # Weakest moments
        for dk in ["voice_adherence", "beat_coverage", "character_voice",
                    "plants_seeded", "prose_quality", "engagement"]:
            dim = ch_eval.get(dk)
            if not dim or not isinstance(dim, dict):
                continue
            score = dim.get("score", "?")
            fix = dim.get("fix", "")
            if score != "?" and int(score) <= 7 and fix:
                change_parts.append(f"{change_num}. [{dk}] {fix}")
                change_num += 1

        # Top 3 revisions
        for rev in ch_eval.get("top_3_revisions", []):
            change_parts.append(f"{change_num}. {rev}")
            change_num += 1

        # AI patterns
        ai_patterns = ch_eval.get("ai_patterns_detected", [])
        if ai_patterns:
            problem_parts.append("\n**AI patterns detected:**")
            for pat in ai_patterns:
                problem_parts.append(f"- {pat}")

        # Strongest sentences
        strongest = ch_eval.get("three_strongest_sentences", [])
        if strongest:
            keep_parts.append("Strongest sentences (eval):")
            for s in strongest:
                keep_parts.append(f'- "{s}"')

        # Weakest sentences
        weakest_sents = ch_eval.get("three_weakest_sentences", [])
        if weakest_sents:
            problem_parts.append("\n**Weakest sentences:**")
            for s in weakest_sents:
                problem_parts.append(f'- "{s}"')

    # Panel cross-reference
    panel = load_panel()
    if panel:
        info = panel_mentions_for_chapter(panel, ch)
        mentions = info["mentions"]
        flagged = info["flagged_issues"]
        if flagged:
            problem_parts.append("\n**Panel flags:**")
            for f in flagged:
                problem_parts.append(f"- {f}")

        for key in ["worst_scene", "momentum_loss", "cut_candidate"]:
            if mentions[key]:
                problem_parts.append(f"\n**Panel — {key.replace('_', ' ')}:**")
                for m in mentions[key]:
                    snippet = m[:400] + "..." if len(m) > 400 else m
                    problem_parts.append(snippet)

        if mentions["best_scene"]:
            for m in mentions["best_scene"]:
                snippet = m[:400] + "..." if len(m) > 400 else m
                keep_parts.append(f"Panel best scene mention: {snippet}")

    # Cuts data
    cuts_data = load_cuts(ch)
    if cuts_data:
        total_cuttable = cuts_data.get("total_cuttable_words", 0)
        fat_pct = cuts_data.get("overall_fat_percentage", 0)
        tightest = cuts_data.get("tightest_passage", "")
        verdict = cuts_data.get("one_sentence_verdict", "")

        if total_cuttable:
            problem_parts.append(
                f"\n**Adversarial edit:** {total_cuttable} cuttable words ({fat_pct}% fat). "
                f"{verdict}"
            )
        if tightest:
            keep_parts.append(f'\nTightest passage (adversarial edit):\n> {tightest}')

        # Add top cuts as change items
        cuts_list = cuts_data.get("cuts", [])
        # Only include the most impactful — REDUNDANT and OVER-EXPLAIN
        priority_cuts = [c for c in cuts_list if c.get("type") in ("REDUNDANT", "OVER-EXPLAIN")]
        for c in priority_cuts[:5]:
            quote = c.get("quote", "")[:150]
            reason = c.get("reason", "")
            action = c.get("action", "CUT")
            rewrite = c.get("rewrite")
            entry = f'{change_num}. `"{quote}..."` — {reason}'
            if action == "REWRITE" and rewrite:
                entry += f'\n   → Rewrite as: "{rewrite}"'
            elif action == "CUT":
                entry += "\n   → Cut entirely"
            change_parts.append(entry)
            change_num += 1

    # Top suggestion from full eval as final change item
    if top_sug:
        change_parts.append(f"{change_num}. [PRIORITY — full eval] {top_sug}")
        change_num += 1

    if not keep_parts:
        keep_parts.append("(Review chapter for strongest passages before revising.)")
    if not change_parts:
        change_parts.append("(No specific changes auto-detected. Manual review recommended.)")

    # Determine brief type
    brief_type = "AUTO-FIX"

    target_note = f"~{wc} words (current: {wc}; adjust based on revision scope)"

    brief = f"# Revision Brief: Chapter {ch} — {title} ({brief_type})\n\n"
    brief += "## PROBLEM\n"
    brief += "\n".join(problem_parts) + "\n\n"
    brief += "## WHAT TO KEEP\n"
    brief += "\n".join(keep_parts) + "\n\n"
    brief += "## WHAT TO CHANGE\n"
    brief += "\n".join(change_parts) + "\n\n"
    brief += "## VOICE RULES\n"
    brief += "\n".join(f"- {r}" for r in voice_rules) + "\n\n"
    brief += "## TARGET\n"
    brief += target_note + "\n"

    return ch, brief


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="从反馈源自动生成修订任务书 (Revision Briefs)。"
    )
    parser.add_argument("--panel", type=int, metavar="CH",
                        help="根据读者评审团(reader panel)的反馈为第 CH 章生成任务书")
    parser.add_argument("--eval", type=int, metavar="CH",
                        help="根据评估(eval)的意见为第 CH 章生成任务书")
    parser.add_argument("--cuts", type=int, metavar="CH",
                        help="根据对抗性删减(adversarial cuts)为第 CH 章生成任务书")
    parser.add_argument("--auto", action="store_true",
                        help="自动检测最弱的章节并生成综合任务书")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅在控制台打印任务书而不保存文件")

    args = parser.parse_args()

    # Validate: exactly one mode
    modes = sum([
        args.panel is not None,
        args.eval is not None,
        args.cuts is not None,
        args.auto,
    ])
    if modes == 0:
        parser.print_help()
        sys.exit(1)
    if modes > 1:
        sys.exit("ERROR: specify exactly one of --panel, --eval, --cuts, --auto")

    # Generate
    if args.panel is not None:
        ch = args.panel
        brief_text = build_panel_brief(ch)
        suffix = "panel"
    elif args.eval is not None:
        ch = args.eval
        brief_text = build_eval_brief(ch)
        suffix = "eval"
    elif args.cuts is not None:
        ch = args.cuts
        brief_text = build_cuts_brief(ch)
        suffix = "cuts"
    else:  # --auto
        ch, brief_text = build_auto_brief()
        suffix = "auto"

    if args.dry_run:
        print(brief_text)
        return

    # Save
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRIEFS_DIR / f"ch{ch:02d}_{suffix}.md"
    out_path.write_text(brief_text, encoding="utf-8")
    print(f"Saved: {out_path}", file=sys.stderr)
    print(f"Chapter: {ch}", file=sys.stderr)
    print(f"Type: {suffix}", file=sys.stderr)
    print(f"Brief length: {word_count(brief_text)} words", file=sys.stderr)


if __name__ == "__main__":
    main()
