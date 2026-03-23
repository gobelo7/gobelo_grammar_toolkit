"""
tests/unit/test_loader_chitonga.py
===================================
34 loader round-trip checks against the real chitonga.yaml grammar.

Run:
    pytest tests/unit/test_loader_chitonga.py -v
    pytest tests/unit/test_loader_chitonga.py -v --tb=short

All assertions use exact values sampled from the live grammar.
If a grammar edit changes a value, the failing test tells you which field.
"""

import pytest
from pathlib import Path

# ── path bootstrap ────────────────────────────────────────────────
import sys
_REPO = Path(__file__).resolve().parents[2]
_GGT  = _REPO / "ggt"
for p in (_GGT, Path("/mnt/user-data/uploads")):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gobelo_grammar_toolkit.core.config     import GrammarConfig
from gobelo_grammar_toolkit.core.loader     import GobeloGrammarLoader
from gobelo_grammar_toolkit.core.exceptions import (
    LanguageNotFoundError, GGTError,
)

# ── fixture ───────────────────────────────────────────────────────
GRAMMAR_PATH = Path(__file__).resolve().parents[2] / "ggt" / "gobelo_grammar_toolkit" / "languages" / "chitonga.yaml"
if not GRAMMAR_PATH.exists():
    # fallback dev path
    GRAMMAR_PATH = Path("/home/claude/ggt/gobelo_grammar_toolkit/languages/chitonga.yaml")


@pytest.fixture(scope="module")
def loader() -> GobeloGrammarLoader:
    """Single shared loader for the entire test module (grammar is immutable)."""
    cfg = GrammarConfig(language="chitonga", override_path=str(GRAMMAR_PATH))
    return GobeloGrammarLoader(cfg)


# ═══════════════════════════════════════════════════════════════════
#  1-5  METADATA
# ═══════════════════════════════════════════════════════════════════

class TestMetadata:
    def test_language_identifier(self, loader):
        assert loader.get_metadata().language == "chitonga"

    def test_iso_code(self, loader):
        assert loader.get_metadata().iso_code == "toi"

    def test_guthrie(self, loader):
        assert loader.get_metadata().guthrie == "M.64"

    def test_grammar_version_semver(self, loader):
        ver = loader.get_metadata().grammar_version
        assert ver == "1.0.0"
        parts = ver.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_verify_count_zero(self, loader):
        """chiTonga is fully verified — no unresolved VERIFY flags."""
        assert loader.get_metadata().verify_count == 0


# ═══════════════════════════════════════════════════════════════════
#  6-12  NOUN CLASSES
# ═══════════════════════════════════════════════════════════════════

class TestNounClasses:
    def test_active_class_count(self, loader):
        """chiTonga has 21 noun classes, all active."""
        ncs = loader.get_noun_classes(active_only=True)
        assert len(ncs) == 21

    def test_total_class_count_equals_active(self, loader):
        """No inactive classes — active and total are equal for chiTonga."""
        assert len(loader.get_noun_classes(active_only=False)) == 21

    def test_nc7_prefix(self, loader):
        nc = loader.get_noun_class("NC7")
        assert nc.prefix == "ci-"

    def test_nc7_semantic_domain(self, loader):
        nc = loader.get_noun_class("NC7")
        assert nc.semantic_domain == "things_diminutives"

    def test_nc7_plural_counterpart(self, loader):
        nc = loader.get_noun_class("NC7")
        assert nc.plural_counterpart == "NC8"

    def test_nc1_nc2_pairing(self, loader):
        """NC1 (human sg) and NC2 (human pl) are mutual counterparts."""
        nc1 = loader.get_noun_class("NC1")
        nc2 = loader.get_noun_class("NC2")
        assert nc1.plural_counterpart == "NC2"
        assert nc2.singular_counterpart == "NC1"

    def test_nc_ids_are_unique(self, loader):
        ids = [nc.id for nc in loader.get_noun_classes(active_only=False)]
        assert len(ids) == len(set(ids))

    def test_all_ncs_have_prefix(self, loader):
        for nc in loader.get_noun_classes(active_only=False):
            assert nc.prefix, f"NC {nc.id} has no prefix"

    def test_all_ncs_have_semantic_domain(self, loader):
        for nc in loader.get_noun_classes(active_only=False):
            assert nc.semantic_domain, f"NC {nc.id} missing semantic_domain"


# ═══════════════════════════════════════════════════════════════════
#  13-19  CONCORD SYSTEMS
# ═══════════════════════════════════════════════════════════════════

class TestConcordSystems:
    def test_subject_concords_type(self, loader):
        sc = loader.get_subject_concords()
        assert sc.concord_type == "subject_concords"

    def test_subject_concord_entry_count(self, loader):
        """25 SC keys: personal pronouns + all NCs."""
        assert len(loader.get_subject_concords().entries) == 25

    def test_first_person_sg_concord(self, loader):
        sc = loader.get_subject_concords()
        assert sc.entries["1SG"] == "ndi"

    def test_nc7_subject_concord(self, loader):
        sc = loader.get_subject_concords()
        assert sc.entries["NC7"] == "ci"

    def test_object_concords_type(self, loader):
        oc = loader.get_object_concords()
        assert oc.concord_type == "object_concords"

    def test_total_concord_type_count(self, loader):
        """chiTonga has 18 named concord paradigms."""
        assert len(loader.get_all_concord_types()) == 18

    def test_possessive_nc7(self, loader):
        poss = loader.get_concords("possessive_concords")
        assert poss.entries.get("NC7") == "ca"

    def test_nc15_subject_concord(self, loader):
        """NC15 (infinitives) has subject concord ku-."""
        sc = loader.get_subject_concords()
        assert sc.entries.get("NC15") == "ku"

    def test_get_concords_returns_correct_type(self, loader):
        adj = loader.get_concords("adjectival_concords")
        assert adj.concord_type == "adjectival_concords"

    def test_subject_concords_in_all_types(self, loader):
        all_types = loader.get_all_concord_types()
        assert "subject_concords" in all_types
        assert "object_concords" in all_types


# ═══════════════════════════════════════════════════════════════════
#  20-24  TAM MARKERS
# ═══════════════════════════════════════════════════════════════════

class TestTAMMarkers:
    def test_tam_count(self, loader):
        assert len(loader.get_tam_markers()) == 8

    def test_tam_pres_form(self, loader):
        tams = {t.id: t for t in loader.get_tam_markers()}
        assert tams["TAM_PRES"].form == "a"

    def test_tam_pres_features(self, loader):
        tams = {t.id: t for t in loader.get_tam_markers()}
        t = tams["TAM_PRES"]
        assert t.tense == "present"
        assert t.aspect == "imperfective"
        assert t.mood == "indicative"

    def test_rem_pst_present(self, loader):
        """TAM_REM_PST (remote past, tone H-L) must exist alongside TAM_PST."""
        ids = [t.id for t in loader.get_tam_markers()]
        assert "TAM_REM_PST" in ids and "TAM_PST" in ids

    def test_all_tam_have_ids(self, loader):
        for t in loader.get_tam_markers():
            assert t.id.startswith("TAM_"), f"TAM id malformed: {t.id!r}"


# ═══════════════════════════════════════════════════════════════════
#  25-28  VERB EXTENSIONS
# ═══════════════════════════════════════════════════════════════════

class TestVerbExtensions:
    def test_extension_count(self, loader):
        assert len(loader.get_extensions()) == 14

    def test_appl_canonical_form(self, loader):
        exts = {e.id: e for e in loader.get_extensions()}
        assert exts["APPL"].canonical_form == "-il-"

    def test_appl_zone(self, loader):
        exts = {e.id: e for e in loader.get_extensions()}
        assert exts["APPL"].zone == "Z1"

    def test_pass_zone(self, loader):
        """PASS (passive) must be in zone Z3 — always final extension."""
        exts = {e.id: e for e in loader.get_extensions()}
        assert exts["PASS"].zone == "Z3"

    def test_zone_ordering(self, loader):
        """Z1 < Z2 < Z3 < Z4 ordering must be maintained."""
        exts = {e.id: e for e in loader.get_extensions()}
        zone_order = {"Z1": 1, "Z2": 2, "Z3": 3, "Z4": 4}
        assert zone_order[exts["APPL"].zone]  < zone_order[exts["RECIP"].zone]  # Z1 < Z2
        assert zone_order[exts["RECIP"].zone] < zone_order[exts["PASS"].zone]   # Z2 < Z3


# ═══════════════════════════════════════════════════════════════════
#  29-30  VERB SLOTS
# ═══════════════════════════════════════════════════════════════════

class TestVerbSlots:
    def test_slot_count(self, loader):
        """chiTonga has an 11-slot verb template."""
        assert len(loader.get_verb_slots()) == 11

    def test_obligatory_slots(self, loader):
        """SLOT3 (SM), SLOT8 (root), SLOT10 (FV) are obligatory."""
        oblig = {s.id for s in loader.get_verb_slots() if s.obligatory}
        assert oblig == {"SLOT3", "SLOT8", "SLOT10"}


# ═══════════════════════════════════════════════════════════════════
#  31-33  PHONOLOGY
# ═══════════════════════════════════════════════════════════════════

class TestPhonology:
    def test_vowel_inventory(self, loader):
        phon = loader.get_phonology()
        assert phon.vowels == ["i", "e", "a", "o", "u"]

    def test_tone_system(self, loader):
        assert loader.get_phonology().tone_system == "four_level"

    def test_sandhi_rule_count(self, loader):
        """Four sandhi rules: SND.1–SND.4."""
        assert len(loader.get_phonology().sandhi_rules) == 4


# ═══════════════════════════════════════════════════════════════════
#  34  VERIFY FLAGS
# ═══════════════════════════════════════════════════════════════════

class TestVerifyFlags:
    def test_no_unresolved_flags(self, loader):
        """chiTonga is fully verified. Zero unresolved VERIFY annotations."""
        flags = loader.list_verify_flags()
        assert len(flags) == 0
        assert loader.get_metadata().verify_count == 0


# ═══════════════════════════════════════════════════════════════════
#  ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════

class TestErrorHandling:
    def test_unknown_language_raises(self):
        with pytest.raises(LanguageNotFoundError) as exc_info:
            GobeloGrammarLoader(GrammarConfig(language="zzzz"))
        assert "zzzz" in str(exc_info.value)

    def test_unknown_nc_raises(self, loader):
        with pytest.raises(GGTError):
            loader.get_noun_class("NC99")

    def test_unknown_concord_type_raises(self, loader):
        with pytest.raises(GGTError):
            loader.get_concords("bogus_concords")

    def test_get_metadata_is_immutable(self, loader):
        """GrammarMetadata is a frozen dataclass — assignment must fail."""
        m = loader.get_metadata()
        with pytest.raises((AttributeError, TypeError)):
            m.language = "mutated"  # type: ignore[misc]
