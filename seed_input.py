#!/usr/bin/env python3
"""
seed_input.py -- 接受用户提供的脑洞概念，评价并优化后保存到 seed.txt。

Usage:
  uv run python seed_input.py --input "《京圈太子爷的白月光是我妈》..."
  uv run python seed_input.py --input-file concept.txt
  uv run python seed_input.py --input-file concept.txt --auto-accept
  uv run python seed_input.py --input-file concept.txt --no-optimize
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
load_dotenv(BASE_DIR / ".env")

from llm_client import (
    call_text_model,
    default_model_for_role,
    get_api_key,
    provider_api_key_env,
)

# ── Models ──
WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6-20250217"),
)
JUDGE_MODEL = os.environ.get(
    "AUTONOVEL_JUDGE_MODEL",
    default_model_for_role("judge", "claude-opus-4-6"),
)


# ── Genre keyword detection ──

GENRE_KEYWORDS = {
    "总裁豪门": ["总裁", "豪门", "京圈", "太子爷", "财阀", "霸总", "首席", "继承人",
                  "陆总", "厉总", "霍先生", "陆少", "厉少", "豪门少爷", "商业帝国"],
    "年代文": ["年代", "知青", "改革开放", "六零", "七零", "八零", "九零", "五零",
               "下乡", "回城", "供销社", "大队长", "工农兵", "票证", "公社"],
}

TAG_KEYWORDS = {
    "穿越": ["穿越", "穿成", "穿到"],
    "重生": ["重生", "回到过去", "重活一世"],
    "穿书": ["穿书", "穿成", "书里", "原书", "原著"],
    "豪门": ["豪门", "财阀", "世家"],
    "总裁": ["总裁", "霸总", "首席"],
    "甜宠": ["甜宠", "撒糖", "甜蜜"],
    "萌娃": ["萌娃", "萌宝", "小团子", "三岁", "五岁", "宝宝"],
    "大女主": ["大女主", "独立女主"],
    "脑洞": ["脑洞", "反转", "反套路", "年龄差"],
    "团宠": ["团宠", "被宠"],
    "现言": ["现代", "都市", "都市"],
    "古言": ["古代", "王爷", "将军", "王妃"],
    "先婚后爱": ["先婚后爱", "契约婚姻", "替嫁"],
    "空间": ["空间", "随身空间"],
    "系统": ["系统", "金手指"],
    "美食": ["美食", "厨神", "食谱"],
    "经商": ["经商", "做生意", "商铺", "商战"],
    "医术": ["医术", "神医", "药膳"],
    "宫斗": ["宫斗", "后宫", "争宠"],
    "宅斗": ["宅斗", "嫡庶", "内宅"],
}


def detect_genre_and_tags(concept: str) -> tuple[str, list[str]]:
    """Detect genre and tags from concept text using keyword matching.

    Returns (genre_display_name, tags_list).
    """
    # Detect genre
    genre_name = "种田文"  # default
    max_score = 0
    for gname, keywords in GENRE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in concept)
        if score > max_score:
            max_score = score
            genre_name = gname

    # Detect tags
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in concept for kw in keywords):
            tags.append(tag)

    # Deduplicate and limit
    tags = list(dict.fromkeys(tags))[:10]

    return genre_name, tags


def extract_title(concept: str) -> str:
    """Extract title from concept text (looks for 《》 pattern)."""
    match = re.search(r'《(.+?)》', concept)
    if match:
        return match.group(1)
    # Also try first line as title
    first_line = concept.strip().split('\n')[0].strip()
    if len(first_line) < 50:
        return first_line
    return ""


# ── Evaluation ──

def build_eval_prompt(concept: str, genre_name: str, tags: list[str]) -> str:
    """Build the evaluation prompt for the judge model."""
    tags_str = "、".join(tags) if tags else "未检测到"
    return f"""请对以下网文脑洞概念进行全面评价。

## 题材识别
初步检测题材：{genre_name}
初步检测标签：{tags_str}

## 概念原文
{concept}

## 评价要求
请从以下维度评价，并以 JSON 格式返回结果：

1. **detected_genre**：确认或修正题材（总裁豪门/年代文/种田文）
2. **detected_tags**：确认或修正标签列表
3. **title**：提取书名（如有《》格式）
4. **market_fit**：市场匹配度评估
   - score (1-10)
   - hot_points: 当前热门元素列表
   - audience_match: 目标受众描述
   - platform_fit: 适合的平台
5. **strengths**: 概念优势列表（3-5条）
6. **weaknesses**: 概念劣势/风险列表（3-5条）
7. **feasibility**: 可行性评估
   - score (1-10)
   - chapter_potential: 可支撑的章节数量
   - expansion_risk: 长篇扩展风险
8. **overall_score**: 综合评分 (1-10)
9. **optimization_suggestions**: 优化建议列表（3-5条）

请以纯 JSON 格式返回，不要包含 Markdown 围栏。"""


def call_judge(prompt: str, max_tokens: int = 3000) -> str:
    """Call the judge model for evaluation."""
    return call_text_model(
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        system=(
            "你是一位网文编辑和市场分析师。你熟悉番茄小说、七猫等平台的读者偏好，"
            "擅长评估网文概念的市场潜力和可行性。"
            "请务必以有效的 JSON 格式返回结果。不要包含 Markdown 围栏，不要有前导文字 —— 仅返回 JSON 对象。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=180,
        include_beta=True,
    )


def parse_json_response(text: str) -> dict:
    """Extract JSON from a response that might have markdown fences or trailing text."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in response")
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
                    fixed = re.sub(r'(?<!\\)\n', '\\n', extracted)
                    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
                    fixed = re.sub(r'(?<!\\)(?<=[^:\[{,\s])"(?=[^:\]},\s])', r'\\"', fixed)
                    try:
                        return json.loads(fixed, strict=False)
                    except json.JSONDecodeError:
                        Path("failed_eval.json").write_text(extracted, encoding="utf-8")
                        raise ValueError(f"Failed to parse JSON (saved to failed_eval.json): {e}")
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


def evaluate_concept(concept: str) -> dict:
    """Evaluate a concept: detect genre/tags, then call judge model."""
    genre_name, tags = detect_genre_and_tags(concept)
    prompt = build_eval_prompt(concept, genre_name, tags)
    raw = call_judge(prompt)
    result = parse_json_response(raw)
    # Ensure detected fields are present (fallback to heuristic)
    result.setdefault("detected_genre", genre_name)
    result.setdefault("detected_tags", tags)
    result.setdefault("title", extract_title(concept))
    return result


# ── Optimization ──

def build_optimize_prompt(concept: str, eval_result: dict) -> str:
    """Build the optimization prompt for the writer model."""
    strengths = "\n".join(f"  - {s}" for s in eval_result.get("strengths", []))
    weaknesses = "\n".join(f"  - {w}" for w in eval_result.get("weaknesses", []))
    suggestions = "\n".join(f"  - {s}" for s in eval_result.get("optimization_suggestions", []))

    return f"""请优化以下网文脑洞概念。保留其核心创意和优势，修正劣势，落实优化建议。

## 原始概念
{concept}

## 评价结果
### 优势（保留）
{strengths}

### 劣势（修正）
{weaknesses}

### 优化建议（落实）
{suggestions}

## 输出要求
1. 保留原始概念的核心创意和差异化亮点
2. 修正评价中指出的劣势
3. 落实优化建议
4. 输出完整的优化版概念，包含：书名、核心创意、主要角色、前10章规划、长篇方向
5. 以纯文本格式输出，不要使用 YAML/JSON/Markdown 标题
6. 优化后的概念应该可以直接用于后续的世界观生成

请输出优化后的完整概念："""


def call_writer(prompt: str, max_tokens: int = 16000) -> str:
    """Call the writer model for optimization."""
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.7,
        system=(
            "你是一位资深网文策划编辑，擅长优化和打磨故事概念。"
            "你保留创作者的核心创意，同时提升概念的市场可行性和结构完整性。"
            "你输出纯文本，不使用任何格式标记。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
        include_beta=True,
    )


def optimize_concept(concept: str, eval_result: dict) -> str:
    """Optimize a concept based on evaluation feedback."""
    prompt = build_optimize_prompt(concept, eval_result)
    return call_writer(prompt)


# ── Save ──

def save_seed(concept: str, title: str, genre_name: str, tags: list[str]) -> None:
    """Save optimized concept to seed.txt and update project.json."""
    from story_schema import ProjectConfig, load_json, save_json

    # Write seed.txt
    seed_path = BASE_DIR / "seed.txt"
    seed_path.write_text(concept, encoding="utf-8")
    print(f"\n已保存到 {seed_path}")

    # Update project.json
    proj_path = STORY_DIR / "project.json"
    if proj_path.exists():
        proj = ProjectConfig(**load_json(proj_path))
    else:
        STORY_DIR.mkdir(parents=True, exist_ok=True)
        proj = ProjectConfig()

    if title:
        proj.title = title
    if genre_name:
        proj.genre = genre_name
    if tags:
        existing = set(proj.tags)
        existing.update(tags)
        proj.tags = sorted(existing)

    save_json(proj_path, proj.model_dump())
    print(f"已更新 {proj_path}")
    print(f"  书名: {proj.title}")
    print(f"  题材: {proj.genre}")
    print(f"  标签: {', '.join(proj.tags)}")


# ── Display ──

def print_evaluation(eval_result: dict) -> None:
    """Print evaluation results in a readable format."""
    print("\n" + "=" * 60)
    print("脑洞评价报告")
    print("=" * 60)

    print(f"\n题材: {eval_result.get('detected_genre', '未知')}")
    print(f"标签: {', '.join(eval_result.get('detected_tags', []))}")
    title = eval_result.get('title', '')
    if title:
        print(f"书名: {title}")

    market = eval_result.get('market_fit', {})
    print(f"\n市场匹配度: {market.get('score', '?')}/10")
    hot = market.get('hot_points', [])
    if hot:
        print(f"热门元素: {', '.join(hot)}")
    audience = market.get('audience_match', '')
    if audience:
        print(f"目标受众: {audience}")

    print(f"\n综合评分: {eval_result.get('overall_score', '?')}/10")

    feas = eval_result.get('feasibility', {})
    print(f"可行性: {feas.get('score', '?')}/10")
    chapters = feas.get('chapter_potential', '')
    if chapters:
        print(f"章节数量: {chapters}")

    strengths = eval_result.get('strengths', [])
    if strengths:
        print("\n优势:")
        for s in strengths:
            print(f"  + {s}")

    weaknesses = eval_result.get('weaknesses', [])
    if weaknesses:
        print("\n劣势:")
        for w in weaknesses:
            print(f"  - {w}")

    suggestions = eval_result.get('optimization_suggestions', [])
    if suggestions:
        print("\n优化建议:")
        for s in suggestions:
            print(f"  > {s}")

    print("=" * 60)


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="评价并优化用户提供的网文脑洞概念")
    parser.add_argument("--input", type=str, default=None,
                        help="直接提供概念文本")
    parser.add_argument("--input-file", type=str, default=None,
                        help="从文件读取概念")
    parser.add_argument("--genre", type=str, default=None,
                        help="手动指定题材（覆盖自动检测）")
    parser.add_argument("--auto-accept", action="store_true",
                        help="跳过确认提示，自动优化并保存")
    parser.add_argument("--no-optimize", action="store_true",
                        help="只评价不优化，原样保存")
    args = parser.parse_args()

    if not get_api_key():
        print(f"ERROR: Set {provider_api_key_env()} in .env first")
        sys.exit(1)

    # Read concept
    if args.input_file:
        path = Path(args.input_file)
        if not path.exists():
            print(f"ERROR: File not found: {path}")
            sys.exit(1)
        concept = path.read_text(encoding="utf-8")
    elif args.input:
        concept = args.input
    else:
        print("ERROR: 请通过 --input 或 --input-file 提供概念文本")
        sys.exit(1)

    concept = concept.strip()
    if len(concept) < 50:
        print("ERROR: 概念文本太短（至少50字符），无法进行有效评价")
        sys.exit(1)

    # Step 1: Detect genre and tags
    genre_name, tags = detect_genre_and_tags(concept)
    if args.genre:
        genre_name = args.genre
    print(f"检测到题材: {genre_name}")
    print(f"检测到标签: {', '.join(tags) if tags else '无'}")

    # Step 2: Evaluate
    print("\n正在评价脑洞概念...")
    eval_result = evaluate_concept(concept)

    # Override with user-specified genre if provided
    if args.genre:
        eval_result["detected_genre"] = args.genre

    # Merge heuristic tags with LLM-detected tags
    llm_tags = eval_result.get("detected_tags", [])
    all_tags = list(dict.fromkeys(tags + llm_tags))[:10]
    eval_result["detected_tags"] = all_tags

    print_evaluation(eval_result)

    # Step 3: Confirm and optimize
    final_concept = concept
    if not args.no_optimize:
        if args.auto_accept:
            do_optimize = True
        else:
            response = input("\n是否要优化这个概念？[Y/n] ").strip().lower()
            do_optimize = response != 'n'

        if do_optimize:
            print("\n正在优化概念...")
            final_concept = optimize_concept(concept, eval_result)
            print("\n优化结果:")
            print("-" * 60)
            print(final_concept)
            print("-" * 60)

    # Step 4: Save
    title = eval_result.get("title", extract_title(concept))
    final_genre = eval_result.get("detected_genre", genre_name)
    final_tags = eval_result.get("detected_tags", tags)

    save_seed(final_concept, title, final_genre, final_tags)

    print("\n下一步:")
    print("  uv run python autonovel_cli.py generate foundation")


if __name__ == "__main__":
    main()
