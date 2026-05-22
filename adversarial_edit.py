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
            "你是一位冷酷无情的文学编辑。你的任务是删减散文中的冗余。 "
            "对于那些“还算凑合”的句子，你绝不手软 —— 如果一个句子不能证明其存在的必要性，就必须删掉。 "
            "请务必从原文中进行精确引用。绝不编造或改述。 "
            "请务必以有效的 JSON 格式返回结果。"
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

EDIT_PROMPT = """你正在编辑一个网文章节。你的任务：准确识别出
应该删减或重写的内容，使本章更加紧凑、锋利、富有烟火气。

本章内容 ({word_count} 字):
{chapter_text}

你的任务：
1. 找出 10-20 处应该被删减（CUT）或重写（REWRITE）的具体片段。
   每一处都必须精确引用原文（引文至少 10 个字以确保无歧义），解释其薄弱的原因并进行分类。

2. 将每一处删减归类为以下之一：
   - 冗余 (FAT): 毫无贡献，删除后没有任何损失
   - 重复 (REDUNDANT): 重复了前一句或前一场景已经展现过的内容
   - 过度解释 (OVER-EXPLAIN): 叙述者在解释场景已经演示过的内容
   - 平庸 (GENERIC): 可能出现在任何小说中，不具有该世界或角色的独特性
   - 直接陈述 (TELL): 直接命名某种情感或状态，而不是通过场景展现它
   - 结构问题 (STRUCTURAL): 段落或章节打乱了节奏或韵律

3. 对于建议重写（而非直接删减）的候选项，提供具体的修订版本。

4. 估算在不损失任何必要内容的情况下，本章总共可以删减多少字。

请以 JSON 格式响应：
{{
  "cuts": [
    {{
      "quote": "章节中的精确引文 (10 字以上)",
      "type": "FAT|REDUNDANT|OVER-EXPLAIN|GENERIC|TELL|STRUCTURAL",
      "reason": "为什么要处理这一处",
      "action": "CUT (删减) 或 REWRITE (重写)",
      "rewrite": "如果是 REWRITE，则提供替换文本；如果是 CUT，则为 null"
    }}
  ],
  "total_cuttable_words": N,
  "tightest_passage": "引用本章中最好的 2-3 句话 —— 那些你绝不会改动的内容",
  "loosest_passage": "引用本章中最差的 2-3 句话 —— 那些最需要改进的内容",
  "overall_fat_percentage": N,
  "one_sentence_verdict": "用一句话评价本章哪些地方做得好，哪些地方拖了后腿"
}}
"""

def edit_chapter(ch_num):
    # Try volume subdirectory first, then flat
    vol = (ch_num - 1) // 20 + 1
    vol_path = CHAPTERS_DIR / f"v{vol:03d}" / f"ch_{ch_num:04d}.md"
    if vol_path.exists():
        ch_path = vol_path
    else:
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
