#!/usr/bin/env python3
"""
Comparative ranking: pair chapters head-to-head.
The judge picks a winner and quotes the deciding moments.
Produces a true rank order from round-robin tournament.

Usage: python compare_chapters.py          # full tournament
       python compare_chapters.py 1 10     # single matchup
"""
import os
import sys
import json
import re
import random
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get(
    "AUTONOVEL_JUDGE_MODEL",
    default_model_for_role("judge", "claude-opus-4-6"),
)
CHAPTERS_DIR = BASE_DIR / "chapters"

def call_judge(prompt, max_tokens=4000):
    return call_text_model(
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.2,
        system=(
            "You are a literary editor comparing two chapters of the same novel. "
            "You pick the better one. You are not allowed to call it a tie. "
            "You quote specific passages to justify your choice. Respond with "
            "valid JSON only."
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
        raise ValueError("No JSON found")
    try:
        return json.loads(text[start:], strict=False)
    except json.JSONDecodeError:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape: escape = False; continue
            if c == '\\' and in_string: escape = True; continue
            if c == '"' and not escape: in_string = not in_string; continue
            if in_string: continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i+1], strict=False)
        return json.loads(text[start:], strict=False)

COMPARE_PROMPT = """Compare these two chapters from the same fantasy novel.
Both are first drafts. Pick the BETTER one. You MUST pick a winner -- no ties.

CHAPTER A (Ch {ch_a}):
{text_a}

CHAPTER B (Ch {ch_b}):
{text_b}

Compare on these axes:
- Which has sharper prose (more specific, less generic)?
- Which has better dialogue (sounds like speech, not written prose)?
- Which creates more genuine tension or surprise?
- Which trusts the reader more (less over-explaining)?
- Which has fewer AI writing patterns?

You MUST pick one. If they're close, pick the one with the single
best moment -- the sentence you wish you'd written.

Respond with JSON:
{{
  "winner": "A" or "B",
  "winner_chapter": N,
  "margin": "clear" or "slight" or "razor-thin",
  "decisive_moment": "quote the passage that tipped it -- from the WINNER",
  "winner_strength": "what the winner does that the loser doesn't",
  "loser_weakness": "what specifically drags the loser down",
  "best_sentence_a": "quote the single best sentence from A",
  "best_sentence_b": "quote the single best sentence from B"
}}
"""

def compare(ch_a, ch_b):
    text_a = (CHAPTERS_DIR / f"ch_{ch_a:02d}.md").read_text()
    text_b = (CHAPTERS_DIR / f"ch_{ch_b:02d}.md").read_text()
    
    # Truncate to ~3000 words each to fit context
    words_a = text_a.split()
    words_b = text_b.split()
    if len(words_a) > 3000:
        text_a = ' '.join(words_a[:3000]) + "\n[truncated]"
    if len(words_b) > 3000:
        text_b = ' '.join(words_b[:3000]) + "\n[truncated]"
    
    prompt = COMPARE_PROMPT.format(
        ch_a=ch_a, ch_b=ch_b,
        text_a=text_a, text_b=text_b
    )
    raw = call_judge(prompt)
    result = parse_json(raw)
    result["ch_a"] = ch_a
    result["ch_b"] = ch_b
    return result

def run_tournament(chapters):
    """Swiss-style tournament: pair by similar Elo, run enough rounds to rank."""
    # Initialize Elo ratings
    elo = {ch: 1500 for ch in chapters}
    K = 32
    matchups = []
    
    # Run 3-4 rounds of Swiss pairings
    n_rounds = 4
    for round_num in range(n_rounds):
        # Sort by Elo, pair adjacent
        ranked = sorted(chapters, key=lambda c: elo[c], reverse=True)
        pairs = []
        used = set()
        for i in range(0, len(ranked) - 1, 2):
            a, b = ranked[i], ranked[i+1]
            if (a, b) not in used and (b, a) not in used:
                pairs.append((a, b))
                used.add((a, b))
        
        print(f"\n--- Round {round_num + 1} ({len(pairs)} matchups) ---")
        for ch_a, ch_b in pairs:
            try:
                result = compare(ch_a, ch_b)
                winner = result.get("winner_chapter", result.get("winner"))
                margin = result.get("margin", "?")
                
                # Handle "A"/"B" vs chapter number
                if winner == "A":
                    winner = ch_a
                elif winner == "B":
                    winner = ch_b
                else:
                    winner = int(winner)
                
                loser = ch_b if winner == ch_a else ch_a
                
                # Update Elo
                exp_a = 1 / (1 + 10 ** ((elo[ch_b] - elo[ch_a]) / 400))
                score_a = 1.0 if winner == ch_a else 0.0
                elo[ch_a] += K * (score_a - exp_a)
                elo[ch_b] += K * ((1 - score_a) - (1 - exp_a))
                
                result["winner_resolved"] = winner
                matchups.append(result)
                
                print(f"  Ch {ch_a} vs Ch {ch_b}: winner=Ch {winner} ({margin})")
                
            except Exception as e:
                print(f"  Ch {ch_a} vs Ch {ch_b}: ERROR ({e})")
    
    # Final ranking
    ranking = sorted(chapters, key=lambda c: elo[c], reverse=True)
    
    return ranking, elo, matchups

def main():
    if len(sys.argv) == 3:
        # Single matchup
        ch_a, ch_b = int(sys.argv[1]), int(sys.argv[2])
        result = compare(ch_a, ch_b)
        print(json.dumps(result, indent=2))
    else:
        # Full tournament
        chapters = list(range(1, 25))
        ranking, elo, matchups = run_tournament(chapters)
        
        print(f"\n{'='*50}")
        print("FINAL RANKING")
        print(f"{'='*50}")
        for i, ch in enumerate(ranking):
            print(f"  {i+1:2d}. Ch {ch:2d}  (Elo: {elo[ch]:.0f})")
        
        # Save results
        results = {
            "ranking": ranking,
            "elo": {str(k): round(v) for k, v in elo.items()},
            "matchups": matchups,
            "timestamp": datetime.now().isoformat()
        }
        out_path = BASE_DIR / "edit_logs" / "tournament_results.json"
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved to {out_path}")

if __name__ == "__main__":
    main()
