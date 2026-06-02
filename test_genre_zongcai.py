#!/usr/bin/env python3
"""Tests for the 总裁豪门 (zongcai) genre configuration and pipeline integration."""

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
    """Verify genre registry loads zongcai correctly."""

    def test_list_genres_includes_zongcai(self):
        genres = list_available_genres()
        names = [g["display_name"] for g in genres]
        self.assertIn("总裁豪门", names)

    def test_list_genres_includes_zhongtian(self):
        genres = list_available_genres()
        names = [g["display_name"] for g in genres]
        self.assertIn("种田文", names)

    def test_list_genres_includes_niandai(self):
        genres = list_available_genres()
        names = [g["display_name"] for g in genres]
        self.assertIn("年代文", names)

    def test_load_zongcai_genre_key(self):
        genre = load_genre("总裁豪门")
        self.assertEqual(genre.genre_key, "zongcai")
        self.assertEqual(genre.display_name, "总裁豪门")

    def test_load_zongcai_has_description(self):
        genre = load_genre("总裁豪门")
        self.assertIn("总裁", genre.description)
        self.assertTrue(len(genre.description) > 20)

    def test_load_zongcai_has_genre_definition(self):
        genre = load_genre("总裁豪门")
        self.assertTrue(len(genre.genre_definition) > 100)
        self.assertIn("身份落差", genre.genre_definition)

    def test_load_zongcai_default_tags(self):
        genre = load_genre("总裁豪门")
        tags = genre.default_tags
        self.assertIn("总裁", tags)
        self.assertIn("豪门", tags)
        self.assertIn("甜宠", tags)
        self.assertIn("大女主", tags)
        self.assertIn("现言", tags)

    def test_load_zongcai_has_craft_file(self):
        genre = load_genre("总裁豪门")
        self.assertIsNotNone(genre.craft_file)
        self.assertIn("zongcai_craft", genre.craft_file)

    def test_load_craft_file_content(self):
        genre = load_genre("总裁豪门")
        craft = load_genre_craft(genre)
        self.assertTrue(len(craft) > 100)
        self.assertIn("商战", craft)
        self.assertIn("身份落差", craft)

    def test_zongcai_title_rules(self):
        genre = load_genre("总裁豪门")
        rules = genre.title_rules
        self.assertIn("总裁", rules)
        self.assertIn("替嫁", rules)
        self.assertIn("豪门", rules)

    def test_zongcai_synopsis_rules(self):
        genre = load_genre("总裁豪门")
        rules = genre.synopsis_rules
        self.assertTrue(len(rules) > 50)
        self.assertIn("契约", rules)

    def test_zongcai_voice_template(self):
        genre = load_genre("总裁豪门")
        vt = genre.get_voice_template()
        self.assertIn("tone_hint", vt)
        self.assertIn("vocabulary_hint", vt)
        self.assertIn("精英", vt["tone_hint"])

    def test_zongcai_mystery_template(self):
        genre = load_genre("总裁豪门")
        mt = genre.get_mystery_template()
        self.assertTrue(len(mt) > 50)


# ---------------------------------------------------------------------------
# Phase 1: System Prompts (all 10 roles)
# ---------------------------------------------------------------------------

class TestZongcaiSystemPrompts(unittest.TestCase):
    """Verify all system prompts load correctly for zongcai."""

    ROLES = [
        "seed_writer", "seed_writer_lf", "architect", "architect_lf",
        "character_designer", "world_builder", "canon_editor",
        "chapter_writer", "revision_writer", "adversarial_editor",
    ]

    def setUp(self):
        self.genre = load_genre("总裁豪门")

    def test_all_roles_have_prompts(self):
        for role in self.ROLES:
            prompt = self.genre.get_system_prompt(role)
            self.assertTrue(len(prompt) > 50, f"Role '{role}' prompt too short: {len(prompt)} chars")

    def test_seed_writer_lf_references_works(self):
        prompt = self.genre.get_system_prompt("seed_writer_lf")
        self.assertIn("总裁", prompt)

    def test_world_builder_demands_business_knowledge(self):
        prompt = self.genre.get_system_prompt("world_builder")
        self.assertIn("商业", prompt)

    def test_chapter_writer_urban_elite(self):
        prompt = self.genre.get_system_prompt("chapter_writer")
        self.assertIn("都市", prompt)

    def test_architect_lf_multi_volume(self):
        prompt = self.genre.get_system_prompt("architect_lf")
        self.assertIn("卷", prompt)

    def test_canon_editor_business_accuracy(self):
        prompt = self.genre.get_system_prompt("canon_editor")
        self.assertIn("商业", prompt)

    def test_character_designer_persona(self):
        prompt = self.genre.get_system_prompt("character_designer")
        self.assertTrue(len(prompt) > 100)

    def test_fallback_for_unknown_role(self):
        prompt = self.genre.get_system_prompt("nonexistent_role")
        self.assertIn("总裁豪门", prompt)


# ---------------------------------------------------------------------------
# Phase 1: Prompt Fragments
# ---------------------------------------------------------------------------

class TestZongcaiPromptFragments(unittest.TestCase):
    """Verify prompt fragments load correctly for zongcai."""

    def setUp(self):
        self.genre = load_genre("总裁豪门")

    def test_seed_diversity_requirements(self):
        frag = self.genre.get_prompt_fragment("seed", "diversity_requirements")
        self.assertIn("契约", frag)
        self.assertIn("替嫁", frag)

    def test_seed_prohibitions(self):
        frag = self.genre.get_prompt_fragment("seed", "prohibitions")
        self.assertIn("霸总", frag)
        self.assertTrue(len(frag) > 50)

    def test_world_requirements(self):
        frag = self.genre.get_prompt_fragment("world", "requirements")
        self.assertTrue(len(frag) > 50)

    def test_world_sections(self):
        frag = self.genre.get_prompt_fragment("world", "sections")
        self.assertIn("商业", frag)
        self.assertIn("豪门", frag)

    def test_characters_requirements(self):
        frag = self.genre.get_prompt_fragment("characters", "requirements")
        self.assertTrue(len(frag) > 50)

    def test_characters_role_types(self):
        frag = self.genre.get_prompt_fragment("characters", "role_types")
        self.assertIn("总裁", frag)

    def test_outline_structure(self):
        frag = self.genre.get_prompt_fragment("outline", "structure")
        self.assertTrue(len(frag) > 50)

    def test_outline_constraints(self):
        frag = self.genre.get_prompt_fragment("outline", "constraints")
        self.assertIn("升级线", frag)

    def test_outline_ledgers(self):
        frag = self.genre.get_prompt_fragment("outline", "ledgers")
        self.assertIn("升级", frag)

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

class TestZongcaiEvaluation(unittest.TestCase):
    """Verify evaluation dimensions load correctly for zongcai."""

    def setUp(self):
        self.genre = load_genre("总裁豪门")

    def test_foundation_evaluation_has_dimensions(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("dimensions", config)
        self.assertIsInstance(config["dimensions"], dict)
        self.assertTrue(len(config["dimensions"]) >= 6)

    def test_foundation_has_business_system(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("business_system", config["dimensions"])

    def test_foundation_has_family_structure(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("family_structure", config["dimensions"])

    def test_foundation_has_upgrade_progression(self):
        config = self.genre.get_evaluation_config("foundation")
        self.assertIn("upgrade_progression", config["dimensions"])

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
        self.assertIn("elite_integration", config["dimensions"])

    def test_chapter_evaluation_has_emotional_payoff(self):
        config = self.genre.get_evaluation_config("chapter")
        self.assertIn("emotional_payoff", config["dimensions"])


# ---------------------------------------------------------------------------
# Phase 1: Reader Personas
# ---------------------------------------------------------------------------

class TestZongcaiReaderPersonas(unittest.TestCase):
    """Verify reader personas load correctly for zongcai."""

    def setUp(self):
        self.genre = load_genre("总裁豪门")

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
        """After merging _base.yaml + zongcai.yaml, base fields should still exist."""
        genre = load_genre("总裁豪门")
        eval_config = genre.get_evaluation_config("foundation")
        self.assertIn("dimensions", eval_config)

    def test_genre_overrides_base(self):
        """Genre-specific fields should override base defaults."""
        genre = load_genre("总裁豪门")
        self.assertEqual(genre.genre_key, "zongcai")
        self.assertEqual(genre.display_name, "总裁豪门")


# ---------------------------------------------------------------------------
# Phase 2: Project Initialization
# ---------------------------------------------------------------------------

class TestProjectInit(unittest.TestCase):
    """Test project initialization with zongcai genre."""

    def test_load_genre_for_project_with_zongcai(self):
        """When project.json has genre='总裁豪门', load_genre_for_project returns zongcai."""
        with tempfile.TemporaryDirectory() as tmpdir:
            story_dir = Path(tmpdir) / "story"
            story_dir.mkdir()
            proj = {"title": "测试", "genre": "总裁豪门", "tags": ["总裁", "豪门"]}
            (story_dir / "project.json").write_text(
                json.dumps(proj, ensure_ascii=False), encoding="utf-8"
            )
            with mock.patch(
                "genres.genre_registry.load_genre_for_project",
                side_effect=lambda: load_genre("总裁豪门"),
            ):
                genre = load_genre("总裁豪门")
                self.assertEqual(genre.genre_key, "zongcai")

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

    def test_tags_coverage_for_zongcai_defaults(self):
        """All default_tags for zongcai should have entries in TAG_DEFINITIONS."""
        from story_schema import TAG_DEFINITIONS
        genre = load_genre("总裁豪门")
        for tag in genre.default_tags:
            self.assertIn(tag, TAG_DEFINITIONS, f"Tag '{tag}' missing from TAG_DEFINITIONS")


# ---------------------------------------------------------------------------
# Phase 3: Prompt Content Verification
# ---------------------------------------------------------------------------

class TestZongcaiPromptContent(unittest.TestCase):
    """Verify that prompts assembled from genre config contain expected content."""

    def setUp(self):
        self.genre = load_genre("总裁豪门")

    def test_seed_prompt_has_urban_references(self):
        """Seed prompt should reference classic 总裁豪门 works."""
        prompt = self.genre.get_system_prompt("seed_writer_lf")
        has_ref = any(
            kw in prompt
            for kw in ["总裁", "豪门", "微微", "何以", "杉杉"]
        )
        self.assertTrue(has_ref, f"Seed prompt missing urban references")

    def test_world_prompt_has_business(self):
        """World builder prompt should mention 商业."""
        prompt = self.genre.get_system_prompt("world_builder")
        self.assertIn("商业", prompt)

    def test_world_sections_have_family_structure(self):
        """World sections should include 豪门家族."""
        sections = self.genre.get_prompt_fragment("world", "sections")
        self.assertIn("豪门", sections)

    def test_character_prompt_has_speech_patterns(self):
        """Character designer should mention speech patterns."""
        prompt = self.genre.get_system_prompt("character_designer")
        has_speech = any(kw in prompt for kw in ["用词", "语气", "说话", "对话"])
        self.assertTrue(has_speech, "Character prompt missing speech pattern guidance")

    def test_outline_constraints_forbid_upgrade_gaps(self):
        """Outline constraints should forbid gaps in upgrade detail."""
        constraints = self.genre.get_prompt_fragment("outline", "constraints")
        self.assertIn("升级线", constraints)

    def test_ledgers_have_upgrade(self):
        """Ledgers should include 升级/逆袭台账."""
        ledgers = self.genre.get_prompt_fragment("outline", "ledgers")
        self.assertIn("升级", ledgers)

    def test_voice_template_forbids_ancient_words(self):
        """Voice template vocabulary should forbid ancient words."""
        vt = self.genre.get_voice_template()
        vocab = vt.get("vocabulary_hint", "")
        has_forbidden = any(kw in vocab for kw in ["夫君", "娘子", "小姐"])
        self.assertTrue(has_forbidden, "Voice template missing forbidden ancient words list")

    def test_voice_template_has_modern_vocabularies(self):
        """Voice template should have modern vocabulary guidance."""
        vt = self.genre.get_voice_template()
        vocab = vt.get("vocabulary_hint", "")
        self.assertIn("总裁", vocab)
        self.assertIn("商业", vocab)

    def test_prohibitions_ban_cliche(self):
        """Prohibitions should ban cliched tropes."""
        prohibitions = self.genre.get_prompt_fragment("seed", "prohibitions")
        self.assertIn("霸总", prohibitions)

    def test_evaluation_cross_checks_business(self):
        """Foundation evaluation should include business cross-checks."""
        config = self.genre.get_evaluation_config("foundation")
        cross_checks = config.get("cross_checks", [])
        cc_text = " ".join(cross_checks)
        self.assertTrue(
            any(kw in cc_text for kw in ["商业", "股权", "公司"]),
            f"Cross-checks missing business verification: {cross_checks}"
        )


# ---------------------------------------------------------------------------
# Phase 3: Genre Differences Verification
# ---------------------------------------------------------------------------

class TestGenreDifferences(unittest.TestCase):
    """Verify zongcai differs from zhongtian and niandai in key ways."""

    def setUp(self):
        self.zongcai = load_genre("总裁豪门")
        self.zhongtian = load_genre("种田文")
        self.niandai = load_genre("年代文")

    def test_different_genre_keys(self):
        self.assertNotEqual(self.zongcai.genre_key, self.zhongtian.genre_key)
        self.assertNotEqual(self.zongcai.genre_key, self.niandai.genre_key)

    def test_different_display_names(self):
        self.assertNotEqual(self.zongcai.display_name, self.zhongtian.display_name)
        self.assertNotEqual(self.zongcai.display_name, self.niandai.display_name)

    def test_different_default_tags(self):
        self.assertNotEqual(self.zongcai.default_tags, self.zhongtian.default_tags)
        self.assertNotEqual(self.zongcai.default_tags, self.niandai.default_tags)

    def test_different_system_prompts(self):
        """Chapter writer prompts should be completely different."""
        z_prompt = self.zongcai.get_system_prompt("chapter_writer")
        t_prompt = self.zhongtian.get_system_prompt("chapter_writer")
        n_prompt = self.niandai.get_system_prompt("chapter_writer")
        self.assertNotEqual(z_prompt, t_prompt)
        self.assertNotEqual(z_prompt, n_prompt)

    def test_different_evaluation_dimensions(self):
        """Foundation evaluation dimensions should differ."""
        z_eval = self.zongcai.get_evaluation_config("foundation")
        t_eval = self.zhongtian.get_evaluation_config("foundation")
        n_eval = self.niandai.get_evaluation_config("foundation")
        z_names = set(z_eval.get("dimensions", {}).keys())
        t_names = set(t_eval.get("dimensions", {}).keys())
        n_names = set(n_eval.get("dimensions", {}).keys())
        self.assertNotEqual(z_names, t_names)
        self.assertNotEqual(z_names, n_names)

    def test_different_voice_templates(self):
        z_vocab = self.zongcai.get_voice_template().get("vocabulary_hint", "")
        t_vocab = self.zhongtian.get_voice_template().get("vocabulary_hint", "")
        n_vocab = self.niandai.get_voice_template().get("vocabulary_hint", "")
        self.assertNotEqual(z_vocab, t_vocab)
        self.assertNotEqual(z_vocab, n_vocab)

    def test_different_craft_files(self):
        z_craft = load_genre_craft(self.zongcai)
        t_craft = load_genre_craft(self.zhongtian)
        n_craft = load_genre_craft(self.niandai)
        self.assertNotEqual(z_craft, t_craft)
        self.assertNotEqual(z_craft, n_craft)
        # zongcai craft should mention business-specific concepts
        self.assertIn("商战", z_craft)
        self.assertIn("身份落差", z_craft)


# ---------------------------------------------------------------------------
# Phase 3: Prompt Assembly (simulating how pipeline scripts use genre)
# ---------------------------------------------------------------------------

class TestPromptAssembly(unittest.TestCase):
    """Simulate how pipeline scripts assemble prompts from genre config."""

    def setUp(self):
        self.genre = load_genre("总裁豪门")

    def test_seed_prompt_assembly(self):
        """Simulate seed_lf.py prompt assembly."""
        system = self.genre.get_system_prompt("seed_writer_lf")
        definition = self.genre.genre_definition
        title_rules = self.genre.title_rules
        diversity = self.genre.get_prompt_fragment("seed", "diversity_requirements")
        prohibitions = self.genre.get_prompt_fragment("seed", "prohibitions")

        full_prompt = f"{system}\n{definition}\n{title_rules}\n{diversity}\n{prohibitions}"
        self.assertIn("总裁", full_prompt)
        self.assertIn("豪门", full_prompt)
        self.assertTrue(len(full_prompt) > 500)

    def test_long_form_seed_prompt_uses_zongcai_requirements(self):
        """Long-form seed prompt should not fall back to old agrarian wording."""
        import seed_lf

        original_genre = seed_lf.genre
        try:
            seed_lf.genre = self.genre
            ranges = seed_lf._compute_volume_ranges(12)
            prompt = seed_lf._build_generate_prompt(
                count=3,
                tags_context="",
                target_words_label="100万字",
                target_chapters=240,
                total_volumes=12,
                early_chapters=20,
                ranges=ranges,
            )
        finally:
            seed_lf.genre = original_genre

        self.assertIn("都市/豪门/商业背景", prompt)
        self.assertIn("董事会", prompt)
        self.assertIn("股权结构", prompt)
        self.assertIn("男主破例", prompt)
        self.assertNotIn("府城", prompt)
        self.assertNotIn("朝堂", prompt)
        self.assertNotIn("三文钱", prompt)

    def test_long_form_seed_prompt_accepts_external_market_research(self):
        """Market research should be injected as replaceable external context."""
        import seed_lf

        original_genre = seed_lf.genre
        try:
            seed_lf.genre = self.genre
            ranges = seed_lf._compute_volume_ranges(12)
            market_context = seed_lf._build_market_research_context(
                "平台：番茄小说\n趋势：男二上位、搞笑甜宠、非京圈地域创新"
            )
            prompt = seed_lf._build_generate_prompt(
                count=3,
                tags_context="",
                target_words_label="100万字",
                target_chapters=240,
                total_volumes=12,
                early_chapters=20,
                ranges=ranges,
                market_research_context=market_context,
            )
        finally:
            seed_lf.genre = original_genre

        self.assertIn("外部榜单/市场调研参考", prompt)
        self.assertIn("番茄小说", prompt)
        self.assertIn("热门基础盘 + 差异化切入", prompt)
        self.assertIn("不要复刻榜单作品", prompt)

    def test_world_prompt_assembly(self):
        """Simulate gen_world_lf.py prompt assembly."""
        system = self.genre.get_system_prompt("world_builder")
        req = self.genre.get_prompt_fragment("world", "requirements")
        sections = self.genre.get_prompt_fragment("world", "sections")

        full_prompt = f"{system}\n{req}\n{sections}"
        self.assertIn("商业", full_prompt)
        self.assertIn("豪门", full_prompt)

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
        self.assertIn("升级", full_prompt)
        self.assertTrue(len(full_prompt) > 300)

    def test_canon_prompt_assembly(self):
        """Simulate gen_canon.py prompt assembly."""
        system = self.genre.get_system_prompt("canon_editor")
        sections = self.genre.get_prompt_fragment("canon", "sections")

        full_prompt = f"{system}\n{sections}"
        self.assertIn("商业", full_prompt)
        self.assertIn("豪门", full_prompt)

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

        self.assertIn("business_system", dims)
        self.assertIn("family_structure", dims)
        self.assertIn("upgrade_progression", dims)
        self.assertIn("urban_setting", dims)


if __name__ == "__main__":
    unittest.main()
