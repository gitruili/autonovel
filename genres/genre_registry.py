#!/usr/bin/env python3
"""
Genre registry — single entry point for genre configuration.

Loads genre-specific prompts, evaluation criteria, and writing guidance
from YAML config files. Merges with _base.yaml for shared webnovel conventions.

Usage:
    from genres.genre_registry import load_genre_for_project
    genre = load_genre_for_project()
    system_prompt = genre.get_system_prompt("seed_writer")
"""

import yaml
from pathlib import Path
from typing import Any

GENRES_DIR = Path(__file__).parent
BASE_YAML = GENRES_DIR / "_base.yaml"

# Chinese display name → YAML filename (without .yaml)
_GENRE_MAP: dict[str, str] | None = None


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge override into base. Lists are replaced, not appended."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _get_genre_map() -> dict[str, str]:
    """Load the genre name → filename mapping from _base.yaml."""
    global _GENRE_MAP
    if _GENRE_MAP is None:
        base = _load_yaml(BASE_YAML)
        _GENRE_MAP = base.get("genre_map", {})
    return _GENRE_MAP


class GenreConfig:
    """Loaded genre configuration with accessors for all genre-specific content."""

    def __init__(self, data: dict):
        self._data = data

    @property
    def genre_key(self) -> str:
        return self._data.get("genre_key", "unknown")

    @property
    def display_name(self) -> str:
        return self._data.get("display_name", "网文")

    @property
    def description(self) -> str:
        return self._data.get("description", "")

    @property
    def genre_definition(self) -> str:
        return self._data.get("genre_definition", "")

    @property
    def title_rules(self) -> str:
        return self._data.get("title_rules", "")

    @property
    def synopsis_rules(self) -> str:
        return self._data.get("synopsis_rules", "")

    @property
    def default_tags(self) -> list[str]:
        return self._data.get("default_tags", [])

    @property
    def craft_file(self) -> str | None:
        return self._data.get("craft_file")

    def get_system_prompt(self, role: str) -> str:
        """Return the full system prompt for a given pipeline role.

        Looks up genre-specific system_prompts[role], falls back to
        a generic placeholder if not found.
        """
        prompts = self._data.get("system_prompts", {})
        if role in prompts and prompts[role]:
            return prompts[role].strip()
        # Fallback: generic placeholder
        return f"你是一位专业的{self.display_name}网文创作者。只输出指定格式的内容。"

    def get_prompt_fragment(self, stage: str, section: str) -> str:
        """Return a prompt template fragment for a given stage and section.

        Example: get_prompt_fragment("seed", "diversity_requirements")
        """
        fragments = self._data.get("prompt_fragments", {})
        stage_data = fragments.get(stage, {})
        if isinstance(stage_data, dict):
            return stage_data.get(section, "")
        return ""

    def get_evaluation_config(self, phase: str) -> dict:
        """Return evaluation dimensions and weights for a given phase.

        Merges base shared evaluation with genre-specific evaluation.
        Returns dict with keys: dimensions, cross_checks, weights
        """
        eval_data = self._data.get("evaluation", {})
        phase_data = eval_data.get(phase, {})
        return phase_data

    def get_reader_persona(self, persona: str) -> str:
        """Return a reader panel persona prompt."""
        personas = self._data.get("reader_personas", {})
        return personas.get(persona, "")

    def get_voice_template(self) -> dict:
        """Return voice.md Part 2 template hints."""
        return self._data.get("voice_template", {})

    def get_mystery_template(self) -> str:
        """Return MYSTERY.md placeholder content."""
        return self._data.get("mystery_template", "")


def load_genre(genre_name: str) -> GenreConfig:
    """Load a genre config by Chinese display name (e.g., "总裁豪门").

    Falls back to "总裁豪门" if the name is not found.
    """
    genre_map = _get_genre_map()

    # Try direct lookup
    filename = genre_map.get(genre_name)
    if filename is None and genre_name:
        # Try matching by display_name in available YAML files
        for key, fname in genre_map.items():
            if key == genre_name or genre_name in key:
                filename = fname
                break
    if filename is None:
        # Default to zongcai
        filename = genre_map.get("总裁豪门", "zongcai")

    genre_path = GENRES_DIR / f"{filename}.yaml"
    if not genre_path.exists():
        raise FileNotFoundError(f"Genre config not found: {genre_path}")

    # Load base + genre, merge
    base_data = _load_yaml(BASE_YAML)
    genre_data = _load_yaml(genre_path)
    merged = _deep_merge(base_data, genre_data)

    return GenreConfig(merged)


def load_genre_for_project() -> GenreConfig:
    """Load the genre config for the current project.

    Reads story/project.json -> genre field.
    Falls back to "总裁豪门" if not set.
    """
    import json
    proj_path = Path(__file__).parent.parent / "story" / "project.json"
    genre_name = "总裁豪门"
    if proj_path.exists():
        try:
            with open(proj_path, "r", encoding="utf-8") as f:
                proj = json.load(f)
            genre_name = proj.get("genre", "") or "总裁豪门"
        except (json.JSONDecodeError, OSError):
            pass
    return load_genre(genre_name)


def list_available_genres() -> list[dict]:
    """Return a list of available genres with their keys and display names."""
    genre_map = _get_genre_map()
    result = []
    for display_name, filename in genre_map.items():
        genre_path = GENRES_DIR / f"{filename}.yaml"
        if genre_path.exists():
            data = _load_yaml(genre_path)
            result.append({
                "display_name": display_name,
                "genre_key": data.get("genre_key", filename),
                "description": data.get("description", ""),
            })
    return result


def load_genre_craft(genre: GenreConfig) -> str:
    """Load the genre-specific craft document, if it exists."""
    craft_file = genre.craft_file
    if not craft_file:
        return ""
    craft_path = GENRES_DIR.parent / craft_file
    if craft_path.exists():
        return craft_path.read_text(encoding="utf-8")
    return ""
