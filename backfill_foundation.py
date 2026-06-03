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

def backfill_characters(char_text, outline_text, total_volumes):
    prompt = f"""我们之前生成了一份《characters.md》，但其中的角色索引表、反派轮换表、角色登场计划表以及核心角色的「长篇弧光规划」都只规划到了前中期。
现在我们已经生成了全书完整的总纲（共 {total_volumes} 卷）。
请根据【全书总纲】，输出补充和更新后的角色设定内容。

【全书总纲】：
{outline_text}

【当前的 characters.md】（供参考）：
{char_text}

请严格按以下格式输出更新后的 4 个部分内容，**用分隔符 `|||---|||` 隔开每一部分**：

【第一部分：角色索引表】
输出完整的表格，包含卷4到第 {total_volumes} 卷需要出场的关键配角。格式：
## 1. 角色索引表（卷4+角色）
| 角色ID | 姓名 | 身份 | 登场卷号 | 退场卷号 | 核心动机 | 与主角关系 |
|||---|||
【第二部分：反派轮换表】
输出完整的反派轮换表格，覆盖从卷1到第 {total_volumes} 卷的所有层级反派。格式：
## 2. 反派轮换表
| 层级 | 活跃卷号 | 反派名称 | 反派类型 | 核心动机 | 退场方式 | 对主角的威胁类型 |
|||---|||
【第三部分：角色登场计划表】
输出 YAML 格式的活跃角色列表，补充后续关键卷（如卷8, 卷12, 卷15, 卷20等，不需要列出全部25卷，挑重点卷即可）。格式：
## 3. 角色登场计划表（YAML格式）
```yaml
...
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
    if len(parts) >= 4:
        part1_idx = parts[0].strip()
        part2_ant = parts[1].strip()
        part3_yaml = parts[2].strip()
        part4_arcs = parts[3].strip()
        
        # 替换 1. 角色索引表
        char_text = re.sub(
            r'## 1\. 角色索引表（卷4\+角色）.*?(?=## 2\. 反派轮换表)',
            part1_idx + "\n\n",
            char_text,
            flags=re.DOTALL
        )
        # 替换 2. 反派轮换表
        char_text = re.sub(
            r'## 2\. 反派轮换表.*?(?=## 3\. 角色登场计划表)',
            part2_ant + "\n\n",
            char_text,
            flags=re.DOTALL
        )
        # 替换 3. 角色登场计划表
        char_text = re.sub(
            r'## 3\. 角色登场计划表（YAML格式）.*?(?=---)',
            part3_yaml + "\n\n",
            char_text,
            flags=re.DOTALL
        )
        
        # 将补充的弧光阶段插入到对应的角色块中
        for block in re.finditer(r'### \d+\. (.+?)\n.*?(?=### \d+\. |## \d+\. |---)', part4_arcs, re.DOTALL):
            char_name = block.group(1).strip()
            # 从 block 中提取阶段列表
            stages = re.findall(r'- 阶段\d+.*?(?=\n- |\n### |$)', block.group(0), re.DOTALL)
            stages_text = "\n".join(s.strip() for s in stages)
            
            if stages_text:
                # 在原 char_text 中找到该角色的 "长篇弧光规划" 部分，并在其末尾追加
                char_pattern = re.compile(rf'(### \d+\. {re.escape(char_name)}.*?\*\*长篇弧光规划\*\*.*?)(?=\n\*\*性格与行为\*\*|\n\*\*)', re.DOTALL)
                match = char_pattern.search(char_text)
                if match:
                    orig_arc = match.group(1).strip()
                    new_arc = orig_arc + "\n" + stages_text + "\n"
                    char_text = char_text[:match.start()] + new_arc + char_text[match.end():]

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
