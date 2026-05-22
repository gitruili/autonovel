#!/usr/bin/env python3
"""
Revision chapter generator. Rewrites a chapter from a specific revision brief.
Usage: python gen_revision.py <chapter_num> <brief_file>
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project

BASE_DIR = Path(__file__).parent
genre = load_genre_for_project()
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)


def call_writer(prompt, max_tokens=16000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.8,
        system=genre.get_system_prompt("revision_writer"),
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


def main():
    ch_num = int(sys.argv[1])
    brief_file = sys.argv[2]
    
    voice = (BASE_DIR / "voice.md").read_text()
    characters = (BASE_DIR / "characters.md").read_text()
    world = (BASE_DIR / "world.md").read_text()
    brief = Path(brief_file).read_text()
    title = load_title()
    
    # Load adjacent chapters for continuity
    prev_path = BASE_DIR / "chapters" / f"ch_{ch_num - 1:02d}.md"
    next_path = BASE_DIR / "chapters" / f"ch_{ch_num + 1:02d}.md"
    prev_tail = prev_path.read_text()[-2000:] if prev_path.exists() else "(第一章——无前文)"
    next_head = next_path.read_text()[:1500] if next_path.exists() else "(最后一章)"
    
    # Load old version if exists
    old_path = BASE_DIR / "chapters" / f"ch_{ch_num:02d}.md"
    old_text = old_path.read_text() if old_path.exists() else "(尚未起草)"
    
    prompt = f"""重写《{title}》的第 {ch_num} 章。

=== 修订任务书 REVISION BRIEF (请严格遵循此文档进行修改) ===
{brief}

=== 语气定义 VOICE DEFINITION ===
{voice}

=== 角色信息 CHARACTER REGISTRY ===
{characters}

=== 世界设定集 WORLD BIBLE ===
{world}

=== 前一章结尾 (用于保持连贯性) ===
{prev_tail}

=== 下一章开头 (结尾应顺滑过渡到这里) ===
{next_head}

=== 现有草稿 (作为原材料——保留好的部分，剪掉坏的部分) ===
{old_text}

=== 避免的负面模式 (ANTI-PATTERN RULES) ===
- 禁止使用三元组感官列表 (例如: 看到X，听到Y，闻到Z)
- 每一章中"不由自主地"或类似词汇不得出现超过一次
- 禁止"她心想/她暗想"——让想法本身作为独立的句子融入叙事
- 禁止过度解释（如果动作或对话已经展示了，就不要再用旁白解释一遍）
- 每章最多 2 个小节分隔符(---)，仅在真正的时空跳转时使用
- 必须包含至少一个令人惊喜/符合人设但打破常规的瞬间
- 至少 70% 的内容必须是即时场景（带对话和动作），而不是干巴巴的叙述总结
- 对话要像真正的说话：带有地方特色、有潜台词，而不是书面语或演讲
- 绝不使用烂俗 AI 网文词汇："不禁"、"映入眼帘"、"心中涌起暖流"、"美眸"等

现在，请写出完整的修订章节。"""

    print(f"Rewriting Chapter {ch_num}...", file=sys.stderr)
    result = call_writer(prompt)
    
    out_path = BASE_DIR / "chapters" / f"ch_{ch_num:02d}.md"
    out_path.write_text(result)
    print(f"Saved to {out_path}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)

if __name__ == "__main__":
    main()
