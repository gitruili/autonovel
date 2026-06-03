#!/usr/bin/env python3
"""
backfill_foundation.py -- Foundation 阶段后处理脚本。
读取 gen_master_outline.py 生成的全书总纲（25卷），
反哺更新 world.md（补全扩展路线图）和 characters.md（补全角色、反派、弧光）。
"""
import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
from llm_client import call_text_model, default_model_for_role
from genres.genre_registry import load_genre_for_project
from story_schema import load_project_tags, load_json

load_dotenv(BASE_DIR / ".env")

genre = load_genre_for_project()

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)

import time

def call_writer(prompt, max_tokens=16000):
    for attempt in range(3):
        try:
            return call_text_model(
                model=WRITER_MODEL,
                max_tokens=max_tokens,
                temperature=0.5,
                system="你是一个资深的网文架构师。你需要根据已经确定的全书总纲，补全前期的设定文件（world.md 和 characters.md）中缺失的后半部设定。严格按照要求的格式输出，不要输出多余的解释性文字。",
                messages=[{"role": "user", "content": prompt}],
                timeout=600,
                include_beta=True,
            )
        except Exception as e:
            print(f"调用 LLM 失败 (尝试 {attempt+1}/3): {e}", file=sys.stderr)
            if attempt == 2:
                raise
            time.sleep(2)

def backfill_world(world_text, outline_text, total_volumes):
    prompt = f"""我们之前生成了一份《world.md》，但其中的「Part B: 扩展路线图」只规划到了前中期（约10卷左右）。
现在我们已经生成了全书完整的总纲（共 {total_volumes} 卷）。
请根据【全书总纲】，重写《world.md》中的「Part B: 扩展路线图」，使其涵盖从卷4到第 {total_volumes} 卷的全部扩展。

【全书总纲】：
{outline_text}

【当前的 world.md】（供参考前期的地理和势力）：
{world_text}

请输出完整的「# Part B: 扩展路线图（卷4+ 的世界扩展规划）」，包含：
## 地理扩展锚点（涵盖到大结局的地图扩展）
## 势力/层级扩展（涵盖到大结局的新势力）
## 世界观伏笔锚点（确保全书超长线伏笔的合理分配）

只输出 `# Part B: 扩展路线图` 及其以下的内容，**不要**包含 `# Part 0` 和 `# Part A`。
请确保直接输出 markdown 文本，不要用 markdown 代码块包裹整个输出。
"""
    print("正在反哺更新 world.md 的 Part B 扩展路线图...", file=sys.stderr)
    result = call_writer(prompt)
    
    # 清理多余的 Markdown 代码块
    result = re.sub(r'^```markdown\s*\n', '', result)
    result = re.sub(r'^```\s*\n', '', result)
    result = re.sub(r'\n```\s*$', '', result)
    
    # 查找原本 world.md 中 Part B 的位置
    part_b_index = world_text.find("# Part B: 扩展路线图")
    if part_b_index == -1:
        part_b_index = world_text.find("# Part B")
        
    if part_b_index != -1:
        new_world_text = world_text[:part_b_index] + result.strip() + "\n"
    else:
        new_world_text = world_text + "\n\n" + result.strip() + "\n"
        
    return new_world_text

def _replace_between_markers(text, start_marker, end_marker, new_content):
    """用 new_content 替换 start_marker 和 end_marker 之间的内容（包括 markers 本身）。
    如果找不到 markers，返回原文不做修改。"""
    s = text.find(start_marker)
    e = text.find(end_marker)
    if s == -1 or e == -1:
        return text, False
    e += len(end_marker)
    # 确保新内容也包含 markers
    replacement = start_marker + "\n" + new_content.strip() + "\n" + end_marker
    return text[:s] + replacement + text[e:], True


def backfill_characters(char_text, outline_text, total_volumes):
    prompt = f"""我们之前生成了一份《characters.md》，但其中的角色索引表、反派轮换表、角色登场计划表只规划到了前中期。
现在我们已经生成了全书完整的总纲（共 {total_volumes} 卷）。
请根据【全书总纲】，输出补充和更新后的角色设定内容。

【全书总纲】：
{outline_text}

【当前的 characters.md】（供参考）：
{char_text}

请严格按以下格式输出更新后的 4 个部分内容，**用分隔符 `|||---|||` 隔开每一部分**：

【第一部分：角色索引表】
输出完整的表格，包含卷4到第 {total_volumes} 卷需要出场的关键配角。格式：
## 3. 角色索引表（卷4+角色）
| 角色ID | 姓名 | 身份 | 登场卷号 | 退场卷号 | 核心动机 | 与主角关系 |
|||---|||
【第二部分：反派轮换表】
输出完整的反派轮换表格，覆盖从卷1到第 {total_volumes} 卷的所有层级反派。格式：
## 4. 反派轮换表
| 层级 | 活跃卷号 | 反派名称 | 反派类型 | 核心动机 | 退场方式 | 对主角的威胁类型 |
|||---|||
【第三部分：角色登场计划表】
请**完整输出** YAML 格式的活跃角色列表。
注意：**必须原样保留并抄录原有 characters.md 中的前几卷（如 volume_1 到 volume_5）登场计划**，然后在此基础上追加后续关键卷（如卷8, 卷12, 卷15, 卷20等，挑重点即可）。不要覆盖或遗漏前面的卷！格式：
## 5. 角色登场计划表
```yaml
volume_1_active: ...
# ... (原样保留原有卷)
volume_8_active: ...
# ... (新增后续关键卷)
```
|||---|||
【第四部分：核心角色长篇弧光规划补充】
由于原档案中核心角色的长篇弧光可能只写到了阶段2或阶段3，请为《characters.md》里的每一个核心主角补充后续的弧光阶段（如 阶段4、阶段5、阶段6），直至大结局。
格式如下：
### 1. 苏念 (主角/视角人物)
- 阶段4（卷13-17）：...
- 阶段5（卷18-22）：...
- 阶段6（卷23-25）：...

### 2. 陆司珩 (核心羁绊/伴侣)
- 阶段4（卷13-17）：...
...
（只列出现有核心角色补充的弧光阶段）
"""
    print("正在反哺更新 characters.md 的角色和反派规划...", file=sys.stderr)
    result = call_writer(prompt)

    parts = result.split("|||---|||")
    if len(parts) < 4:
        print(f"警告：LLM 输出只有 {len(parts)} 个部分（预期 4），跳过反哺替换。", file=sys.stderr)
        return char_text

    part1_idx = parts[0].strip()
    part2_ant = parts[1].strip()
    part3_yaml = parts[2].strip()
    part4_arcs = parts[3].strip()

    # 清理每个 part 可能包含的 markdown 代码块包裹
    for _p in [part1_idx, part2_ant, part3_yaml, part4_arcs]:
        _p = re.sub(r'^```markdown\s*\n', '', _p)
        _p = re.sub(r'\n```\s*$', '', _p)

    # ---- 1. 替换角色索引表 ----
    char_text, ok1 = _replace_between_markers(
        char_text, "<!-- ROLE_INDEX_START -->", "<!-- ROLE_INDEX_END -->", part1_idx
    )
    if not ok1:
        print("警告：未找到 ROLE_INDEX markers，尝试正则 fallback...", file=sys.stderr)
        char_text = re.sub(
            r'## \d+\. 角色索引表（卷4\+角色）.*?(?=<!-- VILLAIN|## \d+\. 反派轮换表)',
            part1_idx + "\n\n",
            char_text, flags=re.DOTALL, count=1,
        )

    # ---- 2. 替换反派轮换表 ----
    char_text, ok2 = _replace_between_markers(
        char_text, "<!-- VILLAIN_ROSTER_START -->", "<!-- VILLAIN_ROSTER_END -->", part2_ant
    )
    if not ok2:
        print("警告：未找到 VILLAIN_ROSTER markers，尝试正则 fallback...", file=sys.stderr)
        char_text = re.sub(
            r'## \d+\. 反派轮换表.*?(?=<!-- APPEARANCE|## \d+\. 角色登场计划表)',
            part2_ant + "\n\n",
            char_text, flags=re.DOTALL, count=1,
        )

    # ---- 3. 替换角色登场计划表 ----
    char_text, ok3 = _replace_between_markers(
        char_text, "<!-- APPEARANCE_PLAN_START -->", "<!-- APPEARANCE_PLAN_END -->", part3_yaml
    )
    if not ok3:
        print("警告：未找到 APPEARANCE_PLAN markers，尝试正则 fallback...", file=sys.stderr)
        char_text = re.sub(
            r'## \d+\. 角色登场计划表.*?(?=---|<!-- CORE|<!-- ROLE|$)',
            part3_yaml + "\n\n",
            char_text, flags=re.DOTALL, count=1,
        )

    # ---- 4. 弧光补充：追加为文末新章节 ----
    arc_section_header = "## 6. 全书核心角色长篇弧光（卷4至大结局扩展）"
    arc_marker_start = "<!-- ARC_SUPPLEMENT_START -->"
    arc_marker_end = "<!-- ARC_SUPPLEMENT_END -->"

    new_arc_block = (
        "\n\n---\n\n"
        + arc_marker_start + "\n"
        + arc_section_header + "\n\n"
        + part4_arcs + "\n"
        + arc_marker_end + "\n"
    )

    # 如果文件中已有旧的弧光补充章节，就替换它
    if arc_marker_start in char_text:
        char_text, _ = _replace_between_markers(
            char_text, arc_marker_start, arc_marker_end,
            arc_section_header + "\n\n" + part4_arcs,
        )
    elif arc_section_header in char_text:
        # 有标题但没有 markers（历史遗留），删除旧章节后追加
        idx = char_text.find(arc_section_header)
        char_text = char_text[:idx].rstrip() + new_arc_block
    else:
        # 全新追加到文末
        char_text = char_text.rstrip() + new_arc_block

    return char_text

def main():
    proj_path = BASE_DIR / "story" / "project.json"
    if not proj_path.exists():
        print("未找到 project.json，无法确认全书卷数。跳过反哺。")
        return 0
        
    proj = load_json(proj_path)
    target_chapters = proj.get("target_chapters", 0)
    if target_chapters < 100:
        print("这不是长篇项目（章数 < 100），跳过反哺。")
        return 0
        
    total_volumes = target_chapters // 20
    
    outline_path = BASE_DIR / "outline.md"
    if not outline_path.exists():
        print("未找到 outline.md。")
        return 1
    outline_text = outline_path.read_text(encoding="utf-8")
    
    world_path = BASE_DIR / "world.md"
    if world_path.exists():
        world_text = world_path.read_text(encoding="utf-8")
        new_world_text = backfill_world(world_text, outline_text, total_volumes)
        world_path.write_text(new_world_text, encoding="utf-8")
        print(f"world.md 反哺更新完成。")
        
    char_path = BASE_DIR / "characters.md"
    if char_path.exists():
        char_text = char_path.read_text(encoding="utf-8")
        new_char_text = backfill_characters(char_text, outline_text, total_volumes)
        char_path.write_text(new_char_text, encoding="utf-8")
        print(f"characters.md 反哺更新完成。")

    return 0

if __name__ == "__main__":
    sys.exit(main())
