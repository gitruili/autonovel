#!/usr/bin/env python3
"""
seed_lf.py -- 生成长篇网文种子概念（100万字+/500+章/25卷）。

Usage:
  uv run python seed_lf.py              # 生成 3 个长篇概念
  uv run python seed_lf.py --count=2    # 生成 2 个概念
  uv run python seed_lf.py --count=5    # 生成 5 个概念（自动分批）
  uv run python seed_lf.py --riff "边关种田美食文"  # 基于想法扩展
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import (
    call_text_model,
    default_model_for_role,
    get_api_key,
    provider_api_key_env,
)

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

from genres.genre_registry import load_genre_for_project
genre = load_genre_for_project()

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6-20250217"),
)

MAX_MARKET_RESEARCH_CHARS = 12000
DEFAULT_MAX_TOKENS = 32000
DEFAULT_BATCH_SIZE = 3  # 每批生成的最大脑洞数量，超过时自动分批


def call_writer(prompt, max_tokens=DEFAULT_MAX_TOKENS):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=1.0,
        system=genre.get_system_prompt("seed_writer_lf"),
        messages=[{"role": "user", "content": prompt}],
        timeout=900,
        include_beta=True,
    )


import math


def _format_long_form_fragment(fragment: str, context: dict) -> str:
    """Format genre prompt fragments with long-form planning values."""
    return fragment.format(**context).strip()


def _load_market_research(paths: list[str]) -> str:
    """Load external market research files for prompt injection."""
    if not paths:
        return ""

    sections = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        if not path.exists():
            raise FileNotFoundError(f"Market research file not found: {path}")

        text = path.read_text(encoding="utf-8").strip()
        if len(text) > MAX_MARKET_RESEARCH_CHARS:
            text = (
                text[:MAX_MARKET_RESEARCH_CHARS].rstrip()
                + "\n\n[市场调研文件过长，已截断。请优先保留趋势总结、开局模型、红海/蓝海判断。]"
            )
        sections.append(f"### 调研文件：{path.name}\n来源路径：{path}\n\n{text}")

    return "\n\n".join(sections).strip()


def _build_market_research_context(market_research: str) -> str:
    """Wrap external research as time-sensitive market signal, not canon."""
    if not market_research.strip():
        return ""
    return f"""## 外部榜单/市场调研参考（可替换、非硬性设定）
以下资料可能来自七猫、番茄或其他平台，统计时间和榜单口径可能变化。
请把它当作市场信号，而不是创作素材库：
- 先提炼热词、红海方向、蓝海机会、开局模型和节奏规律。
- 每个脑洞必须采用"热门基础盘 + 差异化切入"的组合。
- 不要复刻榜单作品，不要复制已有书名、角色、人设组合或具体剧情。
- 如果调研与题材基础 prompt 冲突，以题材基础 prompt 和现代法律/商业逻辑为准。

{market_research.strip()}
"""


def _build_generate_prompt(count: int, tags_context: str, target_words_label: str,
                           target_chapters: int, total_volumes: int, early_chapters: int,
                           ranges: dict, market_research_context: str = "") -> str:
    """Build the long-form seed generation prompt from genre config."""
    context = {
        "count": count,
        "target_words_label": target_words_label,
        "target_chapters": target_chapters,
        "total_volumes": total_volumes,
        "early_chapters": early_chapters,
        **ranges,
    }
    long_requirements = genre.get_prompt_fragment("seed_lf", "generate_requirements")
    long_output_template = genre.get_prompt_fragment("seed_lf", "output_template")
    if long_requirements and long_output_template:
        diversity = (
            genre.get_prompt_fragment("seed_lf", "diversity_requirements")
            or genre.get_prompt_fragment("seed", "diversity_requirements")
        )
        prohibitions = (
            genre.get_prompt_fragment("seed_lf", "prohibitions")
            or genre.get_prompt_fragment("seed", "prohibitions")
        )
        return f"""生成 {count} 个{genre.display_name}网文的**长篇**种子概念。每一个都应该是一个完整的前提，
足以支撑起一部{target_words_label}的长篇网文（{target_chapters}+章，{total_volumes}卷，每卷约{ranges['chapters_per_volume']}章）的构建。

## 初始设定
- 故事题材与标签：{genre.display_name}
- 目标篇幅：{target_words_label}，{target_chapters}+章，{total_volumes}卷
- 其他要求：严格遵从类型标签、题材定义、书名设计原则和简介设计原则；每个脑洞都必须有长篇连载支撑力。

{tags_context}

{genre.genre_definition}

{genre.title_rules}

{genre.synopsis_rules}

{market_research_context}

{_format_long_form_fragment(long_requirements, context)}

{_format_long_form_fragment(diversity, context) if diversity else ""}

{_format_long_form_fragment(prohibitions, context) if prohibitions else ""}

{_format_long_form_fragment(long_output_template, context)}
"""

    return f"""生成 {count} 个{genre.display_name}网文的**长篇**种子概念。每一个都应该是一个完整的前提，
足以支撑起一部{target_words_label}的长篇网文（{target_chapters}+章，{total_volumes}卷，每卷约{ranges['chapters_per_volume']}章）的构建。

{tags_context}

{genre.genre_definition}

{genre.title_rules}

{genre.synopsis_rules}

{market_research_context}

## 每个概念必须包含以下要素

### 主要人设
明确核心人物（如男女主、关键盟友与核心反派）的核心欲望、性格软肋与行为模式。
主角的金手指（如重生记忆、特殊马甲、随身空间等核心优势）是什么？
关键：金手指必须有局限性，不能让主角无所不能。
金手指的升级节奏必须匹配{target_words_label}的篇幅——不能在前{early_chapters}章就把金手指用完。确保每个创意有足够的升级台阶 and 反派轮换空间，能支撑百万字连载。

### 主题
这个故事的精神内核是什么？

{genre.get_prompt_fragment("seed", "diversity_requirements").format(count=count)}

{genre.get_prompt_fragment("seed", "prohibitions")}

## 输出模板（严格按此格式）

# 创意<序号>：《<书名>》

## 作品简介
<按照简介设计原则撰写，标签放在最前面，3-4段，短句为主，情绪炸裂>

## 核心卖点
<一句话描述核心卖点/核心梗>

## 主要人设
<涵盖主要角色的金手指、局限性、核心欲望及软肋等>

## 主题
<一句话精神内核>
"""


def _build_riff_prompt(idea: str, tags_context: str, target_words_label: str,
                       target_chapters: int, total_volumes: int, ranges: dict,
                       market_research_context: str = "") -> str:
    """Build the long-form riff prompt from genre config."""
    context = {
        "target_words_label": target_words_label,
        "target_chapters": target_chapters,
        "total_volumes": total_volumes,
        **ranges,
    }
    long_riff_requirements = genre.get_prompt_fragment("seed_lf", "riff_requirements")
    long_riff_template = (
        genre.get_prompt_fragment("seed_lf", "riff_output_template")
        or genre.get_prompt_fragment("seed_lf", "output_template")
    )
    if long_riff_requirements and long_riff_template:
        return f"""我有一个{genre.display_name}网文的种子构思：

"{idea}"

{tags_context}

{genre.genre_definition}

{genre.title_rules}

{genre.synopsis_rules}

{market_research_context}

{_format_long_form_fragment(long_riff_requirements, context)}

{_format_long_form_fragment(long_riff_template, context)}
"""

    return f"""我有一个{genre.display_name}网文的种子构思：

"{idea}"

{tags_context}

{genre.genre_definition}

{genre.title_rules}

{genre.synopsis_rules}

{market_research_context}

基于这个概念生成 5 个**长篇**变体（每个都应能支撑{target_words_label}/{target_chapters}+章/{total_volumes}卷）。
保留核心构思中吸引人的部分，但将其推向不同的方向。

可以改变的维度包括：时代背景、金手指类型、产业方向、男主人设、
家庭关系结构、故事基调、反派类型、地理扩展路径。

按以下模板输出每个变体：

# 创意<序号>：《<书名>》

## 不同之处
<从原始种子中改变了什么，为什么要改变？>

## 作品简介
<按照简介设计原则撰写>

## 核心卖点
<一句话核心卖点>

## 主要人设
<涵盖主要角色的金手指、局限性、核心欲望及软肋等>

## 爽点设计
<最让读者拍案叫绝的"逆袭"时刻，按卷号列出关键爽点>
"""


def _compute_volume_ranges(total_volumes: int) -> dict:
    """Compute dynamic volume range boundaries for a given total volume count.

    Engine stages, antagonist tiers, and romance phases all share the same
    6-stage percentage split. Antagonist tiers use a coarser 5-tier split.
    All boundaries are strictly increasing (each stage gets at least 1 volume).
    """
    def _strictly_increasing(total: int, pcts: list[float]) -> list[int]:
        raw = [min(total, max(1, math.ceil(total * p))) for p in pcts]
        result = []
        prev = 0
        for v in raw:
            v = max(prev + 1, v)
            result.append(min(total, v))
            prev = result[-1]
        # Last element must equal total
        result[-1] = total
        return result

    # 5-stage split (engines / romance phases) — boundaries e1-e4, 5th stage is e4+1 to total
    e = _strictly_increasing(total_volumes, [0.15, 0.35, 0.55, 0.75, 1.0])

    # 5-tier antagonist split — boundaries a1-a4, 5th tier is a4+1 to total
    a = _strictly_increasing(total_volumes, [0.15, 0.35, 0.55, 0.75, 1.0])

    # Foreshadow: plant in first stage, payoff starting at ~60%
    pf_plant = e[0]
    pf_payoff = min(e[2] + 1, total_volumes)

    return {
        "e1": e[0], "e2": e[1], "e3": e[2], "e4": e[3],
        "e1p1": e[0] + 1, "e2p1": e[1] + 1, "e3p1": e[2] + 1, "e4p1": e[3] + 1,
        "a1": a[0], "a2": a[1], "a3": a[2], "a4": a[3],
        "a1p1": a[0] + 1, "a2p1": a[1] + 1, "a3p1": a[2] + 1, "a4p1": a[3] + 1,
        "pf_plant": pf_plant,
        "pf_payoff": pf_payoff,
        "pf_payoff_p2": pf_payoff + 2,
        "chapters_per_volume": 20,
    }


def _target_words_label(target_words: int) -> str:
    """Return a human-readable label like '50万字' or '100万字'."""
    wan = target_words // 10000
    return f"{wan}万字"


def main():
    parser = argparse.ArgumentParser(description=f"生成{genre.display_name}网文长篇种子构思")
    parser.add_argument("--count", type=int, default=3,
                        help="生成的构思数量 (默认: 3)")
    parser.add_argument("--riff", type=str, default=None,
                        help="基于现有想法进行扩展")
    parser.add_argument("--target-words", type=int, default=1000000,
                        help="目标总字数 (默认: 1000000 即100万字)")
    parser.add_argument("--market-research", action="append", default=[],
                        help="外部榜单/市场调研 Markdown 文件路径，可重复传入；也可配置在 story/project.json 的 market_research_files")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help=f"LLM 每批最大输出 token 数 (默认: {DEFAULT_MAX_TOKENS})")
    parser.add_argument("--batch-size", type=int, default=None,
                        help=f"每批生成的脑洞数量上限，超过时自动分批 (默认: {DEFAULT_BATCH_SIZE})")
    args = parser.parse_args()

    if not get_api_key():
        print(f"ERROR: Set {provider_api_key_env()} in .env first")
        sys.exit(1)

    from story_schema import load_project_tags
    proj, tags_context = load_project_tags()
    research_paths = [*proj.market_research_files, *args.market_research]
    market_research_context = _build_market_research_context(
        _load_market_research(research_paths)
    )

    max_tokens = args.max_tokens or DEFAULT_MAX_TOKENS
    batch_size = args.batch_size or DEFAULT_BATCH_SIZE

    # Compute dynamic values from target_words
    target_words = args.target_words
    label = _target_words_label(target_words)
    cpv = 20  # chapters per volume
    target_chapters = target_words // 4000  # ~4000 chars per chapter
    total_volumes = max(6, target_chapters // cpv)  # min 6 volumes for 6-stage structure
    # Recalculate to be consistent
    target_chapters = total_volumes * cpv

    ranges = _compute_volume_ranges(total_volumes)
    early_chapters = max(10, cpv)  # ~1 volume worth of chapters

    if args.riff:
        print(f"正在基于以下想法扩展长篇变体 ({label}+/{target_chapters}+章/{total_volumes}卷)...\n")
        prompt = _build_riff_prompt(args.riff, tags_context, label, target_chapters, total_volumes, ranges, market_research_context)
        print(prompt)
        print("-----------------")
        result = call_writer(prompt, max_tokens=max_tokens)
        print(result)
    else:
        total_count = args.count
        # Split into batches to avoid truncation
        batches = []
        remaining = total_count
        start_idx = 1
        while remaining > 0:
            batch_count = min(remaining, batch_size)
            batches.append((start_idx, batch_count))
            start_idx += batch_count
            remaining -= batch_count

        if len(batches) > 1:
            print(f"共需生成 {total_count} 个脑洞，将分 {len(batches)} 批进行（每批最多 {batch_size} 个），避免输出截断。\n")

        all_results = []
        for batch_idx, (start_num, batch_count) in enumerate(batches, 1):
            if len(batches) > 1:
                print(f"\n{'='*60}")
                print(f"  第 {batch_idx}/{len(batches)} 批：生成创意 {start_num}-{start_num + batch_count - 1}")
                print(f"{'='*60}\n")

            prompt = _build_generate_prompt(
                batch_count, tags_context, label, target_chapters,
                total_volumes, early_chapters, ranges, market_research_context,
            )

            # If not the first batch, add instruction to continue numbering
            if start_num > 1:
                prompt += f"\n\n注意：请从创意{start_num}开始编号（不是从1开始）。\n"

            if batch_idx == 1:
                print(prompt)
                print("-----------------")

            result = call_writer(prompt, max_tokens=max_tokens)
            print(result)
            all_results.append(result)

    print("\n" + "=" * 60)
    print("要挑选一个种子，请将你喜欢的概念复制到 seed.txt 中：")
    print("  nano seed.txt")
    print("然后运行: uv run python autonovel_cli.py generate foundation")


if __name__ == "__main__":
    main()
