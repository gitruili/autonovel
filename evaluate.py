#!/usr/bin/env python3
"""
evaluate.py -- Novel evaluation harness.

Usage:
  python evaluate.py --phase=foundation    # Score planning docs only
  python evaluate.py --chapter=5           # Score a single chapter
  python evaluate.py --full                # Score the entire novel

Output: structured scores to stdout + eval_logs/<timestamp>.json

This file is READ-ONLY during autonomous runs. The human edits it
to tune what "good" means. The agent treats it as a black box.
"""

import argparse
import json
import os
import sys
import glob
import re
from datetime import datetime
from pathlib import Path
from llm_client import call_text_model, default_model_for_role

# --- Configuration ---
BASE_DIR = Path(__file__).parent

# Load .env file if present
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# Judge uses Opus 4.6 (harsh, critical). Writer uses Sonnet 4.6 (fast, long context).
# Intentionally different to avoid self-congratulation.
JUDGE_MODEL = os.environ.get(
    "AUTONOVEL_JUDGE_MODEL",
    default_model_for_role("judge", "claude-opus-4-6"),
)
CHAPTERS_DIR = BASE_DIR / "chapters"
EVAL_LOG_DIR = BASE_DIR / "eval_logs"
EVAL_LOG_DIR.mkdir(exist_ok=True)


# ---- Mechanical Slop Detection (no LLM needed) ----

TIER1_BANNED = [
    "delve", "utilize", "leverage", "facilitate", "elucidate",
    "embark", "endeavor", "encompass", "multifaceted", "tapestry",
    "paradigm", "synergy", "synergize", "holistic", "catalyze",
    "catalyst", "juxtapose", "myriad", "plethora",
]

TIER2_SUSPICIOUS = [
    "robust", "comprehensive", "seamless", "seamlessly", "cutting-edge",
    "innovative", "streamline", "empower", "foster", "enhance", "elevate",
    "optimize", "pivotal", "intricate", "profound", "resonate",
    "underscore", "harness", "cultivate", "bolster", "galvanize",
    "cornerstone", "game-changer", "scalable",
]

TIER3_FILLER = [
    r"it'?s worth noting that",
    r"it'?s important to note that",
    r"^importantly,?\s",
    r"^notably,?\s",
    r"^interestingly,?\s",
    r"let'?s dive into",
    r"let'?s explore",
    r"as we can see",
    r"^furthermore,?\s",
    r"^moreover,?\s",
    r"^additionally,?\s",
    r"in today'?s .*(fast-paced|digital|modern)",
    r"at the end of the day",
    r"it goes without saying",
    r"when it comes to",
    r"one might argue that",
    r"not just .+, but",
]

TRANSITION_OPENERS = [
    "however", "furthermore", "additionally", "moreover",
    "nevertheless", "consequently", "nonetheless", "similarly",
]

# Fiction-specific AI tells (prose clichés that betray machine origin)
FICTION_AI_TELLS = [
    r"a sense of \w+",
    r"couldn'?t help but feel",
    r"the weight of \w+",
    r"the air was thick with",
    r"eyes widened",
    r"a wave of \w+ washed over",
    r"a pang of \w+",
    r"heart pounded in (?:his|her|their) chest",
    r"(?:raven|dark|golden|silver) (?:hair|tresses) (?:spilled|cascaded|tumbled|fell)",
    r"piercing (?:blue|green|gray|grey|dark) eyes",
    r"a knowing (?:smile|grin|look|glance)",
    r"(?:he|she|they) felt a (?:surge|rush|wave|pang|flicker) of",
    r"the silence (?:was|hung|stretched|grew) (?:heavy|thick|oppressive|deafening)",
    r"let out a breath (?:he|she|they) didn'?t (?:know|realize)",
    r"something (?:dark|ancient|primal|unnamed) stirred",
]

# Structural AI tics -- rhetorical formulas that betray AI composition
STRUCTURAL_AI_TICS = [
    r"(?:I'm|I am) not (?:saying|asking|suggesting) .{3,40}(?:I'm|I am) (?:saying|asking|suggesting)",  # "I'm not saying X. I'm saying Y"
    r"(?:which|that) means either .{3,40} or ",  # "which means either X, or Y"
    r"[Tt]here'?s a (?:difference|distinction)\.",  # formula capper
    r"[Tt]hose are (?:different|not the same) things\.",  # formula capper
    r"[Nn]ot (?:just|merely|simply) .{3,40}, but ",  # "not just X, but Y"
    r"[Nn]ot (?:from|by|because of) .{3,40}, but (?:from|by|because)",  # "not from X, but from Y" in narration
]

# Show-don't-tell detectors: emotion TELLING patterns
TELLING_PATTERNS = [
    r"\b(?:he|she|they|I|we|[A-Z]\w+) (?:felt|was|seemed|looked|appeared) (?:angry|sad|happy|scared|nervous|excited|jealous|guilty|anxious|lonely|desperate|furious|terrified|elated|miserable|hopeful|confused|relieved|horrified|disgusted|ashamed|proud|bitter|defeated|triumphant)\b",
    r"\b(?:angrily|sadly|happily|nervously|excitedly|desperately|furiously|anxiously|guiltily|bitterly|wearily|miserably)\b",
]


def slop_score(text):
    """
    Mechanical slop detection. Returns a dict with:
      - tier1_hits: list of (word, count)
      - tier2_hits: list of (word, count)
      - tier3_hits: list of (pattern, count)
      - em_dash_density: em dashes per 1000 words
      - sentence_length_cv: coefficient of variation (higher = more human)
      - transition_opener_ratio: fraction of paragraphs starting with transitions
      - slop_penalty: 0-10 deduction (0 = clean, 10 = pure slop)
    """
    words = text.lower().split()
    word_count = len(words) or 1

    # Tier 1
    tier1_hits = []
    for w in TIER1_BANNED:
        c = sum(1 for token in words if token.strip(".,;:!?\"'()") == w)
        if c > 0:
            tier1_hits.append((w, c))

    # Tier 2 -- count per paragraph, flag clusters
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    tier2_hits = []
    tier2_cluster_count = 0
    for w in TIER2_SUSPICIOUS:
        c = sum(1 for token in words if token.strip(".,;:!?\"'()") == w)
        if c > 0:
            tier2_hits.append((w, c))
    for para in paragraphs:
        para_lower = para.lower()
        hits_in_para = sum(1 for w in TIER2_SUSPICIOUS if w in para_lower)
        if hits_in_para >= 3:
            tier2_cluster_count += 1

    # Tier 3
    tier3_hits = []
    for pattern in TIER3_FILLER:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            tier3_hits.append((pattern, len(matches)))

    # Em dash density
    em_dashes = text.count("—") + text.count("--")
    em_dash_density = (em_dashes / word_count) * 1000

    # Sentence length variation (coefficient of variation)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) > 2]
    if len(sentences) > 2:
        lengths = [len(s.split()) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_len = variance ** 0.5
        sentence_length_cv = std_len / mean_len if mean_len > 0 else 0
    else:
        sentence_length_cv = 0.5  # not enough data, assume OK

    # Transition opener ratio
    transition_starts = 0
    for para in paragraphs:
        first_word = para.split()[0].lower().strip(".,;:!?\"'()") if para.split() else ""
        if first_word in TRANSITION_OPENERS:
            transition_starts += 1
    transition_ratio = transition_starts / len(paragraphs) if paragraphs else 0

    # Fiction AI tells
    fiction_tells = []
    for pattern in FICTION_AI_TELLS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            fiction_tells.append((pattern[:40], len(matches)))
    fiction_tell_count = sum(c for _, c in fiction_tells)

    # Show-don't-tell violations
    telling_count = 0
    for pattern in TELLING_PATTERNS:
        telling_count += len(re.findall(pattern, text, re.IGNORECASE))

    # Structural AI tics (rhetorical formulas)
    structural_tics = []
    for pattern in STRUCTURAL_AI_TICS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            structural_tics.append((pattern[:40], len(matches)))
    structural_tic_count = sum(c for _, c in structural_tics)

    # Composite penalty (0 = clean, 10 = disaster)
    penalty = 0.0
    penalty += min(len(tier1_hits) * 1.5, 4.0)       # tier1: up to 4 pts
    penalty += min(tier2_cluster_count * 1.0, 2.0)    # tier2 clusters: up to 2 pts
    penalty += min(sum(c for _, c in tier3_hits) * 0.3, 2.0)  # tier3: up to 2 pts
    if em_dash_density > 15:
        penalty += min((em_dash_density - 15) * 0.3, 1.0)  # em dashes: up to 1 pt (threshold raised for voice)
    if sentence_length_cv < 0.3:
        penalty += 1.0  # uniform sentence length: 1 pt
    if transition_ratio > 0.3:
        penalty += min(transition_ratio * 2, 1.0)  # transition abuse: up to 1 pt
    penalty += min(fiction_tell_count * 0.3, 2.0)     # fiction AI tells: up to 2 pts
    penalty += min(telling_count * 0.2, 1.5)          # show-don't-tell: up to 1.5 pts
    penalty += min(structural_tic_count * 0.5, 2.0)   # structural AI tics: up to 2 pts

    penalty = min(penalty, 10.0)

    return {
        "tier1_hits": tier1_hits,
        "tier2_hits": tier2_hits,
        "tier2_clusters": tier2_cluster_count,
        "tier3_hits": tier3_hits,
        "fiction_ai_tells": fiction_tells,
        "structural_ai_tics": structural_tics,
        "telling_violations": telling_count,
        "em_dash_density": round(em_dash_density, 2),
        "sentence_length_cv": round(sentence_length_cv, 3),
        "transition_opener_ratio": round(transition_ratio, 3),
        "slop_penalty": round(penalty, 2),
    }


def load_file(path):
    """Load a text file, return empty string if missing."""
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def load_layer_files():
    """Load all planning layer files."""
    return {
        "voice": load_file(BASE_DIR / "voice.md"),
        "world": load_file(BASE_DIR / "world.md"),
        "characters": load_file(BASE_DIR / "characters.md"),
        "outline": load_file(BASE_DIR / "outline.md"),
        "canon": load_file(BASE_DIR / "canon.md"),
    }


def load_chapter(n):
    """Load a single chapter file."""
    return load_file(CHAPTERS_DIR / f"ch_{n:02d}.md")


def load_all_chapters():
    """Load all chapter files in order."""
    chapters = {}
    for f in sorted(glob.glob(str(CHAPTERS_DIR / "ch_*.md"))):
        num = int(re.search(r'ch_(\d+)', f).group(1))
        chapters[num] = Path(f).read_text()
    return chapters


def call_judge(prompt, max_tokens=2000):
    """Call the configured judge LLM and return its response text."""
    return call_text_model(
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        system=(
            "你是一位文学批评家和小说编辑。你以严谨的态度评估小说作品。 "
            "请务必以有效的 JSON 格式返回结果。不要包含 Markdown 围栏，不要有前导文字 —— 仅返回 JSON 对象。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=180,
        include_beta=True,
    )


def parse_json_response(text):
    """Extract JSON from a response that might have markdown fences or trailing text."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    # Find the outermost JSON object
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in response")
    # Walk forward to find the matching closing brace
    depth = 0
    in_string = False
    escape = False
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
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i+1], strict=False)
    # Fallback: try loading as-is, with strict=False to handle control chars
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        # Last resort: fix common issues (literal newlines in strings)
        fixed = re.sub(r'(?<!\\)\n', '\\n', text)
        return json.loads(fixed, strict=False)


# --- Foundation Evaluation ---

FOUNDATION_PROMPT = """评估这些奇幻小说策划文档。

评分基准（评分前请仔细阅读）：

  9-10: 即便投入一个月的专注编辑工作也无法再提升。
        达到已出版小说的水准。你能指名道姓地说出哪部已出版小说可以与其竞争。
        只有让你感到“惊喜”的作品才能给 10 分。
  7-8:  出色。资深作者只需这份文档即可动笔，无需即兴构思。
        虽有缺失但很轻微且可以罗列。
  5-6:  具备功能性但内容单薄。作者在动笔时需要即兴创作大量内容。
        存在重大缺失或平庸的选择。
  3-4:  草率。问题多于答案。动笔前需要大量补充。
  1-2:  占位符或存根。无法用于动笔撰写。
  0:    空白或缺失。

  8 分以上要求没有任何重大缺陷。9 分以上要求你几乎难以找到瑕疵。评分应趋于严苛。

强制要求：对于每一个维度，在评分前你必须确定：
  (a) 该领域中最大的缺陷（GAP）或弱点（WEAKNESS）
  (b) 能够提升得分的具体、可操作的改进方案（IMPROVEMENT）
  如果你找不到缺陷，请解释为什么你认为它不存在。

语气定义:
{voice}

世界设定集:
{world}

角色注册表:
{characters}

大纲:
{outline}

设定准则 (已确立的事实):
{canon}

交叉核对（评分前执行）：
1. 检查所有对话示例是否符合反 AI 废话（ANTI-SLOP）模式：
   - 检查不同角色之间是否重复使用结构化句式（如“不是 X，而是 Y” / “要么 X，要么 Y” / “这有区别”）。
   - 检查伪装成角色语气的 AI 修辞癖好。
   - 如果多个角色共享相同的句子结构，扣除角色辨识度分数。
2. 检查缺失的“负空间” —— 漏掉了什么？
   - 魔法系统中是否存在阻碍特定情节执行的漏洞？（例如：Cass 能听到书面文档中的谎言吗？高潮部分发生了什么 —— 哪条规则解决了它？）
   - 剧情所需的关键角色是否缺失？
   - 大纲要求的场景，世界观是否无法支撑？
3. 检查“便利性漏洞”与“刻意的悬念”：
   - 便利性漏洞：在需要细节的地方使用了“细节尚不明确”之类的描述。
   - 刻意悬念：作者知道答案，但对读者保留。如果策划文档规避了作者在撰写场景时必须回答的问题，那就是漏洞，而不是“冰山”。
4. 检查设定准则中的内部矛盾：
   - 交叉对比日期、年龄和时间线。
   - 检查角色能力是否符合魔法系统规则。
   - 寻找各文档之间事实上的冲突。

对以下维度进行评分（每个维度需包含缺陷+改进建议）：

设定与世界观 (LORE & WORLDBUILDING):
- 魔法系统 (magic_system): 遵循山德森第二定律，具有代价和局限性的硬规则。作者是否能仅利用已确立的规则解决高潮冲突？代价是否驱动了情节而非装饰？是否具体探索了至少 3 个社会影响？系统是否可测试 —— 你能否在不临时发明新规则的情况下撰写一场法庭戏、一场合同谈判或一场魔法对抗？
- 世界历史 (world_history): 创造当前紧张局势的事件时间线。每一个历史事件都应映射到当前的派系冲突或角色动机。装饰性的历史（酷但与情节无关）会扣分。
- 地理与文化 (geography_and_culture): 地点具有独特的感官特征。文化具有能产生冲突的具体习俗。经济体系产生阶级张力。核对：设定在两个不同地点的场景是否能因这里的内容而让人感到显著不同？
- 设定关联性 (lore_interconnection): 改变一个元素是否会迫使至少另外两个元素发生改变？测试：如果去掉魔法系统，政治结构会崩溃吗？阶级制度会改变吗？如果各元素是模块化/可分离的，给低分。
- 冰山深度 (iceberg_depth): 暗示深度 vs 明确深度。核对：作者是否真的知道悬念的答案，还是在敷衍？如果策划文档说“答案将被揭晓”却未指定答案是什么，那就是穿了冰山外衣的漏洞。

角色 (CHARACTER):
- 角色深度 (character_depth): 具有因果关联（而非仅仅是主题相关）的创伤/欲望/需求/谎言链条。谎言必须逻辑上源自创伤。欲望必须是应对谎言的错误方案。需求必须直接对立于欲望。检查每个链条的逻辑漏洞。同时检查：是否有任何可能需要链条的主要角色缺失了该链条？
- 角色辨识度 (character_distinctiveness): 去掉对话标签，仅凭句子结构能否辨认说话者？检查不同角色之间是否存在重复的结构化句式。检查隐喻领域是否重叠。检查说话方式是否反映了角色背景（14 岁的孩子说话不应像 60 岁的商人）。
- 角色秘密 (character_secrets): 每个主要角色的秘密都应该是那种一旦揭露就会改变剧情走向的事情。模糊的秘密（“他知道的比表现出来的多”）得分低于具体的秘密（“他知道谐波意味着 X，这将导致 Y 失效”）。

结构 (STRUCTURE):
- 大纲完整性 (outline_completeness): 章节包含节拍、POV、情感弧光、尝试-失败循环类型。《救猫咪》节拍处于正确的百分比标记。如果为空得 0 分，只有存在幕后结构才给 5 分以上。
- 伏笔平衡 (foreshadowing_balance): 每一个植入的线索都有规划好的回收。如果台账为空得 0 分，无论其他文档中是否暗示了线索 —— 伏笔必须被跟踪记录才算数。

创作素养 (CRAFT):
- 内部一致性 (internal_consistency): 积极寻找矛盾。交叉核对日期、年龄、人数、命名地点。标记任何文档不一致的情况。一个重大矛盾最高给 6 分，三个及以上最高给 4 分。
- 语气清晰度 (voice_clarity): 语气定义必须具体且具有可操作性。示例段落必须能体现该语气。反面示例必须划定界限。检查对话示例是否存在 AI 废话模式。如果语气文档本身优美但在示例中包含 AI 废话，会削弱说服力 —— 扣分。
- 准则覆盖度 (canon_coverage): 事实已被记录、来源明确且足以捕捉矛盾。核对：如果作者在第 5 章引入了一个新事实，他们能通过设定准则验证它吗？准则是否足够细致？是否存在其他文档中已知但未进入准则的事实？

请以 JSON 格式响应：
{{
  "magic_system": {{"score": N, "gap": "最大弱点", "fix": "具体改进措施", "note": "..."}},
  "world_history": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "geography_and_culture": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "lore_interconnection": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "iceberg_depth": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "character_depth": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "character_distinctiveness": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "character_secrets": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "outline_completeness": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "foreshadowing_balance": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "internal_consistency": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "voice_clarity": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "canon_coverage": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "slop_in_planning_docs": {{"found": ["列出在对话示例、语气示例或角色描述中发现的任何 AI 废话模式"], "note": "..."}},
  "contradictions_found": ["列出文档之间的任何事实矛盾"],
  "overall_score": N,
  "lore_score": N,
  "weakest_dimension": "...",
  "top_3_improvements": ["按优先级排列的 3 个最高杠杆改进方案"]
}}

权重：设定/世界观 40%，角色 30%，结构 20%，创作素养 10%。
世界观单薄但大纲完整的小说，评价要低于世界观深厚但大纲不完整的小说。

最终核对：如果你的总分高于 7 分，请重新阅读你的缺陷列表。如果任何缺陷描述的问题会迫使作者在动笔时停下来临时发明内容，那么你的评分就太高了。请下调分数。
"""


def evaluate_foundation():
    layers = load_layer_files()
    prompt = FOUNDATION_PROMPT.format(**layers)
    raw = call_judge(prompt, max_tokens=16000)
    return parse_json_response(raw)


# --- Chapter Evaluation ---

CHAPTER_PROMPT = """根据策划文档评估此奇幻小说章节。

评分基准：
  9-10: 达到已出版奇幻小说中的顶级水平。评分 9+ 必须能指名道姓地说出哪一个已出版章节可以与其竞争。
  7-8:  优秀，经编辑润色后即可出版。存在具体瑕疵但不会破坏阅读体验。
  5-6:  具备功能性但平淡。一个合格的初稿，但需要大量修订。平庸，缺乏惊喜。
  3-4:  存在重大问题。语气脱节、遗漏节拍、文字平庸。
  1-2:  无法使用。从头重写。

  合格的 AI 生成章节的中位得分应为 6 分。
  7 分意味着它做出了一些通用 AI 初稿做不到的事情。
  8 分意味着人类编辑只需微调即可保留。
  大多数维度得分应在 6-7 分。8 分以上留给真正的卓越。

强制要求：对于每一个维度，你必须确定：
  (a) 该维度中最薄弱的时刻 —— 引用具体的句子或段落
  (b) 改进方案 —— 一个具体的修订建议，而不是模糊的评价
  如果你觉得每一句话都完美，那说明你读得不够仔细。

语气定义:
{voice}

世界设定集 (摘要):
{world}

角色注册表:
{characters}

设定准则 (已确立的硬事实 —— 违反即为 Bug):
{canon}

本章大纲条目:
{chapter_outline}

前一章 (最后 1500 字):
{prev_chapter_tail}

待评估章节:
{chapter_text}

交叉核对（评分前执行）：
1. 引用测试：找出 3 个最强的句子和 3 个最弱的句子。如果你找不出 3 个弱句，请降低你的标准 —— 每一个章节都有弱项。寻找：可以更具体却使用了通用描述的地方、段落中的韵律单调、隐喻不符合角色经历、情感表达“直接陈述”而非“间接展现”、过渡部分“直接总结”而非“戏剧化表现”。
2. 对话真实性：在脑中大声朗读所有对话。它听起来像说话还是像书面散文？角色说的话是否符合 14 岁/60 岁等身份？
3. 场景 vs 总结：本章有多少内容是即时场景（伴随对话和动作），有多少是总结（叙述者压缩时间）？总结过多的章节无论文笔多好，吸引力得分都会较低。
4. AI 模式检查：寻找这些常见的 AI 写作模式：
   - 每个段落长度相同
   - 观察结果总是以三元组形式出现 (X, Y, Z)
   - 情感节拍准时到达而非给人惊喜
   - 角色从不说错话或各说各话
   - 描写像在罗列清单（列出 5 个感官细节，而 2 个具体的会更鲜明）
   - 内心独白在解释场景已经展现的内容
5. 赢得 vs 赋予：紧张感是通过场景描写“赢得”的，还是通过叙述者的断言直接“赋予”给读者的？悬念是通过真正的保留来维持的，还是由于角色刻意不去想他们本该想到的事情？

对以下维度进行评分：

- 语气遵循度 (voice_adherence): 文字是否符合 voice.md 第二部分？核对：句式节奏变化、词汇量运用、身体感受先于情感原则、描述的特定基调。引用最强和最弱的语气瞬间。是否有任何段落听起来像可以出现在任何小说里的通用奇幻散文？如果是，最高给 7 分。
- 节拍覆盖度 (beat_coverage): 是否完成了大纲中的每一个节拍？节拍是戏剧化展现了还是仅仅被提及？在句子中总结而非在场景中生活的节拍只能算完成了一半。分数反映节拍执行的质量，而不只是存在感。
- 角色语气 (character_voice): 在脑中去掉对话标签。你能分辨出是谁在说话吗？角色听起来是否相似？对话读起来像说话还是像书面散文？Cass 听起来像一个特定的 14 岁少年，还是像通用的“年轻主角”？是否有人说了令人惊讶的话 —— 不仅仅是正确的话，而是“真实”的话？从不磕绊、犹豫或说错话的角色是 AI 模式角色。
- 伏笔植入 (plants_seeded): 伏笔元素是否放置得自然？显眼的伏笔比隐形的伏笔更差。根据整合的质量评分，而不只是是否存在。
- 文笔质量 (prose_quality): 句式多样性（核对：是否有 3 条以上连续的句子开头相同？）。具体性（具体名词 > 抽象名词）。隐喻来自角色经历而非词典。情感高峰处的“展现而非陈述”。引用最弱的句子并解释原因。同时核对：重复短语、过度依赖的句式、可以删掉而不造成损失的段落。
- 连贯性 (continuity): 逻辑上是否衔接前一章？包括情感连贯性和情节连贯性。角色的心态是否衔接？
- 准则合规性 (canon_compliance): 对照设定准则检查所有事实。罗列违规项。一个重大违规最高给 6 分。核对：角色名、地点、魔法系统规则、时间线、已发生的事件、身体描写。
- 设定整合度 (lore_integration): 这个世界在本章中是否有实质作用，还是仅仅作为布景？一个通过查找替换专有名词就能发生在任何奇幻城市的场景最高给 5 分。
- 吸引力 (engagement): 读者会翻页吗？张力来自哪里 —— 情节、角色、悬念还是文笔？是否有令人惊喜的瞬间？可预测的优秀依然是可预测的。只有在章节做了意料之外的事情时才给 8 分以上。

请以 JSON 格式响应：
{{
  "voice_adherence": {{"score": N, "weakest_moment": "引用具体的弱势段落", "fix": "如何改进", "note": "..."}},
  "beat_coverage": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "character_voice": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "plants_seeded": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "prose_quality": {{"score": N, "weakest_sentence": "引用该句", "fix": "修订建议", "strongest_sentence": "引用该句", "note": "..."}},
  "continuity": {{"score": N, "note": "..."}},
  "canon_compliance": {{"score": N, "violations": ["列出发现的违规项"], "note": "..."}},
  "lore_integration": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "engagement": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "three_weakest_sentences": ["引用 1", "引用 2", "引用 3"],
  "three_strongest_sentences": ["引用 1", "引用 2", "引用 3"],
  "ai_patterns_detected": ["列出发现的 AI 写作模式"],
  "overall_score": N,
  "weakest_dimension": "...",
  "top_3_revisions": ["具体、可操作的修订建议 1", "建议 2", "建议 3"],
  "new_canon_entries": ["本章确立的任何新事实"]
}}

最终核对：如果你的总分高于 7 分，请重新阅读你的最弱时刻引用。如果其中任何一个描述了编辑会标记的问题，那么你的分数就太高了。中位 AI 章节是 6 分，8 分是杰出的，9 分罕见，初稿不存在 10 分。
"""


def evaluate_chapter(chapter_num):
    layers = load_layer_files()
    chapter_text = load_chapter(chapter_num)
    if not chapter_text.strip():
        return {"error": f"Chapter {chapter_num} is empty or missing",
                "overall_score": 0.0}

    # Extract this chapter's outline entry (rough heuristic)
    outline = layers["outline"]
    ch_pattern = rf'###\s*Ch\s*{chapter_num}\b.*?(?=###\s*Ch\s*\d|## Act|## Foreshadowing|$)'
    ch_match = re.search(ch_pattern, outline, re.DOTALL)
    chapter_outline = ch_match.group(0) if ch_match else "(outline entry not found)"

    # Load previous chapter tail
    prev_text = load_chapter(chapter_num - 1) if chapter_num > 1 else "(first chapter)"
    prev_tail = prev_text[-3000:] if len(prev_text) > 3000 else prev_text

    prompt = CHAPTER_PROMPT.format(
        voice=layers["voice"],
        world=layers["world"][:4000],  # truncate world bible
        characters=layers["characters"],
        canon=layers["canon"],
        chapter_outline=chapter_outline,
        prev_chapter_tail=prev_tail,
        chapter_text=chapter_text,
    )
    raw = call_judge(prompt, max_tokens=8000)
    result = parse_json_response(raw)

    # Mechanical slop check -- adjusts score independently of judge
    slop = slop_score(chapter_text)
    result["slop"] = slop
    if "overall_score" in result:
        adjusted = max(0, result["overall_score"] - slop["slop_penalty"])
        result["raw_judge_score"] = result["overall_score"]
        result["overall_score"] = round(adjusted, 2)

    return result


# --- Full Novel Evaluation ---

FULL_NOVEL_PROMPT = """从整体上全面评估这部奇幻小说。
你拥有策划文档以及每一章的摘要及其个人评分。

语气定义:
{voice}

世界设定集摘要:
{world_summary}

角色注册表:
{characters}

大纲与伏笔台账:
{outline}

各章摘要与得分:
{chapter_summaries}

对以下小说层面的维度进行 0-10 分的评分：
- 弧光完成度 (arc_completion): 角色弧光的解决是否令人满意？
- 节奏曲线 (pacing_curve): 张力是否在整本书中合理构建？
- 主题连贯性 (theme_coherence): 主题探讨是否始终如一？
- 伏笔回收 (foreshadowing_resolution): 所有植入的线索是否都得到了回收？
- 世界观一致性 (world_consistency): 各章节之间是否存在设定矛盾？
- 语气一致性 (voice_consistency): 语气是否贯穿始终？
- 整体吸引力 (overall_engagement): 这部小说从头到尾是否引人入胜？

请以 JSON 格式响应：
{{
  "arc_completion": {{"score": N, "note": "..."}},
  "pacing_curve": {{"score": N, "note": "..."}},
  "theme_coherence": {{"score": N, "note": "..."}},
  "foreshadowing_resolution": {{"score": N, "note": "..."}},
  "world_consistency": {{"score": N, "note": "..."}},
  "voice_consistency": {{"score": N, "note": "..."}},
  "overall_engagement": {{"score": N, "note": "..."}},
  "novel_score": N,
  "weakest_dimension": "...",
  "weakest_chapter": N,
  "top_suggestion": "..."
}}
"""


def evaluate_full():
    layers = load_layer_files()
    chapters = load_all_chapters()

    if not chapters:
        return {"error": "No chapters found", "novel_score": 0.0}

    # Build chapter summaries (first/last 500 chars of each)
    summaries = []
    for num in sorted(chapters.keys()):
        text = chapters[num]
        word_count = len(text.split())
        head = text[:500]
        tail = text[-500:] if len(text) > 500 else ""
        summaries.append(
            f"Chapter {num} ({word_count} words):\n"
            f"  Opening: {head}...\n"
            f"  Closing: ...{tail}\n"
        )

    prompt = FULL_NOVEL_PROMPT.format(
        voice=layers["voice"],
        world_summary=layers["world"][:3000],
        characters=layers["characters"],
        outline=layers["outline"],
        chapter_summaries="\n".join(summaries),
    )
    raw = call_judge(prompt)
    return parse_json_response(raw)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Evaluate the novel")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--phase", choices=["foundation"],
                       help="Evaluate planning documents")
    group.add_argument("--chapter", type=int,
                       help="Evaluate a specific chapter number")
    group.add_argument("--full", action="store_true",
                       help="Evaluate the entire novel")
    args = parser.parse_args()

    if args.phase == "foundation":
        result = evaluate_foundation()
        score_key = "overall_score"
    elif args.chapter is not None:
        result = evaluate_chapter(args.chapter)
        score_key = "overall_score"
    elif args.full:
        result = evaluate_full()
        score_key = "novel_score"

    # Print structured output
    print("---")
    if score_key in result:
        print(f"{score_key}: {result[score_key]}")
    for key, val in result.items():
        if key == score_key:
            continue
        if isinstance(val, dict):
            print(f"{key}: {val.get('score', 'N/A')} -- {val.get('note', '')}")
        else:
            print(f"{key}: {val}")

    # Save full eval log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = args.phase or (f"ch{args.chapter:02d}" if args.chapter else "full")
    log_path = EVAL_LOG_DIR / f"{timestamp}_{mode}.json"
    with open(log_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\neval_log: {log_path}")


if __name__ == "__main__":
    main()
