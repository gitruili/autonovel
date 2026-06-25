#!/usr/bin/env python3
"""
gen_world_sketch.py -- 轻量世界观草稿生成器（Foundation 阶段 Step 1）。
从 seed.txt 提取 5 个核心参数（~300-500字），输出 world_sketch.md。
用于"总纲先行"流程——总纲只需要核心参数作为设定锚点，不需要完整 world.md。
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


def call_writer(prompt, max_tokens=2000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        system="你是一个精确的信息提取器。从网文种子概念中提取关键的世界观参数，用最精简的语言输出，不添加任何额外的描述或解释。",
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )


seed = (BASE_DIR / "seed.txt").read_text(encoding="utf-8")

prompt = f"""从以下{genre.display_name}网文的种子概念中，提取核心世界观参数。
这是为全书总纲设计提供最基础的设定锚点——不需要详细展开，只需要精确的要点。

种子概念 (SEED):
{seed}

请严格按以下格式输出，每个参数 1-3 句话，总字数不超过 300 字：

## 时代背景
[具体年代和时代特征，如"1998年，中国二线城市，下岗潮末尾，个体经济兴起"]

## 货币体系
[核心货币和量级，如"人民币（元/万），初期月收入千元级，后期扩张至亿元级"]

## 科技阶段
[关键技术特征和信息传播方式，如"BB机→手机过渡期，互联网论坛兴起，短信是主流通讯"]

## 核心舞台
[主要城市/区域及环境特征，如"A城，轻工业转型中的二线城市，老城区筒子楼与新开发区并存"]

## 社会阶层
[主要社会分层和阶层流动通道，如"工薪阶层/下岗工人/个体户/乡镇企业主/早期民营企业家/科研人员"]

只输出以上 5 个参数，不要任何前言、总结或额外描述。
"""

print("正在生成轻量世界观草稿...", file=sys.stderr)
result = call_writer(prompt)

# Save
with open(BASE_DIR / "world_sketch.md", "w", encoding="utf-8") as f:
    f.write(result)

print(f"已保存 world_sketch.md ({len(result)} 字符)", file=sys.stderr)
