#!/usr/bin/env python3
"""
Draft a single chapter using the writer model.
Usage: python draft_chapter.py 1
"""
import os
import re
import sys
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

def call_writer(prompt, max_tokens=16000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.8,
        system=(
            "你是一位正在撰写奇幻小说章节的纯文学小说家。 "
            "你使用第三人称限制视角，过去时态，锁定在单一视角人物身上。 "
            "你严格遵循语气定义文件。你完成大纲中的每一个节拍。 "
            "你绝不使用禁用词列表中的词汇。你展现情感，从不直接陈述。 "
            "你的文字具体、具有感官细节且踏实。隐喻来自角色的个人经历。 "
            "你通过改变句子长度来调节节奏。你信任读者。 "
            "你撰写完整的章节 —— 不要截断、总结或跳过情节。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
        include_beta=True,
    )

def load_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""

def extract_chapter_outline(outline_text, chapter_num):
    """Extract a specific chapter's outline entry."""
    pattern = rf'### Ch {chapter_num}:.*?(?=### Ch {chapter_num + 1}:|## Foreshadowing|$)'
    match = re.search(pattern, outline_text, re.DOTALL)
    return match.group(0).strip() if match else "(not found)"

def extract_next_chapter_outline(outline_text, chapter_num):
    """Extract the next chapter's outline (just first few lines for continuity)."""
    next_entry = extract_chapter_outline(outline_text, chapter_num + 1)
    if next_entry == "(not found)":
        return "(final chapter)"
    lines = next_entry.split('\n')[:10]
    return '\n'.join(lines)

def main():
    chapter_num = int(sys.argv[1])
    
    # Load all context
    voice = load_file(BASE_DIR / "voice.md")
    world = load_file(BASE_DIR / "world.md")
    characters = load_file(BASE_DIR / "characters.md")
    outline = load_file(BASE_DIR / "outline.md")
    canon = load_file(BASE_DIR / "canon.md")
    
    # Chapter-specific context
    chapter_outline = extract_chapter_outline(outline, chapter_num)
    next_chapter = extract_next_chapter_outline(outline, chapter_num)
    
    # Previous chapter (if exists)
    prev_path = CHAPTERS_DIR / f"ch_{chapter_num - 1:02d}.md"
    if prev_path.exists():
        prev_text = prev_path.read_text()
        prev_tail = prev_text[-2000:] if len(prev_text) > 2000 else prev_text
    else:
        prev_tail = "(first chapter -- no previous)"
    
    prompt = f"""撰写《钟鸣之家次子》（The Second Son of the House of Bells）的第 {chapter_num} 章。

语气定义 (VOICE DEFINITION，请严格遵循):
{voice}

本章大纲 (完成每一个节拍):
{chapter_outline}

下一章大纲 (用于衔接 —— 确保本章结尾能顺滑过渡到下一章):
{next_chapter}

前一章结尾 (从此处继续):
{prev_tail}

世界设定集 (用于参考世界观细节):
{world}

角色注册表 (用于参考说话模式和行为):
{characters}

写作指令：
1. 撰写完整的章节。目标字数约 3,200 字。不要截断或总结。
2. 第三人称限制视角，过去时态，锁定在 Cass 的视角。
3. 按顺序完成大纲中所有带编号的节拍。
4. 植入“伏笔植入 (Plants)”项下列表的所有元素。
5. 展示感官细节：Cass 听到了什么、闻到了什么、身体感受到了什么。
6. “底音（under-note）”会引起具体的身体疼痛（比如左眼后的针刺感，而不是模糊的不适）。
7. 对话遵循 characters.md 中定义的说话模式。
8. 不要使用 voice.md 第一部分禁用的词汇。
9. 不要出现 AI 小说腔调：不要用“一种……的感觉”、不要用“不由自主地感到”、不要用“眼睛睁大”。
10. 改变句子长度。短句用于冲击力，长句用于铺陈。
11. 隐喻应来自 Cass 的经历：声音、青铜、工艺、身体对音调的反应。
12. 信任读者。不要解释场景的含义，让场景本身产生力量。
13. 从场景中开始这一章，不要以铺陈（exposition）开始。以一个瞬间结束，而不是总结。

需要避免的模式（这些在之前的章节中已被标记）：
14. 禁止使用三元组感官列表。永远不要连续列出三个独立的项（如“X、Y、Z”或“X 和 Y 以及 Z”）。合并其中两个，删掉一个，或者重组。
15. 每章中“他没有[动词]（He did not [verb]）”的使用不得超过一次。将否定表述改为主动表述，或者干脆删掉。
16. 禁止使用“他想到了 [X]（He thought about [X]）”这种句式。替换为：想法本身作为一个片段、一个物理动作或一段对话。
17. 每章中“像 [X] 做 [Y] 那样（the way [X] did [Y]）”这种类比连接词不得超过两次。使用不同的类比结构或直接删掉对比。
18. 展示之后不要过度解释。如果一个场景已经说明了某事，不要让叙述者再重申一遍。信任场景。
19. 不要把小节分隔符 (---) 当作节奏的拐杖。仅在真正的时空跳转时使用。每章最多使用 2 个。
20. 有意识地改变段落长度。绝对不要连续出现超过 3 个长度相近的段落。至少包含一个 1-2 句的短段落和一个 6 句以上的长段落。
21. 本章的结尾方式要与之前的章节有所不同。不要再以 Cass 在外面听他父亲工作作为结尾。为本章寻找一个专属的结局。
22. 包含至少一个令人惊喜的瞬间 —— 角色说错了话、情感爆发得比预期早或晚、或者一个不符合预期模式的细节。可预测的优秀依然是可预测的。
23. 场景优于总结。本章至少 70% 的内容应该是即时场景（伴随对话和动作的每一个瞬间），而不是总结（叙述者压缩时间）。
24. 对话听起来应该是说话，而不是书面语。角色偶尔会有磕绊、打断、话没说完或说错了一点点。一个 14 岁的孩子说话不会总是出口成章。

现在开始撰写章节。完整文本，从头到尾。
"""

    print(f"Drafting Chapter {chapter_num}...", file=sys.stderr)
    result = call_writer(prompt)
    
    # Save
    out_path = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    out_path.write_text(result)
    print(f"Saved to {out_path}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)
    print(result)

if __name__ == "__main__":
    main()
