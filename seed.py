#!/usr/bin/env python3
"""
seed.py -- 生成网文种子概念。

Usage:
  uv run python seed.py              # 生成 3 个概念 (MiniMax 建议 2-3 个以免截断)
  uv run python seed.py --count=5    # 生成 5 个概念 (可能会截断)
  uv run python seed.py --riff "穿越到古代成了弃妇带着空间种田"  # 基于一个想法扩展
"""

import argparse
import json
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


def call_writer(prompt, max_tokens=8192):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=1.0,
        system=genre.get_system_prompt("seed_writer"),
        messages=[{"role": "user", "content": prompt}],
        timeout=720,
        include_beta=True,
    )


def _build_generate_prompt(count: int, tags_context: str) -> str:
    """Build the seed generation prompt from genre config."""
    return f"""生成 {count} 个{genre.display_name}网文的种子概念。每一个都应该是
一个完整的前提，足以支撑起一整部中篇网文（约 8-10 万字，20-24 章）的构建。

{tags_context}

{genre.genre_definition}

{genre.title_rules}

{genre.synopsis_rules}

{genre.get_prompt_fragment("seed", "generate_requirements")}

{genre.get_prompt_fragment("seed", "diversity_requirements").format(count=count)}

{genre.get_prompt_fragment("seed", "prohibitions")}

{genre.get_prompt_fragment("seed", "output_template")}
"""


def _build_riff_prompt(idea: str, tags_context: str) -> str:
    """Build the riff prompt from genre config."""
    return f"""我有一个{genre.display_name}网文的种子构思：

"{idea}"

{tags_context}

{genre.genre_definition}

{genre.title_rules}

{genre.synopsis_rules}

{genre.get_prompt_fragment("seed", "riff_requirements")}
"""


def main():
    parser = argparse.ArgumentParser(description=f"生成{genre.display_name}网文种子构思")
    parser.add_argument("--count", type=int, default=3,
                        help="生成的构思数量 (默认: 3)")
    parser.add_argument("--riff", type=str, default=None,
                        help="基于现有想法进行扩展")
    args = parser.parse_args()

    if not get_api_key():
        print(f"ERROR: Set {provider_api_key_env()} in .env first")
        sys.exit(1)

    from story_schema import load_project_tags
    _, tags_context = load_project_tags()

    if args.riff:
        print(f"正在基于以下想法扩展: {args.riff}\n")
        prompt = _build_riff_prompt(args.riff, tags_context)
    else:
        print(f"正在生成 {args.count} 个{genre.display_name}网文种子构思...\n")
        prompt = _build_generate_prompt(args.count, tags_context)

    print(prompt)
    print("-----------------")
    result = call_writer(prompt, max_tokens=8192)
    print(result)
    print("\n" + "=" * 60)
    print("要挑选一个种子，请将你喜欢的概念复制到 seed.txt 中：")
    print("  nano seed.txt")
    print("或者将几个概念重新组合成你自己的种子。")
    print("然后继续 WORKFLOW.md 中的第 2 步。")


if __name__ == "__main__":
    main()
