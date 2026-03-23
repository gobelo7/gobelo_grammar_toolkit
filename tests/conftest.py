"""
tests/conftest.py
==================
Shared pytest fixtures available to all tests in this project.

Fixture scopes
--------------
``loader``          — module-scoped real chiTonga loader (full 4 236-line grammar)
``loader_minimal``  — session-scoped minimal chiTonga loader (fast: 4 NCs, 2 TAMs)
``loader_chibemba`` — session-scoped chibemba loader (for multi-language tests)
``flask_client``    — function-scoped Flask test client for backend route tests

All fixtures load from real files on disk — no mocking, no monkeypatching.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── path bootstrap ────────────────────────────────────────────────
_ROOT    = Path(__file__).resolve().parent.parent
_GGT     = _ROOT / "ggt"
_UPLOADS = Path("/mnt/user-data/uploads")

for p in (_GGT, _UPLOADS):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# ── grammar file locations ────────────────────────────────────────
_LANG_DIR     = _GGT / "gobelo_grammar_toolkit" / "languages"
_FIXTURE_DIR  = Path(__file__).parent / "fixtures"

_CHITONGA_FULL     = _LANG_DIR / "chitonga.yaml"
_CHITONGA_MINIMAL  = _FIXTURE_DIR / "minimal_chitonga.yaml"
_CHIBEMBA_STUB     = _FIXTURE_DIR / "stub_chibemba.yaml"


# ═══════════════════════════════════════════════════════════════════
#  LOADER FIXTURES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def loader_minimal():
    """
    Session-scoped loader backed by the minimal chiTonga fixture.

    Use this in unit tests that only need the loader API and don't
    require the full linguistic inventory.  Loads in < 50 ms.
    """
    from gobelo_grammar_toolkit.core.config import GrammarConfig
    from gobelo_grammar_toolkit.core.loader import GobeloGrammarLoader

    if not _CHITONGA_MINIMAL.exists():
        pytest.skip(f"Minimal fixture not found: {_CHITONGA_MINIMAL}")

    return GobeloGrammarLoader(
        GrammarConfig(language="chitonga", override_path=str(_CHITONGA_MINIMAL))
    )


@pytest.fixture(scope="module")
def loader():
    """
    Module-scoped loader backed by the full chiTonga grammar.

    Use this in integration tests that need the complete linguistic
    inventory (21 NCs, 8 TAMs, 18 concord types, 14 extensions).
    Loads in ~200 ms; shared across all tests in one module.
    """
    from gobelo_grammar_toolkit.core.config import GrammarConfig
    from gobelo_grammar_toolkit.core.loader import GobeloGrammarLoader

    if not _CHITONGA_FULL.exists():
        pytest.skip(f"Full chiTonga grammar not found: {_CHITONGA_FULL}")

    return GobeloGrammarLoader(
        GrammarConfig(language="chitonga", override_path=str(_CHITONGA_FULL))
    )


@pytest.fixture(scope="session")
def loader_chibemba():
    """
    Session-scoped loader backed by the chiBemba stub fixture.

    Use this in multi-language tests (FeatureComparator, cross-language
    API route tests).  NC1.prefix is 'u-' (vs chiTonga 'mu-').
    """
    from gobelo_grammar_toolkit.core.config import GrammarConfig
    from gobelo_grammar_toolkit.core.loader import GobeloGrammarLoader

    if not _CHIBEMBA_STUB.exists():
        pytest.skip(f"chiBemba fixture not found: {_CHIBEMBA_STUB}")

    return GobeloGrammarLoader(
        GrammarConfig(language="chibemba", override_path=str(_CHIBEMBA_STUB))
    )


# ═══════════════════════════════════════════════════════════════════
#  APP FIXTURES  (built on top of loader fixtures)
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def analyzer(loader):
    """Module-scoped MorphologicalAnalyzer for chiTonga."""
    from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphologicalAnalyzer
    return MorphologicalAnalyzer(loader)


@pytest.fixture(scope="module")
def paradigm_gen(loader):
    """Module-scoped ParadigmGenerator for chiTonga."""
    from gobelo_grammar_toolkit.apps.paradigm_generator import ParadigmGenerator
    return ParadigmGenerator(loader)


@pytest.fixture(scope="module")
def concord_gen(loader):
    """Module-scoped ConcordGenerator for chiTonga."""
    from gobelo_grammar_toolkit.apps.concord_generator import ConcordGenerator
    return ConcordGenerator(loader)


@pytest.fixture(scope="module")
def annotator(loader):
    """Module-scoped CorpusAnnotator for chiTonga."""
    from gobelo_grammar_toolkit.apps.corpus_annotator import CorpusAnnotator
    return CorpusAnnotator(loader)


@pytest.fixture(scope="module")
def ud_mapper(loader):
    """Module-scoped UDFeatureMapper for chiTonga."""
    from gobelo_grammar_toolkit.apps.ud_feature_mapper import UDFeatureMapper
    return UDFeatureMapper(loader)


@pytest.fixture(scope="module")
def slot_validator(loader):
    """Module-scoped VerbSlotValidator for chiTonga."""
    from gobelo_grammar_toolkit.apps.verb_slot_validator import VerbSlotValidator
    return VerbSlotValidator(loader)


@pytest.fixture(scope="module")
def feature_comparator(loader, loader_chibemba):
    """Module-scoped FeatureComparator with chiTonga + chiBemba."""
    from gobelo_grammar_toolkit.apps.feature_comparator import FeatureComparator
    return FeatureComparator({"chitonga": loader, "chibemba": loader_chibemba})


# ═══════════════════════════════════════════════════════════════════
#  FLASK TEST CLIENT
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def flask_client():
    """
    Module-scoped Flask test client for backend route tests.

    Uses the real Flask app from ``web/backend/app.py``.
    Does NOT start an actual server — uses Werkzeug's test client.
    """
    _BACKEND = _ROOT / "web" / "backend" / "app.py"
    _WEB_OUT = Path("/mnt/user-data/outputs/gobelo_web")

    # Try repo-layout path first, then outputs dir
    backend_path = _BACKEND if _BACKEND.exists() else _WEB_OUT / "app.py"
    if not backend_path.exists():
        pytest.skip(f"Backend app.py not found at {_BACKEND} or {_WEB_OUT}/app.py")

    backend_dir = str(backend_path.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    import importlib.util
    spec = importlib.util.spec_from_file_location("app", backend_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with module.app.test_client() as client:
        yield client


# ═══════════════════════════════════════════════════════════════════
#  HELPERS exposed as fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def assert_conllu_valid():
    """
    Fixture that returns a callable for validating CoNLL-U output.

    Usage::
        def test_something(annotator, assert_conllu_valid):
            result = annotator.annotate_text("Balya muntu.")
            conllu = annotator.to_conllu(result)
            assert_conllu_valid(conllu)
    """
    def _check(conllu: str) -> None:
        assert isinstance(conllu, str), "CoNLL-U output must be a string"
        assert "# sent_id" in conllu, "Missing sent_id comment"
        assert "# text" in conllu, "Missing text comment"
        data_rows = [l for l in conllu.splitlines() if l and not l.startswith("#")]
        assert data_rows, "No data rows in CoNLL-U output"
        for row in data_rows:
            cols = row.split("\t")
            assert len(cols) == 10, (
                f"Expected 10 CoNLL-U columns, got {len(cols)} in row: {row!r}"
            )
    return _check
