#!/usr/bin/env python3
"""
init_state.py -- 长篇 Foundation 状态初始化脚本。
从 foundation 文档中提取结构化数据，初始化 story/state/*.json。
混合逻辑：确定性提取 + LLM 辅助提取。
"""
import json
import os
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from llm_client import call_text_model, default_model_for_role
from story_schema import (
    Character,
    CharacterMatrix,
    CurrentState,
    EmotionalArc,
    EmotionalArcs,
    ForeshadowHook,
    PendingHooks,
    PowerLedgerFull,
    ProjectConfig,
    Resource,
    Subplot,
    SubplotBoard,
    save_json,
    load_yaml,
)

BASE_DIR = Path(__file__).parent
STORY_DIR = BASE_DIR / "story"
STATE_DIR = STORY_DIR / "state"
PLANS_DIR = STORY_DIR / "plans"

load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)


def call_llm(prompt, max_tokens=8000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        system=(
            "你是一个数据提取助手。从给定的 Markdown 文档中提取结构化信息，"
            "输出合法的 YAML 格式。不要添加任何解释，只输出 YAML。"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )


# ──────────────────────────────────────────────────────────────
#  1. Project Config (deterministic)
# ──────────────────────────────────────────────────────────────
def init_project():
    master = load_yaml(PLANS_DIR / "master_plan.yaml")
    proj_path = STORY_DIR / "project.json"

    # Merge with existing project.json if it exists
    existing = {}
    if proj_path.exists():
        with open(proj_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    proj = ProjectConfig(
        title=master.get("title", existing.get("title", "")),
        genre=master.get("genre", existing.get("genre", "")),
        target_words=master.get("target_words", existing.get("target_words", 1_000_000)),
        target_chapters=master.get("total_chapters", existing.get("target_chapters", 500)),
        current_volume=1,
        current_chapter=0,
        current_chars=0,
        phase="planning",
        status="active",
    )
    save_json(proj_path, proj.model_dump())
    print(f"  [OK] project.json: {proj.title}", file=sys.stderr)
    return proj


# ──────────────────────────────────────────────────────────────
#  2. Character Matrix (LLM-assisted)
# ──────────────────────────────────────────────────────────────
def init_character_matrix():
    characters_md = (BASE_DIR / "characters.md").read_text()

    prompt = f"""从以下角色注册表中提取所有核心角色（第一层）和卷1-3登场角色（第二层前半部分）的信息。
为每个角色生成一个 JSON 对象，格式如下：

```yaml
characters:
  char_角色id:
    name: "角色名"
    role: "protagonist"  # protagonist | antagonist | supporting | minor
    age: 25
    gender: "女"
    personality: "性格核心描述"
    speech_pattern: "说话特征描述"
    appearance: "外貌速写"
    background: "背景简介"
    motivation: "核心动机"
    arc_summary: "弧光概述"
    secrets: ["秘密1", "秘密2"]
    relationships:
      char_其他角色id: "关系描述"
```

角色注册表内容：
{characters_md[:10000]}

要求：
1. 角色ID使用 char_拼音小写 的格式（如 char_aheng, char_chenyu）
2. relationships 中引用的 char_id 必须与 characters 字典中的 key 一致
3. 只提取第一层（核心角色）和第二层中"卷1-3登场"的角色
4. 输出合法的 YAML
"""

    print("  正在提取角色数据...", file=sys.stderr)
    result = call_llm(prompt)

    # Parse YAML
    try:
        # Try to extract YAML block
        yaml_match = re.search(r'```yaml\s*\n(.*?)```', result, re.DOTALL)
        yaml_str = yaml_match.group(1).strip() if yaml_match else result.strip()
        data = yaml.safe_load(yaml_str)
    except Exception as e:
        print(f"  [WARN] YAML parse failed, trying fallback: {e}", file=sys.stderr)
        data = {"characters": {}}

    # Convert to CharacterMatrix
    char_matrix = CharacterMatrix()
    raw_chars = data.get("characters", {})
    for char_id, char_data in raw_chars.items():
        if not isinstance(char_data, dict):
            continue
        char = Character(
            id=char_id,
            name=char_data.get("name", ""),
            role=char_data.get("role", "supporting"),
            age=char_data.get("age"),
            gender=char_data.get("gender", ""),
            personality=char_data.get("personality", ""),
            speech_pattern=char_data.get("speech_pattern", ""),
            appearance=char_data.get("appearance", ""),
            background=char_data.get("background", ""),
            motivation=char_data.get("motivation", ""),
            arc_summary=char_data.get("arc_summary", ""),
            secrets=char_data.get("secrets", []),
            relationships=char_data.get("relationships", {}),
            source_chapter=0,
            valid_from_chapter=1,
            status="active",
        )
        char_matrix.characters[char_id] = char

    save_json(STATE_DIR / "character_matrix.json", char_matrix.model_dump())
    print(f"  [OK] character_matrix.json: {len(char_matrix.characters)} 个角色", file=sys.stderr)
    return char_matrix


# ──────────────────────────────────────────────────────────────
#  3. Pending Hooks (LLM-assisted)
# ──────────────────────────────────────────────────────────────
def init_pending_hooks():
    outline = (BASE_DIR / "outline.md").read_text()
    master = load_yaml(PLANS_DIR / "master_plan.yaml")

    # Collect hooks from master plan
    master_hooks = []
    for lf in master.get("long_foreshadows", []):
        master_hooks.append({
            "id": lf.get("id", "lf_000"),
            "description": lf.get("description", ""),
            "plant_volume": lf.get("plant_volume", 1),
            "payoff_volume": lf.get("payoff_volume"),
        })

    prompt = f"""从以下第一卷大纲中提取所有"伏笔植入"条目。
同时参考全书总纲中的超长线伏笔。

为每个伏笔生成一个 JSON 对象，格式如下：

```yaml
hooks:
  hook_001:
    description: "伏笔描述"
    hook_type: "setup"  # setup | advance | payoff
    planted_chapter: 1
    expected_payoff_chapter: null  # 如果不知道具体章节就写null
    related_characters: ["char_角色id"]
    related_locations: []
    urgency: "normal"
```

第一卷大纲（截取伏笔相关部分）：
{outline[:6000]}

全书超长线伏笔：
{json.dumps(master_hooks, ensure_ascii=False, indent=2)}

要求：
1. 伏笔ID使用 hook_数字 格式
2. 只提取"伏笔植入"和超长线伏笔
3. related_characters 中的 ID 必须与 character_matrix 中的 ID 一致
4. 输出合法的 YAML
"""

    print("  正在提取伏笔数据...", file=sys.stderr)
    result = call_llm(prompt)

    try:
        yaml_match = re.search(r'```yaml\s*\n(.*?)```', result, re.DOTALL)
        yaml_str = yaml_match.group(1).strip() if yaml_match else result.strip()
        data = yaml.safe_load(yaml_str)
    except Exception as e:
        print(f"  [WARN] YAML parse failed: {e}", file=sys.stderr)
        data = {"hooks": {}}

    hooks = PendingHooks()
    raw_hooks = data.get("hooks", {})
    for hook_id, hook_data in raw_hooks.items():
        if not isinstance(hook_data, dict):
            continue
        hook = ForeshadowHook(
            id=hook_id,
            description=hook_data.get("description", ""),
            hook_type=hook_data.get("hook_type", "setup"),
            planted_chapter=hook_data.get("planted_chapter", 0),
            expected_payoff_chapter=hook_data.get("expected_payoff_chapter"),
            related_characters=hook_data.get("related_characters", []),
            related_locations=hook_data.get("related_locations", []),
            urgency=hook_data.get("urgency", "normal"),
            source_chapter=hook_data.get("planted_chapter", 0),
            valid_from_chapter=hook_data.get("planted_chapter", 0),
        )
        hooks.hooks[hook_id] = hook

    save_json(STATE_DIR / "pending_hooks.json", hooks.model_dump())
    print(f"  [OK] pending_hooks.json: {len(hooks.hooks)} 条伏笔", file=sys.stderr)


# ──────────────────────────────────────────────────────────────
#  4. Subplot Board (LLM-assisted)
# ──────────────────────────────────────────────────────────────
def init_subplot_board():
    outline = (BASE_DIR / "outline.md").read_text()

    prompt = f"""从以下第一卷大纲中提取主要子线（subplot）。
子线是指与主线并行的次要故事线（如：小叔子的成长线、与王婆的竞争线等）。

为每个子线生成一个 JSON 对象，格式如下：

```yaml
subplots:
  subplot_001:
    name: "子线名称"
    description: "子线描述"
    status: "active"
    related_characters: ["char_角色id"]
    chapters_involved: [1, 3, 5, 8]
    tension_level: "building"
```

第一卷大纲：
{outline[:6000]}

要求：
1. 子线ID使用 subplot_数字 格式
2. 只提取第一卷中明确的子线
3. tension_level: building | climax | resolution
4. 输出合法的 YAML
"""

    print("  正在提取子线数据...", file=sys.stderr)
    result = call_llm(prompt)

    try:
        yaml_match = re.search(r'```yaml\s*\n(.*?)```', result, re.DOTALL)
        yaml_str = yaml_match.group(1).strip() if yaml_match else result.strip()
        data = yaml.safe_load(yaml_str)
    except Exception as e:
        print(f"  [WARN] YAML parse failed: {e}", file=sys.stderr)
        data = {"subplots": {}}

    board = SubplotBoard()
    raw_subplots = data.get("subplots", {})
    for sp_id, sp_data in raw_subplots.items():
        if not isinstance(sp_data, dict):
            continue
        subplot = Subplot(
            id=sp_id,
            name=sp_data.get("name", ""),
            description=sp_data.get("description", ""),
            status=sp_data.get("status", "active"),
            related_characters=sp_data.get("related_characters", []),
            chapters_involved=sp_data.get("chapters_involved", []),
            tension_level=sp_data.get("tension_level", "building"),
        )
        board.subplots[sp_id] = subplot

    save_json(STATE_DIR / "subplot_board.json", board.model_dump())
    print(f"  [OK] subplot_board.json: {len(board.subplots)} 条子线", file=sys.stderr)


# ──────────────────────────────────────────────────────────────
#  5. Current State (deterministic from seed + world)
# ──────────────────────────────────────────────────────────────
def init_current_state():
    seed = (BASE_DIR / "seed.txt").read_text()
    world = (BASE_DIR / "world.md").read_text()
    master = load_yaml(PLANS_DIR / "master_plan.yaml")

    # Extract initial location from seed
    location = ""
    for line in seed.split("\n"):
        if "边关" in line or "寨" in line or "村" in line:
            location = line.strip()[:50]
            break
    if not location:
        location = "故事开始的地方"

    # Extract active plot threads from V1
    v1 = master.get("volumes", [{}])[0] if master.get("volumes") else {}
    threads = []
    if v1.get("main_arc"):
        threads.append(v1["main_arc"])
    threads.extend(["家庭关系建立", "首次经营尝试"])

    # Determine season from world
    season = "春"
    for kw, s in [("春季", "春"), ("夏季", "夏"), ("秋季", "秋"), ("冬季", "冬")]:
        if kw in world[:2000]:
            season = s
            break

    state = CurrentState(
        timeline_position="故事开始",
        current_location=location,
        active_plot_threads=threads,
        recent_events=[],
        world_conditions={"season": season, "war_status": "胶着"},
    )
    save_json(STATE_DIR / "current_state.json", state.model_dump())
    print(f"  [OK] current_state.json", file=sys.stderr)


# ──────────────────────────────────────────────────────────────
#  6. Power Ledger (deterministic from world.md)
# ──────────────────────────────────────────────────────────────
def init_power_ledger():
    world = (BASE_DIR / "world.md").read_text()
    seed = (BASE_DIR / "seed.txt").read_text()

    # Extract currency info from world.md
    resources = {}

    # Try to find currency mentions
    if "铜" in world:
        resources["res_copper"] = Resource(
            id="res_copper", name="铜钱", category="currency",
            quantity=0, unit="文", owner="", location="",
        )
    if "银" in world:
        resources["res_silver"] = Resource(
            id="res_silver", name="银两", category="currency",
            quantity=0, unit="两", owner="", location="",
        )

    # Extract initial food/materials from seed
    # Look for specific quantities mentioned
    grain_match = re.search(r'(\d+).*?(?:粟|米|粮)', seed)
    if grain_match:
        resources["res_millet"] = Resource(
            id="res_millet", name="粟米", category="food",
            quantity=float(grain_match.group(1)), unit="斤", owner="", location="",
        )

    # Add common starting resources
    resources["res_firewood"] = Resource(
        id="res_firewood", name="柴火", category="material",
        quantity=0, unit="捆", owner="", location="",
    )
    resources["res_water"] = Resource(
        id="res_water", name="饮用水", category="material",
        quantity=0, unit="缸", owner="", location="",
    )

    ledger = PowerLedgerFull(
        power_system="经济体系",
        levels=[],
        level_names=[],
        resources=resources,
        items={},
    )
    save_json(STATE_DIR / "power_ledger.json", ledger.model_dump())
    print(f"  [OK] power_ledger.json: {len(resources)} 种资源", file=sys.stderr)


# ──────────────────────────────────────────────────────────────
#  7. Chapter Summaries (empty)
# ──────────────────────────────────────────────────────────────
def init_chapter_summaries():
    save_json(STATE_DIR / "chapter_summaries.json", {"summaries": {}})
    print(f"  [OK] chapter_summaries.json (空)", file=sys.stderr)


# ──────────────────────────────────────────────────────────────
#  8. Emotional Arcs (from master plan romance arc)
# ──────────────────────────────────────────────────────────────
def init_emotional_arcs():
    master = load_yaml(PLANS_DIR / "master_plan.yaml")
    char_matrix = {}
    cm_path = STATE_DIR / "character_matrix.json"
    if cm_path.exists():
        with open(cm_path, "r", encoding="utf-8") as f:
            cm_data = json.load(f)
            char_matrix = cm_data.get("characters", {})

    arcs = EmotionalArcs()

    # Find female lead and male lead from character matrix
    female_lead_id = None
    male_lead_id = None
    for char_id, char_data in char_matrix.items():
        role = char_data.get("role", "")
        gender = char_data.get("gender", "")
        if role == "protagonist" and gender == "女":
            female_lead_id = char_id
        elif role == "protagonist" and gender == "男":
            male_lead_id = char_id
        elif "男" in char_data.get("name", "") or "男主" in char_data.get("role", ""):
            male_lead_id = char_id

    if not female_lead_id:
        female_lead_id = "char_unknown_fl"
    if not male_lead_id:
        male_lead_id = "char_unknown_ml"

    # Create initial emotional arcs from romance plan
    romance_phases = master.get("romance_arc", [])
    if romance_phases:
        phase1 = romance_phases[0] if isinstance(romance_phases[0], dict) else {}
        fl_emotion = phase1.get("description", "陌生与好奇")
    else:
        fl_emotion = "陌生与好奇"

    arcs.arcs["arc_fl_v1"] = EmotionalArc(
        id="arc_fl_v1",
        character_id=female_lead_id,
        emotion=fl_emotion,
        intensity=0.2,
        trigger="与男主的初次相遇",
        resolution="",
        start_chapter=1,
        peak_chapter=None,
        end_chapter=None,
        source_chapter=0,
        valid_from_chapter=1,
    )

    arcs.arcs["arc_ml_v1"] = EmotionalArc(
        id="arc_ml_v1",
        character_id=male_lead_id,
        emotion="观察与保留",
        intensity=0.15,
        trigger="女主的出现",
        resolution="",
        start_chapter=1,
        peak_chapter=None,
        end_chapter=None,
        source_chapter=0,
        valid_from_chapter=1,
    )

    save_json(STATE_DIR / "emotional_arcs.json", arcs.model_dump())
    print(f"  [OK] emotional_arcs.json: {len(arcs.arcs)} 条弧线", file=sys.stderr)


# ──────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────
def main():
    print("正在初始化长篇 Foundation 状态...", file=sys.stderr)

    # Ensure directories exist
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Run all initializations
    proj = init_project()
    init_character_matrix()
    init_pending_hooks()
    init_subplot_board()
    init_current_state()
    init_power_ledger()
    init_chapter_summaries()
    init_emotional_arcs()

    print("\n状态初始化完成！", file=sys.stderr)
    print(f"  项目: {proj.title}", file=sys.stderr)
    print(f"  目标: {proj.target_words:,} 字 / {proj.target_chapters} 章", file=sys.stderr)
    print(f"  状态文件: {STATE_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
