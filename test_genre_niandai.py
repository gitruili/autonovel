#!/usr/bin/env python3
"""Tests for the 年代文 (niandai) genre configuration and pipeline integration."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

from genres.genre_registry import (
    GenreConfig,
    load_genre,
    load_genre_craft,
    load_genre_for_project,
    list_available_genres,
)


# ---------------------------------------------------------------------------
# Phase 1: Genre Loading
# ---------------------------------------------------------------------------

class TestGenreLoading(unittest.TestCase):
    """Verify genre registry loads niandai correctly."""

    def test_list_genres_includes_niandai(self):
        genres = list_available_genres()
        names = [g["display_name"] for g in genres]
        self.assertIn("年代文", names)

    def test_list_genres_includes_zhongtian(self):
        genres = list_available_genres()
        names = [g["display_name"] for g in genres]
        self.assertIn("种田文", names)

    def test_load_niandai_genre_key(self):
        genre = load_genre("年代文")
        self.assertEqual(genre.genre_key, "niandai")
        self.assertEqual(genre.display_name, "年代文")

    def test_load_niandai_has_description(self):
        genre = load_genre("年代文")
        self.assertIn("1950", genre.description)
        self.assertTrue(len(genre.description) > 20)

    def test_load_niandai_has_genre_definition(self):
        genre = load_genre("年代文")
        self.assertTrue(len(genre.genre_definition) > 100)
        self.assertIn("票证", genre.genre_definition)

    def test_load_niandai_default_tags(self):
        genre = load_genre("年代文")
        tags = genre.default_tags
        self.assertIn("穿越", tags)
        self.assertIn("年代", tags)
        self.assertIn("大女主", tags)
        self.assertIn("甜宠", tags)
        self.assertIn("宅斗", tags)

    def test_load_niandai_has_craft_file(self):
        genre = load_genre("年代文")
        self.assertIsNotNone(genre.craft_file)
        self.assertIn("niandai_craft", genre.craft_file)

    def test_load_craft_file_content(self):
        genre = load_genre("年代文")
        craft = load_genre_craft(genre)
        self.assertTrue(len(craft) > 100)
        self.assertIn("票证", craft)
        self.assertIn("时代伏笔", craft)

    def test_niandai_title_rules(self):
        genre = load_genre("年代文")
        rules = genre.title_rules
        self.assertIn("七零", rules)
        self.assertIn("六零", rules)
        self.assertIn("八零", rules)

    def test_niandai_synopsis_rules(self):
        genre = load_genre("年代文")
        rules = genre.synopsis_rules
        self.assertTrue(len(rules) > 50)

    def test_niandai_voice_template(self):
        genre = load_genre("年代文")
        vt = genre.get_voice_template()
        self.assertIn("tone_hint", vt)
        self.assertIn("vocabulary_hint", vt)
        self.assertIn("同志", vt["vocabulary_hint"])
        self.assertIn("个体户", vt["vocabulary_hint"])

    def test_niandai_mystery_template(self):
        genre = load_genre("年代文")
        mt = genre.get_mystery_template()
        self.assertTrue(len(mt) > 50)


# ---------------------------------------------------------------------------
# Phase 1: System Prompts (all 10 roles)
# ---------------------------------------------------------------------------

class TestNiandaiSystemPrompts(unittest.TestCase):
    """Verify all system prompts load correctly for niandai."""

    ROLES = [
        "seed_writer", "seed_writer_lf", "architect", "architect_lf",
        "character_designer", "world_builder", "canon_editor",
        "chapter_writer", "revision_writer", "adversarial_editor",
    ]

    def setUp(self):
        self.genre = load_genre("年代文")

    def test_all_roles_have_prompts(self):
        for role in self.ROLES:
            prompt = self.genre.get_system_prompt(role)
            self.assertTrue(len(prompt) > 50, f"Role '{role}' prompt too short: {len(prompt)} chars")

    def test_seed_writer_lf_references_era_works(self):
        prompt = self.genre.get_system_prompt("seed_writer_lf")
        self.assertIn("七零", prompt)

    def test_world_builder_demands_era_knowledge(self):
        prompt = self.genre.get_system_prompt("world_builder")
        self.assertIn("票证", prompt)

    def test_chapter_writer_forbids_modern_slang(self):
        prompt = self.genre.get_system_prompt("chapter_writer")
        self.assertIn("年代感", prompt)

    def test_architect_lf_multi_decade(self):
        prompt = self.genre.get_system_prompt("architect_lf")
        self.assertIn("时代", prompt)

    def test_canon_editor_historical_accuracy(self):
        prompt = self.genre.get_system_prompt("canon_editor")
        self.assertIn("历史", prompt)

    def test_character_designer_era_speech(self):
        prompt = self.genre.get_system_prompt("character_designer")
        self.assertTrue(len(prompt) > 100)

    def test_fallback_for_unknown_role(self):
        prompt = self.genre.get_system_prompt("nonexistent_role")
        self.assertIn("年代文", prompt)


# ---------------------------------------------------------------------------
# Phase 1: Prompt Fragments
# ---------------------------------------------------------------------------

class TestNiandaiPromptFragments(unittest.TestCase):
    """Verify prompt fragments load correctly for niandai."""

    def setUp(self):
        self.genre = load_genre("年代文")

    def test_seed_diversity_requirements(self):
        frag = self.genre.get_prompt_fragment("seed", "diversity_requirements")
        self.assertIn("知青", frag)
        self.assertIn("改革", frag)

    def test_seed_prohibitions(self):
        frag = self.genre.get_prompt_fragment("seed", "prohibitions")
        self.assertIn("票证", frag)
        self.assertTrue(len(frag) > 50)

    def test_world_requirements(self):
        frag = self.genre.get_prompt_fragment("world", "requirements")
        self.assertTrue(len(frag) > 50)

    def test_world_sections(self):
        frag = self.genre.get_prompt_fragment("world", "sections")
        self.assertIn("票证", frag)
        self.assertIn("阶级", frag)

    def test_characters_requirements(self):
        frag = self.genre.get_prompt_fragment("characters", "requirements")
        self.assertTrue(len(frag) > 50)

    def test_characters_role_types(self):
        frag = self.genre.get_prompt_fragment("characters", "role_types")
        self.assertTrue(len(frag) > 30)

    def test_outline_structure(self):
        frag = self.genre.get_prompt_fragment("outline", "structure")
        self.assertTrue(len(frag) > 50)

    def test_outline_constraints(self):
        frag = self.genre.get_prompt_fragment("outline", "constraints")
        self.assertIn("时代线", frag)

    def test_outline_ledgers(self):
        frag = self.genre.get_prompt_fragment("outline", "ledgers")
        self.assertIn("时代升级", frag)

    def test_canon_sections(self):
        frag = self.genre.get_prompt_fragment("canon", "sections")
        self.assertTrue(len(frag) > 50)

    def test_chapter_draft_genre_detail(self):
        frag = self.genre.get_prompt_fragment("chapter_draft", "genre_specific_detail")
        self.assertTrue(len(frag) > 30)

    def test_missing_fragment_returns_empty(self):
        frag = self.genre.get_prompt_fragment("nonexistent", "nonexistent")
        self.assertEqual(frag, "")


# ---------------------------------------------------------------------------
# Phase 1: Evaluation Config
# ---------------------------------------------------------------------------

class TestNiandaiEvaluation(unittest.TestCase):
    """Verify evaluation dimensions load correctly for niandai."""

    def setUp(self):
        self.genre = load_genre("年代文")

    def test_foundation_evaluation_has_dimensions(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("dimensions", config)
        self.assertIsInstance(config["dimensions"], dict)
        self.assertTrue(len(config["dimensions"]) >= 6)

    def test_foundation_has_historical_accuracy(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("historical_accuracy", config["dimensions"])

    def test_foundation_has_era_progression(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("era_progression", config["dimensions"])

    def test_foundation_has_cross_checks(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("cross_checks", config)
        self.assertTrue(len(config["cross_checks"]) >= 3)

    def test_foundation_has_weights(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("weights", config)

    def test_chapter_evaluation_has_dimensions(self):
        config = self.genre.get_evaluation_config("chapter")
        self.assertIn("dimensions", config)
        self.assertIn("era_integration", config["dimensions"])

    def test_chapter_evaluation_has_emotional_payoff(self):
        config = self.genre.get_evaluation_config("chapter")
        self.assertIn("emotional_payoff", config["dimensions"])


# ---------------------------------------------------------------------------
# Phase 1: Reader Personas
# ---------------------------------------------------------------------------

class TestNiandaiReaderPersonas(unittest.TestCase):
    """Verify reader personas load correctly for niandai."""

    def setUp(self):
        self.genre = load_genre("年代文")

    def test_genre_reader_persona(self):
        persona = self.genre.get_reader_persona("genre_reader")
        self.assertTrue(len(persona) > 50)

    def test_writer_persona(self):
        persona = self.genre.get_reader_persona("writer")
        self.assertTrue(len(persona) > 50)

    def test_missing_persona_returns_empty(self):
        persona = self.genre.get_reader_persona("nonexistent")
        self.assertEqual(persona, "")


# ---------------------------------------------------------------------------
# Phase 1: Deep Merge & Fallback
# ---------------------------------------------------------------------------

class TestGenreFallback(unittest.TestCase):
    """Verify fallback behavior when genre is missing."""

    def test_unknown_genre_falls_back_to_zhongtian(self):
        genre = load_genre("不存在的题材")
        self.assertEqual(genre.genre_key, "zhongtian")

    def test_empty_genre_falls_back_to_zhongtian(self):
        genre = load_genre("")
        self.assertEqual(genre.genre_key, "zhongtian")

    def test_base_fields_preserved_after_merge(self):
        """After merging _base.yaml + niandai.yaml, base fields should still exist."""
        genre = load_genre("年代文")
        # _base.yaml has shared evaluation dimensions
        eval_config = genre.get_evaluation_config("foundation")
        # Should have both base and genre-specific dimensions
        self.assertIn("dimensions", eval_config)

    def test_genre_overrides_base(self):
        """Genre-specific fields should override base defaults."""
        genre = load_genre("年代文")
        self.assertEqual(genre.genre_key, "niandai")
        # display_name should come from niandai.yaml, not _base.yaml
        self.assertEqual(genre.display_name, "年代文")


# ---------------------------------------------------------------------------
# Phase 2: Project Initialization
# ---------------------------------------------------------------------------

class TestProjectInit(unittest.TestCase):
    """Test project initialization with niandai genre."""

    def test_load_genre_for_project_with_niandai(self):
        """When project.json has genre='年代文', load_genre_for_project returns niandai."""
        with tempfile.TemporaryDirectory() as tmpdir:
            story_dir = Path(tmpdir) / "story"
            story_dir.mkdir()
            proj = {"title": "测试", "genre": "年代文", "tags": ["穿越", "年代"]}
            (story_dir / "project.json").write_text(
                json.dumps(proj, ensure_ascii=False), encoding="utf-8"
            )
            with mock.patch(
                "genres.genre_registry.load_genre_for_project",
                side_effect=lambda: load_genre("年代文"),
            ):
                genre = load_genre("年代文")
                self.assertEqual(genre.genre_key, "niandai")

    def test_load_genre_for_project_empty_genre(self):
        """When project.json has empty genre, should fall back to 种田文."""
        with tempfile.TemporaryDirectory() as tmpdir:
            story_dir = Path(tmpdir) / "story"
            story_dir.mkdir()
            proj = {"title": "测试", "genre": ""}
            (story_dir / "project.json").write_text(
                json.dumps(proj, ensure_ascii=False), encoding="utf-8"
            )
            genre = load_genre("")
            self.assertEqual(genre.genre_key, "zhongtian")

    def test_tags_coverage_for_niandai_defaults(self):
        """All default_tags for niandai should have entries in TAG_DEFINITIONS."""
        from story_schema import TAG_DEFINITIONS
        genre = load_genre("年代文")
        for tag in genre.default_tags:
            self.assertIn(tag, TAG_DEFINITIONS, f"Tag '{tag}' missing from TAG_DEFINITIONS")


# ---------------------------------------------------------------------------
# Phase 3: Prompt Content Verification
# ---------------------------------------------------------------------------

class TestNiandaiPromptContent(unittest.TestCase):
    """Verify that prompts assembled from genre config contain expected content."""

    def setUp(self):
        self.genre = load_genre("年代文")

    def test_seed_prompt_has_era_references(self):
        """Seed prompt should reference classic 年代文 works."""
        prompt = self.genre.get_system_prompt("seed_writer_lf")
        # Should reference era-specific works or concepts
        has_era_ref = any(
            kw in prompt
            for kw in ["七零", "六零", "八零", "九零", "知青", "军嫂"]
        )
        self.assertTrue(has_era_ref, f"Seed prompt missing era references")

    def test_world_prompt_has_ration_system(self):
        """World builder prompt should mention 票证制度."""
        prompt = self.genre.get_system_prompt("world_builder")
        self.assertIn("票证", prompt)

    def test_world_sections_have_class_system(self):
        """World sections should include 阶级成分."""
        sections = self.genre.get_prompt_fragment("world", "sections")
        self.assertIn("阶级", sections)

    def test_character_prompt_has_speech_patterns(self):
        """Character designer should mention era-appropriate speech."""
        prompt = self.genre.get_system_prompt("character_designer")
        has_speech = any(kw in prompt for kw in ["用语", "同志", "社员", "师傅"])
        self.assertTrue(has_speech, "Character prompt missing speech pattern guidance")

    def test_outline_constraints_forbid_era_gaps(self):
        """Outline constraints should forbid gaps in era detail."""
        constraints = self.genre.get_prompt_fragment("outline", "constraints")
        self.assertIn("时代线", constraints)

    def test_ledgers_have_era_upgrade(self):
        """Ledgers should include 时代升级台账."""
        ledgers = self.genre.get_prompt_fragment("outline", "ledgers")
        self.assertIn("时代升级", ledgers)

    def test_voice_template_forbids_modern_words(self):
        """Voice template vocabulary should forbid modern slang."""
        vt = self.genre.get_voice_template()
        vocab = vt.get("vocabulary_hint", "")
        # Should contain forbidden modern words
        has_forbidden = any(kw in vocab for kw in ["效率", "流量", "赋能", "互联网"])
        self.assertTrue(has_forbidden, "Voice template missing forbidden modern words list")

    def test_voice_template_has_era_vocabularies(self):
        """Voice template should have decade-specific vocabulary."""
        vt = self.genre.get_voice_template()
        vocab = vt.get("vocabulary_hint", "")
        self.assertIn("同志", vocab)  # 50-60s
        self.assertIn("知青", vocab)  # 70s
        self.assertIn("个体户", vocab)  # 80-90s

    def test_prohibitions_ban_pseudo_era(self):
        """Prohibitions should ban 'pseudo-era' novels that ignore key systems."""
        prohibitions = self.genre.get_prompt_fragment("seed", "prohibitions")
        self.assertIn("票证", prohibitions)

    def test_evaluation_cross_checks_historical(self):
        """Foundation evaluation should include historical cross-checks."""
        config = self.genre.get_evaluation_config("foundation")
        cross_checks = config.get("cross_checks", [])
        cc_text = " ".join(cross_checks)
        self.assertTrue(
            any(kw in cc_text for kw in ["历史", "年代", "票证", "阶级"]),
            f"Cross-checks missing historical/era verification: {cross_checks}"
        )


# ---------------------------------------------------------------------------
# Phase 3: Genre Differences Verification
# ---------------------------------------------------------------------------

class TestGenreDifferences(unittest.TestCase):
    """Verify niandai differs from zhongtian in key ways."""

    def setUp(self):
        self.niandai = load_genre("年代文")
        self.zhongtian = load_genre("种田文")

    def test_different_genre_keys(self):
        self.assertNotEqual(self.niandai.genre_key, self.zhongtian.genre_key)

    def test_different_display_names(self):
        self.assertNotEqual(self.niandai.display_name, self.zhongtian.display_name)

    def test_different_default_tags(self):
        self.assertNotEqual(self.niandai.default_tags, self.zhongtian.default_tags)

    def test_different_system_prompts(self):
        """Chapter writer prompts should be completely different."""
        n_prompt = self.niandai.get_system_prompt("chapter_writer")
        z_prompt = self.zhongtian.get_system_prompt("chapter_writer")
        self.assertNotEqual(n_prompt, z_prompt)

    def test_different_evaluation_dimensions(self):
        """Foundation evaluation dimensions should differ."""
        n_eval = self.niandai.get_evaluation_config("foundation")
        z_eval = self.zhongtian.get_evaluation_config("foundation")
        n_names = set(n_eval.get("dimensions", {}).keys())
        z_names = set(z_eval.get("dimensions", {}).keys())
        self.assertNotEqual(n_names, z_names)

    def test_different_voice_templates(self):
        n_vocab = self.niandai.get_voice_template().get("vocabulary_hint", "")
        z_vocab = self.zhongtian.get_voice_template().get("vocabulary_hint", "")
        self.assertNotEqual(n_vocab, z_vocab)

    def test_different_craft_files(self):
        n_craft = load_genre_craft(self.niandai)
        z_craft = load_genre_craft(self.zhongtian)
        self.assertNotEqual(n_craft, z_craft)
        # niandai craft should mention era-specific concepts
        self.assertIn("票证", n_craft)
        self.assertIn("时代伏笔", n_craft)


# ---------------------------------------------------------------------------
# Phase 3: Prompt Assembly (simulating how pipeline scripts use genre)
# ---------------------------------------------------------------------------

class TestPromptAssembly(unittest.TestCase):
    """Simulate how pipeline scripts assemble prompts from genre config."""

    def setUp(self):
        self.genre = load_genre("年代文")

    def test_seed_prompt_assembly(self):
        """Simulate seed_lf.py prompt assembly."""
        system = self.genre.get_system_prompt("seed_writer_lf")
        definition = self.genre.genre_definition
        title_rules = self.genre.title_rules
        diversity = self.genre.get_prompt_fragment("seed", "diversity_requirements")
        prohibitions = self.genre.get_prompt_fragment("seed", "prohibitions")

        full_prompt = f"{system}\n{definition}\n{title_rules}\n{diversity}\n{prohibitions}"
        self.assertIn("年代", full_prompt)
        self.assertIn("票证", full_prompt)
        self.assertTrue(len(full_prompt) > 500)

    def test_world_prompt_assembly(self):
        """Simulate gen_world_lf.py prompt assembly."""
        system = self.genre.get_system_prompt("world_builder")
        req = self.genre.get_prompt_fragment("world", "requirements")
        sections = self.genre.get_prompt_fragment("world", "sections")

        full_prompt = f"{system}\n{req}\n{sections}"
        self.assertIn("票证", full_prompt)
        self.assertIn("阶级", full_prompt)

    def test_character_prompt_assembly(self):
        """Simulate gen_characters_lf.py prompt assembly."""
        system = self.genre.get_system_prompt("character_designer")
        req = self.genre.get_prompt_fragment("characters", "requirements")
        roles = self.genre.get_prompt_fragment("characters", "role_types")

        full_prompt = f"{system}\n{req}\n{roles}"
        self.assertTrue(len(full_prompt) > 300)

    def test_outline_prompt_assembly(self):
        """Simulate gen_outline_v1.py prompt assembly."""
        system = self.genre.get_system_prompt("architect")
        structure = self.genre.get_prompt_fragment("outline", "structure")
        constraints = self.genre.get_prompt_fragment("outline", "constraints")
        ledgers = self.genre.get_prompt_fragment("outline", "ledgers")

        full_prompt = f"{system}\n{structure}\n{constraints}\n{ledgers}"
        self.assertIn("时代", full_prompt)
        self.assertTrue(len(full_prompt) > 300)

    def test_canon_prompt_assembly(self):
        """Simulate gen_canon.py prompt assembly."""
        system = self.genre.get_system_prompt("canon_editor")
        sections = self.genre.get_prompt_fragment("canon", "sections")

        full_prompt = f"{system}\n{sections}"
        self.assertIn("时代", full_prompt)
        self.assertIn("票证", full_prompt)

    def test_evaluation_prompt_assembly(self):
        """Simulate evaluate.py prompt assembly."""
        config = self.genre.get_evaluation_config("foundation")
        dims = config.get("dimensions", {})
        cross_checks = config.get("cross_checks", [])
        weights = config.get("weights", {})

        self.assertIsInstance(dims, dict)
        self.assertTrue(len(dims) >= 6)
        self.assertTrue(len(cross_checks) >= 3)
        self.assertTrue(len(weights) > 0)

        self.assertIn("historical_accuracy", dims)
        self.assertIn("era_progression", dims)
        self.assertIn("economic_system", dims)
        self.assertIn("social_structure", dims)


if __name__ == "__main__":
    unittest.main()
