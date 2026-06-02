#!/usr/bin/env python3
"""
Rebuild outline.md from the actual chapters.
Reads each chapter, calls the LLM for a structured summary,
and assembles into an outline that reflects the novel as-written.
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
    default_model_for_role("judge", "claude-sonnet-4-6"),
)
CHAPTERS_DIR = BASE_DIR / "chapters"
PLANS_DIR = BASE_DIR / "story" / "plans"
PLANS_DIR.mkdir(parents=True, exist_ok=True)

def call_model(prompt, max_tokens=1500):
    text = call_text_model(
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.1,
        system=(
            "你可以为小说章节生成结构化的大纲条目。 "
            "请精确说明发生了什么，改变了什么，以及埋下/回收了什么伏笔。 "
            "只输出有效的 JSON 格式。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )
    # Extract JSON from response
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    return json.loads(text)

def load_file(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

def load_title():
    seed = load_file(BASE_DIR / "seed.txt")
    if seed:
        first_line = seed.strip().split('\n')[0].strip()
        if first_line:
            return first_line
    return "本小说"

def main():
    # Load supporting docs for context
    characters = load_file(BASE_DIR / "characters.md")[:3000]
    
    entries = []
    
    chapter_files = sorted(CHAPTERS_DIR.glob("ch_*.md"))
    if not chapter_files:
        print("No chapter files found.")
        return
        
    for path in chapter_files:
        m = re.match(r"ch_(\d+)\.md", path.name)
        if not m:
            continue
        ch = int(m.group(1))
        
        text = path.read_text(encoding="utf-8")
        wc = len(text.split())
        
        title_line = text.strip().split('\n')[0].lstrip('# ').strip()
        
        prompt = f"""分析这个章节并生成结构化的大纲条目。

第 {ch} 章: "{title_line}" ({wc} 字)

{text}

请返回包含以下字段的 JSON:
- "title": 章节标题 (string)
- "location": 主要场景/地点 (string)
- "characters": 出场的角色列表 (list of strings)
- "summary": 2-3句话总结发生了什么 (string)
- "beats": 按顺序排列的3-5个关键情节节拍 (list of strings)
- "try_fail": 尝试-失败循环的类型: "yes-but" (成功但有代价), "no-and" (失败且情况更糟), "yes-and" (成功且有奖励), 或 "no-but" (失败但有收获) (string)
- "plants": 本章中埋下的伏笔/铺垫 (list of strings)
- "harvests": 本章中回收的伏笔/铺垫 (list of strings)
- "emotional_arc": 用一句话描述主角的情感轨迹变化 (string)
- "chapter_question": 章节末尾留下的悬念或未解问题 (string)

只输出 JSON，不要有其他文本。"""

        data = call_model(prompt)
        data["num"] = ch
        data["words"] = wc
        entries.append(data)
        print(f"  {ch:2d}. {title_line} ({wc}w)")
    
    title = load_title()
    
    # Build new outline
    lines = []
    lines.append(f"# {title}")
    lines.append("## Chapter Outline (反映实际写出的最终小说大纲)")
    lines.append("")
    lines.append(f"**共 {len(chapter_files)} 章, {sum(e['words'] for e in entries):,} 字**")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    for e in entries:
        lines.append(f"### 第 {e['num']} 章: {e.get('title', 'N/A')}")
        lines.append(f"**{e['words']} 字** | **地点:** {e.get('location', 'N/A')}")
        lines.append(f"- **出场角色:** {', '.join(e.get('characters', []))}")
        lines.append(f"- **循环类型:** {e.get('try_fail', 'N/A')}")
        lines.append(f"- **情感轨迹:** {e.get('emotional_arc', 'N/A')}")
        lines.append("")
        lines.append(f"**总结:** {e.get('summary', 'N/A')}")
        lines.append("")
        lines.append("**关键节拍:**")
        for b in e.get("beats", []):
            lines.append(f"1. {b}")
        lines.append("")
        if e.get("plants"):
            lines.append("**埋下伏笔:**")
            for p in e["plants"]:
                lines.append(f"- {p}")
            lines.append("")
        if e.get("harvests"):
            lines.append("**回收伏笔:**")
            for h in e["harvests"]:
                lines.append(f"- {h}")
            lines.append("")
        lines.append(f"**章节末尾悬念:** {e.get('chapter_question', 'N/A')}")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # Foreshadowing ledger
    lines.append("## 伏笔账本 (FORESHADOWING LEDGER)")
    lines.append("")
    lines.append("| 伏笔线索 | 埋下章节 | 回收章节 |")
    lines.append("|--------|---------|-----------|")
    
    # Collect all plants and harvests
    all_plants = {}
    all_harvests = {}
    for e in entries:
        for p in e.get("plants", []):
            key = p[:60]
            if key not in all_plants:
                all_plants[key] = []
            all_plants[key].append(e["num"])
        for h in e.get("harvests", []):
            key = h[:60]
            if key not in all_harvests:
                all_harvests[key] = []
            all_harvests[key].append(e["num"])
    
    # Match plants to harvests by keyword overlap
    all_threads = set(list(all_plants.keys()) + list(all_harvests.keys()))
    for thread in sorted(all_threads):
        planted = ", ".join(f"Ch {n}" for n in all_plants.get(thread, []))
        harvested = ", ".join(f"Ch {n}" for n in all_harvests.get(thread, []))
        lines.append(f"| {thread} | {planted} | {harvested} |")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*大纲根据最终实际撰写的章节重新生成。*")
    
    out = '\n'.join(lines)
    actual_path = PLANS_DIR / "outline_actual.md"
    actual_path.write_text(out, encoding="utf-8")
    print(f"\nSaved {actual_path.name} ({len(out.split())} words)")

if __name__ == "__main__":
    main()
