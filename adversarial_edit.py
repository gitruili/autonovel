#!/usr/bin/env python3
"""
Adversarial editing pass: ask the judge to CUT 500 words from each chapter.
What gets cut reveals what's weakest. The cut list IS the revision plan.

Usage: python adversarial_edit.py 1        # single chapter
       python adversarial_edit.py all      # all chapters
"""
import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get(
    "AUTONOVEL_JUDGE_MODEL",
    default_model_for_role("judge", "claude-opus-4-6"),
)
CHAPTERS_DIR = BASE_DIR / "chapters"
EDIT_LOG_DIR = BASE_DIR / "edit_logs"
EDIT_LOG_DIR.mkdir(exist_ok=True)

def call_judge(prompt, max_tokens=8000):
    return call_text_model(
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        system=(
            "You are a ruthless literary editor. You cut fat from prose. "
            "You have no sentiment about good-enough sentences -- if a sentence "
            "isn't earning its place, it goes. You quote exactly from the text. "
            "You never invent or paraphrase. Always respond with valid JSON."
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    start = text.find('{')
    if start == -1:
        start = text.find('[')
    if start == -1:
        raise ValueError("No JSON found")
    # Try direct parse first
    try:
        return json.loads(text[start:], strict=False)
    except json.JSONDecodeError:
        # Find matching brace
        depth = 0
        in_string = False
        escape = False
        open_char = text[start]
        close_char = '}' if open_char == '{' else ']'
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i+1], strict=False)
        return json.loads(text[start:], strict=False)

EDIT_PROMPT = """You are editing a fantasy novel chapter. Your job: identify exactly
what to cut or rewrite to make this chapter tighter, sharper, more alive.

THE CHAPTER ({word_count} words):
{chapter_text}

YOUR TASK:
1. Find 10-20 specific passages that should be CUT or REWRITTEN.
   For each, quote the EXACT text (minimum 10 words of the quote so
   it's unambiguous), explain why it's weak, and classify it.

2. Classify each cut as one of:
   - FAT: adds nothing, could be removed with no loss
   - REDUNDANT: restates what a previous sentence/scene already showed
   - OVER-EXPLAIN: narrator explaining what the scene already demonstrated
   - GENERIC: could appear in any novel, not specific to this world/character
   - TELL: names an emotion or state instead of showing it
   - STRUCTURAL: paragraph/section that disrupts pacing or rhythm

3. For REWRITE candidates (not cuts), provide a specific revision.

4. Estimate how many words could be cut total without losing anything
   the chapter needs.

Respond with JSON:
{{
  "cuts": [
    {{
      "quote": "exact text from the chapter (10+ words)",
      "type": "FAT|REDUNDANT|OVER-EXPLAIN|GENERIC|TELL|STRUCTURAL",
      "reason": "why this should go",
      "action": "CUT or REWRITE",
      "rewrite": "replacement text if action is REWRITE, null if CUT"
    }}
  ],
  "total_cuttable_words": N,
  "tightest_passage": "quote the best 2-3 sentences in the chapter -- the ones you'd never touch",
  "loosest_passage": "quote the worst 2-3 sentences -- the ones that most need work",
  "overall_fat_percentage": N,
  "one_sentence_verdict": "what this chapter does well and what drags it down, in one sentence"
}}
"""

def edit_chapter(ch_num):
    ch_path = CHAPTERS_DIR / f"ch_{ch_num:02d}.md"
    text = ch_path.read_text()
    word_count = len(text.split())
    
    prompt = EDIT_PROMPT.format(chapter_text=text, word_count=word_count)
    raw = call_judge(prompt)
    result = parse_json(raw)
    
    # Save log
    log_path = EDIT_LOG_DIR / f"ch{ch_num:02d}_cuts.json"
    with open(log_path, "w") as f:
        json.dump(result, f, indent=2)
    
    return result, word_count

def main():
    if len(sys.argv) < 2:
        print("Usage: python adversarial_edit.py <chapter_num|all>")
        sys.exit(1)
    
    if sys.argv[1] == "all":
        chapters = list(range(1, 25))
    else:
        chapters = [int(sys.argv[1])]
    
    for ch in chapters:
        print(f"\n{'='*50}")
        print(f"EDITING CH {ch}")
        print(f"{'='*50}")
        
        try:
            result, wc = edit_chapter(ch)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        
        cuts = result.get("cuts", [])
        cuttable = result.get("total_cuttable_words", 0)
        fat_pct = result.get("overall_fat_percentage", 0)
        verdict = result.get("one_sentence_verdict", "")
        
        # Count by type
        type_counts = {}
        for c in cuts:
            t = c.get("type", "?")
            type_counts[t] = type_counts.get(t, 0) + 1
        
        print(f"  Words: {wc}")
        print(f"  Cuts found: {len(cuts)}")
        print(f"  Cuttable words: ~{cuttable} ({fat_pct}% fat)")
        print(f"  By type: {type_counts}")
        print(f"  Verdict: {verdict}")
        print(f"  Tightest: {result.get('tightest_passage', '')[:100]}...")
        print(f"  Loosest:  {result.get('loosest_passage', '')[:100]}...")

if __name__ == "__main__":
    main()
