#!/usr/bin/env python3
"""
Build a condensed arc summary for full-novel evaluation.
For each chapter: first 150 words, last 150 words, plus any dialogue.
Gives the reader panel enough to evaluate the ARC without full token cost.
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)
CHAPTERS_DIR = BASE_DIR / "chapters"

def call_writer(prompt, max_tokens=4000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.1,
        system=(
            "你可以精确地总结小说章节。陈述发生了什么、改变了什么、"
            "留下了什么悬念。不要进行任何评价或赞美。只关注事件和变化。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )

def extract_key_passages(text):
    """Get opening, closing, and best dialogue from a chapter."""
    words = text.split()
    opening = ' '.join(words[:150])
    closing = ' '.join(words[-150:])
    
    # Extract dialogue lines
    dialogue = re.findall(r'["“]([^"”]{20,})["”]', text)
    # Pick up to 3 longest dialogue lines
    dialogue.sort(key=len, reverse=True)
    top_dialogue = dialogue[:3]
    
    return opening, closing, top_dialogue

def load_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""

def load_title():
    seed = load_file(BASE_DIR / "seed.txt")
    if seed:
        first_line = seed.strip().split('\n')[0].strip()
        if first_line:
            return first_line
    outline = load_file(BASE_DIR / "outline.md")
    if outline:
        first_line = outline.strip().split('\n')[0].strip().lstrip('#').strip()
        if first_line:
            return first_line
    return "本小说"

def main():
    summaries = []
    
    # Dynamically find all chapter files
    chapter_files = sorted(CHAPTERS_DIR.glob("ch_*.md"))
    if not chapter_files:
        print("No chapter files found.")
        return

    total_wc = 0
    
    for path in chapter_files:
        # Extract chapter number
        m = re.match(r"ch_(\d+)\.md", path.name)
        if not m:
            continue
        ch = int(m.group(1))
        
        text = path.read_text()
        wc = len(text.split())
        total_wc += wc
        
        opening, closing, dialogue = extract_key_passages(text)
        
        # Get a 100-word summary from the model
        summary = call_writer(
            f"用整好3句话总结这个章节。发生了什么，改变了什么，留下了什么悬念。\n\n第 {ch} 章:\n{text}",
            max_tokens=200
        )
        
        entry = f"""### 第 {ch} 章 ({wc} 字)
**总结:** {summary}

**开场:** {opening}...

**结尾:** ...{closing}

**核心对话:**
"""
        for d in dialogue:
            entry += f'> "{d}"\n\n'
        
        summaries.append(entry)
        print(f"Ch {ch}: summarized ({wc}w)")
    
    title = load_title()
    seed_text = load_file(BASE_DIR / "seed.txt")
    
    # Assemble
    full = f"""# {title}
## 读者评审团全书大纲摘要 (Full-Arc Summary)

本文档包含了所有 {len(chapter_files)} 个章节的摘要、开场/结尾段落以及关键对话。
全书总字数：{total_wc:,} 字。

核心概念与前提：
{seed_text[:1000]}...

---

"""
    full += '\n---\n\n'.join(summaries)
    
    out_path = BASE_DIR / "arc_summary.md"
    out_path.write_text(full)
    print(f"\nSaved to {out_path} ({len(full.split())} words)")

if __name__ == "__main__":
    main()
