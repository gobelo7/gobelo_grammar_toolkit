"""
tests/integration/test_apps_chitonga.py
========================================
Integration tests for all GGT NLP apps against the chiTonga grammar.

Tests validate that every public method on every app:
  - Returns the correct data type
  - Produces linguistically sensible values for known chiTonga words
  - Handles error conditions gracefully

Run:
    pytest tests/integration/test_apps_chitonga.py -v
"""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for p in (_REPO / "ggt", Path("/mnt/user-data/uploads")):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pytest
from gobelo_grammar_toolkit.core.config     import GrammarConfig
from gobelo_grammar_toolkit.core.loader     import GobeloGrammarLoader
from gobelo_grammar_toolkit.core.exceptions import GGTError

GRAMMAR_PATH = _REPO / "ggt" / "gobelo_grammar_toolkit" / "languages" / "chitonga.yaml"
if not GRAMMAR_PATH.exists():
    GRAMMAR_PATH = Path("/home/claude/ggt/gobelo_grammar_toolkit/languages/chitonga.yaml")


@pytest.fixture(scope="module")
def loader():
    return GobeloGrammarLoader(GrammarConfig(language="chitonga", override_path=str(GRAMMAR_PATH)))


# ═══════════════════════════════════════════════════════════════════
#  MorphologicalAnalyzer
# ═══════════════════════════════════════════════════════════════════

class TestMorphologicalAnalyzer:
    @pytest.fixture(scope="class")
    def az(self, loader):
        from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphologicalAnalyzer
        return MorphologicalAnalyzer(loader)

    def test_analyze_returns_segmented_token(self, az):
        from gobelo_grammar_toolkit.apps.morphological_analyzer import SegmentedToken
        tok = az.analyze("cilya")
        assert isinstance(tok, SegmentedToken)

    def test_cilya_best_segmented(self, az):
        """cilya = ci (NC7 SM) + ly (root) + a (FV_IND)."""
        tok = az.analyze("cilya")
        assert tok.best is not None
        assert tok.best.segmented == "ci-ly-a"

    def test_cilya_has_hypotheses(self, az):
        tok = az.analyze("cilya")
        assert len(tok.hypotheses) >= 1

    def test_balya_subject_marker(self, az):
        """balya = ba (NC2 SM) + ly (root) + a (FV_IND)."""
        tok = az.analyze("balya")
        assert tok.best is not None
        # subject marker morpheme must exist
        sm_morphemes = [m for m in tok.best.morphemes if m.content_type == "subject_concord"]
        assert len(sm_morphemes) >= 1

    def test_muntu_is_nominal(self, az):
        """muntu is a noun (NC1 prefix + root)."""
        tok = az.analyze("muntu")
        assert tok.best is not None
        nc_morphemes = [m for m in tok.best.morphemes if m.content_type == "noun_prefix"]
        assert len(nc_morphemes) >= 1

    def test_is_ambiguous_property(self, az):
        tok = az.analyze("cilya")
        assert isinstance(tok.is_ambiguous, bool)

    def test_generate_nc7_pres(self, az):
        from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphFeatureBundle, SurfaceForm
        feat = MorphFeatureBundle(root="lya", subject_nc="NC7", tam_id="TAM_PRES")
        sf = az.generate(feat)
        assert isinstance(sf, SurfaceForm)
        assert sf.surface  # non-empty
        assert "lya" in sf.surface  # root appears in surface

    def test_generate_nc2_past(self, az):
        from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphFeatureBundle
        feat = MorphFeatureBundle(root="bona", subject_nc="NC2", tam_id="TAM_PST")
        sf = az.generate(feat)
        assert sf.surface

    def test_generate_interlinear(self, az):
        result = az.generate_interlinear("cilya")
        assert isinstance(result, str)
        assert "ci-ly-a" in result or "ci" in result  # segmentation in output

    def test_segment_text(self, az):
        tokens = az.segment_text("Balya muntu.")
        assert len(tokens) == 2  # "Balya" and "muntu."

    def test_language_property(self, az):
        assert az.language == "chitonga"

    def test_analyze_empty_raises(self, az):
        from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphAnalysisError
        with pytest.raises((MorphAnalysisError, GGTError, ValueError)):
            az.analyze("")


# ═══════════════════════════════════════════════════════════════════
#  ParadigmGenerator
# ═══════════════════════════════════════════════════════════════════

class TestParadigmGenerator:
    @pytest.fixture(scope="class")
    def gen(self, loader):
        from gobelo_grammar_toolkit.apps.paradigm_generator import ParadigmGenerator
        return ParadigmGenerator(loader)

    def test_generate_verb_paradigm_returns_table(self, gen):
        from gobelo_grammar_toolkit.apps.paradigm_generator import ParadigmTable
        table = gen.generate_verb_paradigm("lya")
        assert isinstance(table, ParadigmTable)

    def test_paradigm_dimensions(self, gen):
        """25 SC rows × 8 TAM columns."""
        table = gen.generate_verb_paradigm("lya")
        assert len(table.rows) == 25
        assert len(table.columns) == 8

    def test_paradigm_root(self, gen):
        table = gen.generate_verb_paradigm("bona")
        assert table.root == "bona"

    def test_paradigm_language(self, gen):
        table = gen.generate_verb_paradigm("lya")
        assert table.language == "chitonga"

    def test_nc7_pres_cell_exists(self, gen):
        table = gen.generate_verb_paradigm("lya")
        cell = table.cells.get(("NC7", "TAM_PRES"))
        assert cell is not None
        assert cell.surface  # non-empty surface form

    def test_nc7_pres_surface_contains_root(self, gen):
        table = gen.generate_verb_paradigm("lya")
        cell = table.cells[("NC7", "TAM_PRES")]
        assert "ly" in cell.surface or "lya" in cell.surface

    def test_paradigm_with_appl_extension(self, gen):
        table = gen.generate_verb_paradigm("lya", extensions=("APPL",))
        # All cells should have APPL marker
        cell = table.cells.get(("NC7", "TAM_PRES"))
        assert cell is not None

    def test_negative_polarity(self, gen):
        table = gen.generate_verb_paradigm("lya", polarities=("negative",))
        assert table.metadata["polarities"] == "negative"

    def test_to_csv(self, gen):
        table = gen.generate_verb_paradigm("lya")
        csv = gen.to_csv(table)
        assert isinstance(csv, str)
        assert "lya" in csv
        assert "," in csv

    def test_to_markdown(self, gen):
        table = gen.generate_verb_paradigm("lya")
        md = gen.to_markdown(table)
        assert isinstance(md, str)
        assert "|" in md  # markdown table

    def test_sc_keys_property(self, gen):
        keys = gen.sc_keys
        assert "NC7" in keys
        assert "1SG" in keys

    def test_tam_ids_property(self, gen):
        ids = gen.tam_ids
        assert "TAM_PRES" in ids
        assert "TAM_REM_PST" in ids

    def test_empty_root_raises(self, gen):
        from gobelo_grammar_toolkit.apps.paradigm_generator import ParadigmGenerationError
        with pytest.raises((ParadigmGenerationError, GGTError, ValueError)):
            gen.generate_verb_paradigm("")


# ═══════════════════════════════════════════════════════════════════
#  ConcordGenerator
# ═══════════════════════════════════════════════════════════════════

class TestConcordGenerator:
    @pytest.fixture(scope="class")
    def cg(self, loader):
        from gobelo_grammar_toolkit.apps.concord_generator import ConcordGenerator
        return ConcordGenerator(loader)

    def test_generate_all_concords_returns_dict(self, cg):
        forms = cg.generate_all_concords("NC7")
        assert isinstance(forms, dict)

    def test_nc7_has_subject_concord(self, cg):
        forms = cg.generate_all_concords("NC7")
        assert forms.get("subject_concords") == "ci"

    def test_nc7_has_possessive_concord(self, cg):
        forms = cg.generate_all_concords("NC7")
        assert forms.get("possessive_concords") == "ca"

    def test_generate_all_concords_rich(self, cg):
        from gobelo_grammar_toolkit.apps.concord_generator import AllConcordsResult
        rich = cg.generate_all_concords_rich("NC7")
        assert isinstance(rich, AllConcordsResult)
        assert rich.nc_id == "NC7"
        assert rich.language == "chitonga"

    def test_rich_result_forms(self, cg):
        rich = cg.generate_all_concords_rich("NC7")
        assert "subject_concords" in rich.forms
        assert rich.forms["subject_concords"] == "ci"

    def test_generate_concord_single(self, cg):
        result = cg.generate_concord("NC7", "subject_concords")
        assert result.nc_id == "NC7"
        assert result.form == "ci"

    def test_generate_paradigm(self, cg):
        from gobelo_grammar_toolkit.apps.concord_generator import ConcordParadigm
        paradigm = cg.generate_paradigm("subject_concords")
        assert isinstance(paradigm, ConcordParadigm)
        assert paradigm.concord_type == "subject_concords"
        assert paradigm.entries.get("NC7") == "ci"

    def test_cross_tab(self, cg):
        from gobelo_grammar_toolkit.apps.concord_generator import CrossTab
        xtab = cg.cross_tab()
        assert isinstance(xtab, CrossTab)
        assert xtab.noun_class_count == 21
        assert xtab.concord_type_count == 18

    def test_cross_tab_nc7_row(self, cg):
        xtab = cg.cross_tab()
        nc7_row = next(r for r in xtab.rows if r.nc_id == "NC7")
        assert nc7_row.forms.get("subject_concords") == "ci"

    def test_list_concord_types(self, cg):
        types = cg.list_available_concord_types("NC7")
        assert "subject_concords" in types

    def test_nc1a_subclass_fallback(self, cg):
        """NC1a should fall back to NC1 for concords not explicitly defined."""
        rich = cg.generate_all_concords_rich("NC1a")
        # Should have forms (either direct or via fallback)
        assert len(rich.forms) > 0


# ═══════════════════════════════════════════════════════════════════
#  CorpusAnnotator
# ═══════════════════════════════════════════════════════════════════

class TestCorpusAnnotator:
    @pytest.fixture(scope="class")
    def ann(self, loader):
        from gobelo_grammar_toolkit.apps.corpus_annotator import CorpusAnnotator
        return CorpusAnnotator(loader)

    def test_annotate_text_returns_result(self, ann):
        from gobelo_grammar_toolkit.apps.corpus_annotator import AnnotationResult
        result = ann.annotate_text("Balya muntu.")
        assert isinstance(result, AnnotationResult)

    def test_sentence_count(self, ann):
        result = ann.annotate_text("Balya muntu. Cilya cintu.")
        assert result.total_sentences == 2

    def test_token_count(self, ann):
        result = ann.annotate_text("Balya muntu.")
        assert result.total_tokens == 2

    def test_conllu_output_format(self, ann):
        result = ann.annotate_text("Balya muntu.")
        conllu = ann.to_conllu(result)
        assert isinstance(conllu, str)
        assert "# sent_id" in conllu
        assert "# text" in conllu
        # CoNLL-U rows have 10 tab-separated columns
        data_rows = [l for l in conllu.splitlines() if l and not l.startswith("#")]
        assert len(data_rows) >= 2
        for row in data_rows:
            cols = row.split("\t")
            assert len(cols) == 10, f"Expected 10 CoNLL-U columns, got {len(cols)}: {row!r}"

    def test_conllu_upos_verb(self, ann):
        result = ann.annotate_text("Balya.")
        conllu = ann.to_conllu(result)
        data_rows = [l for l in conllu.splitlines() if l and not l.startswith("#")]
        upos_values = [row.split("\t")[3] for row in data_rows]
        assert "VERB" in upos_values

    def test_conllu_feats_not_empty(self, ann):
        result = ann.annotate_text("Cilya cintu.")
        conllu = ann.to_conllu(result)
        data_rows = [l for l in conllu.splitlines() if l and not l.startswith("#")]
        feats_values = [row.split("\t")[5] for row in data_rows]
        # At least one token should have non-underscore features
        assert any(f != "_" for f in feats_values)

    def test_summary_format(self, ann):
        result = ann.annotate_text("Balya muntu.")
        summary = result.summary()
        assert isinstance(summary, str)
        assert "chitonga" in summary
        assert "sentence" in summary

    def test_multi_sentence_annotation(self, ann):
        result = ann.annotate_text("Balya muntu.\nCilya cintu.\nTwalya bana.")
        assert result.total_sentences == 3

    def test_language_property(self, ann):
        assert ann.language == "chitonga"

    def test_empty_text_raises_or_returns_empty(self, ann):
        """Empty text should either raise or return 0 sentences gracefully."""
        try:
            result = ann.annotate_text("   ")
            assert result.total_sentences == 0 or result.total_tokens == 0
        except (GGTError, ValueError):
            pass  # also acceptable


# ═══════════════════════════════════════════════════════════════════
#  UDFeatureMapper
# ═══════════════════════════════════════════════════════════════════

class TestUDFeatureMapper:
    @pytest.fixture(scope="class")
    def az(self, loader):
        from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphologicalAnalyzer
        return MorphologicalAnalyzer(loader)

    @pytest.fixture(scope="class")
    def mp(self, loader):
        from gobelo_grammar_toolkit.apps.ud_feature_mapper import UDFeatureMapper
        return UDFeatureMapper(loader)

    def test_map_nc7(self, mp):
        feat = mp.map_nc("NC7")
        assert feat.nounclass == "Bantu7"
        assert feat.number == "Sing"

    def test_map_nc2_plural(self, mp):
        feat = mp.map_nc("NC2")
        assert feat.nounclass == "Bantu2"
        assert feat.number == "Plur"

    def test_map_nc1a_strips_suffix(self, mp):
        """NC1a → Bantu1 (suffix stripped)."""
        feat = mp.map_nc("NC1a")
        assert feat.nounclass == "Bantu1"

    def test_map_tam_pres(self, mp):
        feat = mp.map_tam("TAM_PRES")
        assert feat.tense == "Pres"
        assert feat.aspect == "Imp"
        assert feat.mood == "Ind"

    def test_map_tam_pst(self, mp):
        feat = mp.map_tam("TAM_PST")
        assert feat.tense == "Past"

    def test_map_tam_fut_near(self, mp):
        feat = mp.map_tam("TAM_FUT_NEAR")
        assert feat.tense == "Fut"

    def test_map_concord_1sg(self, mp):
        feat = mp.map_concord_key("1SG")
        assert feat.person == "1"
        assert feat.number == "Sing"

    def test_map_concord_nc7(self, mp):
        feat = mp.map_concord_key("NC7")
        assert feat.person == "3"

    def test_map_extension_pass(self, mp):
        feat = mp.map_extension("PASS")
        assert feat.voice == "Pass"

    def test_map_extension_appl(self, mp):
        feat = mp.map_extension("APPL")
        assert feat.voice == "Appl"

    def test_map_extension_caus(self, mp):
        feat = mp.map_extension("CAUS")
        assert feat.voice == "Caus"

    def test_map_segmented_token_cilya(self, az, mp):
        tok = az.analyze("cilya")
        bundle = mp.map_segmented_token(tok)
        assert bundle.nounclass == "Bantu7"
        assert bundle.number == "Sing"
        assert bundle.person == "3"

    def test_to_conllu_feats_cilya(self, az, mp):
        tok = az.analyze("cilya")
        bundle = mp.map_segmented_token(tok)
        feats = mp.to_conllu_feats(bundle)
        assert isinstance(feats, str)
        assert "Nounclass=Bantu7" in feats

    def test_export_nc_table(self, mp):
        table = mp.export_nc_table()
        assert isinstance(table, str)
        assert "NC7" in table
        assert "Bantu7" in table

    def test_map_all_tams(self, mp):
        result = mp.map_all_tams()
        assert len(result) == 8
        assert "TAM_PRES" in result


# ═══════════════════════════════════════════════════════════════════
#  VerbSlotValidator
# ═══════════════════════════════════════════════════════════════════

class TestVerbSlotValidator:
    @pytest.fixture(scope="class")
    def vv(self, loader):
        from gobelo_grammar_toolkit.apps.verb_slot_validator import VerbSlotValidator
        return VerbSlotValidator(loader)

    def test_validate_returns_result(self, vv):
        from gobelo_grammar_toolkit.apps.verb_slot_validator import ValidationResult
        result = vv.validate("cilya")
        assert isinstance(result, ValidationResult)

    def test_obligatory_slots(self, vv):
        oblig = vv.obligatory_slots()
        assert "SLOT3" in oblig
        assert "SLOT8" in oblig
        assert "SLOT10" in oblig

    def test_known_extension_ids(self, vv):
        ext_ids = vv.known_extension_ids()
        assert "APPL" in ext_ids
        assert "PASS" in ext_ids
        assert "CAUS" in ext_ids

    def test_extension_zone(self, vv):
        assert vv.extension_zone("APPL") == "Z1"
        assert vv.extension_zone("PASS") == "Z3"
        assert vv.extension_zone("RECIP") == "Z2"

    def test_check_extension_ordering_valid(self, vv):
        """APPL (Z1) before PASS (Z3) is valid."""
        result = vv.check_extension_ordering(["APPL", "PASS"])
        assert result.is_valid or len(result.violations) == 0 or result.error_count == 0

    def test_language_property(self, vv):
        assert vv.language == "chitonga"

    def test_max_extensions(self, vv):
        assert vv.max_extensions() >= 4

    def test_allowed_content_types_slot3(self, vv):
        types = vv.allowed_content_types("SLOT3")
        assert "subject_concord" in types


# ═══════════════════════════════════════════════════════════════════
#  FeatureComparator  (multi-language)
# ═══════════════════════════════════════════════════════════════════

class TestFeatureComparator:
    @pytest.fixture(scope="class")
    def loaders(self):
        """Load both chitonga and chibemba for cross-language comparison."""
        result = {}
        for lang in ("chitonga", "chibemba"):
            p = Path("/home/claude/ggt/gobelo_grammar_toolkit/languages") / f"{lang}.yaml"
            override = str(p) if p.exists() else None
            try:
                result[lang] = GobeloGrammarLoader(GrammarConfig(language=lang, override_path=override))
            except Exception:
                pass
        return result

    @pytest.fixture(scope="class")
    def fc(self, loaders):
        from gobelo_grammar_toolkit.apps.feature_comparator import FeatureComparator
        if len(loaders) < 2:
            pytest.skip("Need both chitonga and chibemba grammars for this test")
        return FeatureComparator(loaders)

    def test_languages_property(self, fc):
        langs = fc.languages()
        assert "chitonga" in langs

    def test_loader_count(self, fc):
        assert fc.loader_count() >= 2

    def test_compare_nc_prefix(self, fc):
        """NC1 prefix differs: chitonga=mu-, chibemba=u-."""
        table = fc.compare("noun_class.NC1.prefix")
        assert "chitonga" in table.values
        assert table.values["chitonga"].value_str == "mu-"

    def test_compare_many(self, fc):
        tables = fc.compare_many([
            "noun_class.NC1.prefix",
            "noun_class.NC2.prefix",
        ])
        assert len(tables) == 2

    def test_to_markdown(self, fc):
        table = fc.compare("noun_class.NC1.prefix")
        md = fc.to_markdown(table)
        assert isinstance(md, str)
        assert "chitonga" in md
