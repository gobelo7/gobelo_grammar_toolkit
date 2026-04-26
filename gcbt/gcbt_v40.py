#!/usr/bin/env python3
"""
Gobelo Corpus Builder Toolkit (gcbt) v4.0
Multi-Format Text Extraction, Cleaning & Segmentation Pipeline

Supports all 7 official Zambian regional languages + any language added via YAML:
  - ChiTonga  (M.64) | toi
  - ChiBemba  (M.42) | bem
  - ChiNyanja (N.31) | nya
  - SiLozi    (K.21) | loz
  - ciLunda   (L.52) | lun
  - ciLuvale  (K.14) | lue
  - ciKaonde  (L.41) | kqn

Author: Gobelo Grammar Toolkit / GGT
License: MIT

Key v4.0 changes vs v3.0:
  1.  TWO-LAYER CONFIG ARCHITECTURE replaces the hardcoded LANGUAGE_PROFILES registry:
        Layer 1 — GGT YAML grammar files  (phonology, orthography, iso_code, special_chars)
        Layer 2 — corpus_config.yaml       (corpus-pipeline settings only — see file)
  2.  CorpusConfigLoader reads corpus_config.yaml at startup; GGT YAMLs supply
      linguistic data; the two layers are merged into LanguageProfile objects.
  3.  LanguageProfile dataclass has NO hardcoded defaults — all values come from YAML.
  4.  corpus_config.yaml key names (all corpus-builder-specific):
        global.chapter_words         — chapter heading words (additive)
        global.book_abbreviations    — sentence-boundary abbreviations (additive)
        global.ocr_corrections       — glyph substitutions (key-by-key override)
        global.valid_single_chars    — Bantu morpheme single chars (additive)
        global.extra_special_chars   — digraphs / trigraphs (additive)
        global.strip_patterns        — regex line-removal patterns (additive)
        global.punctuation_map       — typographic→ASCII map (global only)
        global.verse_pattern         — scripture reference regex (global only)
        per-language.display_name    — optional name override
        per-language.ggt_yaml        — path to the GGT grammar file
        per-language.path_keywords   — corpus directory name hints for auto-detect
  5.  Adding a new language: drop GGT YAML into languages/, add block in
      corpus_config.yaml. Zero Python changes required.
  6.  LANGUAGE_PROFILES dict populated dynamically — all downstream code unchanged.
  7.  Backward-compatibility aliases preserved:
        CorpusProcessingPipeline = ZambianCorpusBuilder
        ChitongaTextCleaner      = ZambianTextCleaner
        fix_ocr_errors           = fix_ocr_corrections  (method alias)
"""

import os
import sys
import json
import re
import logging
import unicodedata
import gc
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field, asdict
import traceback
import argparse

# ============================================================================
# OPTIONAL DEPENDENCIES
# ============================================================================

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import PyPDF2
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import ebooklib
    from ebooklib import epub
    EPUB_AVAILABLE = True
except ImportError:
    EPUB_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import nltk
    from nltk.tokenize import sent_tokenize
    NLTK_AVAILABLE = True
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        try:
            nltk.download('punkt', quiet=True)
        except Exception:
            pass
except ImportError:
    NLTK_AVAILABLE = False

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
    SPACY_MODELS = []
    for _model_name in ["en_core_web_sm", "en_core_web_md", "xx_ent_wiki_sm"]:
        try:
            _test = spacy.load(_model_name, disable=["ner"])
            SPACY_MODELS.append(_model_name)
            del _test
        except OSError:
            pass
except ImportError:
    SPACY_AVAILABLE = False
    SPACY_MODELS = []

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class CorpusBuilderError(Exception):
    pass

class ExtractionError(CorpusBuilderError):
    pass

class CleaningError(CorpusBuilderError):
    pass

class SegmentationError(CorpusBuilderError):
    pass

class MemoryLimitError(CorpusBuilderError):
    pass

class ConfigError(CorpusBuilderError):
    pass


# ============================================================================
# LANGUAGE PROFILE DATACLASS  (unchanged from v3.0 — data now comes from YAML)
# ============================================================================

@dataclass
class LanguageProfile:
    """
    Runtime container for one language's corpus-processing settings.

    All fields are populated exclusively by CorpusConfigLoader from two
    YAML sources — no defaults are embedded here:

      GGT YAML  → name, iso_code, guthrie, path_keywords, special_chars
      corpus_config.yaml → everything else (chapter_words, book_abbreviations,
                           ocr_corrections, valid_single_chars, punctuation_map,
                           extra_special_chars, strip_patterns)

    The universal values from corpus_config.yaml `global:` are merged in first;
    language-specific values extend or override them field by field.
    """

    # ── Identity (from GGT YAML) ─────────────────────────────────────────
    name: str                              # e.g. "ChiTonga"
    iso_code: str                          # ISO 639-3, e.g. "toi"
    guthrie: str = ""                      # Guthrie zone code, e.g. "M.64"

    # ── Auto-detection keywords (GGT YAML metadata + corpus_config) ──────
    path_keywords: List[str] = field(default_factory=list)

    # ── Phonology (from GGT YAML; corpus_config may extend via extra_special_chars) ──
    special_chars: Set[str] = field(default_factory=set)

    # ── Corpus-processing settings (all from corpus_config.yaml) ─────────

    # Typographic → ASCII substitutions applied before segmentation
    # Populated from corpus_config.yaml `global.punctuation_map`
    punctuation_map: Dict[str, str] = field(default_factory=dict)

    # OCR glyph corrections: global baseline merged with per-language overrides
    # Key name in YAML: ocr_corrections
    ocr_corrections: Dict[str, str] = field(default_factory=dict)

    # Single-character tokens that are valid Bantu grammatical morphemes
    # and must NOT be filtered out by the single-char filter
    valid_single_chars: Set[str] = field(default_factory=set)

    # Chapter/section heading words used to detect and strip structural lines
    chapter_words: List[str] = field(default_factory=list)

    # Book/title abbreviations that must NOT trigger a sentence boundary
    # Key name in YAML: book_abbreviations
    book_abbreviations: Set[str] = field(default_factory=set)

    # Additional multi-char sequences valid in this language's orthography
    # (e.g. digraphs "sh", "ng", "ny") — extends special_chars at runtime
    # Key name in YAML: extra_special_chars
    extra_special_chars: List[str] = field(default_factory=list)

    # Extra regex patterns whose matching lines are stripped before segmentation
    # Key name in YAML: strip_patterns
    strip_patterns: List[str] = field(default_factory=list)


# ============================================================================
# TWO-LAYER CORPUS CONFIG LOADER  ← NEW in v4.0
# ============================================================================

class CorpusConfigLoader:
    """
    Loads language profiles from two YAML layers:

      Layer 1 — GGT YAML  (languages/<lang>.yaml)
        Provides: language name, iso_code, guthrie, path_keywords,
                  phonology.vowels / consonants → special_chars.
        This file is the authoritative linguistic source; the loader
        reads it but never writes to it.

      Layer 2 — corpus_config.yaml  (this project's config)
        Provides: all corpus-pipeline settings that are NOT derivable
        from the GGT grammar files:
          global section  — pipeline toggles, verse_pattern,
                            punctuation_map, and the baseline values for
                            every additive/override field below.
          per-language section — language-specific extensions/overrides.

    corpus_config.yaml key names (as specified):
      display_name          optional human-readable override for the language name
      ggt_yaml              path to the GGT grammar file for this language
      chapter_words         additive with global (set union)
      book_abbreviations    additive with global (set union)
      ocr_corrections       key-by-key override of global entries
      valid_single_chars    additive with global (set union)
      extra_special_chars   additive with GGT-derived special_chars
      strip_patterns        additive with global (list append)

    Merging rules:
      Additive fields (chapter_words, book_abbreviations, valid_single_chars,
                       extra_special_chars, strip_patterns):
          effective = global_value ∪ language_value
      Override fields (ocr_corrections):
          effective = {**global_value, **language_value}  (language wins per key)
      Scalar fields (all pipeline toggles):
          global only — not overridable per language.
    """

    # Key-paths tried in GGT YAML for each piece of identity/phonology data.
    # Multiple paths cover different GGT YAML schema versions.
    _GGT_ISO_PATHS       = [["metadata", "language", "iso_code"],
                             ["metadata", "iso_code"]]
    _GGT_NAME_PATHS      = [["metadata", "language", "name"],
                             ["metadata", "name"]]
    _GGT_GUTHRIE_PATHS   = [["metadata", "guthrie"],
                             ["metadata", "language", "guthrie"]]
    _GGT_VOWEL_PATHS     = [["phonology", "vowels"]]
    _GGT_CONSONANT_PATHS = [["phonology", "consonants"]]
    _GGT_SPECIAL_PATHS   = [["metadata", "special_chars"],
                             ["orthography", "special_chars"]]
    _GGT_KEYWORD_PATHS   = [["metadata", "path_keywords"],
                             ["metadata", "keywords"]]

    def __init__(self, corpus_config_path: str = "corpus_config.yaml"):
        if not YAML_AVAILABLE:
            raise ConfigError(
                "PyYAML is required for the two-layer config system.\n"
                "Install with: pip install PyYAML"
            )
        self._config_path = Path(corpus_config_path)
        self._raw: Dict = {}
        self.profiles: Dict[str, LanguageProfile] = {}
        self.universal_cfg: Dict[str, Any] = {}
        self.verse_pattern: re.Pattern = re.compile(
            r'\b(?:\d{1,2}\s*)?[A-Za-z#]{1,20}\.?\s?\d{1,3}:\d{1,3}'
            r'(?:[,\-]\d{1,3})*\b'
        )
        self._load()

    # ── Public interface ──────────────────────────────────────────────────

    def get_profile(self, iso_code: str) -> LanguageProfile:
        """Return a LanguageProfile by ISO code, falling back to 'und'."""
        return self.profiles.get(iso_code, self.profiles["und"])

    def detect_language(self, path: Path) -> LanguageProfile:
        """
        Auto-detect a language profile from a file or directory path.

        Strategy:
          1. Check every component of the path against path_keywords
             (case-insensitive substring match)
          2. Fall back to the universal "und" profile
        """
        path_str = str(path).lower()
        for iso_code, profile in self.profiles.items():
            if iso_code == "und":
                continue
            for keyword in profile.path_keywords:
                if keyword.lower() in path_str:
                    return profile
        return self.profiles["und"]

    # ── Loading ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load corpus_config.yaml, resolve GGT YAMLs, build all profiles."""
        if not self._config_path.exists():
            raise ConfigError(
                f"corpus_config.yaml not found: {self._config_path}\n"
                "Create it or point --corpus-config at the correct path."
            )
        with open(self._config_path, 'r', encoding='utf-8') as f:
            self._raw = yaml.safe_load(f) or {}

        global_raw = self._raw.get("global", {})
        self.universal_cfg = global_raw

        # Compile verse_pattern from global section
        verse_pat = global_raw.get("verse_pattern")
        if verse_pat:
            try:
                self.verse_pattern = re.compile(verse_pat)
            except re.error as e:
                logging.warning(
                    f"Invalid verse_pattern in corpus_config.yaml: {e}. "
                    "Using built-in default."
                )

        languages_raw = self._raw.get("languages", {})
        for iso_code, lang_cfg in languages_raw.items():
            lang_cfg = lang_cfg or {}
            ggt_data = self._load_ggt_yaml(lang_cfg.get("ggt_yaml", ""), iso_code)
            self.profiles[iso_code] = self._build_profile(
                iso_code, ggt_data, lang_cfg, global_raw
            )

        # "und" is always built last — it is the union of all per-language profiles
        self.profiles["und"] = self._build_universal_profile(global_raw)

        if len(self.profiles) < 2:  # at minimum 1 language + und
            raise ConfigError(
                "No language profiles loaded. Check corpus_config.yaml has "
                "at least one entry under `languages:`."
            )

    def _load_ggt_yaml(self, ggt_path_str: str, iso_code: str) -> Dict:
        """Load and return raw GGT YAML data, or {} if the path is absent/invalid."""
        if not ggt_path_str:
            return {}
        ggt_path = self._config_path.parent / ggt_path_str
        if not ggt_path.exists():
            logging.warning(
                f"[{iso_code}] GGT YAML not found: {ggt_path}. "
                "Identity and phonology will be derived from corpus_config.yaml only."
            )
            return {}
        try:
            with open(ggt_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.warning(f"[{iso_code}] Could not parse GGT YAML {ggt_path}: {e}")
            return {}

    def _build_profile(self, iso_code: str,
                       ggt: Dict,
                       lang_cfg: Dict,
                       global_cfg: Dict) -> LanguageProfile:
        """
        Construct a LanguageProfile by merging:
          Layer 1 (GGT YAML)       → identity + phonology
          Layer 2a (global_cfg)    → baseline corpus-processing values
          Layer 2b (lang_cfg)      → language-specific extensions/overrides

        All data values come from YAML — no fallbacks are encoded here.
        If a field is absent from both YAML layers the profile field stays
        at its empty dataclass default (empty set / list / dict).
        """

        # ── Layer 1: Identity from GGT YAML ──────────────────────────────
        # display_name in corpus_config.yaml takes precedence over GGT name
        ggt_name = self._ggt_get(ggt, self._GGT_NAME_PATHS) or iso_code
        name     = lang_cfg.get("display_name") or ggt_name
        guthrie  = self._ggt_get(ggt, self._GGT_GUTHRIE_PATHS) or ""

        # ── Layer 1: special_chars from GGT phonology ─────────────────────
        # Collect vowels + consonants + any explicit special_chars field
        special_chars: Set[str] = set()
        for path in [self._GGT_VOWEL_PATHS, self._GGT_CONSONANT_PATHS,
                     self._GGT_SPECIAL_PATHS]:
            src = self._ggt_get(ggt, path) or ""
            if isinstance(src, list):
                special_chars.update(src)
            elif isinstance(src, str):
                special_chars.update(src)

        # ── Layer 1: path_keywords from GGT, extended by corpus_config ───
        ggt_keywords = self._ggt_get(ggt, self._GGT_KEYWORD_PATHS) or []
        cfg_keywords = lang_cfg.get("path_keywords", [])
        # iso_code itself is always a valid keyword; preserve insertion order
        path_keywords: List[str] = list(
            dict.fromkeys([iso_code] + list(ggt_keywords) + list(cfg_keywords))
        )

        # ── Layer 2: punctuation_map — global only, no per-language override ──
        punctuation_map: Dict[str, str] = dict(global_cfg.get("punctuation_map", {}))

        # ── Layer 2: additive fields — global ∪ language ─────────────────
        # _strs() coerces all values to str, guarding against YAML boolean
        # contamination (e.g. bare `no` parsed as False, `yes` as True).
        def _strs(seq) -> List[str]:
            return [str(v) for v in (seq or []) if v is not None]

        chapter_words = sorted(
            set(_strs(global_cfg.get("chapter_words", [])))
            | set(_strs(lang_cfg.get("chapter_words", [])))
        )
        book_abbreviations: Set[str] = (
            set(_strs(global_cfg.get("book_abbreviations", [])))
            | set(_strs(lang_cfg.get("book_abbreviations", [])))
        )
        valid_single_chars: Set[str] = (
            set(_strs(global_cfg.get("valid_single_chars", [])))
            | set(_strs(lang_cfg.get("valid_single_chars", [])))
        )
        extra_special_chars: List[str] = (
            _strs(global_cfg.get("extra_special_chars", []))
            + _strs(lang_cfg.get("extra_special_chars", []))
        )
        strip_patterns: List[str] = (
            _strs(global_cfg.get("strip_patterns", []))
            + _strs(lang_cfg.get("strip_patterns", []))
        )

        # ── Layer 2: ocr_corrections — key-by-key override ───────────────
        ocr_corrections: Dict[str, str] = dict(global_cfg.get("ocr_corrections", {}))
        ocr_corrections.update(lang_cfg.get("ocr_corrections", {}))

        return LanguageProfile(
            name=name,
            iso_code=iso_code,
            guthrie=guthrie,
            path_keywords=path_keywords,
            special_chars=special_chars,
            punctuation_map=punctuation_map,
            ocr_corrections=ocr_corrections,
            valid_single_chars=valid_single_chars,
            chapter_words=chapter_words,
            book_abbreviations=book_abbreviations,
            extra_special_chars=extra_special_chars,
            strip_patterns=strip_patterns,
        )

    def _build_universal_profile(self, global_cfg: Dict) -> LanguageProfile:
        """
        Build the 'und' (undetermined) profile as the union of all per-language
        profiles merged on top of the global baseline.  Used when language
        cannot be detected from the file path.
        """
        all_special    : Set[str]       = set()
        all_vsc        : Set[str]       = set(global_cfg.get("valid_single_chars", []))
        all_cw         : Set[str]       = set(global_cfg.get("chapter_words", []))
        all_abbr       : Set[str]       = set(global_cfg.get("book_abbreviations", []))
        all_extra      : List[str]      = list(global_cfg.get("extra_special_chars", []))
        all_strip      : List[str]      = list(global_cfg.get("strip_patterns", []))
        all_ocr        : Dict[str, str] = dict(global_cfg.get("ocr_corrections", {}))

        for iso, profile in self.profiles.items():
            if iso == "und":
                continue
            all_special.update(profile.special_chars)
            all_vsc.update(profile.valid_single_chars)
            all_cw.update(profile.chapter_words)
            all_abbr.update(profile.book_abbreviations)
            all_extra.extend(
                x for x in profile.extra_special_chars if x not in all_extra
            )
            all_strip.extend(
                p for p in profile.strip_patterns if p not in all_strip
            )
            # For ocr_corrections in "und": global wins (do not override with
            # any single language's corrections — that would be too aggressive)

        return LanguageProfile(
            name="Universal",
            iso_code="und",
            guthrie="",
            path_keywords=[],
            special_chars=all_special,
            punctuation_map=dict(global_cfg.get("punctuation_map", {})),
            ocr_corrections=all_ocr,
            valid_single_chars=all_vsc,
            chapter_words=sorted(all_cw),
            book_abbreviations=all_abbr,
            extra_special_chars=list(dict.fromkeys(all_extra)),
            strip_patterns=list(dict.fromkeys(all_strip)),
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _ggt_get(data: Dict, path_options: List[List[str]]) -> Any:
        """
        Walk path_options (list of key-paths) against a nested dict.
        Returns the first non-None value found, or None.
        """
        for key_path in path_options:
            node = data
            for key in key_path:
                if not isinstance(node, dict):
                    node = None
                    break
                node = node.get(key)
            if node is not None:
                return node
        return None


# ============================================================================
# MODULE-LEVEL PROFILE REGISTRY
# Populated at import time from corpus_config.yaml.
# All downstream code references LANGUAGE_PROFILES and detect_language()
# exactly as in v3.0 — no call-site changes needed.
# ============================================================================

def _initialise_profiles(config_path: str = "corpus_config.yaml") -> Tuple[
        Dict[str, LanguageProfile], LanguageProfile, re.Pattern, CorpusConfigLoader]:
    """
    Attempt to load profiles from YAML.  Falls back gracefully if YAML is
    unavailable or the config file is missing, preserving v3.0 behaviour.
    """
    try:
        loader = CorpusConfigLoader(config_path)
        profiles = loader.profiles
        universal = profiles["und"]
        verse_pat = loader.verse_pattern
        return profiles, universal, verse_pat, loader
    except ConfigError as e:
        logging.warning(
            f"Could not load corpus_config.yaml ({e}). "
            "Falling back to built-in universal defaults."
        )
    except Exception as e:
        logging.warning(
            f"Unexpected error loading corpus_config.yaml: {e}. "
            "Falling back to built-in universal defaults."
        )

    # Empty fallback — no data hardcoded.  The app runs but applies no
    # language-specific cleaning until a valid corpus_config.yaml is found.
    _fallback = LanguageProfile(name="Universal", iso_code="und")
    _fallback_verse = re.compile(
        r'\b(?:\d{1,2}\s*)?[A-Za-z#]{1,20}\.?\s?\d{1,3}:\d{1,3}'
        r'(?:[,\-]\d{1,3})*\b'
    )
    return {"und": _fallback}, _fallback, _fallback_verse, None


# Populate module-level globals used throughout this file
LANGUAGE_PROFILES, _UNIVERSAL_PROFILE, UNIVERSAL_VERSE_PATTERN, _CONFIG_LOADER = (
    _initialise_profiles()
)


def reload_profiles(config_path: str = "corpus_config.yaml") -> None:
    """
    Hot-reload language profiles from YAML without restarting the process.
    Called by the CLI's "Reload corpus_config.yaml" menu option.
    """
    global LANGUAGE_PROFILES, _UNIVERSAL_PROFILE, UNIVERSAL_VERSE_PATTERN, _CONFIG_LOADER
    LANGUAGE_PROFILES, _UNIVERSAL_PROFILE, UNIVERSAL_VERSE_PATTERN, _CONFIG_LOADER = (
        _initialise_profiles(config_path)
    )
    logging.getLogger(__name__).info(
        f"Profiles reloaded: {list(LANGUAGE_PROFILES.keys())}"
    )


def detect_language(path: Path) -> LanguageProfile:
    """
    Auto-detect the language profile from a file or directory path.

    Delegates to CorpusConfigLoader.detect_language when a loader is available,
    otherwise falls back to path-keyword matching against the loaded profiles.
    """
    if _CONFIG_LOADER is not None:
        return _CONFIG_LOADER.detect_language(path)

    # Fallback: manual keyword scan over whatever profiles are loaded
    path_str = str(path).lower()
    for iso_code, profile in LANGUAGE_PROFILES.items():
        if iso_code == "und":
            continue
        for keyword in profile.path_keywords:
            if keyword.lower() in path_str:
                return profile
    return _UNIVERSAL_PROFILE


# ============================================================================
# BIBLE VERSE REFERENCE UTILITIES
# (verse regex now comes from corpus_config.yaml via CorpusConfigLoader)
# ============================================================================

def build_bible_verse_pattern() -> re.Pattern:
    """
    Return the current universal Bible-verse regex.

    In v4.0 this is driven by corpus_config.yaml's `global.verse_pattern`.
    This function is kept for backward compatibility with call sites that
    expected it to exist.
    """
    return UNIVERSAL_VERSE_PATTERN


def remove_bible_references(text: str) -> Tuple[str, int]:
    """
    Remove all Bible verse references from text using the universal pattern.
    Returns (cleaned_text, count_removed).
    Also collapses stray punctuation left after removal.
    """
    count = len(UNIVERSAL_VERSE_PATTERN.findall(text))
    text  = UNIVERSAL_VERSE_PATTERN.sub('', text)
    text  = re.sub(r'\s*[;,]+\s*', ' ', text)
    text  = re.sub(r'\s+', ' ', text)
    return text.strip(), count


def build_chapter_heading_pattern(profile: LanguageProfile) -> re.Pattern:
    """
    Build a chapter-heading regex for the given language profile.

    Matches lines like "Matalikilo 3", "Chapter IV", "Kauhanyo 12".
    The word list comes from the profile, which was loaded from YAML.
    """
    if not profile.chapter_words:
        word_alts = r'Chapter'
    else:
        word_alts = '|'.join(re.escape(w) for w in profile.chapter_words)
    pattern = (
        r'^\s*(?:' + word_alts + r')\s+(?:[IVXLCDM]+|\d+)\s*$'
    )
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


# ============================================================================
# TEXT PATTERNS  (language-agnostic core)
# ============================================================================

class TextPatterns:
    """Pre-compiled regex patterns for text processing."""
    MULTIPLE_SPACES   = re.compile(r'[ \t]+')
    MULTIPLE_NEWLINES = re.compile(r'\n{3,}')
    URL               = re.compile(r'https?://\S+|www\.\S+')
    EMAIL             = re.compile(r'\S+@\S+\.\S+')
    DOUBLE_HYPHENATED = re.compile(r'(\w+)-\n-(\w+)')
    HYPHENATED        = re.compile(r'(\w+)-\s*\n\s*(\w+)')
    LINE_BREAK_WORDS  = re.compile(r'(\w+)\n(\w+)')
    SINGLE_NEWLINE    = re.compile(r'(?<!\n)\n(?!\n)')
    JUNK_CONSONANTS   = re.compile(
        r'\b(?=[a-z]{5,})[^aeiouyāēīōūáéíóú\s]+\b', re.IGNORECASE
    )
    ET_AL             = re.compile(r'\bet al\.')

    @staticmethod
    def verse_reference() -> re.Pattern:
        """Always returns the current UNIVERSAL_VERSE_PATTERN.

        Using a static method rather than a class attribute ensures that
        TextPatterns.verse_reference() reflects any pattern loaded from
        corpus_config.yaml, even if that loading happened after this class
        was defined.  Call as TextPatterns.verse_reference(), not as an
        attribute.
        """
        return UNIVERSAL_VERSE_PATTERN

    @staticmethod
    def chapter_heading(profile: LanguageProfile) -> re.Pattern:
        return build_chapter_heading_pattern(profile)


# ============================================================================
# CONFIGURATION SYSTEM
# ============================================================================

@dataclass
class ExtractionConfig:
    pdf_method: str = "pdfplumber"
    max_file_size_mb: int = 100
    supported_formats: Set[str] = field(default_factory=lambda: {
        '.pdf', '.docx', '.doc', '.epub', '.html', '.htm',
        '.md', '.markdown', '.txt', '.text', '.csv', '.xml', '.srt'
    })
    encoding_fallback: str = "utf-8"
    pymupdf_margin: float = 0.1


@dataclass
class CleaningConfig:
    remove_urls: bool = True
    remove_emails: bool = True
    preserve_bible_text: bool = False
    remove_bible_references: bool = False    # strip scripture verse refs (e.g. "Gen 1:1")
    filter_single_chars: bool = True
    fix_hyphenation: bool = True             # rejoin words split across line breaks
    unwrap_lines: bool = False               # collapse soft newlines within paragraphs
    protect_abbreviations: bool = False      # protect period-terminated abbreviations
    normalize_whitespace: bool = True
    normalize_unicode: bool = True
    normalize_punctuation: bool = True
    process_ocr_artifacts: bool = True
    remove_junk_consonants: bool = False     # strip 5+-consonant OCR garbage tokens
    max_line_length: int = 4192
    min_line_length: int = 3
    custom_replacements: Dict[str, str] = field(default_factory=dict)
    custom_single_chars: List[str] = field(default_factory=list)
    pristine_mode: bool = False
    unicode_form: str = "NFC"
    protect_citations: bool = False


@dataclass
class SegmentationConfig:
    min_sentence_length: int = 3
    max_sentence_length: int = 1000
    use_nltk: bool = True
    use_spacy: bool = False
    spacy_model: str = "en_core_web_sm"
    language_aware: bool = True


@dataclass
class OutputConfig:
    formats: Set[str] = field(default_factory=lambda: {'txt', 'json'})
    include_metadata: bool = True
    preserve_structure: bool = True


@dataclass
class UnifiedConfig:
    """Master configuration for the entire pipeline."""

    # Language selection: ISO code, "auto" (path-based detection), or "und"
    language: str = "auto"

    # Path to the two-layer corpus config file
    corpus_config_file: str = "corpus_config.yaml"

    # Stage configurations
    extraction:   ExtractionConfig   = field(default_factory=ExtractionConfig)
    cleaning:     CleaningConfig     = field(default_factory=CleaningConfig)
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    output:       OutputConfig       = field(default_factory=OutputConfig)

    # Global settings
    max_memory_mb: int = 1000
    chunk_size:    int = 5000
    log_level:     str = "INFO"
    recursive:     bool = True

    # Legacy flat-config fields (backward compat)
    input_dir: str = ""
    output_dir: str = ""
    pdf_method: str = "pdfplumber"
    process_ocr: bool = True
    pdf_use_margins: bool = False
    pdf_top_margin: float = 0.1
    pdf_bottom_margin: float = 0.1
    pdf_left_margin: float = 0.05
    pdf_right_margin: float = 0.05
    normalize_unicode: bool = True
    remove_consonant_clusters: bool = True
    unwrap_lines: bool = True
    protect_abbreviations: bool = False
    remove_urls: bool = True
    remove_emails: bool = True
    remove_bible_references: bool = False
    preserve_bible: bool = False
    fix_hyphenation: bool = True
    filter_single_chars: bool = True
    min_sentence_length: int = 3   # aligned with SegmentationConfig and corpus_config.yaml default
    max_sentence_length: int = 1000
    use_nltk_segmentation: bool = False
    output_formats: List[str] = field(default_factory=lambda: ['cleaned'])
    stage_completed: str = ""
    max_file_size_mb: int = 50

    def __post_init__(self):
        if self.output_formats is None:
            self.output_formats = ['cleaned']

        # Sync pipeline toggles from corpus_config.yaml global section,
        # making it the single source of truth for default values.
        #
        # Guard: only sync when cleaning / segmentation are still the
        # vanilla dataclass defaults — i.e., the caller did NOT explicitly
        # pass a configured sub-object (as presets do).  This preserves
        # preset and CLI overrides while ensuring a plain UnifiedConfig()
        # picks up whatever is in corpus_config.yaml.
        if _CONFIG_LOADER is None:
            return  # no YAML loaded — keep Python class-level defaults

        g = _CONFIG_LOADER.universal_cfg

        # Sync cleaning toggles only when cleaning is still vanilla default
        if self.cleaning == CleaningConfig():
            cl = self.cleaning
            cl.remove_urls             = bool(g.get('remove_urls',             cl.remove_urls))
            cl.remove_emails           = bool(g.get('remove_emails',           cl.remove_emails))
            cl.preserve_bible_text     = bool(g.get('preserve_bible_text',     cl.preserve_bible_text))
            cl.filter_single_chars     = bool(g.get('filter_single_chars',     cl.filter_single_chars))
            cl.fix_hyphenation         = bool(g.get('fix_hyphenation',         cl.fix_hyphenation))
            cl.normalize_whitespace    = bool(g.get('normalize_whitespace',    cl.normalize_whitespace))
            cl.normalize_unicode       = bool(g.get('normalize_unicode',       cl.normalize_unicode))
            cl.normalize_punctuation   = bool(g.get('normalize_punctuation',   cl.normalize_punctuation))
            cl.process_ocr_artifacts   = bool(g.get('process_ocr_artifacts',   cl.process_ocr_artifacts))
            cl.protect_citations       = bool(g.get('protect_citations',       cl.protect_citations))

        # Sync sentence length bounds only when segmentation is still vanilla default
        if self.segmentation == SegmentationConfig():
            seg = self.segmentation
            seg.min_sentence_length = int(g.get('min_sentence_length', seg.min_sentence_length))
            seg.max_sentence_length = int(g.get('max_sentence_length', seg.max_sentence_length))

    def resolve_profile(self, path: Optional[Path] = None) -> LanguageProfile:
        """
        Return the LanguageProfile for this configuration.

        If language == "auto", detect from *path* using the YAML-driven
        detect_language(); if path is None, return the universal profile.
        """
        if self.language == "auto":
            if path is not None:
                return detect_language(path)
            return _UNIVERSAL_PROFILE
        return LANGUAGE_PROFILES.get(self.language, _UNIVERSAL_PROFILE)

    # ── JSON serialisation ────────────────────────────────────────────────

    @classmethod
    def from_json(cls, json_path: str) -> 'UnifiedConfig':
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(
            language=data.get('language', 'auto'),
            corpus_config_file=data.get('corpus_config_file', 'corpus_config.yaml'),
            extraction=ExtractionConfig(**data.get('extraction', {})),
            cleaning=CleaningConfig(**data.get('cleaning', {})),
            segmentation=SegmentationConfig(**data.get('segmentation', {})),
            output=OutputConfig(**data.get('output', {})),
            max_memory_mb=data.get('max_memory_mb', 500),
            chunk_size=data.get('chunk_size', 5000),
            log_level=data.get('log_level', 'INFO'),
            recursive=data.get('recursive', True),
        )

    def to_json(self, json_path: str) -> None:
        def convert_sets(obj):
            if isinstance(obj, dict):
                return {k: convert_sets(v) for k, v in obj.items()}
            elif isinstance(obj, set):
                return sorted(obj)
            elif isinstance(obj, list):
                return [convert_sets(item) for item in obj]
            return obj

        data = {
            'language': self.language,
            'corpus_config_file': self.corpus_config_file,
            'extraction':   asdict(self.extraction),
            'cleaning':     asdict(self.cleaning),
            'segmentation': asdict(self.segmentation),
            'output':       asdict(self.output),
            'max_memory_mb': self.max_memory_mb,
            'chunk_size':    self.chunk_size,
            'log_level':     self.log_level,
            'recursive':     self.recursive,
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(convert_sets(data), f, indent=2)

    # ── Presets ───────────────────────────────────────────────────────────

    @classmethod
    def preset_minimal(cls, language: str = "auto") -> 'UnifiedConfig':
        return cls(
            language=language,
            cleaning=CleaningConfig(
                remove_urls=True, remove_emails=True,
                normalize_whitespace=True, normalize_unicode=True,
                process_ocr_artifacts=False, filter_single_chars=False,
            )
        )

    @classmethod
    def preset_standard(cls, language: str = "auto") -> 'UnifiedConfig':
        return cls(language=language)

    @classmethod
    def preset_aggressive(cls, language: str = "auto") -> 'UnifiedConfig':
        return cls(
            language=language,
            cleaning=CleaningConfig(
                remove_urls=True, remove_emails=True,
                preserve_bible_text=False, filter_single_chars=True,
                normalize_whitespace=True, normalize_unicode=True,
                normalize_punctuation=True, process_ocr_artifacts=True,
                min_line_length=5,
            )
        )

    @classmethod
    def preset_pristine(cls, language: str = "auto") -> 'UnifiedConfig':
        return cls(
            language=language,
            extraction=ExtractionConfig(
                pdf_method="pymupdf" if PYMUPDF_AVAILABLE else "pdfplumber",
                pymupdf_margin=0.1,
            ),
            cleaning=CleaningConfig(
                remove_urls=True, remove_emails=True,
                preserve_bible_text=False, filter_single_chars=True,
                normalize_whitespace=True, normalize_unicode=True,
                normalize_punctuation=True, process_ocr_artifacts=True,
                pristine_mode=True, remove_junk_consonants=True,
                unwrap_lines=True, unicode_form="NFKD", protect_citations=True,
                min_line_length=5,
            ),
            segmentation=SegmentationConfig(
                use_spacy=SPACY_AVAILABLE and len(SPACY_MODELS) > 0,
                use_nltk=True, min_sentence_length=5,
            ),
        )


# ============================================================================
# STATISTICS & RESULTS
# ============================================================================

@dataclass
class ProcessingStats:
    total_files:       int = 0
    successful_files:  int = 0
    failed_files:      int = 0
    files_by_language: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    extraction_successes: int = 0
    extraction_failures:  int = 0
    total_lines:             int = 0
    total_chars_before:      int = 0
    total_chars_after:       int = 0
    urls_removed:            int = 0
    emails_removed:          int = 0
    single_chars_removed:    int = 0
    bible_refs_removed:      int = 0
    chapter_headings_removed: int = 0
    lines_truncated:         int = 0
    lines_removed_too_short: int = 0
    hyphenations_fixed:      int = 0
    linebreaks_fixed:        int = 0
    junk_consonants_removed: int = 0
    lines_unwrapped:         int = 0
    total_sentences:     int = 0
    total_words:         int = 0
    segmentation_method: str = "unknown"
    chunks_processed:    int = 0
    memory_warnings:     int = 0
    errors_by_stage:     Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    start_time: Optional[datetime] = None
    end_time:   Optional[datetime] = None

    @property
    def reduction_percentage(self) -> float:
        if self.total_chars_before == 0:
            return 0.0
        return round((1 - self.total_chars_after / self.total_chars_before) * 100, 2)

    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return round((self.successful_files / self.total_files) * 100, 2)

    @property
    def processing_time(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def avg_sentences_per_file(self) -> float:
        if self.successful_files == 0:
            return 0.0
        return round(self.total_sentences / self.successful_files, 2)

    @property
    def avg_words_per_sentence(self) -> float:
        if self.total_sentences == 0:
            return 0.0
        return round(self.total_words / self.total_sentences, 2)

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['reduction_percentage']   = self.reduction_percentage
        data['success_rate']           = self.success_rate
        data['processing_time']        = self.processing_time
        data['avg_sentences_per_file'] = self.avg_sentences_per_file
        data['avg_words_per_sentence'] = self.avg_words_per_sentence
        return data

    def __str__(self) -> str:
        lang_breakdown = ', '.join(
            f"{k}: {v}" for k, v in sorted(self.files_by_language.items())
        ) or "n/a"
        lines = [
            "=" * 70,
            "GOBELO CORPUS BUILDER TOOLKIT v4.0 — PROCESSING STATISTICS",
            "=" * 70,
            "",
            "Overall Processing:",
            f"  Total files:       {self.total_files}",
            f"  Successful:        {self.successful_files}",
            f"  Failed:            {self.failed_files}",
            f"  Success rate:      {self.success_rate}%",
            f"  Processing time:   {self.processing_time:.2f}s",
            f"  Languages found:   {lang_breakdown}",
            "",
            "Extraction Stage:",
            f"  Successful:        {self.extraction_successes}",
            f"  Failed:            {self.extraction_failures}",
            "",
            "Cleaning Stage:",
            f"  Lines processed:   {self.total_lines}",
            f"  URLs removed:      {self.urls_removed}",
            f"  Emails removed:    {self.emails_removed}",
            f"  Bible refs removed:{self.bible_refs_removed}",
            f"  Chapter headings:  {self.chapter_headings_removed}",
            f"  Single chars:      {self.single_chars_removed}",
            f"  Hyphenations fixed:{self.hyphenations_fixed}",
            "",
            "Segmentation Stage:",
            f"  Method:            {self.segmentation_method}",
            f"  Total sentences:   {self.total_sentences}",
            f"  Total words:       {self.total_words}",
            f"  Avg sent/file:     {self.avg_sentences_per_file}",
            f"  Avg words/sent:    {self.avg_words_per_sentence}",
            "",
            "Size Reduction:",
            f"  Chars before:      {self.total_chars_before:,}",
            f"  Chars after:       {self.total_chars_after:,}",
            f"  Reduction:         {self.reduction_percentage}%",
            "",
            "Performance:",
            f"  Memory warnings:   {self.memory_warnings}",
            f"  Errors by stage:   {dict(self.errors_by_stage)}",
            "=" * 70,
        ]
        return "\n".join(lines)


@dataclass
class ProcessingResult:
    file_path:       Path
    success:         bool
    language:        str = "und"
    stage_completed: str = ""
    error:           Optional[str] = None
    extracted_text:  Optional[str] = None
    cleaned_text:    Optional[str] = None
    sentences:       Optional[List[str]] = None
    metadata:        Optional[Dict[str, Any]] = None
    output_paths:    Dict[str, Path] = field(default_factory=dict)

    @classmethod
    def failed(cls, file_path: Path, stage: str, error: str,
               language: str = "und") -> 'ProcessingResult':
        return cls(file_path=file_path, success=False,
                   language=language, stage_completed=stage, error=error)

    @classmethod
    def success_result(cls, file_path: Path, language: str = "und",
                       **kwargs) -> 'ProcessingResult':
        return cls(file_path=file_path, success=True,
                   language=language, stage_completed='output', **kwargs)


# ============================================================================
# MEMORY MANAGEMENT
# ============================================================================

class MemoryManager:
    def __init__(self, max_memory_mb: int = 250,
                 logger: Optional[logging.Logger] = None):
        self.max_memory_mb = max_memory_mb
        self.warning_count = 0
        self.logger = logger or logging.getLogger(__name__)

    def check(self) -> Tuple[bool, float]:
        if not PSUTIL_AVAILABLE:
            return False, 0.0
        try:
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)
            if memory_mb > self.max_memory_mb:
                self.warning_count += 1
                self.logger.warning(
                    f"Memory {memory_mb:.1f} MB > limit {self.max_memory_mb} MB. Running GC.")
                gc.collect()
                new_memory = process.memory_info().rss / (1024 * 1024)
                if new_memory > self.max_memory_mb * 1.2:
                    raise MemoryLimitError(
                        f"Memory {new_memory:.1f} MB still exceeds limit.")
                return True, new_memory
            return False, memory_mb
        except psutil.Error as e:
            self.logger.error(f"Memory check error: {e}")
            return False, 0.0

    def get_warning_count(self) -> int:
        return self.warning_count


# ============================================================================
# TEXT EXTRACTION — Stage 1
# ============================================================================

class FileProcessor(ABC):
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    @abstractmethod
    def extract_text(self, file_path: Path) -> Optional[str]:
        pass

    def can_process(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.get_supported_extensions()

    @abstractmethod
    def get_supported_extensions(self) -> set:
        pass


class PDFProcessor(FileProcessor):
    def get_supported_extensions(self) -> set:
        return {'.pdf'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        if not PDF_AVAILABLE:
            raise ExtractionError("PDF libraries not installed")
        try:
            try:
                with pdfplumber.open(file_path) as pdf:
                    parts = [p.extract_text() for p in pdf.pages if p.extract_text()]
                    return '\n'.join(parts) if parts else None
            except Exception:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    parts = [p.extract_text() for p in reader.pages if p.extract_text()]
                    return '\n'.join(parts) if parts else None
        except Exception as e:
            raise ExtractionError(f"PDF extraction failed: {e}")


class PyMuPDFProcessor(FileProcessor):
    def __init__(self, logger: logging.Logger, config: ExtractionConfig):
        super().__init__(logger)
        self.margin = config.pymupdf_margin

    def get_supported_extensions(self) -> set:
        return {'.pdf'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        if not PYMUPDF_AVAILABLE:
            raise ExtractionError("PyMuPDF not installed")
        try:
            doc = fitz.open(file_path)
            chunks = []
            for page in doc:
                h, w = page.rect.height, page.rect.width
                top, bottom = h * self.margin, h * (1 - self.margin)
                left, right = w * (self.margin / 2), w * (1 - self.margin / 2)
                for b in page.get_text("dict")["blocks"]:
                    if b["type"] == 0:
                        bbox = b["bbox"]
                        if (bbox[1] > top and bbox[3] < bottom
                                and bbox[0] > left and bbox[2] < right):
                            chunks.append(" ".join(
                                s["text"] for l in b["lines"] for s in l["spans"]
                            ))
            doc.close()
            return " ".join(chunks) if chunks else None
        except Exception as e:
            raise ExtractionError(f"PyMuPDF extraction failed: {e}")


class DOCXProcessor(FileProcessor):
    def get_supported_extensions(self) -> set:
        return {'.docx', '.doc'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        if not DOCX_AVAILABLE:
            raise ExtractionError("python-docx not installed")
        try:
            doc = Document(file_path)
            return '\n'.join(p.text for p in doc.paragraphs)
        except Exception as e:
            raise ExtractionError(f"DOCX extraction failed: {e}")


class EPUBProcessor(FileProcessor):
    def get_supported_extensions(self) -> set:
        return {'.epub'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        if not (EPUB_AVAILABLE and BS4_AVAILABLE):
            raise ExtractionError("ebooklib or beautifulsoup4 not installed")
        try:
            book = epub.read_epub(file_path)
            parts = []
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_body_content(), 'html.parser')
                    text = soup.get_text()
                    if text.strip():
                        parts.append(text.strip())
            return '\n'.join(parts) if parts else None
        except Exception as e:
            raise ExtractionError(f"EPUB extraction failed: {e}")


class HTMLProcessor(FileProcessor):
    def get_supported_extensions(self) -> set:
        return {'.html', '.htm', '.xml'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        if not BS4_AVAILABLE:
            raise ExtractionError("beautifulsoup4 not installed")
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            for tag in soup(["script", "style"]):
                tag.decompose()
            text = soup.get_text()
            return text.strip() if text else None
        except Exception as e:
            raise ExtractionError(f"HTML extraction failed: {e}")


class MarkdownProcessor(FileProcessor):
    def get_supported_extensions(self) -> set:
        return {'.md', '.markdown'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            if MARKDOWN_AVAILABLE and BS4_AVAILABLE:
                html = markdown.markdown(content)
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text()
            return re.sub(r'[#*`_\[\]()]+', '', content)
        except Exception as e:
            raise ExtractionError(f"Markdown extraction failed: {e}")


class TXTProcessor(FileProcessor):
    def get_supported_extensions(self) -> set:
        return {'.txt', '.text'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        try:
            encoding = 'utf-8'
            if CHARDET_AVAILABLE:
                with open(file_path, 'rb') as f:
                    result = chardet.detect(f.read(10000))
                    encoding = result.get('encoding', 'utf-8')
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                return f.read()
        except Exception as e:
            raise ExtractionError(f"TXT extraction failed: {e}")


class SRTProcessor(FileProcessor):
    """
    SubRip subtitle (.srt) extractor.

    Strips sequence numbers, timecode lines (00:00:01,000 --> 00:00:03,000),
    and HTML-style formatting tags, leaving only the spoken dialogue text.
    This makes subtitle files usable as natural-language sentence corpora.
    """
    # Matches: "1\n", "42\n" — sequence index lines
    _SEQ  = re.compile(r'^\d+\s*$', re.MULTILINE)
    # Matches: "00:00:01,000 --> 00:00:03,000" and optional position metadata
    _TIME = re.compile(
        r'^\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}.*$',
        re.MULTILINE
    )
    # Matches: <i>, </b>, <font color="...">, etc.
    _TAGS = re.compile(r'<[^>]+>')

    def get_supported_extensions(self) -> set:
        return {'.srt'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        try:
            encoding = 'utf-8'
            if CHARDET_AVAILABLE:
                with open(file_path, 'rb') as f:
                    result = chardet.detect(f.read(10000))
                    encoding = result.get('encoding', 'utf-8-sig')  # handle BOM
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                raw = f.read()
            # Remove timecodes and sequence numbers
            text = self._TIME.sub('', raw)
            text = self._SEQ.sub('', text)
            # Remove HTML-style formatting
            text = self._TAGS.sub('', text)
            # Collapse runs of blank lines left behind
            text = re.sub(r'\n{3,}', '\n\n', text).strip()
            return text if text else None
        except Exception as e:
            raise ExtractionError(f"SRT extraction failed: {e}")


class CSVProcessor(FileProcessor):
    def get_supported_extensions(self) -> set:
        return {'.csv'}

    def extract_text(self, file_path: Path) -> Optional[str]:
        if PANDAS_AVAILABLE:
            try:
                df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip')
                parts = []
                for col in df.select_dtypes(include=['object']):
                    parts.extend(df[col].dropna().astype(str).tolist())
                return '\n'.join(parts) if parts else None
            except Exception as e:
                raise ExtractionError(f"CSV extraction failed: {e}")
        else:
            import csv
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    rows = [' '.join(row) for row in csv.reader(f)]
                return '\n'.join(rows)
            except Exception as e:
                raise ExtractionError(f"CSV extraction failed: {e}")


class ProcessorFactory:
    def __init__(self, logger: logging.Logger, config: ExtractionConfig):
        self.logger = logger
        pdf = (PyMuPDFProcessor(logger, config)
               if config.pdf_method == "pymupdf" and PYMUPDF_AVAILABLE
               else PDFProcessor(logger))
        self.processors = [
            pdf, DOCXProcessor(logger), EPUBProcessor(logger),
            HTMLProcessor(logger), MarkdownProcessor(logger),
            SRTProcessor(logger), TXTProcessor(logger), CSVProcessor(logger),
        ]

    def get_processor(self, file_path: Path) -> Optional[FileProcessor]:
        for p in self.processors:
            if p.can_process(file_path):
                return p
        return None

    def extract_text(self, file_path: Path) -> Optional[str]:
        proc = self.get_processor(file_path)
        if proc:
            return proc.extract_text(file_path)
        raise ExtractionError(f"Unsupported file format: {file_path.suffix}")


# ============================================================================
# TEXT CLEANING — Stage 2  (language-profile-aware; profile injected from YAML)
# ============================================================================

class ZambianTextCleaner:
    """
    Language-agnostic text cleaner driven by a LanguageProfile.

    In v4.0 the profile is always built from YAML (via CorpusConfigLoader)
    rather than from hardcoded dicts.  The interface is identical to v3.0.
    Pass profile=None to use the universal profile.
    """

    def __init__(self, config: UnifiedConfig,
                 logger: logging.Logger,
                 stats: ProcessingStats,
                 profile: Optional[LanguageProfile] = None):
        self.config  = config
        self.logger  = logger
        self.stats   = stats
        self.profile = profile or _UNIVERSAL_PROFILE
        self._chapter_pattern: Optional[re.Pattern] = None
        logger.info(
            f"TextCleaner initialised for language: "
            f"{self.profile.name} ({self.profile.iso_code})"
        )

    def set_profile(self, profile: LanguageProfile) -> None:
        """Switch language profile (called per-file in auto-detect mode)."""
        self.profile = profile
        self._chapter_pattern = None

    @property
    def chapter_pattern(self) -> re.Pattern:
        if self._chapter_pattern is None:
            self._chapter_pattern = build_chapter_heading_pattern(self.profile)
        return self._chapter_pattern

    # ── Cleaning steps ────────────────────────────────────────────────────

    def normalize_unicode(self, text: str) -> str:
        form = getattr(self.config.cleaning, 'unicode_form', 'NFC')
        if form == "NFKD":
            return unicodedata.normalize('NFKD', text)
        nfd = unicodedata.normalize('NFD', text)
        result, i = [], 0
        while i < len(nfd):
            char = nfd[i]
            if (i + 1 < len(nfd)
                    and unicodedata.category(nfd[i + 1]) == 'Mn'):
                combined = char + nfd[i + 1]
                composed = unicodedata.normalize('NFC', combined)
                if composed in self.profile.special_chars:
                    result.append(composed)
                    i += 2
                    continue
            result.append(char)
            i += 1
        return unicodedata.normalize('NFC', ''.join(result))

    def normalize_punctuation(self, text: str) -> str:
        for old, new in self.profile.punctuation_map.items():
            text = text.replace(old, new)
        return text

    def fix_hyphenation(self, text: str) -> str:
        count = len(re.findall(r'(\w+)-\s*\n\s*(\w+)', text))
        text  = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        text  = re.sub(r'(\w+)-\s+(\w+)(?=\s|$)', r'\1\2', text)
        self.stats.hyphenations_fixed += count
        return text

    def unwrap_lines(self, text: str) -> str:
        count = len(TextPatterns.SINGLE_NEWLINE.findall(text))
        self.stats.lines_unwrapped += count
        return TextPatterns.SINGLE_NEWLINE.sub(' ', text)

    def protect_abbreviations(self, text: str) -> str:
        """
        Temporarily replace period-terminated abbreviations with a sentinel
        so the sentence segmenter does not split on them.

        The abbreviation list is taken from profile.book_abbreviations, which
        is populated entirely from corpus_config.yaml (global + per-language).
        No abbreviations are hardcoded here.
        """
        for abbr in sorted(self.profile.book_abbreviations, key=len, reverse=True):
            # Sort longest-first so "et al" matches before "al"
            safe_abbr = abbr.replace('.', '<DOT>')
            pattern = r'\b' + re.escape(abbr) + r'\.'
            replacement = safe_abbr + '<DOT>'
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def restore_abbreviations(self, text: str) -> str:
        return text.replace('<DOT>', '.')

    def remove_urls(self, text: str) -> str:
        p1 = r'http[s]?://\S+'
        p2 = r'www\.\S+'
        n1 = len(re.findall(p1, text))
        text = re.sub(p1, '', text)
        n2 = len(re.findall(p2, text))
        text = re.sub(p2, '', text)
        self.stats.urls_removed += n1 + n2
        return text

    def remove_emails(self, text: str) -> str:
        pat = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
        count = len(re.findall(pat, text))
        self.stats.emails_removed += count
        return re.sub(pat, '', text)

    def remove_bible_references_text(self, text: str) -> str:
        cleaned, count = remove_bible_references(text)
        self.stats.bible_refs_removed += count
        return cleaned

    def remove_chapter_headings(self, text: str) -> str:
        lines = text.split('\n')
        filtered = []
        for line in lines:
            if self.chapter_pattern.match(line.strip()):
                self.stats.chapter_headings_removed += 1
            else:
                filtered.append(line)
        return '\n'.join(filtered)

    def apply_strip_patterns(self, text: str) -> str:
        """
        Remove lines matching any regex in profile.strip_patterns.

        Patterns come from corpus_config.yaml `strip_patterns` (global and
        per-language). Useful for footnotes, page headers, running titles,
        and other structural noise that varies by corpus.

        Example corpus_config.yaml entry:
            strip_patterns:
              - '^\\s*Footnote\\s+\\d+'
              - '^\\s*Page\\s+\\d+\\s*$'
        """
        if not self.profile.strip_patterns:
            return text
        try:
            compiled = [re.compile(p, re.MULTILINE) for p in self.profile.strip_patterns]
        except re.error as e:
            self.logger.warning(f"Invalid strip_pattern: {e}. Skipping.")
            return text
        lines = text.split('\n')
        filtered, removed = [], 0
        for line in lines:
            if any(pat.match(line.strip()) for pat in compiled):
                removed += 1
            else:
                filtered.append(line)
        if removed:
            self.logger.debug(f"strip_patterns removed {removed} line(s)")
        return '\n'.join(filtered)

    def remove_consonant_clusters(self, text: str) -> str:
        pattern = r'\b(?=[a-z]{5,})[^aeiouy\s]+\b'
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        self.stats.junk_consonants_removed += len(matches)
        return re.sub(pattern, '', text, flags=re.IGNORECASE)

    def filter_single_characters(self, text: str) -> str:
        """Remove single-character tokens not in the active profile's valid set."""
        valid = self.profile.valid_single_chars
        words = text.split()
        filtered = []
        for word in words:
            if len(word) != 1 or word.lower() in valid:
                filtered.append(word)
            else:
                self.stats.single_chars_removed += 1
        return ' '.join(filtered)

    def fix_ocr_corrections(self, text: str) -> str:
        """Apply language-specific OCR corrections from corpus_config.yaml ocr_corrections."""
        for wrong, right in self.profile.ocr_corrections.items():
            text = re.sub(rf'\b{re.escape(wrong)}\b', right, text)
        return text

    # Backward-compat alias — remove in v5.0
    fix_ocr_errors = fix_ocr_corrections

    def collapse_whitespace(self, text: str) -> str:
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # ── Master cleaning pipeline ──────────────────────────────────────────

    def clean(self, text: str) -> str:
        if not text or not text.strip():
            return ""

        if self.config.cleaning.normalize_unicode:
            text = self.normalize_unicode(text)
        if self.config.cleaning.normalize_punctuation:
            text = self.normalize_punctuation(text)
        if self.config.cleaning.fix_hyphenation:
            text = self.fix_hyphenation(text)
        if self.config.cleaning.unwrap_lines:
            text = self.unwrap_lines(text)
        if self.config.cleaning.protect_abbreviations:
            text = self.protect_abbreviations(text)
        if self.config.cleaning.remove_urls:
            text = self.remove_urls(text)
        if self.config.cleaning.remove_emails:
            text = self.remove_emails(text)
        if not self.config.cleaning.preserve_bible_text and self.config.cleaning.remove_bible_references:
            text = self.remove_bible_references_text(text)

        text = self.remove_chapter_headings(text)
        text = self.apply_strip_patterns(text)

        if self.config.cleaning.process_ocr_artifacts:
            text = self.fix_ocr_corrections(text)
        if self.config.cleaning.remove_junk_consonants:
            text = self.remove_consonant_clusters(text)
        if self.config.cleaning.filter_single_chars:
            text = self.filter_single_characters(text)
        if self.config.cleaning.protect_abbreviations:
            text = self.restore_abbreviations(text)

        text = self.collapse_whitespace(text)
        return text

    # Backward-compat alias
    def clean_text(self, text: str) -> str:
        return self.clean(text)


# Backward-compatibility alias
ChitongaTextCleaner = ZambianTextCleaner


# ============================================================================
# SENTENCE SEGMENTATION — Stage 3
# ============================================================================

class SentenceSegmenter:
    """
    Language-aware sentence segmenter.

    Abbreviation sets come from the active LanguageProfile, which in v4.0
    is built from corpus_config.yaml rather than hardcoded dicts.
    """

    def __init__(self, config: SegmentationConfig,
                 logger: logging.Logger,
                 stats: ProcessingStats,
                 profile: Optional[LanguageProfile] = None):
        self.config  = config
        self.logger  = logger
        self.stats   = stats
        self.profile = profile or _UNIVERSAL_PROFILE
        self.sentence_endings = {'.', '!', '?', ':', ';'}
        self._build_abbrev_pattern()
        self.spacy_nlp = None
        if config.use_spacy and SPACY_AVAILABLE:
            self._init_spacy()

    def set_profile(self, profile: LanguageProfile) -> None:
        self.profile = profile
        self._build_abbrev_pattern()

    def _build_abbrev_pattern(self) -> None:
        """
        Build the abbreviation regex from profile.book_abbreviations.

        Guards against an empty set (e.g. when running without corpus_config.yaml)
        by falling back to a pattern that never matches, so segmentation still
        works — it just won't protect any abbreviations.
        """
        abbreviations = self.profile.book_abbreviations
        if not abbreviations:
            # Never-matching sentinel — avoids re.compile('\\b()\\.$') crash
            self.abbrev_pattern = re.compile(r'(?!)')
            return
        self.abbrev_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(a) for a in sorted(abbreviations, key=len, reverse=True)) + r')\.$',
            re.IGNORECASE
        )

    def _init_spacy(self) -> None:
        try:
            self.spacy_nlp = spacy.load(
                self.config.spacy_model, disable=["ner", "parser", "textcat"])
            if "sentencizer" not in self.spacy_nlp.pipe_names:
                self.spacy_nlp.add_pipe("sentencizer")
            self.logger.info(f"spaCy model loaded: {self.config.spacy_model}")
        except Exception as e:
            self.logger.warning(f"spaCy load failed: {e}. Falling back.")
            self.spacy_nlp = None

    def segment_sentences(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []
        if self.spacy_nlp:
            self.stats.segmentation_method = "spaCy"
            return self._spacy_segment(text)
        if NLTK_AVAILABLE and self.config.use_nltk:
            self.stats.segmentation_method = "NLTK"
            return self._nltk_segment(text)
        self.stats.segmentation_method = "fallback"
        return self._fallback_segment(text)

    def _spacy_segment(self, text: str) -> List[str]:
        try:
            doc = self.spacy_nlp(text)
            return self._post_process([s.text.strip() for s in doc.sents])
        except Exception as e:
            self.logger.warning(f"spaCy failed: {e}. Using NLTK.")
            return self._nltk_segment(text) if NLTK_AVAILABLE else self._fallback_segment(text)

    def _nltk_segment(self, text: str) -> List[str]:
        try:
            return self._post_process(sent_tokenize(text))
        except Exception as e:
            self.logger.warning(f"NLTK failed: {e}. Using fallback.")
            return self._fallback_segment(text)

    def _fallback_segment(self, text: str) -> List[str]:
        sentences, current = [], ""
        for char in text:
            current += char
            if char in self.sentence_endings and self._is_sentence_ending(current):
                sentences.append(current.strip())
                current = ""
        if current.strip():
            sentences.append(current.strip())
        return self._post_process(sentences)

    def _is_sentence_ending(self, sentence: str) -> bool:
        words = sentence.split()
        if words and self.abbrev_pattern.match(words[-1]):
            return False
        return True

    def _post_process(self, sentences: List[str]) -> List[str]:
        processed = []
        for s in sentences:
            s = s.strip()
            if not s or len(s) < self.config.min_sentence_length:
                continue
            if len(s) > self.config.max_sentence_length:
                processed.extend(self._split_long_sentence(s))
            else:
                processed.append(s)
        return processed

    def _split_long_sentence(self, sentence: str) -> List[str]:
        for bp in [';', ':', ',', ' - ', ' – ', ' — ']:
            if bp in sentence:
                parts = sentence.split(bp)
                if len(parts) > 1:
                    result = []
                    for i, part in enumerate(parts):
                        part = part.strip()
                        if part:
                            if i < len(parts) - 1:
                                part += bp.strip()
                            result.append(part)
                    return result
        return [sentence]


# ============================================================================
# OUTPUT GENERATION — Stage 4
# ============================================================================

class OutputGenerator:
    def __init__(self, config: OutputConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def generate_outputs(self, result: ProcessingResult,
                         output_dir: Path,
                         subject_category: str) -> Dict[str, Path]:
        outputs = {}
        try:
            metadata = self._generate_metadata(result, subject_category)
            if 'txt' in self.config.formats:
                p = output_dir.with_suffix('.txt')
                if self._save_txt(result.sentences, p):
                    outputs['txt'] = p
            if 'json' in self.config.formats:
                p = output_dir.with_suffix('.json')
                if self._save_json(metadata, p):
                    outputs['json'] = p
            if 'cleaned' in self.config.formats:
                p = output_dir.with_suffix('.cleaned.txt')
                if self._save_cleaned(result.cleaned_text, p):
                    outputs['cleaned'] = p
        except Exception as e:
            self.logger.error(f"Output generation error: {e}")
            raise
        return outputs

    def _generate_metadata(self, result: ProcessingResult,
                            subject_category: str) -> Dict[str, Any]:
        wc = len(result.cleaned_text.split()) if result.cleaned_text else 0
        cc = len(result.cleaned_text) if result.cleaned_text else 0
        sc = len(result.sentences) if result.sentences else 0
        lang_name = LANGUAGE_PROFILES.get(result.language, _UNIVERSAL_PROFILE).name
        return {
            "filename":               result.file_path.name,
            "original_path":          str(result.file_path),
            "original_format":        result.file_path.suffix.lower(),
            "subject_category":       subject_category,
            "language_iso":           result.language,
            "language_name":          lang_name,
            "processing_timestamp":   datetime.now().isoformat(),
            "statistics": {
                "sentence_count":         sc,
                "word_count":             wc,
                "character_count":        cc,
                "avg_words_per_sentence": round(wc / sc, 2) if sc else 0,
                "avg_chars_per_sentence": round(cc / sc, 2) if sc else 0,
            },
            "sentences": result.sentences if self.config.include_metadata else [],
        }

    def _save_txt(self, sentences: List[str], path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                for s in sentences:
                    f.write(s + '\n')
            return True
        except Exception as e:
            self.logger.error(f"Error saving TXT: {e}")
            return False

    def _save_json(self, metadata: Dict, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving JSON: {e}")
            return False

    def _save_cleaned(self, text: str, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            return True
        except Exception as e:
            self.logger.error(f"Error saving cleaned text: {e}")
            return False


# ============================================================================
# MAIN PIPELINE — ZambianCorpusBuilder
# ============================================================================

class ZambianCorpusBuilder:
    """
    Main pipeline: Extract → Clean → Segment → Export.

    In v4.0 language profiles are resolved from YAML-driven LANGUAGE_PROFILES
    (populated by CorpusConfigLoader at startup) rather than from hardcoded dicts.
    All per-file and per-directory logic is unchanged from v3.0.
    """

    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.stats  = ProcessingStats()
        self.stats.start_time = datetime.now()

        # Always attempt to load/reload profiles from the configured YAML path.
        # This ensures that a non-default CWD, a custom --corpus-config flag,
        # or a hot-reload request all resolve correctly.
        _cfg_path = Path(config.corpus_config_file)
        if _cfg_path.exists():
            reload_profiles(str(_cfg_path))
        else:
            logging.getLogger('gcbt').warning(
                f"corpus_config.yaml not found at '{_cfg_path}'. "
                "Running with currently loaded profiles."
            )

        self.logger         = self._setup_logging()
        self.memory_manager = MemoryManager(config.max_memory_mb, self.logger)
        self.extractor      = ProcessorFactory(self.logger, config.extraction)

        initial_profile = (
            LANGUAGE_PROFILES.get(config.language, _UNIVERSAL_PROFILE)
            if config.language != "auto"
            else _UNIVERSAL_PROFILE
        )
        self.cleaner          = ZambianTextCleaner(config, self.logger,
                                                   self.stats, initial_profile)
        self.segmenter        = SentenceSegmenter(config.segmentation, self.logger,
                                                  self.stats, initial_profile)
        self.output_generator = OutputGenerator(config.output, self.logger)

        loaded = sorted(LANGUAGE_PROFILES.keys())
        self.logger.info(
            f"gcbt v4.0 — language mode: '{config.language}' | "
            f"profiles loaded: {loaded}"
        )

    def _setup_logging(self) -> logging.Logger:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        logger = logging.getLogger('gcbt')
        logger.setLevel(getattr(logging, self.config.log_level))
        logger.handlers.clear()
        log_file = log_dir / f"gcbt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(getattr(logging, self.config.log_level))
        fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
        return logger

    def _resolve_profile(self, file_path: Path) -> LanguageProfile:
        if self.config.language == "auto":
            return detect_language(file_path)
        return LANGUAGE_PROFILES.get(self.config.language, _UNIVERSAL_PROFILE)

    def process_file(self, file_path: Path,
                     input_root: Path,
                     output_dir: Path) -> ProcessingResult:
        self.stats.total_files += 1
        self.logger.info(f"Processing: {file_path.name}")

        profile = self._resolve_profile(file_path)
        self.cleaner.set_profile(profile)
        self.segmenter.set_profile(profile)
        self.stats.files_by_language[profile.iso_code] += 1
        self.logger.debug(f"  Language: {profile.name} ({profile.iso_code})")

        try:
            # Stage 1 — Extract
            try:
                raw_text = self.extractor.extract_text(file_path)
                if not raw_text or not raw_text.strip():
                    self.stats.extraction_failures += 1
                    return ProcessingResult.failed(
                        file_path, 'extraction', 'No text extracted', profile.iso_code)
                self.stats.extraction_successes += 1
            except ExtractionError as e:
                self.stats.extraction_failures += 1
                return ProcessingResult.failed(
                    file_path, 'extraction', str(e), profile.iso_code)

            # Stage 2 — Clean
            try:
                cleaned_text = self.cleaner.clean(raw_text)
                if not cleaned_text or not cleaned_text.strip():
                    return ProcessingResult.failed(
                        file_path, 'cleaning', 'Empty after cleaning', profile.iso_code)
            except CleaningError as e:
                return ProcessingResult.failed(
                    file_path, 'cleaning', str(e), profile.iso_code)

            # Stage 3 — Segment
            try:
                sentences = self.segmenter.segment_sentences(cleaned_text)
                if not sentences:
                    return ProcessingResult.failed(
                        file_path, 'segmentation', 'No sentences', profile.iso_code)
                self.stats.total_sentences += len(sentences)
                self.stats.total_words    += sum(len(s.split()) for s in sentences)
            except SegmentationError as e:
                return ProcessingResult.failed(
                    file_path, 'segmentation', str(e), profile.iso_code)

            # Stage 4 — Output
            try:
                relative_path    = file_path.relative_to(input_root)
                subject_category = (relative_path.parts[0]
                                    if len(relative_path.parts) > 1
                                    else "uncategorized")
                output_base = output_dir / relative_path.with_suffix('')

                result = ProcessingResult(
                    file_path=file_path, success=True,
                    language=profile.iso_code,
                    stage_completed='segmentation',
                    extracted_text=raw_text,
                    cleaned_text=cleaned_text,
                    sentences=sentences,
                )
                result.output_paths = self.output_generator.generate_outputs(
                    result, output_base, subject_category)
                result.stage_completed = 'output'
                self.stats.successful_files += 1
                self.logger.info(f"✓ {file_path.name} [{profile.name}]")
                return result

            except Exception as e:
                return ProcessingResult.failed(
                    file_path, 'output', str(e), profile.iso_code)

        except Exception as e:
            self.stats.failed_files += 1
            self.stats.errors_by_stage['unknown'] += 1
            self.logger.error(f"Unexpected error processing {file_path}: {e}")
            return ProcessingResult.failed(file_path, 'unknown', str(e))

        finally:
            exceeded, _ = self.memory_manager.check()
            if exceeded:
                self.stats.memory_warnings += 1

    def process_directory(self, input_dir: Path,
                          output_dir: Path) -> List[ProcessingResult]:
        self.logger.info(f"Input:  {input_dir}")
        self.logger.info(f"Output: {output_dir}")

        glob = input_dir.rglob if self.config.recursive else input_dir.glob
        files = [
            f for f in glob("*")
            if f.is_file()
            and f.suffix.lower() in self.config.extraction.supported_formats
        ]

        if not files:
            self.logger.warning(f"No supported files in {input_dir}")
            return []

        self.logger.info(f"Found {len(files)} file(s)")
        results = []

        if RICH_AVAILABLE:
            console = Console()
            with Progress(SpinnerColumn(),
                          TextColumn("[progress.description]{task.description}"),
                          BarColumn(), TaskProgressColumn(),
                          console=console) as progress:
                task = progress.add_task("Processing...", total=len(files))
                for fp in files:
                    progress.update(task, description=f"{fp.name}")
                    results.append(self.process_file(fp, input_dir, output_dir))
                    progress.advance(task)
        else:
            for i, fp in enumerate(files, 1):
                print(f"[{i}/{len(files)}] {fp.name}")
                results.append(self.process_file(fp, input_dir, output_dir))

        self.stats.end_time = datetime.now()
        self.stats.memory_warnings = self.memory_manager.get_warning_count()
        self._write_language_manifest(output_dir, results)
        return results

    def _write_language_manifest(self, output_dir: Path,
                                 results: List[ProcessingResult]) -> None:
        manifest: Dict[str, List[str]] = defaultdict(list)
        for r in results:
            if r.success:
                for fmt, path in r.output_paths.items():
                    manifest[r.language].append(str(path))

        manifest_path = output_dir / "corpus_manifest.json"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "generated":  datetime.now().isoformat(),
                    "gcbt_version": "4.0",
                    "config_source": str(Path(self.config.corpus_config_file).resolve()),
                    "languages":  dict(manifest),
                    "stats":      dict(self.stats.files_by_language),
                }, f, indent=2)
            self.logger.info(f"✓ Corpus manifest: {manifest_path}")
        except Exception as e:
            self.logger.warning(f"Could not write manifest: {e}")

    def get_stats(self) -> ProcessingStats:
        return self.stats


# Backward-compatibility aliases
CorpusProcessingPipeline = ZambianCorpusBuilder
GobeloCorpusBuilder      = ZambianCorpusBuilder


# ============================================================================
# CLI INTERFACE
# ============================================================================

def setup_argument_parser() -> argparse.ArgumentParser:
    # Build language choices dynamically from loaded profiles
    lang_choices = list(LANGUAGE_PROFILES.keys()) + ['auto']

    parser = argparse.ArgumentParser(
        description='Gobelo Corpus Builder Toolkit (gcbt) v4.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Languages loaded (from corpus_config.yaml):
  {", ".join(sorted(k for k in LANGUAGE_PROFILES if k != "und"))}
  und  Universal   auto  Path-based detection (default)

Examples:
  # Auto-detect from directory structure
  python gcbt.py -i corpus/ -o processed/

  # Force Bemba mode
  python gcbt.py -i bemba_docs/ -o out/ --language bem

  # Custom corpus config location
  python gcbt.py -i docs/ -o out/ --corpus-config /path/to/corpus_config.yaml

  # Aggressive preset + Nyanja
  python gcbt.py -i nyanja/ -o out/ --preset aggressive --language nya
        """
    )

    parser.add_argument('--input',  '-i', type=str, help='Input directory')
    parser.add_argument('--output', '-o', type=str, help='Output directory')
    parser.add_argument('--config', '-c', type=str, help='JSON pipeline config file')
    parser.add_argument('--save-config', type=str, help='Save pipeline config to JSON')
    parser.add_argument('--corpus-config', type=str, default='corpus_config.yaml',
                        help='Path to corpus_config.yaml (default: ./corpus_config.yaml)')
    parser.add_argument('--no-recursive', action='store_true')
    parser.add_argument('--formats', type=str, default='txt,json',
                        help='Output formats: txt,json,cleaned')

    parser.add_argument(
        '--language', '-l',
        type=str,
        default='auto',
        choices=lang_choices,
        metavar='LANG',
        help=(
            f'Language ISO code ({", ".join(sorted(k for k in LANGUAGE_PROFILES if k != "und"))}), '
            '"und" for universal, or "auto" (default) for path-based detection.'
        ),
    )

    parser.add_argument('--pdf-method', choices=['pdfplumber', 'pypdf2', 'pymupdf'],
                        default='pdfplumber')
    parser.add_argument('--max-file-size', type=int, default=100)
    parser.add_argument('--no-remove-urls',   action='store_true')
    parser.add_argument('--no-remove-emails', action='store_true')
    parser.add_argument('--preserve-bible',   action='store_true')
    parser.add_argument('--no-process-ocr',   action='store_true')
    parser.add_argument('--no-filter-single-chars', action='store_true')
    parser.add_argument('--min-sentence-length', type=int, default=3)
    parser.add_argument('--max-sentence-length', type=int, default=1000)
    parser.add_argument('--no-nltk', action='store_true')
    parser.add_argument('--max-memory', type=int, default=250)
    parser.add_argument('--chunk-size', type=int, default=5000)
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default='INFO')
    parser.add_argument('--preset',
                        choices=['minimal', 'standard', 'aggressive', 'pristine'],
                        help='Use a preset configuration')
    return parser


def create_config_from_args(args: argparse.Namespace) -> UnifiedConfig:
    # If a custom corpus_config.yaml is given, reload profiles before building config
    if hasattr(args, 'corpus_config') and args.corpus_config != 'corpus_config.yaml':
        reload_profiles(args.corpus_config)

    lang = args.language
    corpus_config_file = getattr(args, 'corpus_config', 'corpus_config.yaml')

    if args.preset:
        presets = {
            'minimal':    UnifiedConfig.preset_minimal,
            'aggressive': UnifiedConfig.preset_aggressive,
            'pristine':   UnifiedConfig.preset_pristine,
        }
        factory = presets.get(args.preset, UnifiedConfig.preset_standard)
        config  = factory(language=lang)
    elif args.config:
        config = UnifiedConfig.from_json(args.config)
        config.language = lang
    else:
        config = UnifiedConfig(
            language=lang,
            corpus_config_file=corpus_config_file,
            extraction=ExtractionConfig(
                pdf_method=args.pdf_method,
                max_file_size_mb=args.max_file_size,
            ),
            cleaning=CleaningConfig(
                remove_urls=not args.no_remove_urls,
                remove_emails=not args.no_remove_emails,
                preserve_bible_text=args.preserve_bible,
                process_ocr_artifacts=not args.no_process_ocr,
                filter_single_chars=not args.no_filter_single_chars,
            ),
            segmentation=SegmentationConfig(
                min_sentence_length=args.min_sentence_length,
                max_sentence_length=args.max_sentence_length,
                use_nltk=not args.no_nltk,
            ),
            output=OutputConfig(formats=set(args.formats.split(','))),
            max_memory_mb=args.max_memory,
            chunk_size=args.chunk_size,
            log_level=args.log_level,
            recursive=not args.no_recursive,
        )

    if args.save_config:
        config.to_json(args.save_config)
        print(f"✓ Config saved: {args.save_config}")

    return config


def run_batch_mode(args: argparse.Namespace) -> int:
    print("=" * 70)
    print("GOBELO CORPUS BUILDER TOOLKIT (gcbt) v4.0")
    print("=" * 70)

    if not args.input or not args.output:
        print("Error: --input and --output are required")
        return 1

    input_dir  = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    if not input_dir.exists():
        print(f"Error: input directory not found: {input_dir}")
        return 1

    config   = create_config_from_args(args)
    pipeline = ZambianCorpusBuilder(config)

    try:
        pipeline.process_directory(input_dir, output_dir)
        stats = pipeline.get_stats()
        print("\n" + str(stats))

        stats_file = output_dir / "processing_stats.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats.to_dict(), f, indent=2, default=str)
        print(f"\n✓ Stats saved: {stats_file}")
        return 0 if stats.success_rate > 0 else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return 1


def run_interactive_mode() -> int:
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║          GOBELO CORPUS BUILDER TOOLKIT (gcbt) v4.0                          ║
║     Multi-Format Extraction · YAML-Driven Language Profiles · Segmentation  ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # Corpus config selection
    cfg_input = input(
        f"Corpus config YAML [corpus_config.yaml]: "
    ).strip()
    corpus_config_path = cfg_input if cfg_input else "corpus_config.yaml"
    if cfg_input:
        reload_profiles(corpus_config_path)

    while True:
        input_str = input("Input directory: ").strip()
        if not input_str:
            print("Required.")
            continue
        input_dir = Path(input_str).expanduser().resolve()
        if not input_dir.exists():
            print(f"Not found: {input_dir}")
            continue
        break

    output_str = input("Output directory [output/]: ").strip()
    output_dir = Path(output_str if output_str else "output").expanduser().resolve()

    print("\nLanguage mode:")
    print("  [1] auto   — detect from directory/filename (recommended)")
    lang_options = {
        str(i + 2): (code, profile.name)
        for i, (code, profile) in enumerate(
            (k, v) for k, v in LANGUAGE_PROFILES.items() if k != "und"
        )
    }
    for num, (code, name) in sorted(lang_options.items()):
        print(f"  [{num}] {code}    — {name}")
    und_idx = len(lang_options) + 2
    print(f"  [{und_idx}] und    — Universal (no language-specific rules)")

    lang_choice = input("Select [1]: ").strip() or "1"
    if lang_choice == "1":
        language = "auto"
    elif lang_choice == str(und_idx):
        language = "und"
    else:
        language = lang_options.get(lang_choice, ("auto", ""))[0]

    print("\nPreset:")
    print("  [1] Minimal   [2] Standard (default)   [3] Aggressive   [4] Pristine")
    preset = input("Select [2]: ").strip() or "2"
    presets = {
        "1": UnifiedConfig.preset_minimal,
        "3": UnifiedConfig.preset_aggressive,
        "4": UnifiedConfig.preset_pristine,
    }
    config = presets.get(preset, UnifiedConfig.preset_standard)(language=language)
    config.corpus_config_file = corpus_config_path

    print(f"\nInput:       {input_dir}")
    print(f"Output:      {output_dir}")
    print(f"Language:    {language}")
    print(f"Config YAML: {corpus_config_path}")
    if input("Proceed? (y/n): ").strip().lower() != 'y':
        print("Cancelled.")
        return 0

    pipeline = ZambianCorpusBuilder(config)
    try:
        pipeline.process_directory(input_dir, output_dir)
        stats = pipeline.get_stats()
        print("\n" + str(stats))
        stats_file = output_dir / "processing_stats.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats.to_dict(), f, indent=2, default=str)
        print(f"\n✓ Stats saved: {stats_file}")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return 1


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    if len(sys.argv) > 1:
        parser = setup_argument_parser()
        args   = parser.parse_args()
        return run_batch_mode(args)
    return run_interactive_mode()


if __name__ == "__main__":
    sys.exit(main())
