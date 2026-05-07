#!/usr/bin/env python3
"""
Deep manuscript review via the configured review model.
通过配置的审阅模型进行深度全书审阅。

发送全本书稿给模型，进行双重人格审阅：
  1. 文学评论家 (报纸书评风格)
  2. 创意写作教授 (提供具体、可操作的创作建议)

用法:
  python review.py                    # 进行审阅，保存至 edit_logs/
  python review.py --output reviews.md  # 同时保存一份人类可读的副本
  python review.py --parse            # 解析最近一次审阅结果为可操作项
"""
import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from llm_client import (
    call_text_model,
    default_model_for_role,
    get_api_key,
    provider_api_key_env,
)

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

# 审阅模型，默认为配置的角色，可以在 .env 中覆盖
REVIEW_MODEL = os.environ.get(
    "AUTONOVEL_REVIEW_MODEL",
    default_model_for_role("review", "claude-opus-4-6"),
)

CHAPTERS_DIR = BASE_DIR / "chapters"
LOGS_DIR = BASE_DIR / "edit_logs"

REVIEW_PROMPT = """请阅读下面的小说《{title}》。
首先请作为一名【文学评论家】（类似报纸书评风格）撰写一段综述；
然后请作为一名【创意写作教授】，针对你发现的任何缺陷提供具体、可操作的修改建议。

请保持公正但诚实的态度。如果你认为小说已经非常完美，不必强行寻找缺陷。

在【创意写作教授】的建议部分，请务必使用以下格式：
1. [严重程度] 建议标题
   - 问题描述：...
   - 修改建议：...

严重程度请标注为：重大、中等、轻微。

{manuscript}"""


def call_opus(prompt, max_tokens=8000):
    """调用配置的审阅模型处理全本手稿。"""
    print(f"正在发送至 {REVIEW_MODEL} ({len(prompt):,} 字符)...", file=sys.stderr)
    return call_text_model(
        model=REVIEW_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
        include_beta=True,
    )


def get_title():
    """从第一章或大纲中提取小说标题。"""
    outline = BASE_DIR / "outline.md"
    if outline.exists():
        first_line = outline.read_text().split("\n")[0]
        title = first_line.lstrip("# ").strip()
        if title:
            return title
    ch1 = CHAPTERS_DIR / "ch_01.md"
    if ch1.exists():
        first_line = ch1.read_text().split("\n")[0]
        return first_line.lstrip("# ").strip()
    return "未命名小说"


def build_manuscript():
    """将所有章节合并为一个文本。"""
    chapters = sorted(CHAPTERS_DIR.glob("ch_*.md"))
    if not chapters:
        print("错误：未找到任何章节文件。", file=sys.stderr)
        sys.exit(1)
    
    parts = []
    for ch in chapters:
        parts.append(ch.read_text())
    
    manuscript = "\n\n---\n\n".join(parts)
    wc = len(manuscript.split())
    print(f"手稿：{len(chapters)} 章节, {wc:,} 字/词", file=sys.stderr)
    return manuscript


def parse_review(review_text):
    """将审阅文本解析为结构化的可操作项。"""
    items = []
    
    # 分割评论家和教授部分
    sections = re.split(r'(?:教授|PROFESSOR|professor|写作建议|建议部分)', 
                        review_text, maxsplit=1)
    
    critic_text = sections[0] if sections else review_text
    professor_text = sections[1] if len(sections) > 1 else ""
    
    # 提取星级评分 (寻找 ★ 或 "评分: X/5")
    star_match = re.search(r'★+½?|评分[:：]\s*(\d+\.?\d*)', review_text)
    stars = None
    if star_match:
        star_str = star_match.group(0)
        if '★' in star_str:
            stars = star_str.count('★') + (0.5 if '½' in star_str else 0)
        else:
            try:
                stars = float(star_match.group(1))
            except: pass
    
    # 提取教授的编号条目
    prof_items = re.split(r'\n(?=\d+[\.、]\s*[\[【])', professor_text)
    
    for section in prof_items:
        if not section.strip():
            continue
        
        # 提取条目编号、严重程度和标题
        # 匹配格式如: 1. [重大] 建议标题
        title_match = re.search(r'(\d+)[\.、]\s*[\[【](.+?)[\]】]\s*(.+?)(?:\n|$)', section)
        if not title_match:
            continue
        
        num = int(title_match.group(1))
        severity_raw = title_match.group(2).strip()
        title = title_match.group(3).strip()
        
        # 映射严重程度
        sev_map = {"重大": "major", "中等": "moderate", "轻微": "minor"}
        severity = "moderate"
        for k, v in sev_map.items():
            if k in severity_raw:
                severity = v
                break
        
        # 尝试分类修改类型
        text_lower = section.lower()
        if any(w in text_lower for w in ['删减', '冗余', '瘦身', '压缩', 'cut', 'compress']):
            fix_type = "compression"
        elif any(w in text_lower for w in ['增加', '展开', '细节', '补充', 'add', 'expand']):
            fix_type = "addition"  
        elif any(w in text_lower for w in ['重复', '惯用语', '口癖', '重复性', 'repetit']):
            fix_type = "mechanical"
        elif any(w in text_lower for w in ['结构', '节奏', '调整', '顺序', 'structur']):
            fix_type = "structural"
        else:
            fix_type = "revision"
        
    # 检查是否为“带有保留意见/委婉的” (作为停止信号)
        qualified = any(phrase in text_lower for phrase in [
            '本身很好', '基本成功', '算不上缺陷', '有意的选择', '符合设定',
            '已经不错', '瑕不掩瑜', '作为权衡'
        ])
        
        # 提取具体建议
        suggestion = ""
        sugg_match = re.search(r'(?:修改建议|建议)[:：]\s*\n?(.*?)(?=\n\d+[\.、]|\n\n[A-Z]|\Z)', 
                               section, re.DOTALL)
        if sugg_match:
            suggestion = sugg_match.group(1).strip()[:500]
        
        items.append({
            "number": num,
            "title": title,
            "severity": severity,
            "type": fix_type,
            "qualified": qualified,
            "suggestion": suggestion,
            "full_text": section.strip()[:1000],
        })
    
    return {
        "stars": stars,
        "critic_summary": critic_text.strip()[:500],
        "professor_items": items,
        "total_items": len(items),
        "major_items": sum(1 for i in items if i["severity"] == "major"),
        "qualified_items": sum(1 for i in items if i["qualified"]),
        "raw_text": review_text,
    }


def should_stop(parsed_review):
    """判断小说是否修订完成。
    
    停止条件：
    - 评分 >= 4.5 且无重大缺陷
    - 或者 评分 >= 4 且超过一半的建议是委婉的/建议性的
    - 或者 总建议数 <= 2
    """
    stars = parsed_review.get("stars", 0) or 0
    total = parsed_review["total_items"]
    major = parsed_review["major_items"]
    qualified = parsed_review["qualified_items"]
    
    if stars >= 4.5 and major == 0:
        return True, "评分 4.5 且无重大缺陷"
    if stars >= 4 and total > 0 and qualified / total > 0.5:
        return True, f"评分 {stars} 且 {qualified}/{total} 条建议为保留意见"
    if total <= 2:
        return True, f"仅发现 {total} 条建议"
    
    return False, f"仍有 {major} 个重大问题，{total - qualified} 个非保留意见"


def cmd_review(args):
    """执行审阅。"""
    title = get_title()
    manuscript = build_manuscript()
    
    prompt = REVIEW_PROMPT.format(title=title, manuscript=manuscript)
    
    review_text = call_opus(prompt)
    
    # 保存原始审阅结果
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"{timestamp}_review.json"
    
    parsed = parse_review(review_text)
    parsed["timestamp"] = timestamp
    parsed["title"] = title
    parsed["word_count"] = len(manuscript.split())
    
    log_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n审阅报告已保存至 {log_path}", file=sys.stderr)
    
    # 保存可读副本
    if args.output:
        Path(args.output).write_text(review_text, encoding="utf-8")
        print(f"人类可读副本：{args.output}", file=sys.stderr)
    
    # 打印摘要
    stop, reason = should_stop(parsed)
    print(f"\n{'='*50}")
    print(f"审阅摘要 (REVIEW SUMMARY)")
    print(f"  星级: {parsed['stars'] or '?'}")
    print(f"  建议数: {parsed['total_items']} (重大问题: {parsed['major_items']})")
    print(f"  保留意见比例: {parsed['qualified_items']}/{parsed['total_items']}")
    print(f"  是否停止修订? {'是 —— ' + reason if stop else '否 —— ' + reason}")
    print(f"{'='*50}")
    
    return parsed


def cmd_parse(args):
    """解析最近一次审阅结果。"""
    LOGS_DIR.mkdir(exist_ok=True)
    reviews = sorted(LOGS_DIR.glob("*_review.json"), reverse=True)
    if not reviews:
        print("未找到审阅报告。请先运行: review.py")
        sys.exit(1)
    
    latest = json.loads(reviews[0].read_text(encoding="utf-8"))
    
    print(f"最新审阅时间: {latest.get('timestamp', '未知')}")
    print(f"星级: {latest.get('stars', '?')}")
    print(f"\n待处理项 ({latest['total_items']}):")
    
    for item in latest.get("professor_items", []):
        qual = " [已达到较好水平/保留意见]" if item["qualified"] else ""
        print(f"\n  {item['number']}. [{item['severity'].upper()}] [{item['type']}]{qual}")
        print(f"     标题: {item['title']}")
        if item["suggestion"]:
            print(f"     建议: {item['suggestion'][:120]}...")
    
    stop, reason = should_stop(latest)
    print(f"\n{'='*50}")
    print(f"是否停止修订? {'是 —— ' + reason if stop else '否 —— ' + reason}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="深度书稿审阅工具")
    parser.add_argument("--output", "-o", default=None, help="将可读审阅结果保存至文件")
    parser.add_argument("--parse", action="store_true", help="解析最近一次审阅结果")
    
    args = parser.parse_args()
    
    if not get_api_key():
        print(f"错误：.env 中未设置 {provider_api_key_env()}", file=sys.stderr)
        sys.exit(1)
    
    if args.parse:
        cmd_parse(args)
    else:
        cmd_review(args)


if __name__ == "__main__":
    main()
