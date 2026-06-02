#!/usr/bin/env python3
"""
4-reader panel for full-arc novel evaluation.
Each reader has a distinct persona and evaluates the NOVEL, not chapters.
The disagreements between readers are where editorial decisions live.

Usage: python reader_panel.py
"""
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get(
    "AUTONOVEL_JUDGE_MODEL",
    default_model_for_role("judge", "claude-opus-4-6"),
)

def get_readers() -> dict:
    """Build reader personas, loading genre-specific ones from genre config."""
    genre = load_genre_for_project()

    # Genre-specific personas from genre YAML
    genre_reader_text = genre.get_reader_persona("genre_reader")
    writer_text = genre.get_reader_persona("writer")

    return {
        "editor": {
            "name": "The Editor",
            "system": (
                "你是一家大型出版机构的高级文学编辑，编辑过200多部小说。"
                "你在乎散文质感、潜台词、句子级别的技法，以及行文基调（烟火气）"
                "是否一致且自然。你会注意到叙述者何时在过度解释，对话何时听起来像"
                "书面语而不是人话，比喻何时显得生硬。你不刻薄但非常精准。"
                "你只用有效的 JSON 格式回复。"
            ),
        },
        "genre_reader": {
            "name": "The Genre Reader",
            "system": genre_reader_text if genre_reader_text else (
                "你是一个每年阅读上百部网文的资深读者。"
                "你在乎爽点是否密集、升级路线是否清晰、打脸是否痛快。你讨厌憋屈的剧情"
                "和无意义的虐主。你敏锐地察觉到节奏拖沓、升级停滞、或者反派降智的时刻。"
                "你对喜欢的情节毫不吝啬赞美，对无聊的桥段也会直言不讳。"
                "你只用有效的 JSON 格式回复。"
            ),
        },
        "writer": {
            "name": "The Writer",
            "system": writer_text if writer_text else (
                "你是一位出版过五部畅销网文的资深网络小说作家。"
                "你从手艺人的角度阅读。你关注结构：情节节拍落点在哪里，伏笔是否回收，"
                "角色弧光是否完整，金手指的设定是否平衡且有局限性。你关注作者的技法"
                "是刻意为之还是无缝融入故事中。你最看重的是’期待感’的建立与释放。"
                "你在乎小说设定与实际呈现之间的差距。你只用有效的 JSON 格式回复。"
            ),
        },
        "first_reader": {
            "name": "The First Reader",
            "system": (
                "你是一位有思想的普通读者。不是作家，不是编辑，也不是流派专家。"
                "你为了体验而阅读。你知道自己的感受，但不一定知道原因。你会注意自己何时"
                "被感动、何时感到无聊、何时感到困惑。你不使用写作术语。你会说"
                "’我不在乎这部分’或’这个场景太解气了’。你的反馈是基于情感和直觉的，"
                "而不是分析性的。你只用有效的 JSON 格式回复。"
            ),
        },
    }

READER_PROMPT = """你刚刚阅读了一部完整小说的故事大纲。
这份大纲包含了逐章的事件描述、每章的开头和结尾段落，以及关键对话。

{arc_summary}

现在请回答关于整部小说的以下问题。请尽可能具体，引用原文片段，并指出具体的章节号。

请以 JSON 格式回复:
{{
  "momentum_loss": "故事在哪里失去了动力（节奏拖沓）？指出具体的章节，并说明是什么导致了拖沓。如果没有失去动力，请说明原因。",
  
  "earned_ending": "结局是否水到渠成？主角的最终选择是否合理？最终章的画面是否与开头形成了令人满意的呼应？有没有什么地方感觉是强行设定的？",
  
  "cut_candidate": "如果小说必须缩减10%的篇幅，你会首先砍掉哪一章或哪个部分？为什么？砍掉后会失去什么？",
  
  "missing_scene": "小说中是否缺少某个必须有的场景？比如一场本该发生却没写的对话，或者某个配角需要更多的出场时间？请具体说明这个场景应该加在哪里。",
  
  "thinnest_character": "到最后哪个角色感觉最单薄？你想了解关于谁的更多信息？哪个角色即使被删掉也不会影响小说质量？",
  
  "best_scene": "小说中最精彩的场景是哪个？引用让你有所触动的片段，并说明它为什么写得好（爽点/情感爆发点在哪）。",
  
  "worst_scene": "最弱/最差的场景是哪个？哪里出了问题？你会如何修改它？",
  
  "would_recommend": "你会推荐这部小说吗？推荐给谁？如果用一句话评价它，你会说什么？",
  
  "haunts_you": "读完后有没有哪句话或哪个瞬间让你印象深刻？请引用它。",
  
  "next_book": "你会读这位作者的下一本书吗？为什么？"
}}
"""

def call_reader(reader_key, arc_summary, readers):
    reader = readers[reader_key]
    raw = call_text_model(
        model=JUDGE_MODEL,
        max_tokens=4000,
        temperature=0.7,
        system=reader["system"],
        messages=[{"role": "user", "content": READER_PROMPT.format(arc_summary=arc_summary)}],
        timeout=300,
    )
    
    # Parse JSON
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```\w*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
    start = raw.find('{')
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(raw)):
            c = raw[i]
            if escape: escape = False; continue
            if c == '\\' and in_string: escape = True; continue
            if c == '"' and not escape: in_string = not in_string; continue
            if in_string: continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(raw[start:i+1], strict=False)
    return json.loads(raw, strict=False)

def find_disagreements(results):
    """Find where readers disagree -- that's where the editorial decisions live."""
    disagreements = []
    
    for question in ["momentum_loss", "cut_candidate", "thinnest_character", "worst_scene"]:
        answers = {k: v.get(question, "") for k, v in results.items()}
        # Extract chapter numbers mentioned
        chapters_mentioned = {}
        for reader, answer in answers.items():
            chs = set(re.findall(r'Ch(?:apter)?\s*(\d+)', answer, re.IGNORECASE))
            chapters_mentioned[reader] = chs
        
        # Find chapters where only some readers flagged an issue
        all_chs = set()
        for chs in chapters_mentioned.values():
            all_chs.update(chs)
        
        for ch in all_chs:
            flagged_by = [r for r, chs in chapters_mentioned.items() if ch in chs]
            not_flagged = [r for r, chs in chapters_mentioned.items() if ch not in chs]
            if flagged_by and not_flagged:
                disagreements.append({
                    "question": question,
                    "chapter": int(ch),
                    "flagged_by": flagged_by,
                    "not_flagged": not_flagged,
                    "details": {r: answers[r][:200] for r in flagged_by}
                })
    
    return disagreements

def main():
    arc_summary = (BASE_DIR / "arc_summary.md").read_text(encoding="utf-8")
    readers = get_readers()

    results = {}
    for reader_key, reader_info in readers.items():
        print(f"\n{'='*50}")
        print(f"READING: {reader_info['name']}")
        print(f"{'='*50}")

        try:
            result = call_reader(reader_key, arc_summary, readers)
            results[reader_key] = result
            
            # Print highlights
            print(f"  Momentum loss: {result.get('momentum_loss', '')[:150]}...")
            print(f"  Best scene: {result.get('best_scene', '')[:150]}...")
            print(f"  Would recommend: {result.get('would_recommend', '')[:150]}...")
        except Exception as e:
            print(f"  ERROR: {e}")
    
    # Find disagreements
    disagreements = find_disagreements(results)
    
    # Print consensus and disagreement
    print(f"\n{'='*60}")
    print("READER PANEL RESULTS")
    print(f"{'='*60}")
    
    for question in ["momentum_loss", "earned_ending", "cut_candidate", "missing_scene",
                      "thinnest_character", "best_scene", "worst_scene", "would_recommend",
                      "haunts_you", "next_book"]:
        print(f"\n--- {question.upper()} ---")
        for reader_key in readers:
            if reader_key in results:
                answer = results[reader_key].get(question, "N/A")
                print(f"  [{readers[reader_key]['name']}]: {answer[:300]}")
    
    if disagreements:
        print(f"\n{'='*60}")
        print("DISAGREEMENTS (editorial decisions needed)")
        print(f"{'='*60}")
        for d in disagreements:
            print(f"\n  {d['question']} -- Ch {d['chapter']}")
            print(f"    Flagged by: {', '.join(d['flagged_by'])}")
            print(f"    Not flagged: {', '.join(d['not_flagged'])}")
    
    # Save full results
    output = {
        "readers": results,
        "disagreements": disagreements,
        "timestamp": datetime.now().isoformat()
    }
    out_path = BASE_DIR / "edit_logs" / "reader_panel.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")

if __name__ == "__main__":
    main()
