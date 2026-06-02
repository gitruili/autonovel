#!/usr/bin/env python3
"""
gen_briefs.py -- 生成浓缩设定摘要 (Foundation 阶段)。
将几万字的 world.md 和 characters.md 浓缩为带结构化约束的摘要版本，
避免下游脚本因 max_tokens 截断而丢失关键信息。
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

genre = load_genre_for_project()

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)

def call_writer(prompt, max_tokens=8000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        system=genre.get_system_prompt("architect"),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
    )

def generate_world_brief():
    world_path = BASE_DIR / "world.md"
    if not world_path.exists():
        print("world.md 不存在，跳过 world_brief 生成。")
        return
        
    world_content = world_path.read_text(encoding="utf-8")
    
    prompt = f"""请将以下长篇世界观设定集（约几万字）浓缩为 3000 字以内的精华摘要。
这是为了给下游生成脚本提供上下文，必须保留关键结构，去掉繁复的文学描写。

【必须保留的核心要素】：
1. 世界观速查表中的所有硬性参数（时代、货币、科技阶段）
2. 所有的扩展路线锚点（未来卷号解锁的地名/势力等）
3. 金手指/系统核心规则及其代价
4. 最重要的几条核心逻辑与限制

原文档：
{world_content}

请直接输出浓缩后的 Markdown 内容，不要有任何前言或总结语句。
"""
    print("正在生成 world_brief.md...", file=sys.stderr)
    result = call_writer(prompt)
    with open(BASE_DIR / "world_brief.md", "w", encoding="utf-8") as f:
        f.write(result)
    print(f"已保存 world_brief.md ({len(result)} 字符)", file=sys.stderr)


def generate_characters_brief():
    char_path = BASE_DIR / "characters.md"
    if not char_path.exists():
        print("characters.md 不存在，跳过 characters_brief 生成。")
        return
        
    char_content = char_path.read_text(encoding="utf-8")
    
    prompt = f"""请将以下角色注册表（约几万字）浓缩为 3000 字以内的精华摘要。
这是为了给下游生成脚本提供上下文，避免超长截断导致丢失卷级角色的信息。

【必须保留的核心要素】：
1. 角色索引表（包含所有卷4+角色的简要信息和登场退场卷号）
2. 反派轮换表（完全保留）
3. 角色登场计划表 YAML 数据（完全保留）
4. 核心角色（第一层）的简明档案：只保留姓名、身份、一句话核心性格/驱动力。省略详细外貌、示例对话和身体习惯等长文本描写。
5. 卷1-3 角色（第二层）：保留姓名、身份、登场卷号和核心作用。

原文档：
{char_content}

请直接输出浓缩后的 Markdown 内容，不要有任何前言或总结语句。
"""
    print("正在生成 characters_brief.md...", file=sys.stderr)
    result = call_writer(prompt)
    with open(BASE_DIR / "characters_brief.md", "w", encoding="utf-8") as f:
        f.write(result)
    print(f"已保存 characters_brief.md ({len(result)} 字符)", file=sys.stderr)

if __name__ == "__main__":
    generate_world_brief()
    generate_characters_brief()
    print("浓缩摘要生成完成！", file=sys.stderr)
