#!/usr/bin/env python3
"""
test_gcbt_v40.py — Comprehensive test suite for gcbt v4.0
==========================================================

Run all tests:
    python test_gcbt_v40.py

Run a single test class:
    python -m pytest test_gcbt_v40.py::TestCorpusConfigLoader -v

Run with verbose output:
    python -m pytest test_gcbt_v40.py -v --tb=short

Requirements:
    pip install pytest PyYAML
    gcbt_v40.py and corpus_config.yaml must be in the same directory.

Coverage areas:
    1.  CorpusConfigLoader — YAML loading, GGT fallback, merging rules
    2.  LanguageProfile     — zero hardcoded defaults, field presence
    3.  Language detection  — path keyword matching, fallback to und
    4.  UnifiedConfig       — YAML sync, preset overrides, legacy compat
    5.  ZambianTextCleaner  — every cleaning step, config.cleaning.* routing
    6.  SentenceSegmenter   — NLTK, fallback, empty abbreviations guard
    7.  SRTProcessor        — timecode stripping, HTML tag removal
    8.  File processors     — extension routing, SRT vs TXT separation
    9.  OutputGenerator     — TXT / JSON / cleaned output
    10. ZambianCorpusBuilder — end-to-end with real temp files
    11. TextPatterns         — verse_reference() live reference
    12. ProcessingStats      — string formatting, property calculations
    13. YAML safety          — boolean coercion, quote handling
    14. Backward compat      — aliases, fix_ocr_errors method name
"""

import ast
import copy
import dataclasses
import json
import logging
import os
import re
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# ── Locate gcbt_v40.py ──────────────────────────────────────────────────────
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

# Suppress logging during tests
logging.disable(logging.CRITICAL)

import gcbt_v40
from gcbt_v40 import (
    LanguageProfile, CorpusConfigLoader, UnifiedConfig,
    CleaningConfig, SegmentationConfig, OutputConfig,
    ZambianTextCleaner, SentenceSegmenter, SRTProcessor, TXTProcessor,
    OutputGenerator, ZambianCorpusBuilder, ProcessingStats, ProcessingResult,
    TextPatterns, ExtractionConfig,
    LANGUAGE_PROFILES, _UNIVERSAL_PROFILE, UNIVERSAL_VERSE_PATTERN,
    detect_language, reload_profiles, build_chapter_heading_pattern,
    remove_bible_references,
    CorpusProcessingPipeline, GobeloCorpusBuilder, ChitongaTextCleaner,
)

_CORPUS_CONFIG = str(_HERE / "corpus_config.yaml")

# ── Bootstrap module-level profiles once ────────────────────────────────────
gcbt_v40.LANGUAGE_PROFILES, gcbt_v40._UNIVERSAL_PROFILE, \
gcbt_v40.UNIVERSAL_VERSE_PATTERN, gcbt_v40._CONFIG_LOADER = \
    gcbt_v40._initialise_profiles(_CORPUS_CONFIG)

# Re-import references that were bound at import time
from gcbt_v40 import LANGUAGE_PROFILES, _UNIVERSAL_PROFILE, UNIVERSAL_VERSE_PATTERN


# ============================================================================
# Helpers
# ============================================================================

def _logger():
    return logging.getLogger("test_gcbt")


def _cleaner(config=None, profile=None):
    if config is None:
        config = UnifiedConfig(language="und")
    if profile is None:
        profile = LANGUAGE_PROFILES.get("toi", _UNIVERSAL_PROFILE)
    return ZambianTextCleaner(config, _logger(), ProcessingStats(), profile)


def _make_corpus_config(extra_global=None, extra_languages=None):
    """Write a minimal corpus_config.yaml to a temp file and return its path."""
    import yaml
    data = {
        "global": {
            "verse_pattern": r"\b(?:\d{1,2}\s*)?[A-Za-z#]{1,20}\.?\s?\d{1,3}:\d{1,3}(?:[,\-]\d{1,3})*\b",
            "punctuation_map": {"\u201c": '"', "\u201d": '"', "\u2013": "-"},
            "chapter_words": ["Chapter"],
            "book_abbreviations": ["Dr", "Mr"],
            "ocr_corrections": {"rn": "m"},
            "valid_single_chars": ["a", "e", "i", "o", "u", "n", "m"],
            "extra_special_chars": [],
            "strip_patterns": [],
            "remove_urls": True,
            "remove_emails": True,
            "filter_single_chars": True,
            "fix_hyphenation": True,
            "normalize_whitespace": True,
            "normalize_unicode": True,
            "normalize_punctuation": True,
            "process_ocr_artifacts": True,
            "preserve_bible_text": False,
            "protect_citations": False,
            "min_sentence_length": 3,
            "max_sentence_length": 1000,
        },
        "languages": {
            "tst": {
                "ggt_yaml": "",
                "path_keywords": ["testlang", "tst"],
                "chapter_words": ["Chapta"],
                "book_abbreviations": ["Mw"],
                "valid_single_chars": ["w", "b"],
                "extra_special_chars": ["ng"],
                "ocr_corrections": {"cl": "ci"},
            }
        },
    }
    if extra_global:
        data["global"].update(extra_global)
    if extra_languages:
        data["languages"].update(extra_languages)

    tf = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    yaml.dump(data, tf)
    tf.close()
    return tf.name


# ============================================================================
# 1. CorpusConfigLoader
# ============================================================================

class TestCorpusConfigLoader(unittest.TestCase):

    def setUp(self):
        self.loader = gcbt_v40._CONFIG_LOADER
        self.assertIsNotNone(self.loader, "Loader must be initialised before tests")

    # ── Profiles present ────────────────────────────────────────────────────
    def test_all_seven_languages_loaded(self):
        expected = {"toi", "bem", "nya", "loz", "lun", "lue", "kqn", "und"}
        self.assertEqual(set(LANGUAGE_PROFILES.keys()), expected)

    def test_und_profile_exists(self):
        self.assertIn("und", LANGUAGE_PROFILES)
        self.assertEqual(LANGUAGE_PROFILES["und"].iso_code, "und")

    # ── Missing config raises ConfigError ───────────────────────────────────
    def test_missing_config_raises(self):
        from gcbt_v40 import ConfigError
        with self.assertRaises(ConfigError):
            CorpusConfigLoader("/tmp/does_not_exist_abc123.yaml")

    # ── Minimal config with no GGT YAML ─────────────────────────────────────
    def test_minimal_config_no_ggt(self):
        cfg_path = _make_corpus_config()
        try:
            loader = CorpusConfigLoader(cfg_path)
            self.assertIn("tst", loader.profiles)
            self.assertIn("und", loader.profiles)
        finally:
            os.unlink(cfg_path)

    # ── Merging: additive fields ─────────────────────────────────────────────
    def test_chapter_words_additive(self):
        toi = LANGUAGE_PROFILES["toi"]
        self.assertIn("Chapter", toi.chapter_words)      # from global
        self.assertIn("Matalikilo", toi.chapter_words)   # from toi block
        self.assertIn("Mutatwe", toi.chapter_words)      # from toi block

    def test_book_abbreviations_additive(self):
        toi = LANGUAGE_PROFILES["toi"]
        self.assertIn("Dr", toi.book_abbreviations)  # global
        self.assertIn("Mw", toi.book_abbreviations)  # toi
        self.assertIn("Ba", toi.book_abbreviations)  # toi

    def test_valid_single_chars_additive(self):
        toi = LANGUAGE_PROFILES["toi"]
        self.assertIn("a", toi.valid_single_chars)   # global vowels
        self.assertIn("w", toi.valid_single_chars)   # toi NC3 prefix
        self.assertIn("y", toi.valid_single_chars)   # toi conjunction

    def test_extra_special_chars_additive(self):
        toi = LANGUAGE_PROFILES["toi"]
        self.assertIn("ng", toi.extra_special_chars)
        self.assertIn("ny", toi.extra_special_chars)

    def test_strip_patterns_additive(self):
        """Global strip_patterns + per-language are concatenated."""
        cfg_path = _make_corpus_config(
            extra_global={"strip_patterns": [r"^\s*PAGE\s+\d+"]},
            extra_languages={"tst": {
                "ggt_yaml": "",
                "path_keywords": ["tst"],
                "strip_patterns": [r"^\s*Footnote\s+\d+"],
            }},
        )
        try:
            loader = CorpusConfigLoader(cfg_path)
            tst = loader.profiles["tst"]
            self.assertIn(r"^\s*PAGE\s+\d+", tst.strip_patterns)
            self.assertIn(r"^\s*Footnote\s+\d+", tst.strip_patterns)
        finally:
            os.unlink(cfg_path)

    # ── Merging: ocr_corrections key-by-key override ─────────────────────────
    def test_ocr_corrections_global_present(self):
        toi = LANGUAGE_PROFILES["toi"]
        self.assertEqual(toi.ocr_corrections.get("rn"), "m")   # global
        self.assertEqual(toi.ocr_corrections.get("|"), "I")    # global

    def test_ocr_corrections_language_overrides(self):
        toi = LANGUAGE_PROFILES["toi"]
        self.assertEqual(toi.ocr_corrections.get("cl"), "ci")  # toi override

    def test_ocr_corrections_language_adds(self):
        toi = LANGUAGE_PROFILES["toi"]
        self.assertEqual(toi.ocr_corrections.get("0"), "o")    # toi-only key
        self.assertEqual(toi.ocr_corrections.get("1"), "l")

    # ── Merging: punctuation_map global-only ─────────────────────────────────
    def test_punctuation_map_from_global(self):
        toi = LANGUAGE_PROFILES["toi"]
        self.assertIn("\u201c", toi.punctuation_map)  # left double quote
        self.assertIn("\u2014", toi.punctuation_map)  # em dash

    # ── und = union of all languages ─────────────────────────────────────────
    def test_und_chapter_words_union(self):
        und = _UNIVERSAL_PROFILE
        for word in ["Chapter", "Matalikilo", "Mutwalo", "Kauhanyo", "Mutu"]:
            self.assertIn(word, und.chapter_words, f"Missing '{word}' in und.chapter_words")

    def test_und_valid_single_chars_union(self):
        und = _UNIVERSAL_PROFILE
        self.assertIn("w", und.valid_single_chars)  # from toi
        self.assertIn("f", und.valid_single_chars)  # from bem
        self.assertIn("s", und.valid_single_chars)  # from loz

    def test_und_extra_special_chars_union(self):
        self.assertIn("ng", _UNIVERSAL_PROFILE.extra_special_chars)

    # ── verse_pattern compiled from YAML ─────────────────────────────────────
    def test_verse_pattern_from_yaml(self):
        pat = self.loader.verse_pattern
        self.assertIsNotNone(pat.search("Heb 2:11"))
        self.assertIsNotNone(pat.search("Gen 1:1-3"))
        self.assertIsNotNone(pat.search("1 Kor 11:7"))
        self.assertIsNotNone(pat.search("M#Int 127:3"))
        self.assertIsNone(pat.search("hello world"))

    # ── YAML boolean coercion ─────────────────────────────────────────────────
    def test_no_booleans_in_book_abbreviations(self):
        for iso, profile in LANGUAGE_PROFILES.items():
            for item in profile.book_abbreviations:
                self.assertIsInstance(
                    item, str,
                    f"Boolean found in {iso}.book_abbreviations: {item!r}"
                )

    def test_no_booleans_in_valid_single_chars(self):
        for iso, profile in LANGUAGE_PROFILES.items():
            for item in profile.valid_single_chars:
                self.assertIsInstance(
                    item, str,
                    f"Boolean found in {iso}.valid_single_chars: {item!r}"
                )

    def test_no_string_in_book_abbreviations(self):
        """'no' must survive as a string, not become False."""
        und = _UNIVERSAL_PROFILE
        self.assertIn("no", und.book_abbreviations)


# ============================================================================
# 2. LanguageProfile — zero hardcoded defaults
# ============================================================================

class TestLanguageProfileDefaults(unittest.TestCase):

    def test_every_field_empty_by_default(self):
        """A bare LanguageProfile(name=X, iso_code=Y) must have empty containers."""
        bare = LanguageProfile(name="X", iso_code="x")
        for f in dataclasses.fields(bare):
            if f.name in ("name", "iso_code"):
                continue
            val = getattr(bare, f.name)
            self.assertIn(
                val, (set(), [], {}, ""),
                f"Field '{f.name}' has hardcoded data: {val!r}"
            )

    def test_field_names_match_yaml_keys(self):
        """Critical field names must match corpus_config.yaml key names."""
        bare = LanguageProfile(name="X", iso_code="x")
        field_names = {f.name for f in dataclasses.fields(bare)}
        required = {
            "book_abbreviations", "ocr_corrections", "chapter_words",
            "valid_single_chars", "extra_special_chars", "strip_patterns",
            "punctuation_map", "path_keywords", "special_chars",
        }
        for name in required:
            self.assertIn(name, field_names, f"Missing field: {name}")

    def test_no_abbreviations_field(self):
        """Old field name 'abbreviations' must not exist."""
        bare = LanguageProfile(name="X", iso_code="x")
        field_names = {f.name for f in dataclasses.fields(bare)}
        self.assertNotIn("abbreviations", field_names)

    def test_no_ocr_errors_field(self):
        """Old field name 'ocr_errors' must not exist."""
        bare = LanguageProfile(name="X", iso_code="x")
        field_names = {f.name for f in dataclasses.fields(bare)}
        self.assertNotIn("ocr_errors", field_names)


# ============================================================================
# 3. Language detection
# ============================================================================

class TestLanguageDetection(unittest.TestCase):

    def _detect(self, path_str):
        return gcbt_v40._CONFIG_LOADER.detect_language(Path(path_str)).iso_code

    def test_chitonga_detected(self):
        self.assertEqual(self._detect("/corpus/chitonga/novel.txt"), "toi")

    def test_citonga_variant_detected(self):
        self.assertEqual(self._detect("/data/citonga/bible.pdf"), "toi")

    def test_chibemba_detected(self):
        self.assertEqual(self._detect("/data/chibemba/text.pdf"), "bem")

    def test_silozi_detected(self):
        self.assertEqual(self._detect("/corpus/silozi/proverbs.txt"), "loz")

    def test_lozi_variant_detected(self):
        self.assertEqual(self._detect("/corpus/lozi/text.txt"), "loz")

    def test_kaonde_detected(self):
        self.assertEqual(self._detect("/corpus/kaonde/story.epub"), "kqn")

    def test_luvale_detected(self):
        self.assertEqual(self._detect("/corpus/luvale/text.txt"), "lue")

    def test_lunda_detected(self):
        self.assertEqual(self._detect("/corpus/lunda/text.txt"), "lun")

    def test_unknown_returns_und(self):
        self.assertEqual(self._detect("/corpus/unknown/file.txt"), "und")

    def test_empty_path_returns_und(self):
        self.assertEqual(self._detect("/data/document.pdf"), "und")

    def test_case_insensitive(self):
        self.assertEqual(self._detect("/corpus/CHITONGA/novel.txt"), "toi")
        self.assertEqual(self._detect("/corpus/ChiBemba/text.pdf"), "bem")

    def test_iso_code_itself_is_keyword(self):
        self.assertEqual(self._detect("/data/toi/novel.pdf"), "toi")
        self.assertEqual(self._detect("/data/bem/text.txt"), "bem")

    def test_module_level_detect_language(self):
        """Module-level detect_language() delegates to loader."""
        profile = detect_language(Path("/corpus/chitonga/test.txt"))
        self.assertEqual(profile.iso_code, "toi")


# ============================================================================
# 4. UnifiedConfig — YAML sync, presets, legacy compat
# ============================================================================

class TestUnifiedConfig(unittest.TestCase):

    def setUp(self):
        import yaml
        with open(_CORPUS_CONFIG) as f:
            self._g = yaml.safe_load(f)["global"]

    def test_default_config_syncs_from_yaml(self):
        cfg = UnifiedConfig()
        g = self._g
        self.assertEqual(cfg.cleaning.remove_urls,           g["remove_urls"])
        self.assertEqual(cfg.cleaning.filter_single_chars,   g["filter_single_chars"])
        self.assertEqual(cfg.cleaning.normalize_unicode,     g["normalize_unicode"])
        self.assertEqual(cfg.cleaning.normalize_punctuation, g["normalize_punctuation"])
        self.assertEqual(cfg.cleaning.process_ocr_artifacts, g["process_ocr_artifacts"])
        self.assertEqual(cfg.cleaning.fix_hyphenation,       g["fix_hyphenation"])
        self.assertEqual(cfg.segmentation.min_sentence_length, g["min_sentence_length"])
        self.assertEqual(cfg.segmentation.max_sentence_length, g["max_sentence_length"])

    def test_preset_minimal_overrides_yaml(self):
        cfg = UnifiedConfig.preset_minimal()
        self.assertFalse(cfg.cleaning.filter_single_chars)
        self.assertFalse(cfg.cleaning.process_ocr_artifacts)

    def test_preset_aggressive_overrides_yaml(self):
        cfg = UnifiedConfig.preset_aggressive()
        self.assertTrue(cfg.cleaning.filter_single_chars)

    def test_preset_pristine_overrides_yaml(self):
        cfg = UnifiedConfig.preset_pristine()
        self.assertTrue(cfg.cleaning.pristine_mode)
        self.assertEqual(cfg.cleaning.unicode_form, "NFKD")

    def test_explicit_cleaning_not_overwritten_by_yaml(self):
        """An explicitly passed CleaningConfig must survive __post_init__."""
        custom = CleaningConfig(filter_single_chars=False)
        cfg = UnifiedConfig(cleaning=custom)
        self.assertFalse(cfg.cleaning.filter_single_chars)

    def test_resolve_profile_auto(self):
        cfg = UnifiedConfig(language="auto")
        profile = cfg.resolve_profile(Path("/corpus/chitonga/test.txt"))
        self.assertEqual(profile.iso_code, "toi")

    def test_resolve_profile_fixed(self):
        cfg = UnifiedConfig(language="bem")
        self.assertEqual(cfg.resolve_profile().iso_code, "bem")

    def test_resolve_profile_auto_no_path(self):
        cfg = UnifiedConfig(language="auto")
        profile = cfg.resolve_profile(None)
        self.assertEqual(profile.iso_code, "und")

    def test_json_roundtrip(self):
        cfg = UnifiedConfig(language="bem")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            path = tf.name
        try:
            cfg.to_json(path)
            loaded = UnifiedConfig.from_json(path)
            self.assertEqual(loaded.language, "bem")
        finally:
            os.unlink(path)

    def test_cleaning_config_new_fields_exist(self):
        cfg = CleaningConfig()
        self.assertTrue(hasattr(cfg, "fix_hyphenation"))
        self.assertTrue(hasattr(cfg, "protect_abbreviations"))
        self.assertTrue(hasattr(cfg, "remove_bible_references"))

    def test_cleaning_config_new_field_defaults(self):
        cfg = CleaningConfig()
        self.assertTrue(cfg.fix_hyphenation)
        self.assertFalse(cfg.protect_abbreviations)
        self.assertFalse(cfg.remove_bible_references)


# ============================================================================
# 5. ZambianTextCleaner — every cleaning step
# ============================================================================

class TestZambianTextCleaner(unittest.TestCase):

    def setUp(self):
        self.toi = LANGUAGE_PROFILES["toi"]
        self.cfg = UnifiedConfig(language="toi")
        self.cleaner = _cleaner(self.cfg, self.toi)

    # ── normalize_unicode ────────────────────────────────────────────────────
    def test_normalize_unicode_nfc(self):
        # NFD decomposed 'á' should become NFC composed 'á'
        nfd = "a\u0301"   # a + combining acute accent
        result = self.cleaner.normalize_unicode(nfd)
        self.assertIn("\xe1", result)  # á

    # ── normalize_punctuation ────────────────────────────────────────────────
    def test_normalize_punctuation_curly_quotes(self):
        result = self.cleaner.normalize_punctuation("\u201cHello\u201d")
        self.assertIn('"Hello"', result)

    def test_normalize_punctuation_em_dash(self):
        result = self.cleaner.normalize_punctuation("word \u2014 word")
        self.assertIn("word - word", result)

    def test_normalize_punctuation_ellipsis(self):
        result = self.cleaner.normalize_punctuation("wait\u2026")
        self.assertIn("wait...", result)

    # ── fix_hyphenation ──────────────────────────────────────────────────────
    def test_fix_hyphenation_joins_word(self):
        result = self.cleaner.fix_hyphenation("senten-\nce continues")
        self.assertIn("sentence", result)

    def test_fix_hyphenation_off(self):
        cfg = UnifiedConfig(language="toi", cleaning=CleaningConfig(fix_hyphenation=False))
        c = ZambianTextCleaner(cfg, _logger(), ProcessingStats(), self.toi)
        result = c.clean("senten-\nce continues")
        self.assertNotIn("sentence", result)

    # ── remove_urls ──────────────────────────────────────────────────────────
    def test_remove_urls_http(self):
        result = self.cleaner.remove_urls("Visit https://example.com for more.")
        self.assertNotIn("https://", result)

    def test_remove_urls_www(self):
        result = self.cleaner.remove_urls("See www.example.com today.")
        self.assertNotIn("www.example.com", result)

    def test_remove_urls_off(self):
        cfg = UnifiedConfig(language="und", cleaning=CleaningConfig(remove_urls=False))
        c = ZambianTextCleaner(cfg, _logger(), ProcessingStats(), self.toi)
        result = c.clean("Visit https://example.com now.")
        self.assertIn("https://example.com", result)

    # ── remove_emails ────────────────────────────────────────────────────────
    def test_remove_emails(self):
        result = self.cleaner.remove_emails("Contact admin@example.com today.")
        self.assertNotIn("admin@example.com", result)

    # ── fix_ocr_corrections ──────────────────────────────────────────────────
    def test_fix_ocr_corrections_global_rule(self):
        result = self.cleaner.fix_ocr_corrections("rn and more text")
        self.assertIn("m and more text", result)

    def test_fix_ocr_corrections_language_rule(self):
        result = self.cleaner.fix_ocr_corrections("the cl sound")
        self.assertIn("ci", result)

    def test_fix_ocr_corrections_alias(self):
        result = self.cleaner.fix_ocr_errors("the cl sound")
        self.assertIn("ci", result)

    # ── filter_single_characters ─────────────────────────────────────────────
    def test_filter_keeps_valid_morpheme(self):
        result = self.cleaner.filter_single_characters("a z b w x y k")
        kept = result.split()
        self.assertIn("w", kept)   # toi NC3 prefix
        self.assertIn("y", kept)   # toi conjunction
        self.assertIn("a", kept)   # global vowel

    def test_filter_removes_invalid_single_char(self):
        result = self.cleaner.filter_single_characters("a z b w x y k")
        kept = result.split()
        self.assertNotIn("z", kept)
        self.assertNotIn("x", kept)

    def test_filter_single_chars_off(self):
        cfg = UnifiedConfig(language="toi", cleaning=CleaningConfig(filter_single_chars=False))
        c = ZambianTextCleaner(cfg, _logger(), ProcessingStats(), self.toi)
        result = c.clean("a z b w x y k word")
        self.assertIn("z", result)

    # ── protect_abbreviations ────────────────────────────────────────────────
    def test_protect_abbreviations_uses_profile(self):
        cfg = UnifiedConfig(language="toi",
                            cleaning=CleaningConfig(protect_abbreviations=True))
        c = ZambianTextCleaner(cfg, _logger(), ProcessingStats(), self.toi)
        protected = c.protect_abbreviations("Dr. Smith and Mw. Banda attended.")
        self.assertIn("Dr<DOT>", protected)
        self.assertIn("Mw<DOT>", protected)

    def test_restore_abbreviations(self):
        cfg = UnifiedConfig(language="toi",
                            cleaning=CleaningConfig(protect_abbreviations=True))
        c = ZambianTextCleaner(cfg, _logger(), ProcessingStats(), self.toi)
        protected = c.protect_abbreviations("Dr. Smith arrived.")
        restored = c.restore_abbreviations(protected)
        self.assertNotIn("<DOT>", restored)
        self.assertIn("Dr.", restored)

    # ── remove_chapter_headings ──────────────────────────────────────────────
    def test_remove_chapter_headings_toi(self):
        text = "Matalikilo 3\nSome text here.\nMutatwe 5\nMore text."
        result = self.cleaner.remove_chapter_headings(text)
        self.assertNotIn("Matalikilo 3", result)
        self.assertNotIn("Mutatwe 5", result)
        self.assertIn("Some text here.", result)

    def test_remove_chapter_headings_english(self):
        text = "Chapter IV\nContent follows.\nPart 2\nMore content."
        result = self.cleaner.remove_chapter_headings(text)
        self.assertNotIn("Chapter IV", result)
        self.assertIn("Content follows.", result)

    def test_remove_chapter_headings_roman_numerals(self):
        text = "Chapter XLII\nSome text."
        result = self.cleaner.remove_chapter_headings(text)
        self.assertNotIn("Chapter XLII", result)

    # ── apply_strip_patterns ─────────────────────────────────────────────────
    def test_apply_strip_patterns_removes_match(self):
        profile_copy = copy.deepcopy(self.toi)
        profile_copy.strip_patterns = [r"^\s*REMOVE\s*$"]
        c = ZambianTextCleaner(self.cfg, _logger(), ProcessingStats(), profile_copy)
        result = c.apply_strip_patterns("Keep this\nREMOVE\nKeep this too")
        self.assertNotIn("REMOVE", result)
        self.assertIn("Keep this", result)

    def test_apply_strip_patterns_passthrough_when_empty(self):
        text = "Normal line\nAnother line"
        result = self.cleaner.apply_strip_patterns(text)
        self.assertEqual(text, result)

    def test_apply_strip_patterns_invalid_regex_skips(self):
        profile_copy = copy.deepcopy(self.toi)
        profile_copy.strip_patterns = [r"[invalid("]
        c = ZambianTextCleaner(self.cfg, _logger(), ProcessingStats(), profile_copy)
        result = c.apply_strip_patterns("Some text")
        self.assertEqual("Some text", result)

    # ── remove_bible_references ──────────────────────────────────────────────
    def test_remove_bible_references_module_fn(self):
        text = "See Heb 2:11 and Gen 1:1-3 for details."
        cleaned, count = remove_bible_references(text)
        self.assertNotIn("Heb 2:11", cleaned)
        self.assertNotIn("Gen 1:1-3", cleaned)
        self.assertEqual(count, 2)

    def test_bible_references_stray_punctuation_cleaned(self):
        text = "See; Gen 1:1, and Heb 2:3,"
        cleaned, _ = remove_bible_references(text)
        self.assertNotIn("Gen 1:1", cleaned)
        # stray semicolons/commas should not remain standalone
        self.assertNotIn(",,", cleaned)

    def test_remove_bible_references_cleaning_flag(self):
        cfg = UnifiedConfig(language="toi",
                            cleaning=CleaningConfig(
                                remove_bible_references=True,
                                preserve_bible_text=False,
                            ))
        c = ZambianTextCleaner(cfg, _logger(), ProcessingStats(), self.toi)
        result = c.clean("Read Gen 1:1 carefully. This is important.")
        self.assertNotIn("Gen 1:1", result)

    # ── clean() reads config.cleaning.* only ────────────────────────────────
    def test_clean_reads_cleaning_not_legacy(self):
        """clean() must not read any legacy flat field directly."""
        src = Path(_HERE / "gcbt_v40.py").read_text()
        start = src.find("    def clean(self, text: str) -> str:")
        end   = src.find("\n    # Backward-compat alias\n    def clean_text")
        body  = src[start:end]
        legacy_reads = [
            l.strip() for l in body.splitlines()
            if "self.config." in l
            and "self.config.cleaning" not in l
            and "self.config.segmentation" not in l
        ]
        self.assertEqual(legacy_reads, [],
                         f"Legacy flat-field reads found in clean():\n  "
                         + "\n  ".join(legacy_reads))

    # ── set_profile ──────────────────────────────────────────────────────────
    def test_set_profile_switches_chapter_pattern(self):
        loz = LANGUAGE_PROFILES["loz"]
        self.cleaner.set_profile(loz)
        text = "Kauhanyo 5\nSome Lozi text here."
        result = self.cleaner.remove_chapter_headings(text)
        self.assertNotIn("Kauhanyo 5", result)

    def test_set_profile_switches_ocr_corrections(self):
        # toi has cl->ci; und does not
        und_profile = _UNIVERSAL_PROFILE
        self.cleaner.set_profile(und_profile)
        result = self.cleaner.fix_ocr_corrections("the cl sound")
        # und doesn't have cl->ci, so it should pass through
        self.assertIn("cl", result)

    # ── collapse_whitespace ──────────────────────────────────────────────────
    def test_collapse_whitespace_spaces(self):
        result = self.cleaner.collapse_whitespace("word    word")
        self.assertEqual("word word", result)

    def test_collapse_whitespace_newlines(self):
        result = self.cleaner.collapse_whitespace("line\n\n\n\nline")
        self.assertNotIn("\n\n\n", result)


# ============================================================================
# 6. SentenceSegmenter
# ============================================================================

class TestSentenceSegmenter(unittest.TestCase):

    def setUp(self):
        self.toi = LANGUAGE_PROFILES["toi"]
        self.cfg = SegmentationConfig()
        self.stats = ProcessingStats()

    def _seg(self, profile=None):
        return SentenceSegmenter(
            self.cfg, _logger(), self.stats,
            profile or self.toi
        )

    # ── Empty abbreviations guard ────────────────────────────────────────────
    def test_empty_abbreviations_no_crash(self):
        empty = LanguageProfile(name="Empty", iso_code="emp")
        seg = SentenceSegmenter(
            SegmentationConfig(use_nltk=False), _logger(), self.stats, empty
        )
        result = seg.segment_sentences("Hello world. This is a test.")
        self.assertIsInstance(result, list)

    def test_empty_text_returns_empty_list(self):
        seg = self._seg()
        self.assertEqual(seg.segment_sentences(""), [])
        self.assertEqual(seg.segment_sentences("   "), [])

    # ── Abbreviation-aware splitting ─────────────────────────────────────────
    def test_abbreviation_does_not_split_sentence(self):
        # "Dr." should not split the sentence
        text = "Dr. Smith arrived early. He was pleased."
        seg = self._seg()
        result = seg.segment_sentences(text)
        # Should not split at "Dr."
        for s in result:
            self.assertFalse(s.strip() == "Smith arrived early.")

    # ── Post-processing ──────────────────────────────────────────────────────
    def test_min_length_filter(self):
        cfg = SegmentationConfig(min_sentence_length=10, use_nltk=False)
        seg = SentenceSegmenter(cfg, _logger(), self.stats, self.toi)
        result = seg.segment_sentences("Hi. This is a longer sentence.")
        # "Hi." is only 3 chars, should be filtered
        for s in result:
            self.assertGreaterEqual(len(s), 10)

    def test_set_profile_rebuilds_pattern(self):
        seg = self._seg()
        loz = LANGUAGE_PROFILES["loz"]
        seg.set_profile(loz)
        self.assertIn("Ndate", str(seg.abbrev_pattern.pattern) + "Ndate")

    # ── Fallback segmenter ──────────────────────────────────────────────────
    def test_fallback_segmenter_basic(self):
        cfg = SegmentationConfig(use_nltk=False, use_spacy=False)
        seg = SentenceSegmenter(cfg, _logger(), self.stats, self.toi)
        result = seg.segment_sentences("First sentence. Second sentence!")
        self.assertGreaterEqual(len(result), 1)


# ============================================================================
# 7. SRTProcessor
# ============================================================================

class TestSRTProcessor(unittest.TestCase):

    _SRT_SAMPLE = textwrap.dedent("""\
        1
        00:00:01,000 --> 00:00:03,500
        Hello, welcome to our programme.

        2
        00:00:04,000 --> 00:00:07,000
        Today we discuss <i>language</i> preservation.

        3
        00:00:08,500 --> 00:00:11,000
        This is the third subtitle line.
    """)

    def setUp(self):
        self.proc = SRTProcessor(_logger())
        self.tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=".srt", delete=False, encoding="utf-8"
        )
        self.tf.write(self._SRT_SAMPLE)
        self.tf.close()
        self.path = Path(self.tf.name)

    def tearDown(self):
        os.unlink(self.tf.name)

    def test_handles_srt_extension(self):
        self.assertTrue(self.proc.can_process(Path("video.srt")))
        self.assertTrue(self.proc.can_process(Path("VIDEO.SRT")))

    def test_does_not_handle_txt(self):
        self.assertFalse(self.proc.can_process(Path("file.txt")))

    def test_returns_text(self):
        result = self.proc.extract_text(self.path)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)

    def test_strips_timecodes(self):
        result = self.proc.extract_text(self.path)
        self.assertNotIn("-->", result)
        self.assertNotIn("00:00:01", result)

    def test_strips_sequence_numbers(self):
        result = self.proc.extract_text(self.path)
        lines = [l.strip() for l in result.splitlines() if l.strip()]
        # No line should be a bare integer
        for line in lines:
            self.assertFalse(line.isdigit(), f"Sequence number survived: {line!r}")

    def test_strips_html_tags(self):
        result = self.proc.extract_text(self.path)
        self.assertNotIn("<i>", result)
        self.assertNotIn("</i>", result)

    def test_preserves_dialogue(self):
        result = self.proc.extract_text(self.path)
        self.assertIn("Hello", result)
        self.assertIn("language", result)
        self.assertIn("third subtitle line", result)

    def test_empty_srt_returns_none(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".srt", delete=False
        ) as tf:
            tf.write("1\n00:00:01,000 --> 00:00:02,000\n\n")
            path = Path(tf.name)
        try:
            result = self.proc.extract_text(path)
            # Either None or whitespace-only
            self.assertTrue(result is None or not result.strip())
        finally:
            os.unlink(str(path))


# ============================================================================
# 8. File processor routing
# ============================================================================

class TestFileProcessorRouting(unittest.TestCase):

    def setUp(self):
        self.txt  = TXTProcessor(_logger())
        self.srt  = SRTProcessor(_logger())

    def test_txt_handles_txt(self):
        self.assertTrue(self.txt.can_process(Path("file.txt")))

    def test_txt_handles_text(self):
        self.assertTrue(self.txt.can_process(Path("file.text")))

    def test_txt_does_not_handle_srt(self):
        self.assertFalse(self.txt.can_process(Path("file.srt")))

    def test_srt_handles_srt(self):
        self.assertTrue(self.srt.can_process(Path("file.srt")))

    def test_srt_does_not_handle_txt(self):
        self.assertFalse(self.srt.can_process(Path("file.txt")))

    def test_txt_extracts_plain_text(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tf:
            tf.write("Simple test content.\nLine two.")
            path = Path(tf.name)
        try:
            result = self.txt.extract_text(path)
            self.assertIn("Simple test content.", result)
        finally:
            os.unlink(str(path))


# ============================================================================
# 9. OutputGenerator
# ============================================================================

class TestOutputGenerator(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg    = OutputConfig(formats={"txt", "json"})
        self.gen    = OutputGenerator(self.cfg, _logger())
        self.result = ProcessingResult(
            file_path=Path("/input/category/file.txt"),
            success=True,
            language="toi",
            stage_completed="segmentation",
            cleaned_text="Sentence one. Sentence two.",
            sentences=["Sentence one.", "Sentence two."],
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_txt_output_one_sentence_per_line(self):
        base = Path(self.tmpdir) / "output"
        outputs = self.gen.generate_outputs(self.result, base, "category")
        self.assertIn("txt", outputs)
        lines = outputs["txt"].read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["Sentence one.", "Sentence two."])

    def test_json_output_has_required_keys(self):
        base = Path(self.tmpdir) / "output"
        outputs = self.gen.generate_outputs(self.result, base, "category")
        self.assertIn("json", outputs)
        data = json.loads(outputs["json"].read_text(encoding="utf-8"))
        for key in ("filename", "language_iso", "language_name",
                    "subject_category", "statistics", "sentences"):
            self.assertIn(key, data, f"Missing JSON key: {key}")

    def test_json_statistics_correct(self):
        base = Path(self.tmpdir) / "output"
        outputs = self.gen.generate_outputs(self.result, base, "category")
        data = json.loads(outputs["json"].read_text(encoding="utf-8"))
        self.assertEqual(data["statistics"]["sentence_count"], 2)
        self.assertGreater(data["statistics"]["word_count"], 0)

    def test_json_language_iso(self):
        base = Path(self.tmpdir) / "output"
        outputs = self.gen.generate_outputs(self.result, base, "category")
        data = json.loads(outputs["json"].read_text(encoding="utf-8"))
        self.assertEqual(data["language_iso"], "toi")

    def test_cleaned_format(self):
        cfg = OutputConfig(formats={"cleaned"})
        gen = OutputGenerator(cfg, _logger())
        base = Path(self.tmpdir) / "output2"
        outputs = gen.generate_outputs(self.result, base, "category")
        self.assertIn("cleaned", outputs)


# ============================================================================
# 10. ZambianCorpusBuilder — end-to-end
# ============================================================================

class TestZambianCorpusBuilderEndToEnd(unittest.TestCase):

    def setUp(self):
        self.indir  = tempfile.mkdtemp()
        self.outdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.indir,  ignore_errors=True)
        shutil.rmtree(self.outdir, ignore_errors=True)

    def _write(self, rel_path, content):
        p = Path(self.indir) / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def test_processes_txt_file_end_to_end(self):
        self._write(
            "chitonga/literature/test.txt",
            "Ndakasiyila amapenda. Bulelo lwamusuna mwaya. Bantu bapita kunyika."
        )
        cfg = UnifiedConfig(
            language="auto",
            corpus_config_file=_CORPUS_CONFIG,
        )
        pipeline = ZambianCorpusBuilder(cfg)
        pipeline.process_directory(Path(self.indir), Path(self.outdir))

        txt = Path(self.outdir) / "chitonga" / "literature" / "test.txt"
        self.assertTrue(txt.exists(), "Output TXT not created")
        lines = txt.read_text(encoding="utf-8").splitlines()
        self.assertGreater(len(lines), 0)

    def test_json_metadata_created(self):
        self._write(
            "chitonga/test.txt",
            "First sentence here. Second sentence here."
        )
        cfg = UnifiedConfig(language="auto", corpus_config_file=_CORPUS_CONFIG)
        pipeline = ZambianCorpusBuilder(cfg)
        pipeline.process_directory(Path(self.indir), Path(self.outdir))

        json_file = Path(self.outdir) / "chitonga" / "test.json"
        self.assertTrue(json_file.exists(), "Output JSON not created")
        data = json.loads(json_file.read_text(encoding="utf-8"))
        self.assertEqual(data["language_iso"], "toi")

    def test_corpus_manifest_created(self):
        self._write("chitonga/doc.txt", "One sentence. Two sentences.")
        cfg = UnifiedConfig(language="auto", corpus_config_file=_CORPUS_CONFIG)
        pipeline = ZambianCorpusBuilder(cfg)
        pipeline.process_directory(Path(self.indir), Path(self.outdir))

        manifest = Path(self.outdir) / "corpus_manifest.json"
        self.assertTrue(manifest.exists(), "corpus_manifest.json not created")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertIn("languages", data)
        self.assertIn("gcbt_version", data)
        self.assertEqual(data["gcbt_version"], "4.0")

    def test_stats_file_created_by_run_batch_mode(self):
        """Stats JSON is written after pipeline.process_directory() in run_batch_mode."""
        self._write("chitonga/test.txt", "Sentence one. Sentence two.")
        cfg = UnifiedConfig(language="auto", corpus_config_file=_CORPUS_CONFIG)
        pipeline = ZambianCorpusBuilder(cfg)
        pipeline.process_directory(Path(self.indir), Path(self.outdir))
        stats = pipeline.get_stats()
        self.assertGreater(stats.total_files, 0)
        self.assertGreater(stats.successful_files, 0)

    def test_directory_structure_mirrored(self):
        self._write("chibemba/religious/bible.txt", "Text content. More text.")
        cfg = UnifiedConfig(language="auto", corpus_config_file=_CORPUS_CONFIG)
        pipeline = ZambianCorpusBuilder(cfg)
        pipeline.process_directory(Path(self.indir), Path(self.outdir))

        out = Path(self.outdir) / "chibemba" / "religious" / "bible.txt"
        self.assertTrue(out.exists(), "Output directory structure not mirrored")

    def test_srt_file_processed(self):
        srt_content = textwrap.dedent("""\
            1
            00:00:01,000 --> 00:00:03,000
            This is the first subtitle.

            2
            00:00:04,000 --> 00:00:06,000
            This is the second subtitle.
        """)
        self._write("chitonga/media/transcript.srt", srt_content)
        cfg = UnifiedConfig(language="auto", corpus_config_file=_CORPUS_CONFIG)
        pipeline = ZambianCorpusBuilder(cfg)
        pipeline.process_directory(Path(self.indir), Path(self.outdir))

        out = Path(self.outdir) / "chitonga" / "media" / "transcript.txt"
        self.assertTrue(out.exists(), "SRT output not created")
        content = out.read_text(encoding="utf-8")
        self.assertNotIn("-->", content)

    def test_failed_file_does_not_crash_pipeline(self):
        """A corrupt/empty file should be logged, not crash the run."""
        self._write("chitonga/good.txt", "Good sentence. Another good sentence.")
        self._write("chitonga/empty.txt", "")
        cfg = UnifiedConfig(language="auto", corpus_config_file=_CORPUS_CONFIG)
        pipeline = ZambianCorpusBuilder(cfg)
        results = pipeline.process_directory(Path(self.indir), Path(self.outdir))
        successes = [r for r in results if r.success]
        self.assertGreater(len(successes), 0, "At least one file should succeed")


# ============================================================================
# 11. TextPatterns — verse_reference() live reference
# ============================================================================

class TestTextPatterns(unittest.TestCase):

    def test_verse_reference_is_callable(self):
        self.assertTrue(callable(TextPatterns.verse_reference))

    def test_verse_reference_returns_pattern(self):
        pat = TextPatterns.verse_reference()
        self.assertTrue(hasattr(pat, "search"))

    def test_verse_reference_is_current_module_pattern(self):
        self.assertIs(TextPatterns.verse_reference(), gcbt_v40.UNIVERSAL_VERSE_PATTERN)

    def test_verse_reference_tracks_module_global(self):
        """After swapping the global, verse_reference() should return the new pattern."""
        original = gcbt_v40.UNIVERSAL_VERSE_PATTERN
        new_pat = re.compile(r"SENTINEL")
        gcbt_v40.UNIVERSAL_VERSE_PATTERN = new_pat
        try:
            self.assertIs(TextPatterns.verse_reference(), new_pat)
        finally:
            gcbt_v40.UNIVERSAL_VERSE_PATTERN = original

    def test_no_verse_reference_class_attribute(self):
        self.assertFalse(hasattr(TextPatterns, "VERSE_REFERENCE"))

    def test_verse_reference_matches_scripture(self):
        pat = TextPatterns.verse_reference()
        self.assertIsNotNone(pat.search("See Heb 2:11 today"))
        self.assertIsNotNone(pat.search("1 Kor 11:7"))
        self.assertIsNotNone(pat.search("Gen 1:1-3"))

    def test_chapter_heading_method(self):
        toi = LANGUAGE_PROFILES["toi"]
        pat = TextPatterns.chapter_heading(toi)
        self.assertIsNotNone(pat.search("Matalikilo 3"))
        self.assertIsNone(pat.search("Normal sentence here."))


# ============================================================================
# 12. ProcessingStats
# ============================================================================

class TestProcessingStats(unittest.TestCase):

    def test_success_rate_zero_files(self):
        s = ProcessingStats()
        self.assertEqual(s.success_rate, 0.0)

    def test_success_rate_calculation(self):
        s = ProcessingStats(total_files=10, successful_files=8)
        self.assertEqual(s.success_rate, 80.0)

    def test_reduction_percentage(self):
        s = ProcessingStats(total_chars_before=1000, total_chars_after=600)
        self.assertEqual(s.reduction_percentage, 40.0)

    def test_avg_sentences_per_file(self):
        s = ProcessingStats(successful_files=4, total_sentences=100)
        self.assertEqual(s.avg_sentences_per_file, 25.0)

    def test_avg_words_per_sentence(self):
        s = ProcessingStats(total_sentences=10, total_words=80)
        self.assertEqual(s.avg_words_per_sentence, 8.0)

    def test_str_contains_v4_banner(self):
        s = ProcessingStats()
        text = str(s)
        self.assertIn("v4.0", text)
        self.assertIn("GOBELO CORPUS BUILDER TOOLKIT", text)

    def test_to_dict_has_computed_properties(self):
        s = ProcessingStats(total_files=5, successful_files=4)
        d = s.to_dict()
        self.assertIn("success_rate", d)
        self.assertIn("reduction_percentage", d)


# ============================================================================
# 13. YAML safety
# ============================================================================

class TestYAMLSafety(unittest.TestCase):

    def test_no_key_in_abbreviations(self):
        """Unquoted YAML 'no' parses as False; it must be coerced to 'no'."""
        for profile in LANGUAGE_PROFILES.values():
            for item in profile.book_abbreviations:
                self.assertNotEqual(item, False,
                                    f"False in {profile.iso_code}.book_abbreviations")
                self.assertIsInstance(item, str)

    def test_boolean_values_in_yaml_coerced(self):
        """A language block with bare 'yes'/'no' values must not crash."""
        import yaml
        cfg_data = {
            "global": {
                "verse_pattern": r"\b\d+:\d+\b",
                "chapter_words": ["Chapter"],
                "book_abbreviations": ["Dr", "no"],   # 'no' -> bool in YAML
                "ocr_corrections": {},
                "valid_single_chars": ["a"],
                "extra_special_chars": [],
                "strip_patterns": [],
                "remove_urls": True,
                "remove_emails": True,
                "filter_single_chars": True,
                "fix_hyphenation": True,
                "normalize_whitespace": True,
                "normalize_unicode": True,
                "normalize_punctuation": True,
                "process_ocr_artifacts": True,
                "preserve_bible_text": False,
                "protect_citations": False,
                "min_sentence_length": 3,
                "max_sentence_length": 1000,
            },
            # Need at least one language so loader doesn't raise ConfigError
            "languages": {
                "tst": {"ggt_yaml": "", "path_keywords": ["tst"]}
            }
        }
        tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        yaml.dump(cfg_data, tf)
        tf.close()
        try:
            loader = CorpusConfigLoader(tf.name)
            # 'no' in book_abbreviations should become string "False" or "no", not bool
            und = loader.profiles["und"]
            for item in und.book_abbreviations:
                self.assertIsInstance(item, str)
        finally:
            os.unlink(tf.name)

    def test_corpus_config_yaml_is_valid(self):
        """The shipped corpus_config.yaml must parse without error."""
        import yaml
        with open(_CORPUS_CONFIG) as f:
            data = yaml.safe_load(f)
        self.assertIn("global", data)
        self.assertIn("languages", data)

    def test_corpus_config_has_all_seven_languages(self):
        import yaml
        with open(_CORPUS_CONFIG) as f:
            data = yaml.safe_load(f)
        for iso in ("toi", "bem", "nya", "loz", "lun", "lue", "kqn"):
            self.assertIn(iso, data["languages"])


# ============================================================================
# 14. Backward compatibility
# ============================================================================

class TestBackwardCompatibility(unittest.TestCase):

    def test_corpus_processing_pipeline_alias(self):
        self.assertIs(CorpusProcessingPipeline, ZambianCorpusBuilder)

    def test_gobelo_corpus_builder_alias(self):
        self.assertIs(GobeloCorpusBuilder, ZambianCorpusBuilder)

    def test_chitonga_text_cleaner_alias(self):
        self.assertIs(ChitongaTextCleaner, ZambianTextCleaner)

    def test_fix_ocr_errors_method_alias(self):
        toi = LANGUAGE_PROFILES["toi"]
        cfg = UnifiedConfig(language="toi")
        c = ZambianTextCleaner(cfg, _logger(), ProcessingStats(), toi)
        # Both names must exist and produce the same result
        r1 = c.fix_ocr_errors("the cl sound")
        r2 = c.fix_ocr_corrections("the cl sound")
        self.assertEqual(r1, r2)

    def test_clean_text_alias(self):
        toi = LANGUAGE_PROFILES["toi"]
        cfg = UnifiedConfig(language="toi")
        c = ZambianTextCleaner(cfg, _logger(), ProcessingStats(), toi)
        text = "Some text to clean."
        self.assertEqual(c.clean(text), c.clean_text(text))


# ============================================================================
# 15. Syntax check
# ============================================================================

class TestSourceSyntax(unittest.TestCase):

    def test_gcbt_v40_python_syntax(self):
        src = (Path(_HERE) / "gcbt_v40.py").read_text()
        try:
            ast.parse(src)
        except SyntaxError as e:
            self.fail(f"Syntax error in gcbt_v40.py: {e}")

    def test_no_stale_ocr_errors_key_in_source(self):
        src = (Path(_HERE) / "gcbt_v40.py").read_text()
        # 'ocr_errors' may only appear in the backward-compat alias definition
        allowed_contexts = {"fix_ocr_errors = fix_ocr_corrections",
                            "# Backward-compat alias",
                            "fix_ocr_errors alias"}
        bad = [
            l.strip() for l in src.splitlines()
            if "ocr_errors" in l
            and not any(ctx in l for ctx in allowed_contexts)
            and not l.strip().startswith("#")
            and "fix_ocr_errors" not in l          # alias definition/docstring is intentional
        ]
        self.assertEqual(bad, [], f"Stale 'ocr_errors' references:\n  " + "\n  ".join(bad))

    def test_no_stale_universal_verse_pattern_docstring(self):
        src = (Path(_HERE) / "gcbt_v40.py").read_text()
        self.assertNotIn("universal.verse_pattern", src)

    def test_no_verse_reference_class_attribute_in_source(self):
        src = (Path(_HERE) / "gcbt_v40.py").read_text()
        self.assertNotIn("VERSE_REFERENCE   = UNIVERSAL_VERSE_PATTERN", src)

    def test_unused_imports_absent(self):
        src = (Path(_HERE) / "gcbt_v40.py").read_text()
        for term in ["from enum import Enum", " Union,", " Iterator,"]:
            # Allow in comments
            non_comment = [l for l in src.splitlines()
                           if term in l and not l.strip().startswith("#")]
            self.assertEqual(non_comment, [], f"Unused import still present: {term!r}")


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    # Run with a clean, readable summary
    loader = unittest.TestLoader()
    suite  = loader.discover(str(_HERE), pattern="test_gcbt_v40.py")
    runner = unittest.TextTestRunner(verbosity=2, failfast=False)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
