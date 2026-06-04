#!/usr/bin/env python3
"""
story_schema.py — Pydantic schemas for the webnovel state system.

Defines all structured state files, chapter deltas, and provides
utility functions like count_cn_words() and JSON load/save helpers.
"""

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

_BASE_DIR = Path(__file__).parent
STORY_DIR = _BASE_DIR / "story"


def count_cn_words(text: str) -> int:
    """Count Chinese characters + English words in text.

    Chinese characters each count as 1 word.
    English words (contiguous ASCII letters) count as 1 word each.
    Numbers and punctuation are not counted.
    """
    # Count Chinese characters (CJK Unified Ideographs + common ranges)
    cn_chars = len(re.findall(r'[一-鿿㐀-䶿]', text))
    # Count English words (sequences of ASCII letters)
    en_words = len(re.findall(r'[a-zA-Z]+', text))
    return cn_chars + en_words


def load_json(path: Path) -> dict:
    """Load a JSON file, returning empty dict if missing."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any, indent: int = 2) -> None:
    """Save data to JSON file, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def load_yaml(path: Path) -> dict:
    """Load a YAML file. Requires pyyaml."""
    import yaml
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: Any) -> None:
    """Save data to YAML file."""
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Temporal fields — all important facts must have these
# ---------------------------------------------------------------------------

class TemporalFields(BaseModel):
    """Common temporal tracking fields for state entities."""
    source_chapter: int = Field(default=0, description="Chapter where this fact was first established")
    valid_from_chapter: int = Field(default=0, description="Chapter from which this fact is valid")
    valid_until_chapter: int | None = Field(default=None, description="Chapter after which this fact is no longer valid")
    last_seen_chapter: int = Field(default=0, description="Last chapter where this fact was referenced")
    visibility: str = Field(default="active", description="active | hidden | revealed")
    status: str = Field(default="active", description="active | resolved | expired | contradicted")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence level 0.0-1.0")


# ---------------------------------------------------------------------------
# Project config
# ---------------------------------------------------------------------------

class ProjectConfig(BaseModel):
    """story/project.json — top-level project configuration."""
    title: str = ""
    genre: str = ""
    tags: list[str] = Field(default_factory=list)
    target_words: int = 1_000_000
    target_chapters: int = 500
    default_chapter_chars: int = 4000
    market_research_files: list[str] = Field(default_factory=list)
    current_volume: int = 1
    current_chapter: int = 0
    current_chars: int = 0
    phase: str = "planning"  # planning | writing | revision | completed
    status: str = "active"   # active | paused | archived


# Tag definitions — maps tag name to its creative guidance
TAG_DEFINITIONS: dict[str, str] = {
    "穿越": "女主从现代穿越到古代/异世界，拥有现代知识优势。需要设计穿越契机、原身困境、现代知识的具体应用场景。",
    "重生": "女主重生回到过去，带着前世记忆。需要设计前世死因、重生时间点、前世遗憾的弥补方向。",
    "大女主": "女主是故事的绝对核心，独立自主、有勇有谋。感情线为辅，事业/权力线为主。女主必须自己解决问题，不能依赖男主。",
    "无cp": "没有感情线或感情线极度淡化。故事完全由剧情、事业、成长驱动。适合权谋、生存、探案类型。",
    "萌娃": "核心看点是亲子互动和萌宝成长。需要设计萌娃的性格特点、天赋异禀、与女主的亲情羁绊。萌娃要有自己的成长线。",
    "团宠": "女主/萌娃被周围人宠爱。核心看点是被偏爱的温暖感。需要设计宠爱来源（家人、邻居、男主等）和宠爱方式。",
    "穿书": "女主穿越到一本小说里，知道原书剧情。需要设计原书剧情、女主的身份（炮灰/恶毒女配/路人甲等）、如何利用已知剧情改命。",
    "系统": "女主获得一个系统金手指。需要设计系统类型、任务机制、奖励体系、系统限制。系统不能让女主无敌。",
    "空间": "女主拥有随身空间。需要设计空间大小、功能、进入限制、升级条件。空间是辅助工具而非万能解决方案。",
    "美食": "核心看点是美食制作和经营。需要设计拿手菜系、食材来源、餐饮经营升级路线。美食描写要具体有食欲。",
    "医术": "女主擅长医术/药膳。需要设计医术来源、擅长领域、行医升级路线。医术要有限制，不能包治百病。",
    "经商": "核心看点是商业经营和财富积累。需要设计经营品类、商业策略、从小摊贩到大商人的升级路线。",
    "年代": "故事设定在1950s-1990s中国。需要设计具体年代、地点（城市/农村）、时代背景（知青下乡/改革开放等）。注意时代细节的真实性。",
    "古言": "故事设定在古代（明清风格为主）。需要设计朝代架空程度、礼法制度、日常生活细节。语言风格偏古风但不过度文言。",
    "现言": "故事设定在现代都市。需要设计城市背景、职业设定、社会关系。贴近当代生活，有代入感。",
    "赶山": "核心看点是上山采集（挖人参、采蘑菇、打猎等）。需要设计山区环境、物产分布、采集技能升级路线。每次进山都有新发现。",
    "赶海": "核心看点是海边采集（捡海螺、抓螃蟹、捞海参等）。需要设计海岸环境、潮汐规律、海洋物产。每次赶海都有收获。",
    "脑洞": "设定新颖、反套路。核心看点是创意和反转。需要一个足够吸引人的高概念设定，同时内部逻辑自洽。",
    "甜宠": "感情线以甜蜜为主，虐心为辅。核心看点是男女主的互动撒糖。需要设计高甜名场面和宠溺细节。",
    "宫斗": "以后宫/宫廷为背景的权谋争斗。需要设计后宫等级、势力分布、争宠策略。注意与种田文的区别——宫斗以人际博弈为核心。",
    "宅斗": "以大家族内宅为背景的人际博弈。需要设计家族关系、嫡庶矛盾、管家权力。宅斗是种田文的常见搭配。",
    "总裁": "以商界精英/霸道总裁为男主的现代都市爱情。需要设计男主的商业帝国、社会地位、以及与女主的身份差距。",
    "豪门": "以大家族/财阀为背景的都市故事。需要设计家族权力结构、继承权争夺、商业联姻等元素。",
    "先婚后爱": "男女主先结婚后产生感情。需要设计婚姻的起因（契约/替嫁/政治联姻等）、从陌生到心动的过程、以及婚姻中的甜蜜互动。",
}


def load_project_tags() -> tuple[ProjectConfig, str]:
    """Load project.json and return (config, tags_context_text).

    Returns the full ProjectConfig and a formatted string of tag guidance
    suitable for injection into LLM prompts. Returns empty string if no tags.
    """
    proj_path = STORY_DIR / "project.json"
    if not proj_path.exists():
        return ProjectConfig(), ""
    proj = ProjectConfig(**load_json(proj_path))
    if not proj.tags:
        return proj, ""
    lines = []
    for tag in proj.tags:
        if tag in TAG_DEFINITIONS:
            lines.append(f"- **{tag}**：{TAG_DEFINITIONS[tag]}")
        else:
            lines.append(f"- **{tag}**")
    return proj, "## 类型标签要求\n以下是本作品需要融合的类型标签，请在创作中充分体现：\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# State entities
# ---------------------------------------------------------------------------

class Character(TemporalFields):
    """A character in the story."""
    id: str
    name: str
    role: str = ""  # protagonist | antagonist | supporting | minor
    age: str | None = None  # 网文中年龄常为描述性文本，不用 int

    @field_validator("age", mode="before")
    @classmethod
    def coerce_age_to_str(cls, v):
        """Accept int and convert to str for backward compatibility."""
        if isinstance(v, int):
            return f"{v}岁"
        return v
    gender: str = ""
    personality: str = ""
    speech_pattern: str = ""
    appearance: str = ""
    background: str = ""
    motivation: str = ""
    arc_summary: str = ""
    secrets: list[str] = Field(default_factory=list)
    relationships: dict[str, str] = Field(default_factory=dict)  # char_id -> relationship
    known_facts: list[str] = Field(default_factory=list)  # fact IDs this character knows


class CurrentState(BaseModel):
    """story/state/current_state.json — global story state."""
    timeline_position: str = ""
    current_location: str = ""
    active_plot_threads: list[str] = Field(default_factory=list)
    recent_events: list[dict] = Field(default_factory=list)  # {chapter, event, impact}
    world_conditions: dict[str, str] = Field(default_factory=dict)


class CharacterMatrix(BaseModel):
    """story/state/character_matrix.json — all characters."""
    characters: dict[str, Character] = Field(default_factory=dict)  # id -> Character


class PowerLevel(TemporalFields):
    """A power/cultivation level entry."""
    id: str
    character_id: str
    level_name: str
    level_rank: int = 0
    breakthrough_chapter: int | None = None
    special_abilities: list[str] = Field(default_factory=list)


class PowerLedger(BaseModel):
    """story/state/power_ledger.json — power/cultivation tracking."""
    power_system: str = ""
    levels: list[PowerLevel] = Field(default_factory=list)
    level_names: list[str] = Field(default_factory=list)  # ordered level names


class ForeshadowHook(TemporalFields):
    """A foreshadowing hook / pending plot thread."""
    id: str
    description: str
    hook_type: str = "setup"  # setup | advance | payoff
    planted_chapter: int = 0
    expected_payoff_chapter: int | None = None
    related_characters: list[str] = Field(default_factory=list)
    related_locations: list[str] = Field(default_factory=list)
    urgency: str = "normal"  # low | normal | high | critical


class PendingHooks(BaseModel):
    """story/state/pending_hooks.json — foreshadowing debt tracking."""
    hooks: dict[str, ForeshadowHook] = Field(default_factory=dict)  # id -> hook


class ChapterSummary(TemporalFields):
    """Summary of a single chapter."""
    chapter: int
    title: str = ""
    summary: str = ""
    key_events: list[str] = Field(default_factory=list)
    characters_present: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    word_count: int = 0
    emotional_tone: str = ""


class ChapterSummaries(BaseModel):
    """story/state/chapter_summaries.json — chapter-by-chapter summaries."""
    summaries: dict[str, ChapterSummary] = Field(default_factory=dict)  # "ch_N" -> summary


class Subplot(TemporalFields):
    """A subplot / secondary storyline."""
    id: str
    name: str
    description: str
    status: str = "active"  # active | resolved | paused | abandoned
    related_characters: list[str] = Field(default_factory=list)
    chapters_involved: list[int] = Field(default_factory=list)
    tension_level: str = "building"  # building | climax | resolution


class SubplotBoard(BaseModel):
    """story/state/subplot_board.json — subplot tracking."""
    subplots: dict[str, Subplot] = Field(default_factory=dict)


class EmotionalArc(TemporalFields):
    """An emotional arc for a character."""
    id: str
    character_id: str
    emotion: str
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    trigger: str = ""
    resolution: str = ""
    start_chapter: int = 0
    peak_chapter: int | None = None
    end_chapter: int | None = None


class EmotionalArcs(BaseModel):
    """story/state/emotional_arcs.json — emotional arc tracking."""
    arcs: dict[str, EmotionalArc] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Resource / Item tracking
# ---------------------------------------------------------------------------

class Resource(TemporalFields):
    """A trackable resource (money, materials, etc.)."""
    id: str
    name: str
    category: str = ""  # currency | material | food | tool | artifact
    quantity: float = Field(default=0.0, ge=0.0)
    unit: str = ""
    owner: str = ""  # character_id
    location: str = ""


class Item(TemporalFields):
    """A significant item."""
    id: str
    name: str
    description: str = ""
    item_type: str = ""  # weapon | armor | accessory | artifact | consumable | misc
    rarity: str = "common"  # common | uncommon | rare | epic | legendary
    owner: str = ""
    location: str = ""
    abilities: list[str] = Field(default_factory=list)
    acquired_chapter: int = 0


class PowerLedgerFull(BaseModel):
    """Extended power ledger with resources and items."""
    power_system: str = ""
    levels: list[PowerLevel] = Field(default_factory=list)
    level_names: list[str] = Field(default_factory=list)
    resources: dict[str, Resource] = Field(default_factory=dict)
    items: dict[str, Item] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Chapter Delta — what changed in a chapter
# ---------------------------------------------------------------------------

class ChapterDelta(BaseModel):
    """story/runtime/ch_NNNN/delta.json — changes extracted from a chapter."""
    chapter: int
    new_facts: list[dict] = Field(default_factory=list)
    character_updates: list[dict] = Field(default_factory=list)
    relationship_updates: list[dict] = Field(default_factory=list)
    power_updates: list[dict] = Field(default_factory=list)
    resource_updates: list[dict] = Field(default_factory=list)
    item_updates: list[dict] = Field(default_factory=list)
    hook_updates: list[dict] = Field(default_factory=list)
    subplot_updates: list[dict] = Field(default_factory=list)
    emotional_arc_updates: list[dict] = Field(default_factory=list)
    chapter_summary: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Context — what the writer model sees
# ---------------------------------------------------------------------------

class ContextBudget(BaseModel):
    """Budget allocation for context assembly."""
    chapter_plan: int = 3200
    volume_contract: int = 1500
    state_slice: int = 3000
    recent_summaries: int = 2000
    retrieved_fragments: int = 2000
    voice_rules: int = 1500
    previous_chapter_tail: int = 1500
    total_budget: int = 15000


class ChapterContext(BaseModel):
    """story/runtime/ch_NNNN/context.json — assembled context for writing."""
    chapter: int
    budget: ContextBudget = Field(default_factory=ContextBudget)
    chapter_plan: str = ""
    volume_contract: str = ""
    state_slice: dict = Field(default_factory=dict)
    recent_summaries: list[dict] = Field(default_factory=list)
    retrieved_fragments: list[dict] = Field(default_factory=list)
    voice_rules: str = ""
    previous_chapter_tail: str = ""
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------

class AuditResult(BaseModel):
    """story/runtime/ch_NNNN/audit.json — webnovel audit results."""
    chapter: int
    overall_score: float = 0.0
    passed: bool = True

    # Blocking items (must pass)
    ledger_compliance: dict = Field(default_factory=dict)  # {passed, issues}
    timeline_consistency: dict = Field(default_factory=dict)
    character_knowledge: dict = Field(default_factory=dict)

    # Warning items (should pass, can retry)
    chapter_hook: dict = Field(default_factory=dict)  # {score, comment}
    promise_fulfillment: dict = Field(default_factory=dict)
    pacing: dict = Field(default_factory=dict)
    payoff_setup: dict = Field(default_factory=dict)
    filler_ratio: dict = Field(default_factory=dict)
    coherence: dict = Field(default_factory=dict)
    hook_debt_change: dict = Field(default_factory=dict)
    volume_progress: dict = Field(default_factory=dict)

    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Snapshot index
# ---------------------------------------------------------------------------

class SnapshotEntry(BaseModel):
    """An entry in commit_index.json."""
    chapter: int
    commit_hash: str
    timestamp: str
    snapshot_path: str = ""
    description: str = ""


class SnapshotIndex(BaseModel):
    """story/memory/snapshots/commit_index.json."""
    entries: list[SnapshotEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Volume summary — aggregated at volume boundaries
# ---------------------------------------------------------------------------

class VolumeSummary(BaseModel):
    """story/plans/volume_{NNN}_summary.yaml — aggregated volume summary."""
    volume: int
    title: str = ""
    theme: str = ""
    chapter_range: str = ""  # e.g. "1-20"
    total_words: int = 0
    main_arc_summary: str = ""
    key_events: list[str] = Field(default_factory=list)
    character_developments: list[dict] = Field(default_factory=list)
    hooks_planted: list[str] = Field(default_factory=list)
    hooks_resolved: list[str] = Field(default_factory=list)
    unresolved_hooks: list[str] = Field(default_factory=list)
    subplots_status: list[dict] = Field(default_factory=list)
    emotional_arcs_summary: list[str] = Field(default_factory=list)
    pacing_notes: str = ""
    next_volume_setup: str = ""


# ---------------------------------------------------------------------------
# Compaction record
# ---------------------------------------------------------------------------

class CompactionRecord(BaseModel):
    """story/memory/compaction_{NNN}.json — record of a compaction run."""
    volume: int
    timestamp: str = ""
    chapters_compacted: int = 0
    summaries_before: int = 0
    summaries_after: int = 0
    archived_summaries: list[int] = Field(default_factory=list)
    compressed_hooks: list[str] = Field(default_factory=list)
    compressed_subplots: list[str] = Field(default_factory=list)
    notes: str = ""
