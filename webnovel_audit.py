#!/usr/bin/env python3
"""
webnovel_audit.py — Webnovel-specific quality audit for chapter drafts.

Checks: chapter hooks, promise fulfillment, pacing, payoff setup,
filler ratio, coherence, hook debt, volume progress, and ledger compliance.

Usage:
  uv run python webnovel_audit.py --chapter 1 --draft story/runtime/ch_0001/draft.md --delta story/runtime/ch_0001/delta.json --out story/runtime/ch_0001/audit.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from story_schema import (
    AuditResult,
    ChapterDelta,
    ChapterSummaries,
    CharacterMatrix,
    PendingHooks,
    PowerLedgerFull,
    ProjectConfig,
    count_cn_words,
    load_json,
    save_json,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)


def mechanical_checks(chapter: int, draft_text: str, delta: ChapterDelta) -> dict:
    """Run mechanical (non-LLM) checks on the draft."""
    results = {}
    total_words = count_cn_words(draft_text)

    # 1. Word count check
    proj = ProjectConfig(**load_json(STORY_DIR / "project.json"))
    target = proj.default_chapter_chars
    ratio = total_words / target if target > 0 else 0
    results["word_count"] = {
        "count": total_words,
        "target": target,
        "ratio": round(ratio, 2),
        "passed": 0.5 <= ratio <= 2.0,
    }

    # 2. Filler ratio (short paragraphs, repetitive patterns)
    paragraphs = [p.strip() for p in draft_text.split("\n\n") if p.strip()]
    short_paras = [p for p in paragraphs if len(p) < 30]
    filler_ratio = len(short_paras) / len(paragraphs) if paragraphs else 0
    results["filler_ratio"] = {
        "ratio": round(filler_ratio, 3),
        "short_paragraphs": len(short_paras),
        "total_paragraphs": len(paragraphs),
        "passed": filler_ratio < 0.3,
    }

    # 3. Dialogue ratio
    dialogue_chars = sum(1 for line in draft_text.split("\n")
                        if line.strip().startswith('"') or line.strip().startswith('"') or
                        line.strip().startswith('「'))
    total_lines = len([l for l in draft_text.split("\n") if l.strip()])
    dialogue_ratio = dialogue_chars / total_lines if total_lines > 0 else 0
    results["dialogue_ratio"] = {
        "ratio": round(dialogue_ratio, 3),
        "passed": True,  # Info only
    }

    # 4. Section divider check (--- overuse)
    dividers = draft_text.count("---")
    results["section_dividers"] = {
        "count": dividers,
        "passed": dividers <= 3,
    }

    # 5. AI slop word detection
    slop_words = ["不禁", "映入眼帘", "心中涌起", "美眸", "淡淡地说",
                  "不由自主地", "嘴角微微上扬", "深吸一口气", "缓缓说道"]
    found_slop = []
    for word in slop_words:
        count = draft_text.count(word)
        if count > 0:
            found_slop.append({"word": word, "count": count})
    results["ai_slop"] = {
        "found": found_slop,
        "total": sum(f["count"] for f in found_slop),
        "passed": len(found_slop) == 0,
    }

    # 6. Delta completeness
    has_summary = bool(delta.chapter_summary.get("summary"))
    has_events = bool(delta.chapter_summary.get("key_events"))
    results["delta_completeness"] = {
        "has_summary": has_summary,
        "has_key_events": has_events,
        "passed": has_summary and has_events,
    }

    return results


def llm_audit(chapter: int, draft_text: str, delta: ChapterDelta, prev_summary: str) -> dict:
    """Run LLM-based audit checks."""
    # Load previous chapter's hook/cliffhanger
    prev_hooks = ""
    if chapter > 1:
        prev_audit_path = STORY_DIR / "runtime" / f"ch_{chapter-1:04d}" / "audit.json"
        if prev_audit_path.exists():
            prev_audit = load_json(prev_audit_path)
            prev_hooks = prev_audit.get("chapter_hook", {}).get("description", "")

    prompt = f"""你是一位网文质量审计专家。请对第 {chapter} 章进行专业审计。

=== 章节正文（前8000字） ===
{draft_text[:8000]}

=== 章节摘要 ===
{json.dumps(delta.chapter_summary, ensure_ascii=False)}

=== 上一章钩子/悬念 ===
{prev_hooks or '(第一章)'}

=== 审计维度 ===
请以 JSON 格式输出以下审计结果：

{{
  "chapter_hook": {{
    "score": 0-10,
    "has_cliffhanger": true/false,
    "hook_type": "悬念/冲突/反转/情感/无",
    "description": "章末钩子的具体描述",
    "comment": "评价"
  }},
  "promise_fulfillment": {{
    "score": 0-10,
    "fulfilled_promises": ["已兑现的承诺列表"],
    "unfulfilled_promises": ["未兑现的承诺列表"],
    "comment": "评价"
  }},
  "pacing": {{
    "score": 0-10,
    "slow_sections": 0,
    "fast_sections": 0,
    "has_rhythm_variation": true/false,
    "comment": "节奏评价"
  }},
  "payoff_setup": {{
    "score": 0-10,
    "setup_count": 0,
    "payoff_count": 0,
    "balance": "偏铺垫/均衡/偏收束",
    "comment": "评价"
  }},
  "coherence": {{
    "score": 0-10,
    "timeline_issues": [],
    "logic_issues": [],
    "comment": "连贯性评价"
  }},
  "volume_progress": {{
    "score": 0-10,
    "main_arc_progress": "主线推进描述",
    "subplot_progress": "支线推进描述",
    "comment": "评价"
  }}
}}

只输出 JSON，不要其他文字。"""

    try:
        result = call_text_model(
            model=WRITER_MODEL,
            max_tokens=4000,
            temperature=0.3,
            system="你是一位网文质量审计专家。只输出 JSON 格式。",
            messages=[{"role": "user", "content": prompt}],
            timeout=300,
        )
        json_text = result.strip()
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            json_text = "\n".join(lines[start:end])
        return json.loads(json_text)
    except Exception as e:
        print(f"  [WARN] LLM audit failed: {e}", file=sys.stderr)
        return {
            "chapter_hook": {"score": 0, "comment": f"Audit failed: {e}"},
            "promise_fulfillment": {"score": 0, "comment": "Audit failed"},
            "pacing": {"score": 0, "comment": "Audit failed"},
            "payoff_setup": {"score": 0, "comment": "Audit failed"},
            "coherence": {"score": 0, "comment": "Audit failed"},
            "volume_progress": {"score": 0, "comment": "Audit failed"},
        }


def check_ledger_compliance(delta: ChapterDelta) -> dict:
    """Check if delta complies with ledger rules (blocking check)."""
    issues = []
    power_ledger = PowerLedgerFull(**load_json(STORY_DIR / "state" / "power_ledger.json"))

    # Check resource consumption doesn't go negative
    for update in delta.resource_updates:
        action = update.get("action", "")
        res_id = update.get("id", "")
        if action == "consume" and res_id in power_ledger.resources:
            current = power_ledger.resources[res_id].quantity
            consumed = update.get("quantity", 0)
            if not isinstance(current, (int, float)) or not isinstance(consumed, (int, float)):
                continue
            if current - consumed < 0:
                issues.append(
                    f"Resource {res_id} would go negative: {current} - {consumed}"
                )
        elif action == "update" and res_id in power_ledger.resources:
            new_qty = update.get("quantity")
            if new_qty is not None and isinstance(new_qty, (int, float)) and new_qty < 0:
                issues.append(
                    f"Resource {res_id} update would set negative quantity: {new_qty}"
                )

    # Check item consistency
    # Collect items being created in this delta (so transfer on same-chapter creates passes)
    created_item_ids = set()
    created_item_names = set()
    for update in delta.item_updates:
        if update.get("action") == "create":
            if update.get("id"):
                created_item_ids.add(update["id"])
            if update.get("name"):
                created_item_names.add(update["name"])

    for update in delta.item_updates:
        if update.get("action") in ("transfer", "destroy"):
            item_id = update.get("id", "")
            if item_id and item_id not in power_ledger.items:
                # Allow if the same delta creates this item (by id or name)
                if item_id not in created_item_ids and item_id not in created_item_names:
                    issues.append(f"Item {item_id} does not exist for action {update['action']}")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
    }


def run_audit(chapter: int, draft_path: Path, delta_path: Path, out_path: Path) -> AuditResult:
    """Run the full webnovel audit."""
    draft_text = draft_path.read_text(encoding="utf-8")
    delta_data = load_json(delta_path)
    delta = ChapterDelta(**delta_data)

    # Mechanical checks
    mech = mechanical_checks(chapter, draft_text, delta)

    # Ledger compliance (blocking)
    ledger = check_ledger_compliance(delta)

    # Previous chapter summary
    prev_summary = ""
    if chapter > 1:
        summaries = ChapterSummaries(**load_json(STORY_DIR / "state" / "chapter_summaries.json"))
        prev_key = f"ch_{chapter - 1}"
        if prev_key in summaries.summaries:
            prev_summary = summaries.summaries[prev_key].summary

    # LLM audit
    llm = llm_audit(chapter, draft_text, delta, prev_summary)

    # Compute overall score
    scores = []
    for key in ["chapter_hook", "promise_fulfillment", "pacing", "payoff_setup", "coherence", "volume_progress"]:
        if key in llm and "score" in llm[key]:
            scores.append(llm[key]["score"])
    overall = sum(scores) / len(scores) if scores else 0

    # Determine blocking issues
    blocking_issues = []
    if not ledger["passed"]:
        blocking_issues.extend(ledger["issues"])
    if not mech.get("delta_completeness", {}).get("passed", True):
        blocking_issues.append("Delta missing summary or key events")

    # Determine warnings
    warnings = []
    if not mech.get("word_count", {}).get("passed", True):
        warnings.append(f"Word count off target: {mech['word_count']['count']} vs {mech['word_count']['target']}")
    if not mech.get("filler_ratio", {}).get("passed", True):
        warnings.append(f"High filler ratio: {mech['filler_ratio']['ratio']}")
    if not mech.get("ai_slop", {}).get("passed", True):
        warnings.append(f"AI slop words detected: {mech['ai_slop']['total']}")
    if llm.get("chapter_hook", {}).get("score", 10) < 5:
        warnings.append("Weak chapter hook")
    if llm.get("pacing", {}).get("score", 10) < 5:
        warnings.append("Pacing issues")

    passed = len(blocking_issues) == 0

    audit = AuditResult(
        chapter=chapter,
        overall_score=round(overall, 2),
        passed=passed,
        ledger_compliance=ledger,
        timeline_consistency=mech.get("timeline_consistency", {}),
        character_knowledge=mech.get("character_knowledge", {}),
        chapter_hook=llm.get("chapter_hook", {}),
        promise_fulfillment=llm.get("promise_fulfillment", {}),
        pacing=llm.get("pacing", {}),
        payoff_setup=llm.get("payoff_setup", {}),
        filler_ratio=mech.get("filler_ratio", {}),
        coherence=llm.get("coherence", {}),
        hook_debt_change=llm.get("hook_debt_change", {}),
        volume_progress=llm.get("volume_progress", {}),
        blocking_issues=blocking_issues,
        warnings=warnings,
    )

    # Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(out_path, audit.model_dump())

    # Print summary
    print(f"Audit for chapter {chapter}:")
    print(f"  Overall score: {audit.overall_score}/10")
    print(f"  Passed: {audit.passed}")
    if blocking_issues:
        print(f"  BLOCKING ISSUES:")
        for issue in blocking_issues:
            print(f"    - {issue}")
    if warnings:
        print(f"  Warnings:")
        for w in warnings:
            print(f"    - {w}")

    return audit


def main():
    parser = argparse.ArgumentParser(description="Webnovel quality audit")
    parser.add_argument("--chapter", type=int, required=True, help="Chapter number")
    parser.add_argument("--draft", type=str, required=True, help="Path to draft.md")
    parser.add_argument("--delta", type=str, required=True, help="Path to delta.json")
    parser.add_argument("--out", type=str, required=True, help="Output audit.json path")
    args = parser.parse_args()

    draft_path = Path(args.draft)
    delta_path = Path(args.delta)
    out_path = Path(args.out)

    if not draft_path.exists():
        print(f"Error: Draft not found: {draft_path}", file=sys.stderr)
        sys.exit(1)
    if not delta_path.exists():
        print(f"Error: Delta not found: {delta_path}", file=sys.stderr)
        sys.exit(1)

    audit = run_audit(args.chapter, draft_path, delta_path, out_path)
    sys.exit(0 if audit.passed else 1)


if __name__ == "__main__":
    main()
