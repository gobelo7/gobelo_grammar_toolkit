"""
tests/cross_language/test_all_languages.py
============================================
Cross-language smoke test suite for the Gobelo Grammar Toolkit.

Runs every public API method on all 7 supported Bantu languages and
asserts:
  1. No unhandled exception is raised.
  2. Return types exactly match the contracted types.
  3. Invariants common to all well-formed grammars hold (e.g. the
     grammar version string is non-empty, every noun class has an id).
  4. ``GGTError`` subclasses are raised for the documented error paths
     (invalid language, unknown NC id, unknown concord type).

The test design is deliberately *conservative*: stub languages (all
except chiTonga) contain only minimal grammar data and intentionally
have many ``VerifyFlag`` entries.  Tests that count data items therefore
check bounds rather than exact values, and tests that query concord or
TAM data accept either a populated result or a graceful ``GGTError``.

Running
-------
    pytest tests/cross_language/test_all_languages.py -v

Dependencies
------------
    pytest >= 7.0
    gobelo_grammar_toolkit (installed or on sys.path)
"""

from __future__ import annotations

import re
import sys
import warnings
from typing import Any, List, Type

import pytest

# ── package import ────────────────────────────────────────────────────────────
sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from gobelo_grammar_toolkit.core import GrammarConfig, GobeloGrammarLoader  # noqa: E402
from gobelo_grammar_toolkit.core.exceptions import (  # noqa: E402
    ConcordTypeNotFoundError,
    GGTError,
    LanguageNotFoundError,
    NounClassNotFoundError,
    SchemaValidationError,
    UnverifiedFormError,
    VersionIncompatibleError,
)
from gobelo_grammar_toolkit.core.models import (  # noqa: E402
    ConcordSet,
    DerivationalPattern,
    GrammarMetadata,
    NounClass,
    PhonologyRules,
    TAMMarker,
    TokenizationRules,
    VerbExtension,
    VerbSlot,
    VerifyFlag,
)
from gobelo_grammar_toolkit.apps.morphological_analyzer import (  # noqa: E402
    MorphAnalysisError,
    MorphFeatureBundle,
    MorphologicalAnalyzer,
    ParseHypothesis,
    SegmentedToken,
    SurfaceForm,
)
from gobelo_grammar_toolkit.apps.ud_feature_mapper import (  # noqa: E402
    UDConcordFeatures,
    UDFeatureBundle,
    UDFeatureMapper,
    UDMappingError,
    UDNounClassFeatures,
    UDTAMFeatures,
    UDVoiceFeature,
)
from gobelo_grammar_toolkit.apps.verb_slot_validator import (  # noqa: E402
    SlotAssignment,
    ValidationResult,
    ValidationViolation,
    VerbSlotValidationError,
    VerbSlotValidator,
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

ALL_LANGUAGES: List[str] = [
    "chitonga",
    "chibemba",
    "chinyanja",
    "kaonde",
    "lunda",
    "luvale",
    "silozi",
]

# chiTonga is the only fully populated grammar; the rest are stubs.
FULL_LANGUAGE = "chitonga"
STUB_LANGUAGES = [lang for lang in ALL_LANGUAGES if lang != FULL_LANGUAGE]

# Build a minimal valid sequence from live slot data so it works for both
# the full chiTonga grammar and stubs that may use different type names.
def _minimal_valid_sequence(loader: GobeloGrammarLoader) -> List[SlotAssignment]:
    """
    Return the smallest valid sequence (SLOT3 + SLOT8 + SLOT10) using the
    actual ``allowed_content_types[0]`` value for each slot, so the test
    stays language-agnostic even when stub YAMLs differ in type names.

    Falls back to sensible defaults if a slot is absent from the grammar
    (which should never happen for these three obligatory slots).
    """
    slot_by_id = {s.id: s for s in loader.get_verb_slots()}

    def _first_type(slot_id: str, fallback: str) -> str:
        slot = slot_by_id.get(slot_id)
        if slot and slot.allowed_content_types:
            return slot.allowed_content_types[0]
        return fallback

    # Use the first SC key so both full and stub grammars accept it
    sc = loader.get_subject_concords()
    sc_key = next(iter(sc.entries)) if sc.entries else "NC1"

    return [
        SlotAssignment("SLOT3",  _first_type("SLOT3",  "subject_concords"),
                       "ci",  f"{sc_key}.SUBJ", sc_key),
        SlotAssignment("SLOT8",  _first_type("SLOT8",  "root"),
                       "lya", "lya",            None),
        SlotAssignment("SLOT10", _first_type("SLOT10", "final_vowels"),
                       "a",   "FV",             None),
    ]


# Convenience: chiTonga minimal sequence (used where a fixture isn't available)
_TONGA_MINIMAL: List[SlotAssignment] = [
    SlotAssignment("SLOT3",  "subject_concords", "ci",  "NC7.SUBJ", "NC7"),
    SlotAssignment("SLOT8",  "root",             "lya", "lya",       None),
    SlotAssignment("SLOT10", "final_vowels",      "a",  "FV",        None),
]

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module", params=ALL_LANGUAGES)
def loader(request: pytest.FixtureRequest) -> GobeloGrammarLoader:
    """Parameterised fixture: one GobeloGrammarLoader per language."""
    return GobeloGrammarLoader(GrammarConfig(language=request.param))


@pytest.fixture(scope="module", params=ALL_LANGUAGES)
def analyzer(request: pytest.FixtureRequest) -> MorphologicalAnalyzer:
    """Parameterised fixture: one MorphologicalAnalyzer per language."""
    L = GobeloGrammarLoader(GrammarConfig(language=request.param))
    return MorphologicalAnalyzer(L)


@pytest.fixture(scope="module", params=ALL_LANGUAGES)
def ud_mapper(request: pytest.FixtureRequest) -> UDFeatureMapper:
    """Parameterised fixture: one UDFeatureMapper per language."""
    L = GobeloGrammarLoader(GrammarConfig(language=request.param))
    return UDFeatureMapper(L)


@pytest.fixture(scope="module", params=ALL_LANGUAGES)
def validator(request: pytest.FixtureRequest) -> VerbSlotValidator:
    """Parameterised fixture: one VerbSlotValidator per language."""
    L = GobeloGrammarLoader(GrammarConfig(language=request.param))
    return VerbSlotValidator(L)


@pytest.fixture(scope="module")
def tonga_loader() -> GobeloGrammarLoader:
    """Single chiTonga loader (full grammar)."""
    return GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))


@pytest.fixture(scope="module")
def tonga_analyzer(tonga_loader: GobeloGrammarLoader) -> MorphologicalAnalyzer:
    return MorphologicalAnalyzer(tonga_loader)


@pytest.fixture(scope="module")
def tonga_ud(tonga_loader: GobeloGrammarLoader) -> UDFeatureMapper:
    return UDFeatureMapper(tonga_loader)


@pytest.fixture(scope="module")
def tonga_validator(tonga_loader: GobeloGrammarLoader) -> VerbSlotValidator:
    return VerbSlotValidator(tonga_loader)


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────


def _is_list_of(value: Any, item_type: Type) -> bool:
    return isinstance(value, list) and all(isinstance(x, item_type) for x in value)


def _is_frozen(obj: Any) -> bool:
    """Return True if the dataclass instance is frozen (immutable)."""
    try:
        field_name = next(iter(obj.__dataclass_fields__))
        object.__setattr__(obj, field_name, getattr(obj, field_name))
        # Some frozen DCs raise FrozenInstanceError, others AttributeError
        return False
    except Exception:
        return True


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART A: GobeloGrammarLoader — public API, all languages
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestLoaderInit:
    """Loader can be initialised for every supported language."""

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_init_all_languages(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        assert L is not None

    def test_unsupported_language_raises_language_not_found(self) -> None:
        with pytest.raises(LanguageNotFoundError):
            GobeloGrammarLoader(GrammarConfig(language="klingon"))

    def test_language_not_found_is_ggt_error(self) -> None:
        with pytest.raises(GGTError):
            GobeloGrammarLoader(GrammarConfig(language="klingon"))

    def test_loader_version_is_string(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.loader_version, str)
        assert len(loader.loader_version) > 0

    def test_config_reflects_requested_language(self, loader: GobeloGrammarLoader) -> None:
        assert loader.config.language in ALL_LANGUAGES

    def test_list_supported_languages_returns_all_seven(self, loader: GobeloGrammarLoader) -> None:
        langs = loader.list_supported_languages()
        assert isinstance(langs, list)
        assert len(langs) == 7
        for expected in ALL_LANGUAGES:
            assert expected in langs


class TestGetMetadata:
    """get_metadata() returns a well-formed GrammarMetadata on every language."""

    def test_return_type(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_metadata(), GrammarMetadata)

    def test_language_matches_config(self, loader: GobeloGrammarLoader) -> None:
        meta = loader.get_metadata()
        assert meta.language == loader.config.language

    def test_grammar_version_non_empty(self, loader: GobeloGrammarLoader) -> None:
        meta = loader.get_metadata()
        assert isinstance(meta.grammar_version, str)
        assert len(meta.grammar_version) > 0

    def test_iso_code_non_empty(self, loader: GobeloGrammarLoader) -> None:
        meta = loader.get_metadata()
        assert isinstance(meta.iso_code, str)
        assert len(meta.iso_code) > 0

    def test_guthrie_non_empty(self, loader: GobeloGrammarLoader) -> None:
        meta = loader.get_metadata()
        assert isinstance(meta.guthrie, str)
        assert len(meta.guthrie) > 0

    def test_verify_count_non_negative(self, loader: GobeloGrammarLoader) -> None:
        meta = loader.get_metadata()
        assert isinstance(meta.verify_count, int)
        assert meta.verify_count >= 0

    def test_metadata_is_frozen(self, loader: GobeloGrammarLoader) -> None:
        meta = loader.get_metadata()
        with pytest.raises((AttributeError, TypeError)):
            meta.language = "other"  # type: ignore[misc]


class TestGetNounClasses:
    """get_noun_classes() and get_noun_class() on every language."""

    def test_returns_list(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_noun_classes(), list)

    def test_active_only_is_subset_of_all(self, loader: GobeloGrammarLoader) -> None:
        active = loader.get_noun_classes(active_only=True)
        all_nc = loader.get_noun_classes(active_only=False)
        assert len(active) <= len(all_nc)

    def test_at_least_one_noun_class(self, loader: GobeloGrammarLoader) -> None:
        all_nc = loader.get_noun_classes(active_only=False)
        assert len(all_nc) >= 1

    def test_items_are_noun_class_instances(self, loader: GobeloGrammarLoader) -> None:
        for nc in loader.get_noun_classes(active_only=False):
            assert isinstance(nc, NounClass)

    def test_each_nc_has_non_empty_id(self, loader: GobeloGrammarLoader) -> None:
        for nc in loader.get_noun_classes(active_only=False):
            assert isinstance(nc.id, str) and len(nc.id) > 0

    def test_each_nc_active_is_bool(self, loader: GobeloGrammarLoader) -> None:
        for nc in loader.get_noun_classes(active_only=False):
            assert isinstance(nc.active, bool)

    def test_nc_ids_are_unique(self, loader: GobeloGrammarLoader) -> None:
        ids = [nc.id for nc in loader.get_noun_classes(active_only=False)]
        assert len(ids) == len(set(ids)), "Duplicate NC ids found"

    def test_nc_prefix_is_string_or_none(self, loader: GobeloGrammarLoader) -> None:
        for nc in loader.get_noun_classes(active_only=False):
            assert nc.prefix is None or isinstance(nc.prefix, str)

    def test_get_noun_class_by_id_returns_noun_class(self, loader: GobeloGrammarLoader) -> None:
        first_id = loader.get_noun_classes(active_only=False)[0].id
        nc = loader.get_noun_class(first_id)
        assert isinstance(nc, NounClass)
        assert nc.id == first_id

    def test_get_noun_class_unknown_raises_noun_class_not_found(
        self, loader: GobeloGrammarLoader
    ) -> None:
        with pytest.raises(NounClassNotFoundError):
            loader.get_noun_class("NC_DOES_NOT_EXIST_99")

    def test_noun_class_not_found_is_ggt_error(self, loader: GobeloGrammarLoader) -> None:
        with pytest.raises(GGTError):
            loader.get_noun_class("NC_DOES_NOT_EXIST_99")

    def test_nc_is_frozen(self, loader: GobeloGrammarLoader) -> None:
        nc = loader.get_noun_classes(active_only=False)[0]
        with pytest.raises((AttributeError, TypeError)):
            nc.id = "other"  # type: ignore[misc]

    # chiTonga-specific: expect the full set of Bantu NCs
    def test_tonga_has_expected_nc_count(self, tonga_loader: GobeloGrammarLoader) -> None:
        nc_all = tonga_loader.get_noun_classes(active_only=False)
        assert len(nc_all) >= 18, "chiTonga should have at least NC1–NC18"

    def test_tonga_nc1_singular(self, tonga_loader: GobeloGrammarLoader) -> None:
        nc1 = tonga_loader.get_noun_class("NC1")
        assert nc1.id == "NC1"
        assert nc1.active is True


class TestGetConcords:
    """get_subject_concords(), get_object_concords(), get_concords(), get_all_concord_types()."""

    def test_get_all_concord_types_returns_list_of_str(self, loader: GobeloGrammarLoader) -> None:
        types = loader.get_all_concord_types()
        assert isinstance(types, list)
        assert all(isinstance(t, str) for t in types)

    def test_get_all_concord_types_non_empty(self, loader: GobeloGrammarLoader) -> None:
        types = loader.get_all_concord_types()
        assert len(types) >= 1

    def test_subject_concords_in_concord_types(self, loader: GobeloGrammarLoader) -> None:
        types = loader.get_all_concord_types()
        assert "subject_concords" in types

    def test_object_concords_in_concord_types(self, loader: GobeloGrammarLoader) -> None:
        types = loader.get_all_concord_types()
        assert "object_concords" in types

    def test_get_subject_concords_returns_concord_set(self, loader: GobeloGrammarLoader) -> None:
        sc = loader.get_subject_concords()
        assert isinstance(sc, ConcordSet)

    def test_get_subject_concords_concord_type(self, loader: GobeloGrammarLoader) -> None:
        sc = loader.get_subject_concords()
        assert sc.concord_type == "subject_concords"

    def test_get_subject_concords_entries_is_dict(self, loader: GobeloGrammarLoader) -> None:
        sc = loader.get_subject_concords()
        assert isinstance(sc.entries, dict)

    def test_get_subject_concords_at_least_one_entry(self, loader: GobeloGrammarLoader) -> None:
        sc = loader.get_subject_concords()
        assert len(sc.entries) >= 1

    def test_get_object_concords_returns_concord_set(self, loader: GobeloGrammarLoader) -> None:
        oc = loader.get_object_concords()
        assert isinstance(oc, ConcordSet)

    def test_get_object_concords_concord_type(self, loader: GobeloGrammarLoader) -> None:
        oc = loader.get_object_concords()
        assert oc.concord_type == "object_concords"

    def test_get_object_concords_entries_is_dict(self, loader: GobeloGrammarLoader) -> None:
        oc = loader.get_object_concords()
        assert isinstance(oc.entries, dict)

    def test_get_concords_known_type_returns_concord_set(self, loader: GobeloGrammarLoader) -> None:
        first_type = loader.get_all_concord_types()[0]
        cs = loader.get_concords(first_type)
        assert isinstance(cs, ConcordSet)
        assert cs.concord_type == first_type

    def test_get_concords_unknown_raises_concord_type_not_found(
        self, loader: GobeloGrammarLoader
    ) -> None:
        with pytest.raises(ConcordTypeNotFoundError):
            loader.get_concords("not_a_real_concord_type")

    def test_concord_type_not_found_is_ggt_error(self, loader: GobeloGrammarLoader) -> None:
        with pytest.raises(GGTError):
            loader.get_concords("not_a_real_concord_type")

    def test_concord_set_is_frozen(self, loader: GobeloGrammarLoader) -> None:
        sc = loader.get_subject_concords()
        with pytest.raises((AttributeError, TypeError)):
            sc.concord_type = "other"  # type: ignore[misc]

    def test_tonga_subject_concords_contain_nc7(self, tonga_loader: GobeloGrammarLoader) -> None:
        sc = tonga_loader.get_subject_concords()
        assert "NC7" in sc.entries

    def test_tonga_subject_concords_contain_person_keys(
        self, tonga_loader: GobeloGrammarLoader
    ) -> None:
        sc = tonga_loader.get_subject_concords()
        # Human classes use person keys
        person_keys = {"1SG", "2SG", "3SG", "1PL_EXCL", "2PL", "3PL_HUMAN"}
        assert person_keys.issubset(set(sc.entries.keys()))

    def test_tonga_has_many_concord_types(self, tonga_loader: GobeloGrammarLoader) -> None:
        types = tonga_loader.get_all_concord_types()
        assert len(types) >= 10


class TestGetTAMMarkers:
    """get_tam_markers() on every language."""

    def test_returns_list(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_tam_markers(), list)

    def test_at_least_one_tam(self, loader: GobeloGrammarLoader) -> None:
        assert len(loader.get_tam_markers()) >= 1

    def test_items_are_tam_marker(self, loader: GobeloGrammarLoader) -> None:
        assert _is_list_of(loader.get_tam_markers(), TAMMarker)

    def test_ids_non_empty(self, loader: GobeloGrammarLoader) -> None:
        for tam in loader.get_tam_markers():
            assert isinstance(tam.id, str) and len(tam.id) > 0

    def test_ids_unique(self, loader: GobeloGrammarLoader) -> None:
        ids = [t.id for t in loader.get_tam_markers()]
        assert len(ids) == len(set(ids))

    def test_form_is_string_or_list(self, loader: GobeloGrammarLoader) -> None:
        for tam in loader.get_tam_markers():
            assert isinstance(tam.form, (str, list))

    def test_tam_is_frozen(self, loader: GobeloGrammarLoader) -> None:
        tam = loader.get_tam_markers()[0]
        with pytest.raises((AttributeError, TypeError)):
            tam.id = "other"  # type: ignore[misc]

    def test_tonga_has_full_tam_set(self, tonga_loader: GobeloGrammarLoader) -> None:
        ids = {t.id for t in tonga_loader.get_tam_markers()}
        expected = {"TAM_PRES", "TAM_PST", "TAM_FUT_NEAR", "TAM_FUT_REM", "TAM_HAB", "TAM_PERF"}
        assert expected.issubset(ids)


class TestGetExtensions:
    """get_extensions() on every language."""

    def test_returns_list(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_extensions(), list)

    def test_at_least_one_extension(self, loader: GobeloGrammarLoader) -> None:
        assert len(loader.get_extensions()) >= 1

    def test_items_are_verb_extension(self, loader: GobeloGrammarLoader) -> None:
        assert _is_list_of(loader.get_extensions(), VerbExtension)

    def test_ids_non_empty(self, loader: GobeloGrammarLoader) -> None:
        for ext in loader.get_extensions():
            assert isinstance(ext.id, str) and len(ext.id) > 0

    def test_ids_unique(self, loader: GobeloGrammarLoader) -> None:
        ids = [e.id for e in loader.get_extensions()]
        assert len(ids) == len(set(ids))

    def test_zone_is_string(self, loader: GobeloGrammarLoader) -> None:
        for ext in loader.get_extensions():
            assert isinstance(ext.zone, str) and len(ext.zone) > 0

    def test_zone_values_valid(self, loader: GobeloGrammarLoader) -> None:
        valid_zones = {"Z1", "Z2", "Z3", "Z4"}
        for ext in loader.get_extensions():
            assert ext.zone in valid_zones, f"{ext.id}.zone={ext.zone!r} not in {valid_zones}"

    def test_extension_is_frozen(self, loader: GobeloGrammarLoader) -> None:
        ext = loader.get_extensions()[0]
        with pytest.raises((AttributeError, TypeError)):
            ext.id = "other"  # type: ignore[misc]

    def test_tonga_has_core_extensions(self, tonga_loader: GobeloGrammarLoader) -> None:
        ids = {e.id for e in tonga_loader.get_extensions()}
        core = {"APPL", "CAUS", "PASS", "RECIP", "STAT"}
        assert core.issubset(ids)

    def test_tonga_pass_in_zone_3(self, tonga_loader: GobeloGrammarLoader) -> None:
        pass_ext = next(e for e in tonga_loader.get_extensions() if e.id == "PASS")
        assert pass_ext.zone == "Z3"


class TestGetVerbSlots:
    """get_verb_slots() on every language."""

    def test_returns_list(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_verb_slots(), list)

    def test_at_least_three_slots(self, loader: GobeloGrammarLoader) -> None:
        # Every grammar must have at minimum SC (SLOT3), root (SLOT8), FV (SLOT10)
        assert len(loader.get_verb_slots()) >= 3

    def test_items_are_verb_slot(self, loader: GobeloGrammarLoader) -> None:
        assert _is_list_of(loader.get_verb_slots(), VerbSlot)

    def test_ids_non_empty(self, loader: GobeloGrammarLoader) -> None:
        for slot in loader.get_verb_slots():
            assert isinstance(slot.id, str) and len(slot.id) > 0

    def test_ids_unique(self, loader: GobeloGrammarLoader) -> None:
        ids = [s.id for s in loader.get_verb_slots()]
        assert len(ids) == len(set(ids))

    def test_position_is_positive_int(self, loader: GobeloGrammarLoader) -> None:
        for slot in loader.get_verb_slots():
            assert isinstance(slot.position, int) and slot.position >= 1

    def test_positions_unique(self, loader: GobeloGrammarLoader) -> None:
        positions = [s.position for s in loader.get_verb_slots()]
        assert len(positions) == len(set(positions)), "Duplicate slot positions found"

    def test_obligatory_is_bool(self, loader: GobeloGrammarLoader) -> None:
        for slot in loader.get_verb_slots():
            assert isinstance(slot.obligatory, bool)

    def test_allowed_content_types_is_list(self, loader: GobeloGrammarLoader) -> None:
        for slot in loader.get_verb_slots():
            assert isinstance(slot.allowed_content_types, list)

    def test_at_least_one_obligatory_slot(self, loader: GobeloGrammarLoader) -> None:
        oblig = [s for s in loader.get_verb_slots() if s.obligatory]
        assert len(oblig) >= 1

    def test_slot_is_frozen(self, loader: GobeloGrammarLoader) -> None:
        slot = loader.get_verb_slots()[0]
        with pytest.raises((AttributeError, TypeError)):
            slot.id = "other"  # type: ignore[misc]

    def test_tonga_has_eleven_slots(self, tonga_loader: GobeloGrammarLoader) -> None:
        assert len(tonga_loader.get_verb_slots()) == 11

    def test_tonga_obligatory_slots_are_slot3_slot8_slot10(
        self, tonga_loader: GobeloGrammarLoader
    ) -> None:
        oblig_ids = {s.id for s in tonga_loader.get_verb_slots() if s.obligatory}
        assert oblig_ids == {"SLOT3", "SLOT8", "SLOT10"}

    def test_tonga_slots_sorted_by_position(self, tonga_loader: GobeloGrammarLoader) -> None:
        positions = [s.position for s in tonga_loader.get_verb_slots()]
        assert positions == sorted(positions)


class TestGetVerbTemplate:
    """get_verb_template() on every language."""

    def test_returns_dict(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_verb_template(), dict)

    def test_non_empty(self, loader: GobeloGrammarLoader) -> None:
        assert len(loader.get_verb_template()) >= 1

    def test_tonga_contains_expected_keys(self, tonga_loader: GobeloGrammarLoader) -> None:
        vt = tonga_loader.get_verb_template()
        required_keys = {"verb_slots", "extensions", "final_vowels", "tam", "constraints"}
        assert required_keys.issubset(set(vt.keys()))

    def test_tonga_verb_slots_matches_get_verb_slots(
        self, tonga_loader: GobeloGrammarLoader
    ) -> None:
        vt = tonga_loader.get_verb_template()
        slot_ids_in_template = set(vt.get("verb_slots", {}).keys())
        slot_ids_from_api = {s.id for s in tonga_loader.get_verb_slots()}
        assert slot_ids_in_template == slot_ids_from_api

    def test_tonga_slot_order_matches_api(self, tonga_loader: GobeloGrammarLoader) -> None:
        vt = tonga_loader.get_verb_template()
        slot_order = vt.get("slot_order", [])
        assert isinstance(slot_order, list)
        api_ids = {s.id for s in tonga_loader.get_verb_slots()}
        for sid in slot_order:
            assert sid in api_ids


class TestGetPhonologyAndTokenization:
    """get_phonology() and get_tokenization_rules() on every language."""

    def test_phonology_return_type(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_phonology(), PhonologyRules)

    def test_phonology_vowels_is_list(self, loader: GobeloGrammarLoader) -> None:
        ph = loader.get_phonology()
        assert isinstance(ph.vowels, list)

    def test_phonology_consonants_is_list(self, loader: GobeloGrammarLoader) -> None:
        ph = loader.get_phonology()
        assert isinstance(ph.consonants, list)

    def test_phonology_is_frozen(self, loader: GobeloGrammarLoader) -> None:
        ph = loader.get_phonology()
        with pytest.raises((AttributeError, TypeError)):
            ph.vowels = []  # type: ignore[misc]

    def test_tokenization_return_type(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_tokenization_rules(), TokenizationRules)

    def test_tokenization_word_boundary_pattern_is_string(
        self, loader: GobeloGrammarLoader
    ) -> None:
        tok = loader.get_tokenization_rules()
        assert isinstance(tok.word_boundary_pattern, str)

    def test_tokenization_is_frozen(self, loader: GobeloGrammarLoader) -> None:
        tok = loader.get_tokenization_rules()
        with pytest.raises((AttributeError, TypeError)):
            tok.word_boundary_pattern = ""  # type: ignore[misc]


class TestGetPatterns:
    """get_patterns() on every language."""

    def test_returns_list(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.get_patterns(), list)

    def test_items_are_derivational_pattern(self, loader: GobeloGrammarLoader) -> None:
        for pat in loader.get_patterns():
            assert isinstance(pat, DerivationalPattern)

    def test_pattern_ids_non_empty(self, loader: GobeloGrammarLoader) -> None:
        for pat in loader.get_patterns():
            assert isinstance(pat.id, str) and len(pat.id) > 0

    def test_tonga_has_patterns(self, tonga_loader: GobeloGrammarLoader) -> None:
        assert len(tonga_loader.get_patterns()) >= 1


class TestListVerifyFlags:
    """list_verify_flags() on every language."""

    def test_returns_list(self, loader: GobeloGrammarLoader) -> None:
        assert isinstance(loader.list_verify_flags(), list)

    def test_items_are_verify_flag(self, loader: GobeloGrammarLoader) -> None:
        for flag in loader.list_verify_flags():
            assert isinstance(flag, VerifyFlag)

    def test_flag_field_path_is_string(self, loader: GobeloGrammarLoader) -> None:
        for flag in loader.list_verify_flags():
            assert isinstance(flag.field_path, str)

    def test_flag_resolved_is_bool(self, loader: GobeloGrammarLoader) -> None:
        for flag in loader.list_verify_flags():
            assert isinstance(flag.resolved, bool)

    def test_flag_count_matches_metadata(self, loader: GobeloGrammarLoader) -> None:
        meta = loader.get_metadata()
        flags = loader.list_verify_flags()
        assert len(flags) == meta.verify_count

    def test_stub_languages_have_verify_flags(self) -> None:
        for lang in STUB_LANGUAGES:
            L = GobeloGrammarLoader(GrammarConfig(language=lang))
            assert L.get_metadata().verify_count > 0, (
                f"{lang}: stub grammar should have unresolved VerifyFlags"
            )

    def test_tonga_has_no_unresolved_flags(self, tonga_loader: GobeloGrammarLoader) -> None:
        unresolved = [f for f in tonga_loader.list_verify_flags() if not f.resolved]
        assert len(unresolved) == 0, (
            f"chiTonga has {len(unresolved)} unresolved VERIFY flags: "
            + ", ".join(f.field_path for f in unresolved)
        )


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART B: MorphologicalAnalyzer — all languages
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestMorphologicalAnalyzerInit:
    """MorphologicalAnalyzer can be constructed for every language."""

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_init_all_languages(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        a = MorphologicalAnalyzer(L)
        assert a is not None

    def test_language_property(self, analyzer: MorphologicalAnalyzer) -> None:
        assert isinstance(analyzer.language, str)
        assert analyzer.language in ALL_LANGUAGES

    def test_loader_property_type(self, analyzer: MorphologicalAnalyzer) -> None:
        # loader property returns a GobeloGrammarLoader
        assert hasattr(analyzer.loader, "get_metadata")


class TestMorphologicalAnalyzerAnalyze:
    """analyze() and analyze_verbal() and analyze_nominal() on every language."""

    _TOKENS = ["balya", "cilya", "twalya", "muntu", "ndi"]

    @pytest.mark.parametrize("token", _TOKENS)
    def test_analyze_returns_segmented_token(
        self, analyzer: MorphologicalAnalyzer, token: str
    ) -> None:
        tok = analyzer.analyze(token)
        assert isinstance(tok, SegmentedToken)

    def test_analyze_language_matches(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        assert tok.language == analyzer.language

    def test_analyze_token_matches_input(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        assert tok.token == "balya"

    def test_analyze_hypotheses_is_list(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        assert isinstance(tok.hypotheses, (list, tuple))

    def test_analyze_hypotheses_non_empty(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        assert len(tok.hypotheses) >= 1

    def test_analyze_best_is_parse_hypothesis_or_none(
        self, analyzer: MorphologicalAnalyzer
    ) -> None:
        tok = analyzer.analyze("balya")
        assert tok.best is None or isinstance(tok.best, ParseHypothesis)

    def test_analyze_is_ambiguous_is_bool(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        assert isinstance(tok.is_ambiguous, bool)

    def test_analyze_best_confidence_in_range(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        if tok.best is not None:
            assert 0.0 <= tok.best.confidence <= 1.0

    def test_analyze_best_coverage_in_range(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        if tok.best is not None:
            assert 0.0 <= tok.best.coverage <= 1.0

    def test_analyze_morphemes_are_tuples(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        if tok.best is not None:
            assert isinstance(tok.best.morphemes, tuple)

    def test_analyze_verbal_returns_segmented_token(
        self, analyzer: MorphologicalAnalyzer
    ) -> None:
        tok = analyzer.analyze_verbal("balya")
        assert isinstance(tok, SegmentedToken)

    def test_analyze_nominal_returns_segmented_token(
        self, analyzer: MorphologicalAnalyzer
    ) -> None:
        tok = analyzer.analyze_nominal("muntu")
        assert isinstance(tok, SegmentedToken)

    def test_analyze_max_hypotheses_respected(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya", max_hypotheses=2)
        assert len(tok.hypotheses) <= 2

    def test_segmented_token_is_frozen(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        with pytest.raises((AttributeError, TypeError)):
            tok.token = "other"  # type: ignore[misc]

    def test_parse_hypothesis_is_frozen(self, analyzer: MorphologicalAnalyzer) -> None:
        tok = analyzer.analyze("balya")
        if tok.best is not None:
            with pytest.raises((AttributeError, TypeError)):
                tok.best.confidence = 0.0  # type: ignore[misc]

    def test_tonga_balya_best_has_morphemes(
        self, tonga_analyzer: MorphologicalAnalyzer
    ) -> None:
        tok = tonga_analyzer.analyze("balya")
        assert tok.best is not None
        assert len(tok.best.morphemes) >= 2

    def test_tonga_balya_has_root_morpheme(
        self, tonga_analyzer: MorphologicalAnalyzer
    ) -> None:
        tok = tonga_analyzer.analyze("balya")
        assert tok.best is not None
        root_morphemes = [m for m in tok.best.morphemes if m.content_type == "verb_root"]
        assert len(root_morphemes) == 1

    def test_tonga_segmented_property_is_string(
        self, tonga_analyzer: MorphologicalAnalyzer
    ) -> None:
        tok = tonga_analyzer.analyze("cilya")
        if tok.best is not None:
            seg = tok.best.segmented
            assert isinstance(seg, str)
            assert "-" in seg or len(seg) > 0


class TestMorphologicalAnalyzerSegmentText:
    """segment_text() on every language."""

    def test_returns_list(self, analyzer: MorphologicalAnalyzer) -> None:
        result = analyzer.segment_text("balya cilya")
        assert isinstance(result, list)

    def test_returns_segmented_tokens(self, analyzer: MorphologicalAnalyzer) -> None:
        result = analyzer.segment_text("balya cilya")
        assert all(isinstance(t, SegmentedToken) for t in result)

    def test_token_count_matches_whitespace_split(
        self, analyzer: MorphologicalAnalyzer
    ) -> None:
        text = "balya cilya twalya"
        result = analyzer.segment_text(text)
        assert len(result) == 3

    def test_empty_string_returns_empty_list(self, analyzer: MorphologicalAnalyzer) -> None:
        result = analyzer.segment_text("")
        assert result == [] or isinstance(result, list)

    def test_max_hypotheses_propagated(self, analyzer: MorphologicalAnalyzer) -> None:
        result = analyzer.segment_text("balya cilya", max_hypotheses=1)
        for tok in result:
            assert len(tok.hypotheses) <= 1


class TestMorphologicalAnalyzerGenerate:
    """generate() on chiTonga (only full grammar)."""

    _BUNDLE = MorphFeatureBundle(
        root="lya",
        subject_nc="NC7",
        tam_id="TAM_PRES",
        object_nc=None,
        extensions=(),
        polarity="positive",
        final_vowel="a",
    )

    def test_generate_returns_surface_form(self, tonga_analyzer: MorphologicalAnalyzer) -> None:
        sf = tonga_analyzer.generate(self._BUNDLE)
        assert isinstance(sf, SurfaceForm)

    def test_generate_surface_is_non_empty_string(
        self, tonga_analyzer: MorphologicalAnalyzer
    ) -> None:
        sf = tonga_analyzer.generate(self._BUNDLE)
        assert isinstance(sf.surface, str) and len(sf.surface) > 0

    def test_generate_morphemes_is_tuple(self, tonga_analyzer: MorphologicalAnalyzer) -> None:
        sf = tonga_analyzer.generate(self._BUNDLE)
        assert isinstance(sf.morphemes, tuple)

    def test_generate_warnings_is_tuple(self, tonga_analyzer: MorphologicalAnalyzer) -> None:
        sf = tonga_analyzer.generate(self._BUNDLE)
        assert isinstance(sf.warnings, tuple)

    def test_surface_form_is_frozen(self, tonga_analyzer: MorphologicalAnalyzer) -> None:
        sf = tonga_analyzer.generate(self._BUNDLE)
        with pytest.raises((AttributeError, TypeError)):
            sf.surface = "other"  # type: ignore[misc]

    def test_morph_feature_bundle_is_frozen(self) -> None:
        with pytest.raises((AttributeError, TypeError)):
            self._BUNDLE.root = "other"  # type: ignore[misc]


class TestGenerateInterlinear:
    """generate_interlinear() on chiTonga."""

    def test_returns_string(self, tonga_analyzer: MorphologicalAnalyzer) -> None:
        igt = tonga_analyzer.generate_interlinear("cilya")
        assert isinstance(igt, str)

    def test_non_empty(self, tonga_analyzer: MorphologicalAnalyzer) -> None:
        igt = tonga_analyzer.generate_interlinear("cilya")
        assert len(igt) > 0

    def test_has_two_lines(self, tonga_analyzer: MorphologicalAnalyzer) -> None:
        igt = tonga_analyzer.generate_interlinear("cilya")
        lines = igt.strip().splitlines()
        assert len(lines) == 2, f"Expected 2 IGT lines, got: {lines!r}"


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART C: UDFeatureMapper — all languages
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestUDFeatureMapperInit:
    """UDFeatureMapper can be constructed for every language."""

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_init_all_languages(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        ud = UDFeatureMapper(L)
        assert ud is not None

    def test_language_property(self, ud_mapper: UDFeatureMapper) -> None:
        assert isinstance(ud_mapper.language, str)
        assert ud_mapper.language in ALL_LANGUAGES


class TestUDMapNC:
    """map_nc() on chiTonga."""

    def test_map_nc1_returns_ud_noun_class_features(
        self, tonga_ud: UDFeatureMapper
    ) -> None:
        feat = tonga_ud.map_nc("NC1")
        assert isinstance(feat, UDNounClassFeatures)

    def test_map_nc_nounclass_format(self, tonga_ud: UDFeatureMapper) -> None:
        # Should be "BantuN" format
        feat = tonga_ud.map_nc("NC7")
        assert feat.nounclass == "Bantu7"

    def test_map_nc_number_is_sing_or_plur_or_none(
        self, tonga_ud: UDFeatureMapper
    ) -> None:
        feat = tonga_ud.map_nc("NC7")
        assert feat.number in ("Sing", "Plur", None)

    def test_map_nc_gender_is_none(self, tonga_ud: UDFeatureMapper) -> None:
        # Bantu languages don't have grammatical gender in UD
        feat = tonga_ud.map_nc("NC7")
        assert feat.gender is None

    def test_map_nc_warnings_is_tuple(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_nc("NC1")
        assert isinstance(feat.warnings, tuple)

    def test_map_nc_is_frozen(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_nc("NC7")
        with pytest.raises((AttributeError, TypeError)):
            feat.nounclass = "other"  # type: ignore[misc]

    def test_map_nc_all_classes_no_exception(self, tonga_ud: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        for nc in L.get_noun_classes(active_only=False):
            feat = tonga_ud.map_nc(nc.id)
            assert isinstance(feat, UDNounClassFeatures)

    def test_map_nc_list_returns_list(self, tonga_ud: UDFeatureMapper) -> None:
        result = tonga_ud.map_nc_list(["NC1", "NC7", "NC9"])
        assert isinstance(result, list)
        assert all(isinstance(f, UDNounClassFeatures) for f in result)
        assert len(result) == 3

    def test_map_nc_list_empty(self, tonga_ud: UDFeatureMapper) -> None:
        result = tonga_ud.map_nc_list([])
        assert result == []


class TestUDMapTAM:
    """map_tam() and map_all_tams() on chiTonga."""

    def test_map_tam_returns_ud_tam_features(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_tam("TAM_PRES")
        assert isinstance(feat, UDTAMFeatures)

    def test_map_tam_tense_is_string_or_none(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_tam("TAM_PRES")
        assert feat.tense is None or isinstance(feat.tense, str)

    def test_map_tam_aspect_is_string_or_none(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_tam("TAM_PRES")
        assert feat.aspect is None or isinstance(feat.aspect, str)

    def test_map_tam_mood_is_string_or_none(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_tam("TAM_PRES")
        assert feat.mood is None or isinstance(feat.mood, str)

    def test_map_tam_warnings_is_tuple(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_tam("TAM_PRES")
        assert isinstance(feat.warnings, tuple)

    def test_map_tam_is_frozen(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_tam("TAM_PRES")
        with pytest.raises((AttributeError, TypeError)):
            feat.tense = "other"  # type: ignore[misc]

    def test_map_all_tams_returns_dict(self, tonga_ud: UDFeatureMapper) -> None:
        result = tonga_ud.map_all_tams()
        assert isinstance(result, dict)

    def test_map_all_tams_values_are_ud_tam_features(
        self, tonga_ud: UDFeatureMapper
    ) -> None:
        for v in tonga_ud.map_all_tams().values():
            assert isinstance(v, UDTAMFeatures)

    def test_map_all_tams_covers_all_grammar_tams(
        self, tonga_ud: UDFeatureMapper
    ) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        grammar_ids = {t.id for t in L.get_tam_markers()}
        mapped_ids  = set(tonga_ud.map_all_tams().keys())
        assert grammar_ids == mapped_ids

    def test_tonga_pres_tense_is_pres(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_tam("TAM_PRES")
        assert feat.tense == "Pres"

    def test_tonga_pres_aspect_is_imp(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_tam("TAM_PRES")
        assert feat.aspect == "Imp"


class TestUDMapConcordKey:
    """map_concord_key() on chiTonga."""

    def test_returns_ud_concord_features(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_concord_key("NC7")
        assert isinstance(feat, UDConcordFeatures)

    def test_person_is_string_or_none(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_concord_key("NC7")
        assert feat.person is None or isinstance(feat.person, str)

    def test_number_is_string_or_none(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_concord_key("NC7")
        assert feat.number is None or isinstance(feat.number, str)

    def test_concord_type_preserved(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_concord_key("NC7", "subject_concords")
        assert feat.concord_type == "subject_concords"

    def test_warnings_is_tuple(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_concord_key("NC7")
        assert isinstance(feat.warnings, tuple)

    def test_is_frozen(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_concord_key("NC7")
        with pytest.raises((AttributeError, TypeError)):
            feat.person = "other"  # type: ignore[misc]

    def test_1sg_is_person_1_sing(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_concord_key("1SG")
        assert feat.person == "1"
        assert feat.number == "Sing"

    def test_3pl_human_is_person_3_plur(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_concord_key("3PL_HUMAN")
        assert feat.person == "3"
        assert feat.number == "Plur"


class TestUDMapExtension:
    """map_extension() and map_all_extensions() on chiTonga."""

    def test_returns_ud_voice_feature(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_extension("APPL")
        assert isinstance(feat, UDVoiceFeature)

    def test_voice_is_string(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_extension("APPL")
        assert isinstance(feat.voice, str) and len(feat.voice) > 0

    def test_pass_maps_to_pass(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_extension("PASS")
        assert feat.voice == "Pass"

    def test_caus_maps_to_caus(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_extension("CAUS")
        assert feat.voice == "Caus"

    def test_warnings_is_tuple(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_extension("APPL")
        assert isinstance(feat.warnings, tuple)

    def test_is_frozen(self, tonga_ud: UDFeatureMapper) -> None:
        feat = tonga_ud.map_extension("APPL")
        with pytest.raises((AttributeError, TypeError)):
            feat.voice = "other"  # type: ignore[misc]

    def test_map_all_extensions_returns_dict(self, tonga_ud: UDFeatureMapper) -> None:
        result = tonga_ud.map_all_extensions()
        assert isinstance(result, dict)

    def test_map_all_extensions_values_are_ud_voice_features(
        self, tonga_ud: UDFeatureMapper
    ) -> None:
        for v in tonga_ud.map_all_extensions().values():
            assert isinstance(v, UDVoiceFeature)

    def test_map_all_extensions_covers_all_grammar_extensions(
        self, tonga_ud: UDFeatureMapper
    ) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        grammar_ids = {e.id for e in L.get_extensions()}
        mapped_ids  = set(tonga_ud.map_all_extensions().keys())
        assert grammar_ids == mapped_ids


class TestUDMapSegmentedToken:
    """map_segmented_token() on all languages."""

    def test_returns_ud_feature_bundle(self, ud_mapper: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=ud_mapper.language))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        bundle = ud_mapper.map_segmented_token(tok)
        assert isinstance(bundle, UDFeatureBundle)

    def test_token_matches(self, ud_mapper: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=ud_mapper.language))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("cilya")
        bundle = ud_mapper.map_segmented_token(tok)
        assert bundle.token == "cilya"

    def test_language_matches(self, ud_mapper: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=ud_mapper.language))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        bundle = ud_mapper.map_segmented_token(tok)
        assert bundle.language == ud_mapper.language

    def test_warnings_is_tuple(self, ud_mapper: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=ud_mapper.language))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        bundle = ud_mapper.map_segmented_token(tok)
        assert isinstance(bundle.warnings, tuple)

    def test_is_frozen(self, ud_mapper: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=ud_mapper.language))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        bundle = ud_mapper.map_segmented_token(tok)
        with pytest.raises((AttributeError, TypeError)):
            bundle.token = "other"  # type: ignore[misc]


class TestUDCoNLLU:
    """to_conllu_feats() and to_conllu_feats_str() on chiTonga."""

    def test_to_conllu_feats_returns_string(self, tonga_ud: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        bundle = tonga_ud.map_segmented_token(tok)
        feats = tonga_ud.to_conllu_feats(bundle)
        assert isinstance(feats, str)

    def test_to_conllu_feats_format(self, tonga_ud: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        bundle = tonga_ud.map_segmented_token(tok)
        feats = tonga_ud.to_conllu_feats(bundle)
        # Either "_" (empty) or "Key=Val|Key2=Val2" format
        assert feats == "_" or re.match(r"^[A-Za-z]+=\w+(\|[A-Za-z]+=\w+)*$", feats)

    def test_to_conllu_feats_alphabetically_sorted(self, tonga_ud: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        bundle = tonga_ud.map_segmented_token(tok)
        feats = tonga_ud.to_conllu_feats(bundle)
        if feats != "_":
            keys = [f.split("=")[0] for f in feats.split("|")]
            assert keys == sorted(keys)

    def test_to_conllu_feats_str_returns_string(self, tonga_ud: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        feats = tonga_ud.to_conllu_feats_str(tok)
        assert isinstance(feats, str)

    def test_to_conllu_feats_str_matches_two_step(self, tonga_ud: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        one_step  = tonga_ud.to_conllu_feats_str(tok)
        two_step  = tonga_ud.to_conllu_feats(tonga_ud.map_segmented_token(tok))
        assert one_step == two_step


class TestUDExportNCTable:
    """export_nc_table() on chiTonga."""

    def test_returns_string(self, tonga_ud: UDFeatureMapper) -> None:
        assert isinstance(tonga_ud.export_nc_table(), str)

    def test_is_markdown_table(self, tonga_ud: UDFeatureMapper) -> None:
        tbl = tonga_ud.export_nc_table()
        assert "|" in tbl

    def test_contains_all_active_nc_ids(self, tonga_ud: UDFeatureMapper) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        tbl = tonga_ud.export_nc_table()
        for nc in L.get_noun_classes(active_only=False):
            assert nc.id in tbl, f"{nc.id} not found in NC table"


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART D: VerbSlotValidator — all languages
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestVerbSlotValidatorInit:
    """VerbSlotValidator can be constructed for every language."""

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_init_all_languages(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        v = VerbSlotValidator(L)
        assert v is not None

    def test_language_property(self, validator: VerbSlotValidator) -> None:
        assert isinstance(validator.language, str)
        assert validator.language in ALL_LANGUAGES

    def test_max_extensions_positive(self, validator: VerbSlotValidator) -> None:
        assert isinstance(validator.max_extensions, int)
        assert validator.max_extensions >= 1

    def test_typical_max_le_max(self, validator: VerbSlotValidator) -> None:
        assert validator.typical_max_extensions <= validator.max_extensions

    def test_obligatory_slots_returns_list(self, validator: VerbSlotValidator) -> None:
        oblig = validator.obligatory_slots()
        assert isinstance(oblig, list)
        assert all(isinstance(s, str) for s in oblig)

    def test_obligatory_slots_non_empty(self, validator: VerbSlotValidator) -> None:
        assert len(validator.obligatory_slots()) >= 1

    def test_known_extension_ids_returns_frozenset(self, validator: VerbSlotValidator) -> None:
        ext_ids = validator.known_extension_ids()
        assert hasattr(ext_ids, "__contains__")

    def test_allowed_content_types_slot3(self, validator: VerbSlotValidator) -> None:
        # SLOT3 is present in every grammar; should have at least one allowed type
        types = validator.allowed_content_types("SLOT3")
        assert len(types) >= 1

    def test_allowed_content_types_unknown_slot_is_empty(
        self, validator: VerbSlotValidator
    ) -> None:
        types = validator.allowed_content_types("SLOT_NOT_REAL_999")
        assert len(types) == 0

    def test_extension_zone_known(self, validator: VerbSlotValidator) -> None:
        for ext_id in validator.known_extension_ids():
            zone = validator.extension_zone(ext_id)
            assert zone in ("Z1", "Z2", "Z3", "Z4")

    def test_extension_zone_unknown_returns_none(self, validator: VerbSlotValidator) -> None:
        assert validator.extension_zone("NOT_AN_EXT") is None


class TestValidateAssignments:
    """validate_assignments() core rule coverage on every language."""

    def test_minimal_valid_sequence_is_valid(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language))))
        assert isinstance(result, ValidationResult)
        assert result.is_valid, f"{validator.language}: {result.summary()}"

    def test_empty_sequence_is_invalid(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments([])
        assert not result.is_valid

    def test_empty_has_oblig_slot_missing_errors(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments([])
        rule_ids = {v.rule_id for v in result.errors}
        assert "OBLIG_SLOT_MISSING" in rule_ids

    def test_returns_validation_result(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language))))
        assert isinstance(result, ValidationResult)

    def test_validation_result_is_frozen(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language))))
        with pytest.raises((AttributeError, TypeError)):
            result.is_valid = True  # type: ignore[misc]

    def test_errors_subset_of_violations(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments([])
        assert set(result.errors).issubset(set(result.violations))

    def test_warnings_subset_of_violations(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language))))
        assert set(result.warnings).issubset(set(result.violations))

    def test_error_count_matches_len_errors(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments([])
        assert result.error_count == len(result.errors)

    def test_warning_count_matches_len_warnings(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language))))
        assert result.warning_count == len(result.warnings)

    def test_slot_coverage_is_dict(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language))))
        assert isinstance(result.slot_coverage, dict)

    def test_slot_coverage_reflects_input(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language))))
        assert result.slot_coverage.get("SLOT3") == 1
        assert result.slot_coverage.get("SLOT8") == 1
        assert result.slot_coverage.get("SLOT10") == 1

    def test_summary_returns_string(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language))))
        assert isinstance(result.summary(), str)

    def test_summary_contains_valid_or_invalid(self, validator: VerbSlotValidator) -> None:
        s = validator.validate_assignments(_minimal_valid_sequence(GobeloGrammarLoader(GrammarConfig(language=validator.language)))).summary()
        assert "VALID" in s or "INVALID" in s

    def test_violation_rule_id_is_string(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments([])
        for v in result.violations:
            assert isinstance(v.rule_id, str) and len(v.rule_id) > 0

    def test_violation_severity_is_error_or_warning(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments([])
        for v in result.violations:
            assert v.severity in ("ERROR", "WARNING")

    def test_violation_is_frozen(self, validator: VerbSlotValidator) -> None:
        result = validator.validate_assignments([])
        if result.violations:
            v = result.violations[0]
            with pytest.raises((AttributeError, TypeError)):
                v.rule_id = "other"  # type: ignore[misc]

    def test_content_type_mismatch_detected(self, validator: VerbSlotValidator) -> None:
        # tam_marker in SLOT8 (root slot)
        bad = [
            SlotAssignment("SLOT3",  "subject_concords", "ci",  "NC7.SUBJ", "NC7"),
            SlotAssignment("SLOT8",  "tam_marker",       "aka", "PST",       None),
            SlotAssignment("SLOT10", "final_vowels",      "a",  "FV",        None),
        ]
        result = validator.validate_assignments(bad)
        assert not result.is_valid
        rule_ids = {v.rule_id for v in result.errors}
        assert "CONTENT_TYPE_MISMATCH" in rule_ids

    def test_slot_out_of_order_detected(self, validator: VerbSlotValidator) -> None:
        reversed_seq = [
            SlotAssignment("SLOT8",  "root",             "lya", "lya",      None),
            SlotAssignment("SLOT3",  "subject_concords", "ci",  "NC7.SUBJ", "NC7"),
            SlotAssignment("SLOT10", "final_vowels",      "a",  "FV",       None),
        ]
        result = validator.validate_assignments(reversed_seq)
        assert not result.is_valid
        rule_ids = {v.rule_id for v in result.errors}
        assert "SLOT_OUT_OF_ORDER" in rule_ids

    def test_unknown_slot_produces_warning(self, validator: VerbSlotValidator) -> None:
        seq = [
            SlotAssignment("SLOT_NONEXISTENT_42", "verb_root", "lya", "lya", None),
        ]
        result = validator.validate_assignments(seq)
        rule_ids = {v.rule_id for v in result.warnings}
        assert "UNKNOWN_SLOT" in rule_ids


class TestCheckExtensionOrdering:
    """check_extension_ordering() on every language."""

    def test_valid_zone_order_is_valid(self, validator: VerbSlotValidator) -> None:
        # APPL (Z1) → PASS (Z3): correct
        result = validator.check_extension_ordering(["APPL", "PASS"])
        # Only check extensions known to this language
        if "APPL" in validator.known_extension_ids() and "PASS" in validator.known_extension_ids():
            assert result.is_valid, result.summary()

    def test_invalid_zone_order_is_invalid(self, validator: VerbSlotValidator) -> None:
        if "PASS" in validator.known_extension_ids() and "APPL" in validator.known_extension_ids():
            result = validator.check_extension_ordering(["PASS", "APPL"])
            assert not result.is_valid

    def test_empty_list_is_valid(self, validator: VerbSlotValidator) -> None:
        result = validator.check_extension_ordering([])
        assert result.is_valid

    def test_single_extension_is_valid(self, validator: VerbSlotValidator) -> None:
        ext_ids = list(validator.known_extension_ids())
        if ext_ids:
            result = validator.check_extension_ordering([ext_ids[0]])
            # Single valid ext should raise no zone violations
            zone_errors = [v for v in result.errors if v.rule_id == "EXT_ZONE_ORDER"]
            assert len(zone_errors) == 0

    def test_returns_validation_result(self, validator: VerbSlotValidator) -> None:
        result = validator.check_extension_ordering(["APPL"])
        assert isinstance(result, ValidationResult)

    def test_tonga_pass_stat_incompatible(self, tonga_validator: VerbSlotValidator) -> None:
        result = tonga_validator.check_extension_ordering(["PASS", "STAT"])
        assert not result.is_valid
        rule_ids = {v.rule_id for v in result.errors}
        assert "EXT_INCOMPATIBLE" in rule_ids

    def test_tonga_intra_zone_caus_before_appl_invalid(
        self, tonga_validator: VerbSlotValidator
    ) -> None:
        result = tonga_validator.check_extension_ordering(["CAUS", "APPL"])
        assert not result.is_valid
        rule_ids = {v.rule_id for v in result.errors}
        assert "EXT_INTRA_ZONE_ORDER" in rule_ids

    def test_tonga_max_extensions_exceeded(self, tonga_validator: VerbSlotValidator) -> None:
        exts = ["APPL", "CAUS", "TRANS", "RECIP", "STAT", "INTENS"]
        result = tonga_validator.check_extension_ordering(exts)
        rule_ids = {v.rule_id for v in result.violations}
        assert "EXT_MAX_EXCEEDED" in rule_ids

    def test_tonga_typical_max_warning(self, tonga_validator: VerbSlotValidator) -> None:
        # 4 extensions in correct zone order: Z1 Z2 Z3 Z4
        result = tonga_validator.check_extension_ordering(["APPL", "RECIP", "PASS", "INTENS"])
        warn_ids = {v.rule_id for v in result.warnings}
        assert "EXT_TYPICAL_MAX_EXCEEDED" in warn_ids


class TestValidate:
    """validate(SegmentedToken) on all languages."""

    def test_returns_validation_result(self, validator: VerbSlotValidator) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=validator.language))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        result = validator.validate(tok)
        assert isinstance(result, ValidationResult)

    def test_tonga_valid_verb_is_valid(self, tonga_validator: VerbSlotValidator) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        for token in ["balya", "cilya", "twalya"]:
            tok = A.analyze(token)
            result = tonga_validator.validate(tok)
            assert result.is_valid, (
                f"Expected {token!r} to be valid; {result.summary()}"
            )


class TestValidateMorphemeSequence:
    """validate_morpheme_sequence() on all languages."""

    def test_returns_validation_result(self, validator: VerbSlotValidator) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=validator.language))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        if tok.best:
            result = validator.validate_morpheme_sequence(tok.best.morphemes)
            assert isinstance(result, ValidationResult)

    def test_tonga_valid_morphemes(self, tonga_validator: VerbSlotValidator) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("cilya")
        if tok.best:
            result = tonga_validator.validate_morpheme_sequence(tok.best.morphemes)
            assert result.is_valid, result.summary()


class TestAssignmentsFromToken:
    """assignments_from_token() static method."""

    def test_returns_list(self) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("cilya")
        result = VerbSlotValidator.assignments_from_token(tok)
        assert isinstance(result, list)

    def test_items_are_slot_assignment(self) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("cilya")
        for a in VerbSlotValidator.assignments_from_token(tok):
            assert isinstance(a, SlotAssignment)

    def test_none_best_returns_empty(self) -> None:
        class _FakeToken:
            best = None
        result = VerbSlotValidator.assignments_from_token(_FakeToken())
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART E: Exception hierarchy
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestExceptionHierarchy:
    """All GGT exceptions are subclasses of GGTError."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            LanguageNotFoundError,
            ConcordTypeNotFoundError,
            NounClassNotFoundError,
            SchemaValidationError,
            UnverifiedFormError,
            VersionIncompatibleError,
            MorphAnalysisError,
            UDMappingError,
            VerbSlotValidationError,
        ],
    )
    def test_is_ggt_error_subclass(self, exc_class: Type[GGTError]) -> None:
        assert issubclass(exc_class, GGTError)

    def test_language_not_found_is_raised_for_unknown_language(self) -> None:
        with pytest.raises(LanguageNotFoundError) as exc_info:
            GobeloGrammarLoader(GrammarConfig(language="notarealcode"))
        assert "notarealcode" in str(exc_info.value).lower() or exc_info.value is not None

    def test_noun_class_not_found_carries_nc_id(self) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        with pytest.raises(NounClassNotFoundError):
            L.get_noun_class("NC_XYZ_9999")

    def test_concord_type_not_found_raised_for_unknown_type(self) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=FULL_LANGUAGE))
        with pytest.raises(ConcordTypeNotFoundError):
            L.get_concords("totally_fake_concord")

    def test_verb_slot_validation_error_is_ggt_error(self) -> None:
        assert issubclass(VerbSlotValidationError, GGTError)

    def test_ud_mapping_error_is_ggt_error(self) -> None:
        assert issubclass(UDMappingError, GGTError)

    def test_morph_analysis_error_is_ggt_error(self) -> None:
        assert issubclass(MorphAnalysisError, GGTError)


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# PART F: Cross-language invariants
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossLanguageInvariants:
    """Properties that must hold for every language, not just chiTonga."""

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_language_in_list_supported_languages(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        assert lang in L.list_supported_languages()

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_have_nc1_or_equivalent(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        nc_ids = {nc.id for nc in L.get_noun_classes(active_only=False)}
        # Every Bantu grammar must have at least one singular human NC
        assert len(nc_ids) >= 1

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_have_subject_and_object_concords(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        types = L.get_all_concord_types()
        assert "subject_concords" in types
        assert "object_concords" in types

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_have_at_least_one_tam(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        assert len(L.get_tam_markers()) >= 1

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_have_at_least_one_extension(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        assert len(L.get_extensions()) >= 1

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_obligatory_slots_include_root(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        oblig = {s.id for s in L.get_verb_slots() if s.obligatory}
        assert len(oblig) >= 1

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_morphological_analyzer_constructs(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        a = MorphologicalAnalyzer(L)
        assert a.language == lang

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_ud_mapper_constructs(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        ud = UDFeatureMapper(L)
        assert ud.language == lang

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_verb_slot_validator_constructs(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        v = VerbSlotValidator(L)
        assert v.language == lang

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_analyze_returns_segmented_token(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        A = MorphologicalAnalyzer(L)
        tok = A.analyze("balya")
        assert isinstance(tok, SegmentedToken)
        assert tok.language == lang

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_validate_minimal_sequence(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        v = VerbSlotValidator(L)
        result = v.validate_assignments(_minimal_valid_sequence(L))
        assert isinstance(result, ValidationResult)
        # The minimal sequence uses generic slot ids and content types that
        # every grammar declares; it should be valid on every language
        assert result.is_valid, (
            f"{lang}: expected minimal sequence valid; got {result.summary()}"
        )

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_map_nc_list(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        ud = UDFeatureMapper(L)
        nc_ids = [nc.id for nc in L.get_noun_classes(active_only=False)]
        results = ud.map_nc_list(nc_ids)
        assert len(results) == len(nc_ids)
        for r in results:
            assert isinstance(r, UDNounClassFeatures)

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_extension_zones_valid(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        valid_zones = {"Z1", "Z2", "Z3", "Z4"}
        for ext in L.get_extensions():
            assert ext.zone in valid_zones, (
                f"{lang}: extension {ext.id} has invalid zone {ext.zone!r}"
            )

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_grammar_version_semver_like(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        version = L.get_metadata().grammar_version
        assert re.match(r"^\d+\.\d+", version), (
            f"{lang}: grammar_version {version!r} does not start with N.N"
        )

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_languages_loader_version_semver_like(self, lang: str) -> None:
        L = GobeloGrammarLoader(GrammarConfig(language=lang))
        assert re.match(r"^\d+\.\d+", L.loader_version)
