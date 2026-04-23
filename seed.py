#!/usr/bin/env python3
"""
seed.py -- Generate fantasy novel seed concepts.

Usage:
  uv run python seed.py              # Generate 10 concepts, pick one
  uv run python seed.py --count=5    # Generate 5 concepts
  uv run python seed.py --riff "magic costs memories"  # Riff on an idea
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

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6-20250217"),
)


def call_writer(prompt, max_tokens=8192):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=1.0,
        system=(
            "你是一位深谙该领域杰作的奇幻小说家 —— 比如托尔金（Tolkien）、勒古恩（Le Guin）、罗斯福斯（Rothfuss）、沃尔夫（Wolfe）、杰米辛（Jemisin）、匹克（Peake）、苏珊娜·克拉克（Susanna Clarke）、安德鲁·彼得森（Andrew Peterson）、索菲亚·萨马塔（Sofia Samatar）。 "
            "你生成的构思必须是**具体、令人惊喜且结构稳健**的。 "
            "永远不要提议平庸的“中世纪欧洲+精灵”设定。每个概念都应该让读者心想：“我以前从未见过这种东西。”"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=720,
        include_beta=True,
    )


GENERATE_PROMPT = """生成 {count} 个奇幻小说种子概念。每一个都应该是
一个完整的前提，足以支撑起一整部小说的构建。

为每个概念提供：

编号. 标题 (一个引人入胜、不落俗套的暂定标题)
悬念 (HOOK): 一句话吸引读者拿起书。要具体且出人意料，不要用“在一个……的世界里”这种陈旧句式。
世界 (WORLD): 这个世界有何不同？不要只说“有魔法”，而要说出定义这个地方的具体、不寻常的事物。要具体化 —— 
  盐滩、倒置的塔、会迁徙的城市、有记忆的海等等。要体现感官细节。
魔法/代价 (MAGIC/COST): 核心超自然元素是什么，它的代价（COST）是什么？根据山德森第二定律，
  局限性 > 能力。代价应该能创造有趣的困境。
张力 (TENSION): 核心冲突是什么？它必须既是个人化的（角色具体的难题），又是宏观的（影响世界）。
  两者必须处于相互博弈的张力之中。
主题 (THEME): 这个故事探讨了什么问题？不是传达一个说教信息，而是一个没有简单答案的真实问题。
为何不平庸 (WHY IT'S NOT GENERIC): 用一句话说明这与标准奇幻套路有何不同。

确保这 {count} 个概念具有多样性：
  - 至少有一个非人类中心的世界
  - 至少有一个偏文学性/静态而非宏大叙事的概念
  - 至少有一个具有非传统叙事结构想法的概念
  - 至少有一个设定在典型的欧洲灵感设定之外的概念
  - 混合不同的色调：黑暗、温暖、诡异、忧郁、奇思妙想

不要生成：
  - “天选之子”预言（除非以有趣的方式被颠覆）
  - 以“黑魔王/终极邪恶”作为主要反派
  - 中世纪欧洲 + 精灵/矮人/兽人
  - “学院”或“魔法学校”设定
  - 以“三角恋”作为核心情节
"""

RIFF_PROMPT = """我有一个奇幻小说的种子构思：

“{idea}”

基于这个概念生成 5 个变体。保留核心构思中吸引人的部分，但将其推向不同的方向。对于每个变体提供：

编号. 标题
悬念 (HOOK): 一句话说明。
不同之处: 你从原始种子中改变了什么，为什么要改变？
世界 (WORLD): 具体的、具有感官细节的世界描述。
魔法/代价 (MAGIC/COST): 超自然元素及其代价。
张力 (TENSION): 个人冲突 + 宏观冲突。
主题 (THEME): 它探讨的问题。

确保这些变体之间有真正的区别 —— 不要只是微调表面细节。改变主角、设定、基调、结构或主题焦点。
"""


def main():
    parser = argparse.ArgumentParser(description="生成小说种子构思")
    parser.add_argument("--count", type=int, default=10,
                        help="生成的构思数量 (默认: 10)")
    parser.add_argument("--riff", type=str, default=None,
                        help="基于现有想法进行扩展")
    args = parser.parse_args()

    if not get_api_key():
        print(f"ERROR: Set {provider_api_key_env()} in .env first")
        sys.exit(1)

    if args.riff:
        print(f"正在基于以下想法扩展: {args.riff}\n")
        prompt = RIFF_PROMPT.format(idea=args.riff)
    else:
        print(f"正在生成 {args.count} 个种子构思...\n")
        prompt = GENERATE_PROMPT.format(count=args.count)

    result = call_writer(prompt, max_tokens=8192)
    print(result)
    print("\n" + "=" * 60)
    print("要挑选一个种子，请将你喜欢的概念复制到 seed.txt 中：")
    print("  nano seed.txt")
    print("或者将几个概念重新组合成你自己的种子。")
    print("然后继续 WORKFLOW.md 中的第 2 步。")


if __name__ == "__main__":
    main()
