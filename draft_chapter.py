#!/usr/bin/env python3
"""
Draft a single chapter using the writer model.

Usage (webnovel / new pipeline):
  python draft_chapter.py 1 --context story/runtime/ch_0001/context.json --out story/runtime/ch_0001/draft.md

Usage (legacy / short story):
  python draft_chapter.py 1
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)
CHAPTERS_DIR = BASE_DIR / "chapters"
STORY_DIR = BASE_DIR / "story"


genre = load_genre_for_project()


def call_writer(prompt, max_tokens=16000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.8,
        system=genre.get_system_prompt("chapter_writer"),
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
    # Try webnovel project.json first
    proj_path = STORY_DIR / "project.json"
    if proj_path.exists():
        with open(proj_path) as f:
            proj = json.load(f)
        if proj.get("title"):
            return proj["title"]

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


def build_prompt_from_context(chapter_num: int, context: dict) -> str:
    """Build writing prompt from context.json (webnovel pipeline)."""
    title = context.get("metadata", {}).get("project_title", "本小说")
    target_chars = context.get("metadata", {}).get("target_chars", 4000)
    intent = context.get("metadata", {}).get("intent", "")

    # State slice
    state = context.get("state_slice", {})
    state_text = ""
    if state.get("characters"):
        state_text += "=== 角色信息 ===\n"
        for cid, c in state["characters"].items():
            state_text += f"- {c['name']} ({c['role']}): {c.get('personality', '')}\n"
            if c.get("speech_pattern"):
                state_text += f"  说话方式: {c['speech_pattern']}\n"
    if state.get("active_hooks"):
        state_text += "\n=== 活跃伏笔 ===\n"
        for hid, h in state["active_hooks"].items():
            state_text += f"- {h['description']}\n"
    if state.get("resources"):
        state_text += "\n=== 资源 ===\n"
        for rid, r in state["resources"].items():
            state_text += f"- {r['name']}: {r['quantity']} {r.get('unit', '')}\n"
    if state.get("items"):
        state_text += "\n=== 重要物品 ===\n"
        for iid, i in state["items"].items():
            state_text += f"- {i['name']} ({i.get('rarity', 'common')}): {i.get('description', '')}\n"

    # Recent summaries
    summaries_text = ""
    for s in context.get("recent_summaries", []):
        summaries_text += f"- 第{s['chapter']}章: {s.get('summary', '')[:200]}\n"

    prompt = f"""撰写《{title}》的第 {chapter_num} 章。

=== 写作意图 ===
{intent}

=== 本章计划 ===
{context.get('chapter_plan', '')}

=== 卷级计划（参考） ===
{context.get('volume_contract', '')[:2000]}

=== 前一章结尾（从此处继续） ===
{context.get('previous_chapter_tail', '(第一章——无前文)')}

{state_text}

=== 最近章节摘要 ===
{summaries_text or '(第一章)'}

=== 语气规则 ===
{context.get('voice_rules', '')}

=== 写作指令 ===
1. 撰写完整的章节。目标字数约 {target_chars} 字。不要截断或总结。
2. 第三人称限制视角，过去时态，紧贴章计划中指定的视角人物。
3. 按顺序完成章计划中所有节拍。
4. 展示感官细节：触觉、嗅觉、听觉融入场景。
5. 对话遵循角色信息中定义的说话模式。
6. 不要使用语气规则中禁用的词汇和句式。
7. 不要出现 AI 网文腔调：不要用"不禁"、"映入眼帘"、"心中涌起暖流"、"美眸"、"淡淡地说"。
8. 改变句子长度。短句用于情绪冲击，长句用于铺陈日常。
9. 信任读者。不要解释场景的含义，让场景本身产生力量。
10. 从场景中开始这一章，不要以铺陈开始。以一个瞬间结束，而不是总结。
11. 展示之后不要过度解释。信任场景。
12. 对话要像说话，不像书面语。角色会磕绊、打断、话没说完。
13. 场景优于总结。本章至少 70% 的内容应是即时场景。
14. 章尾钩子必须让读者想翻下一章。
15. 禁止使用三元组感官列表（"X、Y和Z"）。合并两个，删掉一个。
16. 禁止"她心想/她暗想"——让想法本身作为独立句子出现。

=== 年代文写作示范（对比正确与错误写法）===

技法1：用感官替代情绪标签
❌ 她感到一阵绝望，不知道明天该怎么办。
✅ 她把三张二两的粮票摊在桌上，指尖在纸边停了一下。月底还有八天。窗外风声紧了，她起身去堵门缝，手摸到门框时停住——木头是潮的，今晚怕是要下雪。

技法2：对话要带情境质感
❌ "我回来了。"林战沉默地说道。
✅ 门帘掀开时灌进一股白毛风。林战肩上的雪还没化，他把一袋东西放在门槛内侧，嗓音被冻得发哑："部队食堂多打了两份，你热热。"

技法3：经济细节要具体可感
❌ 这里的煤炭很紧缺，每个月按人头配额，根本不够用。
✅ 月底了，煤棚里只剩拳头大的两块。她把炉子封到最小，火苗舔着铁皮，屋里温度刚好够水不结冰。

现在开始撰写章节。完整文本，从头到尾。
"""
    return prompt


def build_prompt_legacy(chapter_num: int) -> str:
    """Build prompt using legacy file-based context."""
    voice = load_file(BASE_DIR / "voice.md")
    world = load_file(BASE_DIR / "world.md")
    characters = load_file(BASE_DIR / "characters.md")
    outline = load_file(BASE_DIR / "outline.md")
    canon = load_file(BASE_DIR / "canon.md")
    title = load_title()

    chapter_outline = extract_chapter_outline(outline, chapter_num)
    next_chapter = extract_next_chapter_outline(outline, chapter_num)

    prev_path = CHAPTERS_DIR / f"ch_{chapter_num - 1:02d}.md"
    if prev_path.exists():
        prev_text = prev_path.read_text()
        prev_tail = prev_text[-2000:] if len(prev_text) > 2000 else prev_text
    else:
        prev_tail = "(第一章——无前文)"

    return f"""撰写《{title}》的第 {chapter_num} 章。

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
23. {genre.get_prompt_fragment("chapter_draft", "genre_specific_detail") or "题材专属细节要具体有质感，参考世界设定集中的相关描写。"}
24. 章尾钩子必须让读者想翻下一章。

=== 年代文写作示范（对比正确与错误写法）===

技法1：用感官替代情绪标签
❌ 她感到一阵绝望，不知道明天该怎么办。
✅ 她把三张二两的粮票摊在桌上，指尖在纸边停了一下。月底还有八天。窗外风声紧了，她起身去堵门缝，手摸到门框时停住——木头是潮的，今晚怕是要下雪。

技法2：对话要带情境质感
❌ "我回来了。"林战沉默地说道。
✅ 门帘掀开时灌进一股白毛风。林战肩上的雪还没化，他把一袋东西放在门槛内侧，嗓音被冻得发哑："部队食堂多打了两份，你热热。"

技法3：经济细节要具体可感
❌ 这里的煤炭很紧缺，每个月按人头配额，根本不够用。
✅ 月底了，煤棚里只剩拳头大的两块。她把炉子封到最小，火苗舔着铁皮，屋里温度刚好够水不结冰。

现在开始撰写章节。完整文本，从头到尾。
"""


def main():
    parser = argparse.ArgumentParser(description="Draft a single chapter")
    parser.add_argument("chapter", type=int, help="Chapter number")
    parser.add_argument("--context", type=str, help="Path to context.json (webnovel pipeline)")
    parser.add_argument("--out", type=str, help="Output draft path (webnovel pipeline)")
    args = parser.parse_args()

    chapter_num = args.chapter

    if args.context:
        # Webnovel pipeline: read from context.json
        with open(args.context) as f:
            context = json.load(f)
        prompt = build_prompt_from_context(chapter_num, context)
    else:
        # Legacy: read from markdown files
        prompt = build_prompt_legacy(chapter_num)

    print(f"Drafting Chapter {chapter_num}...", file=sys.stderr)
    result = call_writer(prompt)

    if args.out:
        # Webnovel pipeline: save to specified path
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result, encoding="utf-8")
        # Also copy to chapters/vNNN/ (volume-aware)
        proj_path = STORY_DIR / "project.json"
        volume = 1
        if proj_path.exists():
            with open(proj_path) as f:
                proj_data = json.load(f)
            volume = proj_data.get("current_volume", 1)
        v_dir = CHAPTERS_DIR / f"v{volume:03d}"
        v_dir.mkdir(parents=True, exist_ok=True)
        v_file = v_dir / f"ch_{chapter_num:04d}.md"
        v_file.write_text(result, encoding="utf-8")
        from story_schema import count_cn_words
        word_count = count_cn_words(result)
        print(f"Saved to {out_path}", file=sys.stderr)
        print(f"Saved to {v_file}", file=sys.stderr)
        print(f"Word count (CN): {word_count}", file=sys.stderr)
    else:
        # Legacy: save to chapters/ch_XX.md
        out_path = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
        out_path.write_text(result)
        print(f"Saved to {out_path}", file=sys.stderr)
        print(f"Word count: {len(result.split())}", file=sys.stderr)

    print(result)


if __name__ == "__main__":
    main()
