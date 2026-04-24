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
            "你是一位正在撰写女频种田经营网文章节的小说家。"
            "你擅长烟火气十足的日常描写、真实可信的经济逻辑、"
            "以及具体入微的感官细节。"
            "你使用第三人称限制视角，过去时态，紧贴视角人物。"
            "你严格遵循语气定义文件。你完成大纲中的每一个节拍。"
            "你绝不使用禁用词列表中的词汇。你展示情感，从不直接陈述。"
            "你的文字具体、有质感、有烟火气。隐喻来自角色的生活经验。"
            "你通过改变句子长度来调节节奏。你信任读者。"
            "你撰写完整的章节——不要截断、总结或跳过情节。"
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


def load_title():
    """从 seed.txt 或 outline.md 中提取小说标题。"""
    seed = load_file(BASE_DIR / "seed.txt")
    if seed:
        first_line = seed.strip().split('\n')[0].strip()
        if first_line:
            return first_line
    # fallback: 从 outline.md 第一行提取
    outline = load_file(BASE_DIR / "outline.md")
    if outline:
        first_line = outline.strip().split('\n')[0].strip().lstrip('#').strip()
        if first_line:
            return first_line
    return "本小说"


def extract_chapter_outline(outline_text, chapter_num):
    """Extract a specific chapter's outline entry."""
    pattern = rf'###\s*第\s*{chapter_num}\s*章[：:]\s*.*?(?=###\s*第\s*\d+\s*章|##\s*第[一二三四]幕|##\s*种田升级|##\s*情感线|##\s*伏笔|##\s*打脸|##\s*文风|$)'
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
    title = load_title()

    # Chapter-specific context
    chapter_outline = extract_chapter_outline(outline, chapter_num)
    next_chapter = extract_next_chapter_outline(outline, chapter_num)

    # Previous chapter (if exists)
    prev_path = CHAPTERS_DIR / f"ch_{chapter_num - 1:02d}.md"
    if prev_path.exists():
        prev_text = prev_path.read_text()
        prev_tail = prev_text[-2000:] if len(prev_text) > 2000 else prev_text
    else:
        prev_tail = "(第一章——无前文)"

    prompt = f"""撰写《{title}》的第 {chapter_num} 章。

=== 语气定义（请严格遵循） ===
{voice}

=== 本章大纲（完成每一个节拍） ===
{chapter_outline}

=== 下一章大纲（用于衔接——确保本章结尾能顺滑过渡到下一章） ===
{next_chapter}

=== 前一章结尾（从此处继续） ===
{prev_tail}

=== 世界设定集（物价、礼法、地理等硬性参考） ===
{world}

=== 角色信息（说话模式、行为逻辑） ===
{characters}

=== 设定准则（硬性事实，不可违反） ===
{canon}

=== 写作指令 ===
1. 撰写完整的章节。目标字数约 3,500-4,500 字。不要截断或总结。
2. 第三人称限制视角，过去时态，紧贴大纲中指定的视角人物。
3. 按顺序完成大纲中所有关键场景。
4. 植入大纲中"伏笔植入"项下列出的所有元素。
5. 展示感官细节：参考世界设定集中"感官特征"部分，将触觉、嗅觉、听觉融入场景。
6. 经济数据必须与世界设定集中的物价表一致。提到金额时必须具体。
7. 对话遵循角色信息中定义的说话模式和身份特征。
8. 不要使用语气定义中禁用的词汇和句式。
9. 不要出现 AI 网文腔调：不要用"不禁"、"映入眼帘"、"心中涌起暖流"、"美眸"、"淡淡地说"。
10. 改变句子长度。短句用于情绪冲击，长句用于铺陈日常。
11. 隐喻应来自视角人物的职业经验和生活背景（参考角色信息）。
12. 信任读者。不要解释场景的含义，让场景本身产生力量。
13. 从场景中开始这一章，不要以铺陈（exposition）开始。以一个瞬间结束，而不是总结。

=== 需要避免的模式 ===
14. 禁止使用三元组感官列表（"X、Y和Z"）。合并两个，删掉一个。
15. 禁止"她心想/她暗想"——让想法本身作为独立句子出现。
16. 每章中"不由自主地"不得出现超过一次。
17. 展示之后不要过度解释。如果场景已说明了某事，不要让叙述者再重申。信任场景。
18. 不要把小节分隔符 (---) 当作节奏拐杖。仅在真正的时空跳转时使用。每章最多 2 个。
19. 有意识地改变段落长度。至少包含一个 1-2 句的短段落和一个 5 句以上的长段落。
20. 对话要像说话，不像书面语。角色会磕绊、打断、话没说完。
21. 场景优于总结。本章至少 70% 的内容应是即时场景（带对话和动作），而非叙述概括。
22. 包含至少一个令人惊喜的瞬间——角色说错话、情感爆发时机不合预期、打破模式的细节。
23. 种田/经营细节要具体有质感，参考世界设定集中的物价、工序、物产描写。
24. 章尾钩子必须让读者想翻下一章。

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
