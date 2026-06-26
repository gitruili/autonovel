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
from outline_utils import extract_chapter_outline, load_volume_outline_for_chapter
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project, load_genre_craft

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


# ---- 机械化 AI 废话检测（不需要 LLM） ----

# 第一梯队：见到就杀的中文 AI 高频词
TIER1_BANNED = [
    "不禁", "映入眼帘", "心中一动", "不由自主", "若有所思",
    "心下了然", "暗自思忖", "缓缓开口", "一股暖流涌上心头",
    "美眸", "玉手", "樱唇", "宛如仙子", "谪仙",
    "目光如炬", "眸光一闪",
]

# 第二梯队：扎堆可疑的叠词（单独出现没问题，一段 3 个以上 = 扣分）
TIER2_SUSPICIOUS = [
    "暗暗", "默默", "悄悄", "淡淡", "微微", "隐隐",
    "丝丝", "幽幽", "轻轻", "款款", "盈盈", "楚楚",
    "脉脉", "袅袅",
]

# 第三梯队：废话句式（删掉后原文一定更好）
TIER3_FILLER = [
    r"她心想",
    r"她不知道的是",
    r"时间仿佛.{0,6}凝固",
    r"她从未想过自己会",
    r"一切都在朝着好的方向发展",
    r"这一刻.*终于明白",
    r"生活.*不就是这样吗",
    r"他就这样静静地看着",
    r"仿佛回到了.*的时光",
    r"说不出的感觉涌上心头",
]

# 中文转折词成瘾：连续几段用同一个转折词开头
TRANSITION_OPENERS = [
    "然而", "不过", "此外", "与此同时",
    "紧接着", "随后", "就在这时", "说来也巧",
]

# 中文网文特有的 AI 废话（散文中见到就杀）
FICTION_AI_TELLS = [
    r"一抹微笑浮上嘴角",
    r"心中涌起一股暖流",
    r"不禁对[她他]刮目相看",
    r"眼中闪过一丝精光",
    r"仿佛被施了定身咒",
    r"美眸流转",
    r"玉手纤纤",
    r"樱唇微启",
    r"顿时觉得不虚此行",
    r"周围的人都投来了.*的目光",
    r"从未见过如此.*的女子",
    r"柔声道",
    r"淡淡地说",
    r"宛如.*仙[子女]",
    r"一道倩影",
    r"心头一[颤震]",
    r"不由得.*一[呆愣怔]",
]

# 结构性 AI 写作模式
STRUCTURAL_AI_TICS = [
    r"不是.*而是",  # "不是X，而是Y" 反复使用
    r"要么.*要么",  # "要么X，要么Y" 反复使用
    r"一方面.*另一方面",  # 八股对称结构
    r"她知道.*但她更知道",  # AI 式内心独白
    r"不仅仅是.*更是",  # "不仅X，更是Y"
]

# 展示不讲述：直接告诉读者情绪的模式
TELLING_PATTERNS = [
    r"[她他]感到[了一]?[阵股丝].{0,4}(高兴|愤怒|悲伤|害怕|紧张|兴奋|嫉妒|内疚|焦虑|孤独|绝望|愧疚|骄傲|苦涩|委屈|心酸|欣慰|感动|震惊|失落)",
    r"[她他]的心[里中]充满了",
    r"[她他]觉得[很十分非常].*[高兴开心难过伤心]",
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

    # For Chinese text, use character count for density calculations
    # (Chinese doesn't use spaces between words, so split() gives misleading count)
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    if chinese_chars > word_count * 2:
        # Predominantly Chinese text
        density_base = chinese_chars or 1
    else:
        density_base = word_count

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
    # Chinese text uses "——" as standard punctuation; count each "——" as one unit
    # text.count("—") double-counts "——" (each contains two "—"), so subtract overlap
    em_dashes = text.count("—") + text.count("--") - text.count("——")
    em_dash_density = (em_dashes / density_base) * 1000

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
        return Path(path).read_text(encoding="utf-8")
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
    """Load a single chapter file. Tries volume subdirectory first, then flat."""
    # Try volume subdirectory format: chapters/v001/ch_0001.md
    vol = (n - 1) // 20 + 1
    vol_path = CHAPTERS_DIR / f"v{vol:03d}" / f"ch_{n:04d}.md"
    if vol_path.exists():
        return vol_path.read_text(encoding="utf-8")
    # Fallback to flat format: chapters/ch_01.md
    return load_file(CHAPTERS_DIR / f"ch_{n:02d}.md")


def load_all_chapters():
    """Load all chapter files in order."""
    chapters = {}
    for f in sorted(glob.glob(str(CHAPTERS_DIR / "ch_*.md"))):
        num = int(re.search(r'ch_(\d+)', f).group(1))
        chapters[num] = Path(f).read_text(encoding="utf-8")
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
                extracted = text[start:i+1]
                try:
                    return json.loads(extracted, strict=False)
                except json.JSONDecodeError as e:
                    # Last resort: fix common issues (literal newlines, trailing commas, unescaped internal quotes)
                    fixed = re.sub(r'(?<!\\)\n', '\\n', extracted)
                    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
                    fixed = re.sub(r'(?<!\\)(?<=[^:\[{,\s])"(?=[^:\]},\s])', r'\\"', fixed)
                    try:
                        return json.loads(fixed, strict=False)
                    except json.JSONDecodeError:
                        Path("failed_eval.json").write_text(extracted, encoding="utf-8")
                        raise ValueError(f"Failed to parse JSON (saved to failed_eval.json): {e}")

    # Fallback: try loading as-is, with strict=False to handle control chars
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError as e:
        fixed = re.sub(r'(?<!\\)\n', '\\n', text)
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
        fixed = re.sub(r'(?<!\\)(?<=[^:\[{,\s])"(?=[^:\]},\s])', r'\\"', fixed)
        try:
            return json.loads(fixed, strict=False)
        except json.JSONDecodeError:
            Path("failed_eval.json").write_text(text, encoding="utf-8")
            raise ValueError(f"Failed to parse JSON (saved to failed_eval.json): {e}")


# --- Genre-aware evaluation prompt builders ---

def _get_genre():
    """Load genre config for the current project."""
    return load_genre_for_project()


def _build_foundation_dims_text(genre) -> str:
    """Build the evaluation dimensions section for foundation prompt from genre config."""
    eval_cfg = genre.get_evaluation_config("foundation")
    if not eval_cfg:
        return ""

    dims = eval_cfg.get("dimensions", {})
    if not dims:
        return ""

    groups = {}
    for key, dim in dims.items():
        group = dim.get("weight_group", "other")
        if group not in groups:
            groups[group] = []
        groups[group].append((key, dim))

    group_labels = {
        "setting": "设定与世界观 (SETTING)",
        "character": "角色 (CHARACTER)",
        "structure": "结构 (STRUCTURE)",
        "craft": "创作素养 (CRAFT)",
    }

    lines = []
    for group_key in ["setting", "character", "structure", "craft"]:
        if group_key not in groups:
            continue
        label = group_labels.get(group_key, group_key.upper())
        lines.append(f"{label}:")
        for key, dim in groups[group_key]:
            lines.append(f"- {dim.get('label', key)} ({key}): {dim.get('description', '')}")
        lines.append("")

    return "\n".join(lines)


def _build_foundation_cross_checks(genre) -> str:
    """Build cross-checks section from genre config."""
    eval_cfg = genre.get_evaluation_config("foundation")
    if not eval_cfg:
        return ""
    checks = eval_cfg.get("cross_checks", [])
    if not checks:
        return ""
    return "\n".join(f"{i+1}. {c}" for i, c in enumerate(checks))


def _build_foundation_json_keys(genre) -> str:
    """Build the JSON response keys for foundation evaluation from genre config."""
    eval_cfg = genre.get_evaluation_config("foundation")
    if not eval_cfg:
        return ""

    dims = eval_cfg.get("dimensions", {})
    if not dims:
        return ""

    lines = []
    for key in dims:
        lines.append(f'  "{key}": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},')
    return "\n".join(lines)


def _build_foundation_weights_text(genre) -> str:
    """Build the weights explanation text from genre config."""
    eval_cfg = genre.get_evaluation_config("foundation")
    if not eval_cfg:
        return "权重：设定/世界观 35%，角色 25%，结构 30%，创作素养 10%。"

    weights = eval_cfg.get("weights", {})
    if not weights:
        return "权重：设定/世界观 35%，角色 25%，结构 30%，创作素养 10%。"

    weight_labels = {
        "setting": "设定/世界观",
        "character": "角色",
        "structure": "结构",
        "craft": "创作素养",
    }
    parts = []
    for key in ["setting", "character", "structure", "craft"]:
        if key in weights:
            pct = int(weights[key] * 100)
            parts.append(f"{weight_labels.get(key, key)} {pct}%")
    return f"权重：{'，'.join(parts)}。"


def _build_lf_dims_text(genre) -> str:
    """Build evaluation dimensions for long-form foundation prompt."""
    eval_cfg = genre.get_evaluation_config("foundation")
    dims = eval_cfg.get("dimensions", {}) if eval_cfg else {}

    groups = {}
    for key, dim in dims.items():
        group = dim.get("weight_group", "other")
        if group not in groups:
            groups[group] = []
        groups[group].append((key, dim))

    group_labels = {
        "setting": "设定与世界观 (SETTING) — 30%",
        "character": "角色 (CHARACTER) — 30%",
        "structure": "结构 (STRUCTURE) — 30%",
        "craft": "创作素养 (CRAFT) — 10%",
    }

    # 硬编码兜底维度：仅在 genre config 未覆盖对应 group 时启用
    # 这样既支持 genre config 自定义，也保证默认题材有合理评估维度
    _fallback_character = [
        ("villain_rotation", "反派轮换设计", "【依据 master_plan.antagonist_rotation】: 反派梯队是否分层？退场-引入节奏是否合理？每个反派是否有独特动机？"),
    ]
    _fallback_structure = [
        ("volume_structure", "分卷结构", "【依据 master_plan.volumes】: 每卷是否有独立的核心冲突、高潮、和阶段性胜利？卷间是否有递进关系？"),
        ("upgrade_progression", "升级台阶", "【依据 master_plan.economy_milestones + world.md】: 升级台阶是否清晰、可见、有代价？"),
        ("payoff_setup", "爽点铺垫", "【依据 outline 第一卷】: 每个打脸/爽点是否有至少1-2章的铺垫？爽点密度是否合理？"),
        ("foreshadowing_balance", "伏笔平衡", "【依据 master_plan.long_foreshadows + outline】: 伏笔台账是否存在？长线/短线伏笔是否平衡？"),
        ("expansion_roadmap", "扩展路线图", "【依据 master_plan】: 世界观是否预留了足够的扩展空间？"),
    ]

    lines = []
    for group_key in ["setting", "character", "structure", "craft"]:
        label = group_labels.get(group_key, group_key.upper())
        
        # 收集此 group 的维度
        group_dims = list(groups.get(group_key, []))

        # 如果 genre config 未覆盖，使用硬编码兜底
        if not group_dims and group_key == "character":
            group_dims = [(key, {"label": lbl, "description": desc}) for key, lbl, desc in _fallback_character]
        if not group_dims and group_key == "structure":
            group_dims = [(key, {"label": lbl, "description": desc}) for key, lbl, desc in _fallback_structure]
        if not group_dims and group_key == "setting":
            # Setting 必须有 genre config 提供，不兜底
            pass
        
        if not group_dims:
            continue
            
        lines.append(f"{label}:")
        for key, dim in group_dims:
            if isinstance(dim, dict):
                lines.append(f"- {dim.get('label', key)} ({key}): {dim.get('description', '')}")
            else:
                lines.append(f"- {key}: {dim}")
        lines.append("")

    return "\n".join(lines)


def _build_lf_json_keys(genre) -> str:
    """Build JSON response keys for long-form foundation evaluation."""
    eval_cfg = genre.get_evaluation_config("foundation")
    dims = eval_cfg.get("dimensions", {}) if eval_cfg else {}

    # Fallback keys if genre config doesn't provide character/structure dimensions
    _fallback_keys = [
        "villain_rotation", "volume_structure", "upgrade_progression",
        "payoff_setup", "foreshadowing_balance", "expansion_roadmap",
    ]

    # Start with genre config keys
    keys_set = set(dims.keys()) if dims else set()
    
    # Add fallback keys for any group that has no genre config coverage
    has_character = any(dims.get(k, {}).get("weight_group") == "character" for k in dims) if dims else False
    has_structure = any(dims.get(k, {}).get("weight_group") == "structure" for k in dims) if dims else False
    if not has_character or not has_structure:
        keys_set.update(_fallback_keys)

    lines = []
    for key in sorted(keys_set):  # sort for consistency
        lines.append(f'  "{key}": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},')
    return "\n".join(lines)


def _build_chapter_dims_text(genre) -> str:
    """Build genre-specific evaluation dimensions for chapter evaluation."""
    eval_cfg = genre.get_evaluation_config("chapter")
    if not eval_cfg:
        return ""

    dims = eval_cfg.get("dimensions", {})
    if not dims:
        return ""

    lines = []
    for key, dim in dims.items():
        lines.append(f"- {dim.get('label', key)} ({key}): {dim.get('description', '')}")
    return "\n".join(lines)


# --- Foundation Evaluation ---

def _build_foundation_prompt(genre) -> str:
    """Build the foundation evaluation prompt dynamically from genre config."""
    genre_name = genre.display_name
    dims_text = _build_foundation_dims_text(genre)
    cross_checks = _build_foundation_cross_checks(genre)
    json_keys = _build_foundation_json_keys(genre)
    weights_text = _build_foundation_weights_text(genre)

    return f"""评估这些女频{genre_name}网文的策划文档。

评分基准（评分前请仔细阅读）：

  9-10: 即便投入一个月的专注编辑工作也无法再提升。
        达到已出版小说的水准。你能指名道姓地说出哪部已出版小说可以与其竞争。
        只有让你感到"惊喜"的作品才能给 10 分。
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
{{voice}}

世界设定集:
{{world}}

角色注册表:
{{characters}}

大纲:
{{outline}}

设定准则 (已确立的事实):
{{canon}}

交叉核对（评分前执行）：
{cross_checks}

对以下维度进行评分（每个维度需包含缺陷+改进建议）：

{dims_text}
请以 JSON 格式响应：
{{
{json_keys}
  "slop_in_planning_docs": {{"found": ["列出发现的AI废话模式"], "note": "..."}},
  "contradictions_found": ["列出文档之间的事实矛盾"],
  "overall_score": N,
  "lore_score": N,
  "weakest_dimension": "...",
  "top_3_improvements": ["按优先级排列的 3 个最高杠杆改进方案"]
}}

{weights_text}{genre_name}文的结构权重高于奇幻文，因为升级台阶和打脸铺垫是读者追更的核心动力。

最终核对：如果你的总分高于 7 分，请重新阅读你的缺陷列表。如果任何缺陷会迫使作者动笔时临时发明内容，评分就太高了。
"""


def evaluate_foundation():
    """Evaluate foundation phase documents (WORLD.MD, CHARACTERS.MD, OUTLINE)."""
    # If there is a manually fixed failed_eval.json, use it to save time
    failed_eval = Path("failed_eval.json")
    if failed_eval.exists():
        try:
            text = failed_eval.read_text(encoding="utf-8")
            data = parse_json_response(text)
            failed_eval.unlink()
            return data
        except Exception:
            pass

    print("Gathering foundation documents...")
    layers = load_layer_files()
    genre = _get_genre()
    prompt = _build_foundation_prompt(genre).format(**layers)
    raw = call_judge(prompt, max_tokens=16000)
    return parse_json_response(raw)


# --- Long-Form Foundation Evaluation ---

def _build_foundation_lf_prompt(genre) -> str:
    """Build the long-form foundation evaluation prompt dynamically from genre config."""
    genre_name = genre.display_name
    dims_text = _build_lf_dims_text(genre)
    json_keys = _build_lf_json_keys(genre)
    weights_text = _build_foundation_weights_text(genre)

    return f"""评估这部长篇女频{genre_name}网文（100万字+）的策划文档。

评分基准（评分前请仔细阅读）：

  9-10: 即便投入一个月的专注编辑工作也无法再提升。
        达到已出版小说的水准。你能指名道姓地说出哪部已出版小说可以与其竞争。
        只有让你感到"惊喜"的作品才能给 10 分。
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
{{__VOICE__}}

世界设定集:
{{__WORLD__}}

角色注册表:
{{__CHARACTERS__}}

全书总纲 (YAML 格式，含全书所有卷的规划、反派轮换、感情线阶段、经济里程碑、超长线伏笔):
{{__MASTER_PLAN__}}

第一卷详细大纲 (章节级，仅覆盖第一卷约20章):
{{__OUTLINE__}}

设定准则 (已确立的事实):
{{__CANON__}}

注意：全书总纲（master_plan）包含全书所有卷的宏观规划，是评估分卷结构、反派轮换、扩展路线图的主要依据。
第一卷大纲（outline）仅包含第一卷的章节级细节，是评估章节级爽点铺垫、伏笔平衡的依据。
如果全书总纲缺失或为空，则 volume_structure、villain_rotation、expansion_roadmap 三个维度应直接给 0 分并注明"总纲缺失"。

交叉核对（评分前执行）：
1. 经济数据交叉验证：股权比例、交易金额、资产规模、收入量级是否自洽？升级速度是否合理？
2. 角色对话检查：不同角色是否共享相同句式？去掉标签能分辨谁在说话吗？
3. 主角设定完整性检查：是否覆盖了身高/声线/衣品/行事风格/家庭关系等关键维度？是否有遗漏？
4. 配角锚定检查：每个配角是否都有明确的"对主角意味着什么"的答案？是否有悬浮的、与主角无关的角色？
5. 金手指规则检查：局限性、冷却期是否明确？是否有规避不写的漏洞？
6. 文档间矛盾检查：交叉对比年龄、地点、资产、关系、时间线。

对以下维度进行评分（每个维度需包含缺陷+改进建议）：

{dims_text}
请以 JSON 格式响应：
{{
{json_keys}
  "slop_in_planning_docs": {{"found": ["列出发现的AI废话模式"], "note": "..."}},
  "contradictions_found": ["列出文档之间的事实矛盾"],
  "overall_score": N,
  "lore_score": N,
  "weakest_dimension": "...",
  "top_3_improvements": ["按优先级排列的 3 个最高杠杆改进方案"]
}}

{weights_text}设定、角色、结构三足鼎立——缺任何一条腿都撑不起百万字长篇。

最终核对：如果你的总分高于 7 分，请重新阅读你的缺陷列表。如果任何缺陷会迫使作者动笔时临时发明内容，评分就太高了。
"""


def load_layer_files_lf():
    """Load long-form foundation layer files."""
    story_dir = BASE_DIR / "story"
    plans_dir = story_dir / "plans"
    layers = {
        "voice": load_file(BASE_DIR / "voice.md"),
        "world": load_file(BASE_DIR / "world.md"),
        "characters": load_file(BASE_DIR / "characters.md"),
        "outline": load_file(BASE_DIR / "outline.md"),
        "canon": load_file(BASE_DIR / "canon.md"),
        "master_plan": load_file(plans_dir / "master_plan.yaml"),
    }
    # Fallback: if master_plan.yaml missing, try reading from outline.md header
    if not layers["master_plan"]:
        layers["master_plan"] = "(master_plan.yaml not found)"
    return layers


def evaluate_foundation_lf():
    """Evaluate long-form foundation phase documents."""
    failed_eval = Path("failed_eval.json")
    if failed_eval.exists():
        try:
            text = failed_eval.read_text(encoding="utf-8")
            data = parse_json_response(text)
            failed_eval.unlink()
            return data
        except Exception:
            pass

    print("Gathering long-form foundation documents...")
    layers = load_layer_files_lf()
    genre = _get_genre()
    prompt = _build_foundation_lf_prompt(genre)
    for key, value in layers.items():
        prompt = prompt.replace(f"{{__{key.upper()}__}}", value)
    raw = call_judge(prompt, max_tokens=16000)
    return parse_json_response(raw)


# --- Chapter Evaluation ---

def _build_chapter_prompt(genre) -> str:
    """Build the chapter evaluation prompt dynamically from genre config."""
    genre_name = genre.display_name
    genre_dims = _build_chapter_dims_text(genre)
    lore_desc = ""
    eval_cfg = genre.get_evaluation_config("chapter")
    if eval_cfg:
        dims = eval_cfg.get("dimensions", {})
        if "era_integration" in dims:
            lore_desc = dims["era_integration"].get("description", "")
        elif "lore_integration" in dims:
            lore_desc = dims["lore_integration"].get("description", "")
    if not lore_desc:
        lore_desc = f"{genre_name}相关细节在本章中是否有实质作用？"

    return f"""根据策划文档评估此女频{genre_name}网文章节。

评分基准：
  9-10: 达到已出版优质{genre_name}网文的顶级水平。
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
{{__VOICE__}}

世界设定集 (摘要):
{{__WORLD__}}

角色注册表:
{{__CHARACTERS__}}

设定准则 (已确立的硬事实 —— 违反即为 Bug):
{{__CANON__}}

本章大纲条目:
{{__CHAPTER_OUTLINE__}}

前一章 (最后 1500 字):
{{__PREV_CHAPTER_TAIL__}}

待评估章节:
{{__CHAPTER_TEXT__}}

交叉核对（评分前执行）：
1. 引用测试：找出 3 个最强的句子和 3 个最弱的句子。如果你找不出 3 个弱句，请降低你的标准 —— 每一个章节都有弱项。寻找：可以更具体却使用了通用描述的地方、段落中的韵律单调、隐喻不符合角色经历、情感表达"直接陈述"而非"间接展现"、过渡部分"直接总结"而非"戏剧化表现"。
2. 对话真实性：在脑中大声朗读所有对话。它听起来像说话还是像书面散文？角色说的话是否符合 14 岁/60 岁等身份？
3. 场景 vs 总结：本章有多少内容是即时场景（伴随对话和动作），有多少是总结（叙述者压缩时间）？总结过多的章节无论文笔多好，吸引力得分都会较低。
4. AI 模式检查：寻找这些常见的 AI 写作模式：
   - 每个段落长度相同
   - 观察结果总是以三元组形式出现 (X, Y, Z)
   - 情感节拍准时到达而非给人惊喜
   - 角色从不说错话或各说各话
   - 描写像在罗列清单（列出 5 个感官细节，而 2 个具体的会更鲜明）
   - 内心独白在解释场景已经展现的内容
5. 赢得 vs 赋予：紧张感是通过场景描写"赢得"的，还是通过叙述者的断言直接"赋予"给读者的？悬念是通过真正的保留来维持的，还是由于角色刻意不去想他们本该想到的事情？

对以下维度进行评分：

- 语气遵循度 (voice_adherence): 文字是否符合 voice.md 第二部分？核对：句式节奏变化、感官细节优先于情感标签、{genre_name}基调。是否有段落像通用AI网文散文？如果是，最高给 7 分。
- 节拍覆盖度 (beat_coverage): 是否完成了大纲中的每一个节拍？节拍是戏剧化展现了还是仅仅被提及？在句子中总结而非在场景中生活的节拍只能算完成了一半。分数反映节拍执行的质量，而不只是存在感。
- 角色语气 (character_voice): 去掉对话标签能分辨谁在说话吗？对话读起来像人说话还是像写作文？是否有人说了真实的、令人意外的话？从不说错话的角色是AI模式角色。
- 伏笔植入 (plants_seeded): 伏笔元素是否放置得自然？显眼的伏笔比隐形的伏笔更差。根据整合的质量评分，而不只是是否存在。
- 文笔质量 (prose_quality): 句式多样性（核对：是否有 3 条以上连续的句子开头相同？）。具体性（具体名词 > 抽象名词）。隐喻来自角色经历而非词典。情感高峰处的"展现而非陈述"。引用最弱的句子并解释原因。同时核对：重复短语、过度依赖的句式、可以删掉而不造成损失的段落。
- 连贯性 (continuity): 逻辑上是否衔接前一章？包括情感连贯性和情节连贯性。角色的心态是否衔接？
- 准则合规性 (canon_compliance): 对照设定准则检查所有事实。核对：角色名、地点、物价、金手指规则、时间线。一个重大违规最高给 6 分。
- 设定整合度 (lore_integration): {lore_desc}经济逻辑是否自洽？
- 吸引力 (engagement): 读者会翻页吗？张力来自哪里 —— 情节、角色、悬念还是文笔？是否有令人惊喜的瞬间？可预测的优秀依然是可预测的。只有在章节做了意料之外的事情时才给 8 分以上。
{f'''
题材特有维度：
{genre_dims}
''' if genre_dims else ''}
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

    # Extract this chapter's outline entry (prefer volume outline, fallback outline.md)
    vol_outline_text, _ = load_volume_outline_for_chapter(chapter_num, BASE_DIR)
    chapter_outline = extract_chapter_outline(vol_outline_text, chapter_num)
    if not chapter_outline:
        # Fallback for short-form mode or missing volume outline
        chapter_outline = extract_chapter_outline(layers["outline"], chapter_num)
    if not chapter_outline:
        chapter_outline = "(outline entry not found)"

    # Load previous chapter tail
    prev_text = load_chapter(chapter_num - 1) if chapter_num > 1 else "(first chapter)"
    prev_tail = prev_text[-3000:] if len(prev_text) > 3000 else prev_text

    genre = _get_genre()
    prompt = _build_chapter_prompt(genre)
    replacements = {
        "voice": layers["voice"],
        "world": layers["world"][:4000],
        "characters": layers["characters"],
        "canon": layers["canon"],
        "chapter_outline": chapter_outline,
        "prev_chapter_tail": prev_tail,
        "chapter_text": chapter_text,
    }
    for key, value in replacements.items():
        prompt = prompt.replace(f"{{__{key.upper()}__}}", value)
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

def _build_full_novel_prompt(genre) -> str:
    """Build the full novel evaluation prompt dynamically from genre config."""
    genre_name = genre.display_name

    return f"""从整体上全面评估这部女频{genre_name}网文。
你拥有策划文档以及每一章的摘要及其个人评分。

语气定义:
{{voice}}

世界设定集摘要:
{{world_summary}}

角色注册表:
{{characters}}

大纲与伏笔台账:
{{outline}}

各章摘要与得分:
{{chapter_summaries}}

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

    genre = _get_genre()
    prompt = _build_full_novel_prompt(genre).format(
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
    group.add_argument("--phase", choices=["foundation", "foundation-lf"],
                       help="Evaluate planning documents (foundation or foundation-lf for long-form)")
    group.add_argument("--chapter", type=int,
                       help="Evaluate a specific chapter number")
    group.add_argument("--full", action="store_true",
                       help="Evaluate the entire novel")
    args = parser.parse_args()

    if args.phase == "foundation":
        result = evaluate_foundation()
        score_key = "overall_score"
    elif args.phase == "foundation-lf":
        result = evaluate_foundation_lf()
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
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\neval_log: {log_path}")


if __name__ == "__main__":
    main()
