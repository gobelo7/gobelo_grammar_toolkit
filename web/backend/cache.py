"""
web/backend/cache.py — In-process cache and GGT service factories.

One loader/app instance per language is created on first use and reused.
Call init_cache(grammar_dir) once at startup (from app.py create_app).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional

from gobelo_grammar_toolkit.core.config      import GrammarConfig
from gobelo_grammar_toolkit.core.loader      import GobeloGrammarLoader
from gobelo_grammar_toolkit.core.registry    import list_languages, is_registered
from gobelo_grammar_toolkit.core.exceptions  import LanguageNotFoundError
from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphologicalAnalyzer
from gobelo_grammar_toolkit.apps.paradigm_generator     import ParadigmGenerator
from gobelo_grammar_toolkit.apps.concord_generator      import ConcordGenerator
from gobelo_grammar_toolkit.apps.corpus_annotator       import CorpusAnnotator
from gobelo_grammar_toolkit.apps.ud_feature_mapper      import UDFeatureMapper
from gobelo_grammar_toolkit.apps.verb_slot_validator    import VerbSlotValidator

_cache: Dict[str, Dict[str, Any]] = {}
_grammar_dir: Optional[Path] = None


def init_cache(grammar_dir: Optional[Path]) -> None:
    """Called once from create_app() to wire the grammar directory."""
    global _grammar_dir
    _grammar_dir = grammar_dir


def flush(lang: Optional[str] = None) -> None:
    """Evict one language or the entire cache (forces YAML reload on next request)."""
    if lang:
        _cache.pop(lang, None)
    else:
        _cache.clear()


def cache_status() -> Dict[str, Any]:
    """Return a snapshot of what is currently loaded — used by the admin routes."""
    return {
        lang: list(keys.keys())
        for lang, keys in _cache.items()
    }


# ── internal helpers ──────────────────────────────────────────────────

def _slot(lang: str, key: str, factory):
    _cache.setdefault(lang, {})
    if key not in _cache[lang]:
        _cache[lang][key] = factory()
    return _cache[lang][key]


def _override(lang: str) -> Optional[str]:
    """Return an override YAML path if the file exists, else None (use embedded data)."""
    if _grammar_dir is None:
        return None
    p = Path(_grammar_dir) / f"{lang}.yaml"
    return str(p) if p.exists() else None


# ── public service accessors ──────────────────────────────────────────

def get_loader(lang: str) -> GobeloGrammarLoader:
    def make():
        if not is_registered(lang):
            raise LanguageNotFoundError(language=lang, available_languages=list_languages())
        override = _override(lang)
        try:
            return GobeloGrammarLoader(GrammarConfig(language=lang, override_path=override))
        except FileNotFoundError:
            lang_dir = _grammar_dir or Path("gobelo_grammar_toolkit/languages")
            raise FileNotFoundError(
                f"Grammar YAML for '{lang}' not found.\n"
                f"Expected: {lang_dir}/{lang}.yaml\n\n"
                f"Fix: extract grammar_yaml_files.zip into {lang_dir}/"
            )
    return _slot(lang, "loader", make)


def get_analyzer(lang: str)  -> MorphologicalAnalyzer:
    return _slot(lang, "az", lambda: MorphologicalAnalyzer(get_loader(lang)))

def get_generator(lang: str) -> ParadigmGenerator:
    return _slot(lang, "pg", lambda: ParadigmGenerator(get_loader(lang)))

def get_cg(lang: str)        -> ConcordGenerator:
    return _slot(lang, "cg", lambda: ConcordGenerator(get_loader(lang)))

def get_annotator(lang: str) -> CorpusAnnotator:
    return _slot(lang, "ca", lambda: CorpusAnnotator(get_loader(lang)))

def get_mapper(lang: str)    -> UDFeatureMapper:
    return _slot(lang, "mp", lambda: UDFeatureMapper(get_loader(lang)))

def get_validator(lang: str) -> VerbSlotValidator:
    return _slot(lang, "vv", lambda: VerbSlotValidator(get_loader(lang)))
