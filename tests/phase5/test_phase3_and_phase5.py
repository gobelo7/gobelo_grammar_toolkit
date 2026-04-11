"""
test_phase3_and_phase5.py — Comprehensive tests for pos_tagger.py (Phase 3)
and annotation_pipeline.py (Phase 5)
============================================================================

Coverage plan
-------------

Phase 3 — GobeloPOSTagger (pos_tagger.py)                         55 tests
  G1  _build_config / _TaggerConfig construction                   8 tests
  G2  TAM inference helpers (_infer_tam_ud, keywords)              7 tests
  G3  FV inference helpers (_infer_fv_verbform)                    5 tests
  G4  Extension → Voice (_ext_to_voice)                            4 tests
  G5  _build_verb_feats                                            8 tests
  G6  _build_noun_feats                                            4 tests
  G7  _build_xpos                                                  5 tests
  G8  _assign_shallow_deprel                                       4 tests
  G9  _upos_from_slot_parse                                        5 tests
  G10 _surface_heuristics                                          3 tests
  G11 _tag_token — all 8 priority branches                         8 tests
  G12 _refine_context (Pass 3)                                     4 tests

Phase 5 — GobeloAnnotationPipeline + CLI (annotation_pipeline.py) 34 tests
  G13 _iter_txt                                                    4 tests
  G14 _iter_gcbt_json                                              5 tests
  G15 _iter_gcbt_jsonl                                             4 tests
  G16 _collect_input_files                                         3 tests
  G17 _batches                                                     3 tests
  G18 PipelineStats                                                5 tests
  G19 GobeloAnnotationPipeline.run_sentence                        4 tests
  G20 GobeloAnnotationPipeline.run (corpus run)                    6 tests

Total: 89 tests
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/home/claude")

import pytest

from models import (
    AnnotatedSentence,
    ConfidenceLevel,
    LexiconCategory,
    LexiconEntry,
    MorphemeSpan,
    POSTag,
    SlotFill,
    SlotParse,
    TokenType,
    WordToken,
)

# ── Phase 3 imports ───────────────────────────────────────────────────────────
from pos_tagger import (
    VERSION,
    GobeloPOSTagger,
    _TaggerConfig,
    _assign_shallow_deprel,
    _build_config,
    _build_noun_feats,
    _build_verb_feats,
    _build_xpos,
    _ext_to_voice,
    _infer_fv_verbform,
    _infer_tam_ud,
    _load_word_set,
    _NullLoader as POS_NullLoader,
)

# ── Phase 5 imports ───────────────────────────────────────────────────────────
from annotation_pipeline import (
    VERSION as PIPELINE_VERSION,
    GobeloAnnotationPipeline,
    GobeloPipelineCLI,
    PipelineStats,
    _batches,
    _collect_input_files,
    _iter_gcbt_json,
    _iter_gcbt_jsonl,
    _iter_txt,
    _load_manifest,
)


# =============================================================================
# Shared mock infrastructure
# =============================================================================

class MockLoader:
    """Realistic GGT loader stub with enough YAML data to drive both phases."""

    lang_iso = "toi"
    lexicon_verb: Dict = {}
    lexicon_noun: Dict = {}

    def get(self, key: str, default: Any = None) -> Any:
        return _MOCK_GRAMMAR.get(key, default)


_MOCK_GRAMMAR: Dict[str, Any] = {
    # ── Noun classes ────────────────────────────────────────────────────────
    "morphology.noun_classes": {
        "NC1": {"prefix": {"canonical_form": "mu-"}, "grammatical_number": "singular",
                "number": "singular"},
        "NC2": {"prefix": {"canonical_form": "ba-"}, "grammatical_number": "plural",
                "number": "plural"},
        "NC3": {"prefix": {"canonical_form": "mu-"}, "grammatical_number": "singular",
                "number": "singular"},
        "NC4": {"prefix": {"canonical_form": "mi-"}, "grammatical_number": "plural",
                "number": "plural"},
        "NC7": {"prefix": {"canonical_form": "ci-"}, "grammatical_number": "singular",
                "number": "singular"},
        "NC9": {"prefix": {"canonical_form": "N-"},  "grammatical_number": "singular",
                "number": "singular"},
        "NC15": {"prefix": "ku", "number": "singular", "nc_number": "15"},
        "NC16": {"prefix": "pa", "number": "singular"},
        "NC17": {"prefix": "ku", "number": "singular"},
        "NC18": {"prefix": "mu", "number": "singular"},
    },
    # ── TAM ─────────────────────────────────────────────────────────────────
    "morphology.tense_aspect": {
        "PRES":        {"gloss": "PRES",    "function": "Present habitual"},
        "PAST":        {"gloss": "PST",     "function": "Past tense"},
        "PAST_HOD":    {"gloss": "PST.HOD", "function": "Hodiernal past"},
        "FUT_NEAR":    {"gloss": "FUT",     "function": "Near future"},
        "HAB":         {"gloss": "HAB",     "function": "Habitual aspect"},
        "PERF":        {"gloss": "PERF",    "function": "Perfect aspect"},
        "SUBJ_TAM":    {"gloss": "SUBJ",    "function": "Subjunctive mood"},
        "COND_TAM":    {"gloss": "COND",    "function": "Conditional mood"},
        "IMPERF":      {"gloss": "IMPERF",  "function": "Imperfective aspect"},
        "PROSP":       {"gloss": "PROSP",   "function": "Prospective"},
        # explicit UD fields take priority
        "EXPLICIT_UD": {"gloss": "PST",
                        "ud_tense": "Past", "ud_aspect": "Perf", "ud_mood": "Ind"},
    },
    # ── Final vowels ─────────────────────────────────────────────────────────
    "morphology.final_vowels": {
        "indicative":          {"form": "a",   "gloss": "IND"},
        "subjunctive":         {"form": "e",   "gloss": "SUBJ", "ud_verbform": "Sub"},
        "perfective":          {"form": "ide", "gloss": "PERF"},
        "infinitive":          {"form": "a",   "gloss": "INF"},
        "imperative_singular": {"form": "a",   "gloss": "IMP.SG"},
        "gerund_form":         {"form": "a",   "gloss": "GER"},
        "relative_clause":     {"form": "o",   "gloss": "REL"},
    },
    # ── Extensions ───────────────────────────────────────────────────────────
    "morphology.extensions": {
        "APPL": {"form": ["-il-"], "gloss": "APPL", "zone": "A"},
        "CAUS": {"form": ["-is-"], "gloss": "CAUS", "zone": "A"},
        "PASS": {"form": ["-w-"],  "gloss": "PASS", "zone": "C"},
        "RECIP":{"form": ["-an-"], "gloss": "RECIP","zone": "B"},
        "REFL": {"form": ["-ib-"], "gloss": "REFL", "zone": "B"},
    },
    # ── Subject markers ──────────────────────────────────────────────────────
    "morphology.subject_markers": {
        "1SG": {"form": "ndi", "gloss": "1SG.SM", "person": "1", "number": "Sing"},
        "2SG": {"form": "u",   "gloss": "2SG.SM", "person": "2", "number": "Sing"},
        "NC1": {"form": "a",   "gloss": "CL1.SM"},
        "NC2": {"form": "ba",  "gloss": "CL2.SM"},
        "NC3": {"form": "u",   "gloss": "CL3.SM"},
        "NC7": {"form": "ci",  "gloss": "CL7.SM"},
    },
    # ── Closed-class word lists ───────────────────────────────────────────────
    "particles":                  ["pe", "ko"],
    "conjunctions.coordinating":  ["na", "pele"],
    "conjunctions.subordinating": ["kuti", "busena"],
    "adverbs":                    ["lyonse", "busiku"],
    "determiners":                ["uyu", "uyo"],
    "pronouns":                   ["iwe", "imwe"],
    "ideophones":                 ["pyu", "bwete"],
    "copula.forms":               ["ndi", "ndiwe"],
    "negation.free_particles":    ["te", "pe"],
    # ── Copula roots ─────────────────────────────────────────────────────────
    "copula": {"roots": ["ndi", "li"]},
}


# =============================================================================
# Shared token / sentence factories
# =============================================================================

def _slot_parse(
    sm_nc: str = "NC3",
    tam_key: Optional[str] = "PRES",
    root: str = "bon",
    fv_key: str = "indicative",
    ext_key: Optional[str] = None,
    neg: bool = False,
    score: float = 0.68,
) -> SlotParse:
    sp = SlotParse(lang_iso="toi", analyser_version="2.0.0", score=score)
    pos = 0
    if neg:
        sp.set("SLOT1", SlotFill(
            form="ta", gloss="NEG", source_rule="ta",
            confidence=ConfidenceLevel.HIGH, start=0, end=2,
        ))
        pos = 2
    sp.set("SLOT2", SlotFill(
        form="a", gloss=f"CL{sm_nc[2:]}.SM" if sm_nc.startswith("NC") else sm_nc,
        source_rule=f"SM.{sm_nc}",
        confidence=ConfidenceLevel.HIGH, start=pos, end=pos + 1,
    ))
    pos += 1
    if tam_key:
        tam_forms = {"PRES": "a", "PAST": "ka", "FUT_NEAR": "yo",
                     "HAB": "la", "PERF": "a", "SUBJ_TAM": ""}
        tf = tam_forms.get(tam_key, "a")
        if tf:
            sp.set("SLOT3", SlotFill(
                form=tf, gloss=tam_key, source_rule=tam_key,
                confidence=ConfidenceLevel.HIGH, start=pos, end=pos + len(tf),
            ))
            pos += len(tf)
    sp.set("SLOT5", SlotFill(
        form=root, gloss=root, source_rule=f"LEX:{root}",
        confidence=ConfidenceLevel.HIGH, start=pos, end=pos + len(root),
    ))
    pos += len(root)
    if ext_key:
        ef = {"PASS": "w", "APPL": "il", "CAUS": "is", "RECIP": "an"}.get(ext_key, "il")
        sp.set("SLOT6", SlotFill(
            form=ef, gloss=ext_key, source_rule=ext_key,
            confidence=ConfidenceLevel.HIGH, start=pos, end=pos + len(ef),
        ))
        pos += len(ef)
    if fv_key:
        fv_forms = {"indicative": "a", "subjunctive": "e", "perfective": "ide",
                    "infinitive": "a", "imperative_singular": "a"}
        ff = fv_forms.get(fv_key, "a")
        sp.set("SLOT10", SlotFill(
            form=ff, gloss=fv_key, source_rule=fv_key,
            confidence=ConfidenceLevel.HIGH, start=pos, end=pos + len(ff),
        ))
    return sp


def _verb_token(
    form: str = "ubona",
    sm_nc: str = "NC3",
    tam_key: Optional[str] = "PRES",
    root: str = "bon",
    fv_key: str = "indicative",
    ext_key: Optional[str] = None,
    neg: bool = False,
    score: float = 0.68,
    pre_tagged: bool = False,   # simulate VERB_ANALYSED from Phase 2
) -> WordToken:
    tok = WordToken(
        form=form, lang_iso="toi", token_type=TokenType.WORD,
        char_start=0, char_end=len(form),
    )
    sp = _slot_parse(sm_nc=sm_nc, tam_key=tam_key, root=root,
                     fv_key=fv_key, ext_key=ext_key, neg=neg, score=score)
    tok.add_slot_parse(sp)
    tok.add_morpheme_span(MorphemeSpan(0, 1, "u", "SM", f"CL{sm_nc[2:]}.SM", "SLOT2"))
    if pre_tagged:
        tok.upos = POSTag.VERB
        tok.add_flag("VERB_ANALYSED")
    tok.is_oov = False
    return tok


def _noun_token(
    form: str = "muti",
    nc: str = "NC3",
    pre_tagged: bool = False,
) -> WordToken:
    tok = WordToken(
        form=form, lang_iso="toi", token_type=TokenType.WORD,
        char_start=0, char_end=len(form),
        noun_class=nc,
    )
    tok.add_morpheme_span(MorphemeSpan(0, 2, form[:2], "NC_PREFIX", nc))
    if pre_tagged:
        tok.upos = POSTag.NOUN
        tok.add_flag("NOUN_ANALYSED")
    tok.is_oov = False
    return tok


def _sent(*tokens: WordToken, sent_id: str = "toi-001") -> AnnotatedSentence:
    sent = AnnotatedSentence(
        sent_id=sent_id, text=" ".join(t.form for t in tokens), lang_iso="toi",
        tokens=list(tokens),
    )
    for i, t in enumerate(tokens, 1):
        t.token_id = str(i)
    return sent


def _tagger(overwrite: bool = False) -> GobeloPOSTagger:
    return GobeloPOSTagger(MockLoader(), overwrite_upos=overwrite)


# =============================================================================
# Phase 3 — pos_tagger.py
# =============================================================================

# G1 — _build_config / _TaggerConfig construction (8 tests)
# --------------------------------------------------------------------------

class TestBuildConfig:

    def setup_method(self):
        self.cfg = _build_config(MockLoader())

    def test_particles_populated(self):
        assert "pe" in self.cfg.particles

    def test_cconjs_populated(self):
        assert "na" in self.cfg.cconjs

    def test_sconjs_populated(self):
        assert "kuti" in self.cfg.sconjs

    def test_adverbs_populated(self):
        assert "lyonse" in self.cfg.adverbs

    def test_ideophones_populated(self):
        assert "pyu" in self.cfg.ideophones

    def test_copula_forms_populated(self):
        assert "ndi" in self.cfg.copula_forms

    def test_nc_number_odd_singular_even_plural(self):
        # NC3 (odd) → Sing; NC4 (even) → Plur via fallback heuristic
        assert "sing" in self.cfg.nc_number.get("NC3", "sing").lower()
        assert "plur" in self.cfg.nc_number.get("NC4", "plur").lower()

    def test_sm_pn_populated_for_explicit_person(self):
        # 1SG has person=1, number=Sing in mock grammar
        pn = self.cfg.sm_pn.get("1SG")
        assert pn is not None
        assert pn.get("Person") == "1"
        assert pn.get("Number") == "Sing"


# G2 — _infer_tam_ud (7 tests)
# --------------------------------------------------------------------------

class TestInferTamUd:

    def test_past_keyword_gives_past_tense(self):
        result = _infer_tam_ud("PAST_HOD", {})
        assert result.get("Tense") == "Past"

    def test_pres_keyword_gives_pres_tense(self):
        result = _infer_tam_ud("PRES_HAB", {})
        assert result.get("Tense") == "Pres"

    def test_fut_keyword_gives_fut_tense(self):
        result = _infer_tam_ud("FUT_NEAR", {})
        assert result.get("Tense") == "Fut"

    def test_perf_keyword_gives_perf_aspect(self):
        result = _infer_tam_ud("PERF", {})
        assert result.get("Aspect") == "Perf"

    def test_subj_keyword_gives_sub_mood(self):
        result = _infer_tam_ud("SUBJ", {})
        assert result.get("Mood") == "Sub"

    def test_default_mood_ind_when_tense_found(self):
        # If tense matched but no mood keyword → default Ind
        result = _infer_tam_ud("PAST", {})
        assert result.get("Mood") == "Ind"

    def test_explicit_ud_fields_override_inference(self):
        cfg = _build_config(MockLoader())
        # EXPLICIT_UD in mock has ud_tense/aspect/mood
        result = cfg.tam_ud.get("EXPLICIT_UD", {})
        assert result.get("Tense") == "Past"
        assert result.get("Aspect") == "Perf"
        assert result.get("Mood") == "Ind"


# G3 — _infer_fv_verbform (5 tests)
# --------------------------------------------------------------------------

class TestInferFvVerbform:

    def test_infinitive_key_gives_inf(self):
        assert _infer_fv_verbform("infinitive", {}) == "Inf"

    def test_subjunctive_key_gives_sub(self):
        assert _infer_fv_verbform("subjunctive", {}) == "Sub"

    def test_gerund_key_gives_ger(self):
        assert _infer_fv_verbform("gerund_form", {}) == "Ger"

    def test_relative_key_gives_part(self):
        assert _infer_fv_verbform("relative_clause", {}) == "Part"

    def test_unknown_key_defaults_fin(self):
        assert _infer_fv_verbform("indicative", {}) == "Fin"


# G4 — _ext_to_voice (4 tests)
# --------------------------------------------------------------------------

class TestExtToVoice:

    def test_pass_gives_pass(self):
        assert _ext_to_voice("PASS") == "Pass"

    def test_caus_gives_cau(self):
        assert _ext_to_voice("CAUS") == "Cau"

    def test_recip_gives_mid(self):
        assert _ext_to_voice("RECIP") == "Mid"

    def test_appl_gives_none(self):
        assert _ext_to_voice("APPL") is None


# G5 — _build_verb_feats (8 tests)
# --------------------------------------------------------------------------

class TestBuildVerbFeats:

    def setup_method(self):
        self.loader = MockLoader()
        self.cfg = _build_config(self.loader)

    def test_person_number_from_sm(self):
        tok = _verb_token(sm_nc="1SG")
        feats = _build_verb_feats(tok, tok.best_slot_parse, self.cfg)
        assert feats.get("Person") == "1"
        assert feats.get("Number") == "Sing"

    def test_verbform_defaults_fin(self):
        tok = _verb_token()
        feats = _build_verb_feats(tok, tok.best_slot_parse, self.cfg)
        assert feats.get("VerbForm") == "Fin"

    def test_subjunctive_fv_gives_sub_verbform(self):
        tok = _verb_token(fv_key="subjunctive")
        feats = _build_verb_feats(tok, tok.best_slot_parse, self.cfg)
        assert feats.get("VerbForm") == "Sub"

    def test_infinitive_fv_gives_inf_verbform(self):
        tok = _verb_token(fv_key="infinitive")
        feats = _build_verb_feats(tok, tok.best_slot_parse, self.cfg)
        assert feats.get("VerbForm") == "Inf"

    def test_negation_slot1_sets_polarity_neg(self):
        tok = _verb_token(neg=True)
        feats = _build_verb_feats(tok, tok.best_slot_parse, self.cfg)
        assert feats.get("Polarity") == "Neg"

    def test_pass_extension_sets_voice_pass(self):
        tok = _verb_token(ext_key="PASS")
        feats = _build_verb_feats(tok, tok.best_slot_parse, self.cfg)
        assert feats.get("Voice") == "Pass"

    def test_caus_extension_sets_voice_cau(self):
        tok = _verb_token(ext_key="CAUS")
        feats = _build_verb_feats(tok, tok.best_slot_parse, self.cfg)
        assert feats.get("Voice") == "Cau"

    def test_phase2_feats_merged_at_lower_priority(self):
        tok = _verb_token()
        tok.feats["CustomFeat"] = "CustomVal"
        feats = _build_verb_feats(tok, tok.best_slot_parse, self.cfg)
        # Phase 2 custom feat preserved
        assert feats.get("CustomFeat") == "CustomVal"


# G6 — _build_noun_feats (4 tests)
# --------------------------------------------------------------------------

class TestBuildNounFeats:

    def setup_method(self):
        self.cfg = _build_config(MockLoader())

    def test_nc3_gives_sing_number(self):
        tok = _noun_token(nc="NC3")
        feats = _build_noun_feats(tok, self.cfg)
        assert feats.get("NounClass") == "NC3"
        # NC3 is odd → Sing
        assert feats.get("Number", "Sing").startswith("S")

    def test_nc4_gives_plur_number(self):
        tok = _noun_token(nc="NC4")
        feats = _build_noun_feats(tok, self.cfg)
        assert feats.get("Number", "Plur").startswith("P")

    def test_noun_class_key_set(self):
        tok = _noun_token(nc="NC7")
        feats = _build_noun_feats(tok, self.cfg)
        assert feats.get("NounClass") == "NC7"

    def test_phase2_feats_merged(self):
        tok = _noun_token()
        tok.feats["ExtraFeat"] = "ExtraVal"
        feats = _build_noun_feats(tok, self.cfg)
        assert feats.get("ExtraFeat") == "ExtraVal"


# G7 — _build_xpos (5 tests)
# --------------------------------------------------------------------------

class TestBuildXpos:

    def test_verb_xpos_starts_verb(self):
        tok = _verb_token(pre_tagged=True)
        tok.feats = {"VerbForm": "Fin"}
        xpos = _build_xpos(tok, POSTag.VERB, tok.best_slot_parse)
        assert xpos.startswith("VERB")

    def test_verb_xpos_contains_fin(self):
        tok = _verb_token()
        tok.feats = {"VerbForm": "Fin"}
        xpos = _build_xpos(tok, POSTag.VERB, tok.best_slot_parse)
        assert "FIN" in xpos

    def test_verb_xpos_contains_sm_nc(self):
        tok = _verb_token(sm_nc="NC3")
        tok.feats = {"VerbForm": "Fin"}
        xpos = _build_xpos(tok, POSTag.VERB, tok.best_slot_parse)
        assert "NC3" in xpos

    def test_noun_xpos_contains_nc(self):
        tok = _noun_token(nc="NC7")
        tok.feats = {}
        xpos = _build_xpos(tok, POSTag.NOUN, None)
        assert "NC7" in xpos

    def test_noun_xpos_without_nc(self):
        tok = WordToken(form="xyz", lang_iso="toi", token_type=TokenType.WORD)
        xpos = _build_xpos(tok, POSTag.NOUN, None)
        assert xpos == "NOUN"


# G8 — _assign_shallow_deprel (4 tests)
# --------------------------------------------------------------------------

class TestAssignShallowDeprel:

    def setup_method(self):
        self.cfg = _build_config(MockLoader())

    def _tokens_with_upos(self, *pairs):
        toks = []
        for i, (form, upos, xpos) in enumerate(pairs, 1):
            t = WordToken(token_id=str(i), form=form, lang_iso="toi",
                          token_type=TokenType.WORD, upos=upos, xpos=xpos)
            toks.append(t)
        return toks

    def test_punct_gets_punct_deprel(self):
        toks = self._tokens_with_upos((".", POSTag.PUNCT, "PUNCT"))
        _assign_shallow_deprel(toks, self.cfg)
        assert toks[0].deprel == "punct"

    def test_num_gets_nummod_deprel(self):
        toks = self._tokens_with_upos(("3", POSTag.NUM, "NUM"))
        _assign_shallow_deprel(toks, self.cfg)
        assert toks[0].deprel == "nummod"

    def test_neg_gets_neg_deprel(self):
        toks = self._tokens_with_upos(("pe", POSTag.NEG, "NEG"))
        _assign_shallow_deprel(toks, self.cfg)
        assert toks[0].deprel == "neg"

    def test_cop_aux_gets_cop_deprel(self):
        toks = self._tokens_with_upos(("ndi", POSTag.AUX, "AUX.COP"))
        _assign_shallow_deprel(toks, self.cfg)
        assert toks[0].deprel == "cop"


# G9 — _upos_from_slot_parse (5 tests)
# --------------------------------------------------------------------------

class TestUposFromSlotParse:

    def setup_method(self):
        self.tagger = _tagger()

    def test_sm_plus_root_gives_verb(self):
        tok = _verb_token()
        upos = self.tagger._upos_from_slot_parse(tok.best_slot_parse, tok)
        assert upos == POSTag.VERB

    def test_copula_root_gives_aux(self):
        # Root "ndi" is in copula_roots
        tok = _verb_token(root="ndi")
        upos = self.tagger._upos_from_slot_parse(tok.best_slot_parse, tok)
        assert upos == POSTag.AUX

    def test_nc15_prefix_morpheme_gives_verb(self):
        tok = WordToken(form="kubona", lang_iso="toi", token_type=TokenType.WORD)
        sp = SlotParse(lang_iso="toi", analyser_version="2.0.0", score=0.50)
        sp.set("SLOT5", SlotFill(form="bon", gloss="see", source_rule="LEX:bon",
                                  confidence=ConfidenceLevel.HIGH, start=2, end=5))
        tok.add_slot_parse(sp)
        tok.add_morpheme_span(MorphemeSpan(0, 2, "ku", "NC_PREFIX", "NC15"))
        upos = self.tagger._upos_from_slot_parse(sp, tok)
        assert upos == POSTag.VERB

    def test_tam_plus_root_no_sm_gives_verb(self):
        tok = _verb_token()
        # Remove SM from slot parse
        sp = tok.best_slot_parse
        sp.slots.pop("SLOT2", None)
        sp.set("SLOT3", SlotFill(form="ka", gloss="PST", source_rule="PAST",
                                  confidence=ConfidenceLevel.HIGH, start=0, end=2))
        upos = self.tagger._upos_from_slot_parse(sp, tok)
        assert upos == POSTag.VERB

    def test_root_only_no_sm_no_tam_gives_noun(self):
        sp = SlotParse(lang_iso="toi", analyser_version="2.0.0", score=0.30)
        sp.set("SLOT5", SlotFill(form="bon", gloss="see", source_rule="LEX:bon",
                                  confidence=ConfidenceLevel.HIGH, start=0, end=3))
        tok = WordToken(form="bon", lang_iso="toi", token_type=TokenType.WORD)
        tok.add_slot_parse(sp)
        upos = self.tagger._upos_from_slot_parse(sp, tok)
        assert upos == POSTag.NOUN


# G10 — _surface_heuristics (3 tests)
# --------------------------------------------------------------------------

class TestSurfaceHeuristics:

    def setup_method(self):
        self.tagger = _tagger()

    def test_digit_gives_num(self):
        tok = WordToken(form="42", lang_iso="toi", token_type=TokenType.WORD)
        result = self.tagger._surface_heuristics(tok)
        assert result == POSTag.NUM

    def test_single_non_alpha_gives_punct(self):
        tok = WordToken(form="!", lang_iso="toi", token_type=TokenType.WORD)
        result = self.tagger._surface_heuristics(tok)
        assert result == POSTag.PUNCT

    def test_short_vowel_only_gives_part(self):
        tok = WordToken(form="a", lang_iso="toi", token_type=TokenType.WORD)
        result = self.tagger._surface_heuristics(tok)
        assert result == POSTag.PART


# G11 — _tag_token — all priority branches (8 tests)
# --------------------------------------------------------------------------

class TestTagTokenBranches:

    def setup_method(self):
        self.tagger = _tagger()

    def test_branch1_punct_token(self):
        tok = WordToken(form=".", lang_iso="toi", token_type=TokenType.PUNCT)
        self.tagger._tag_token(tok)
        assert tok.upos == POSTag.PUNCT
        assert tok.xpos == "PUNCT"

    def test_branch1_number_token(self):
        tok = WordToken(form="42", lang_iso="toi", token_type=TokenType.NUMBER)
        self.tagger._tag_token(tok)
        assert tok.upos == POSTag.NUM

    def test_branch1_code_switch_token(self):
        tok = WordToken(form="hello", lang_iso="toi", token_type=TokenType.CODE_SWITCH)
        self.tagger._tag_token(tok)
        assert tok.upos == POSTag.X
        assert tok.xpos == "X.CS"

    def test_branch2_trusts_verb_analysed_flag(self):
        tok = _verb_token(pre_tagged=True)  # has VERB_ANALYSED + upos=VERB
        self.tagger._tag_token(tok)
        assert "TAGGED_V2" in tok.flags
        assert tok.upos == POSTag.VERB

    def test_branch3_trusts_noun_analysed_flag(self):
        tok = _noun_token(pre_tagged=True)  # has NOUN_ANALYSED + upos=NOUN
        self.tagger._tag_token(tok)
        assert "TAGGED_N2" in tok.flags
        assert tok.upos == POSTag.NOUN

    def test_branch4_closed_class_lookup(self):
        tok = WordToken(form="na", lang_iso="toi", token_type=TokenType.WORD)
        self.tagger._tag_token(tok)
        assert tok.upos == POSTag.CCONJ
        assert "TAGGED_CLOSED" in tok.flags

    def test_branch5_slot_parse_based_tagging(self):
        # overwrite_upos=True forces slot-parse path even if pre-tagged
        tagger = _tagger(overwrite=True)
        tok = _verb_token(pre_tagged=False)
        tagger._tag_token(tok)
        assert tok.upos in (POSTag.VERB, POSTag.AUX)
        assert "TAGGED_SLOT" in tok.flags

    def test_branch6_noun_class_fallback(self):
        # No slot parse, no flags, but noun_class set
        tok = _noun_token(nc="NC7", pre_tagged=False)
        self.tagger._tag_token(tok)
        assert tok.upos == POSTag.NOUN
        assert "TAGGED_NC" in tok.flags


# G12 — _refine_context / Pass 3 (4 tests)
# --------------------------------------------------------------------------

class TestRefineContext:

    def setup_method(self):
        self.tagger = _tagger()

    def test_clitic_inherits_host_upos(self):
        host = WordToken(token_id="1", form="ubona", lang_iso="toi",
                         token_type=TokenType.WORD, upos=POSTag.VERB)
        clitic = WordToken(token_id="2", form="mo", lang_iso="toi",
                           token_type=TokenType.CLITIC, upos=None,
                           clitic_of="1")
        self.tagger._refine_context([host, clitic])
        assert clitic.upos == POSTag.VERB
        assert "UPOS_CLITIC_INHERIT" in clitic.flags

    def test_ideophone_gets_adv_upos_and_ideoph_xpos(self):
        tok = WordToken(token_id="1", form="pyu", lang_iso="toi",
                        token_type=TokenType.WORD, upos=POSTag.NOUN)
        self.tagger._refine_context([tok])
        assert tok.upos == POSTag.ADV
        assert tok.xpos == "IDEOPH"

    def test_copula_form_gets_cop_xpos(self):
        tok = WordToken(token_id="1", form="ndi", lang_iso="toi",
                        token_type=TokenType.WORD, upos=POSTag.AUX,
                        xpos="AUX")  # not yet COP
        self.tagger._refine_context([tok])
        assert tok.xpos == "AUX.COP"

    def test_non_clitic_token_not_affected_by_clitic_rule(self):
        tok = WordToken(token_id="1", form="muti", lang_iso="toi",
                        token_type=TokenType.WORD, upos=POSTag.NOUN)
        self.tagger._refine_context([tok])
        assert "UPOS_CLITIC_INHERIT" not in tok.flags
        assert tok.upos == POSTag.NOUN


# =============================================================================
# Phase 5 — annotation_pipeline.py
# =============================================================================

# G13 — _iter_txt (4 tests)
# --------------------------------------------------------------------------

class TestIterTxt:

    def test_yields_sent_id_and_text(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Bakali balima.\nMuntu abona.\n", encoding="utf-8")
        results = list(_iter_txt(f))
        assert len(results) == 2
        assert all(isinstance(sid, str) and isinstance(text, str)
                   for sid, text in results)

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Line one.\n\n   \nLine two.\n", encoding="utf-8")
        results = list(_iter_txt(f))
        assert len(results) == 2

    def test_sent_id_includes_filename_stem(self, tmp_path):
        f = tmp_path / "genesis.txt"
        f.write_text("In the beginning.\n", encoding="utf-8")
        results = list(_iter_txt(f))
        assert "genesis" in results[0][0]

    def test_sent_id_is_zero_padded(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("First.\n", encoding="utf-8")
        results = list(_iter_txt(f))
        sid = results[0][0]
        # Line number should be 6-digit padded
        assert sid.split("-")[-1] == "000001"


# G14 — _iter_gcbt_json (5 tests)
# --------------------------------------------------------------------------

class TestIterGcbtJson:

    def _write_json(self, tmp_path, data):
        f = tmp_path / "corpus.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        return f

    def test_canonical_gcbt_format(self, tmp_path):
        data = {
            "language_iso": "toi",
            "sentences": [
                {"sent_id": "toi-001", "text": "Bakali balima."},
                {"sent_id": "toi-002", "text": "Muntu abona."},
            ],
        }
        f = self._write_json(tmp_path, data)
        results = list(_iter_gcbt_json(f))
        assert len(results) == 2
        assert results[0] == ("toi", "toi-001", "Bakali balima.")

    def test_array_format_uses_und_lang(self, tmp_path):
        data = [{"sent_id": "s1", "text": "Hello."}]
        f = self._write_json(tmp_path, data)
        results = list(_iter_gcbt_json(f))
        assert results[0][0] == "und"

    def test_lang_iso_alternative_key(self, tmp_path):
        data = {"lang_iso": "bem", "sentences": [{"text": "Bakali."}]}
        f = self._write_json(tmp_path, data)
        results = list(_iter_gcbt_json(f))
        assert results[0][0] == "bem"

    def test_skips_empty_text(self, tmp_path):
        data = {"language_iso": "toi", "sentences": [
            {"sent_id": "s1", "text": ""},
            {"sent_id": "s2", "text": "   "},
            {"sent_id": "s3", "text": "Good text."},
        ]}
        f = self._write_json(tmp_path, data)
        results = list(_iter_gcbt_json(f))
        assert len(results) == 1

    def test_id_field_alternative(self, tmp_path):
        data = {"language_iso": "toi", "sentences": [{"id": "alt-001", "text": "Text."}]}
        f = self._write_json(tmp_path, data)
        results = list(_iter_gcbt_json(f))
        assert results[0][1] == "alt-001"


# G15 — _iter_gcbt_jsonl (4 tests)
# --------------------------------------------------------------------------

class TestIterGcbtJsonl:

    def _write_jsonl(self, tmp_path, lines):
        f = tmp_path / "corpus.jsonl"
        f.write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")
        return f

    def test_yields_lang_sent_id_text(self, tmp_path):
        f = self._write_jsonl(tmp_path, [
            {"lang_iso": "toi", "sent_id": "toi-001", "text": "Bakali balima."},
        ])
        results = list(_iter_gcbt_jsonl(f))
        assert results[0] == ("toi", "toi-001", "Bakali balima.")

    def test_skips_corpus_header_lines(self, tmp_path):
        f = self._write_jsonl(tmp_path, [
            {"_type": "corpus_header", "lang_iso": "toi"},
            {"lang_iso": "toi", "sent_id": "s1", "text": "Text."},
        ])
        results = list(_iter_gcbt_jsonl(f))
        assert len(results) == 1

    def test_skips_hash_comment_lines(self, tmp_path):
        f = tmp_path / "corpus.jsonl"
        f.write_text('# comment\n{"lang_iso":"toi","sent_id":"s1","text":"Hi."}\n',
                     encoding="utf-8")
        results = list(_iter_gcbt_jsonl(f))
        assert len(results) == 1

    def test_skips_malformed_json_lines(self, tmp_path):
        f = tmp_path / "corpus.jsonl"
        f.write_text('not-json\n{"lang_iso":"toi","sent_id":"s1","text":"Good."}\n',
                     encoding="utf-8")
        results = list(_iter_gcbt_jsonl(f))
        assert len(results) == 1


# G16 — _collect_input_files (3 tests)
# --------------------------------------------------------------------------

class TestCollectInputFiles:

    def test_single_file_returned(self, tmp_path):
        f = tmp_path / "corpus.txt"
        f.write_text("text\n", encoding="utf-8")
        result = _collect_input_files(f)
        assert result == [f]

    def test_directory_finds_txt_json_jsonl(self, tmp_path):
        (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
        (tmp_path / "b.json").write_text("{}\n", encoding="utf-8")
        (tmp_path / "c.jsonl").write_text("{}\n", encoding="utf-8")
        (tmp_path / "d.csv").write_text("x,y\n", encoding="utf-8")
        result = _collect_input_files(tmp_path)
        suffixes = {f.suffix for f in result}
        assert ".txt" in suffixes
        assert ".json" in suffixes
        assert ".jsonl" in suffixes
        assert ".csv" not in suffixes

    def test_empty_directory_returns_empty_list(self, tmp_path):
        result = _collect_input_files(tmp_path)
        assert result == []


# G17 — _batches (3 tests)
# --------------------------------------------------------------------------

class TestBatches:

    def test_even_batches(self):
        items = list(range(6))
        result = list(_batches(items, 2))
        assert result == [[0, 1], [2, 3], [4, 5]]

    def test_trailing_partial_batch(self):
        items = list(range(5))
        result = list(_batches(items, 2))
        assert result[-1] == [4]

    def test_empty_input_yields_nothing(self):
        assert list(_batches([], 10)) == []


# G18 — PipelineStats (5 tests)
# --------------------------------------------------------------------------

class TestPipelineStats:

    def test_sentences_per_second_zero_on_no_elapsed(self):
        s = PipelineStats(lang_iso="toi", sentences_written=100)
        assert s.sentences_per_second() == 0.0

    def test_sentences_per_second_computed(self):
        s = PipelineStats(lang_iso="toi", sentences_written=100,
                          elapsed_seconds=10.0)
        assert s.sentences_per_second() == 10.0

    def test_to_dict_contains_required_keys(self):
        s = PipelineStats(lang_iso="toi")
        d = s.to_dict()
        for key in ("lang_iso", "sentences_written", "sentences_total",
                    "tokens_total", "elapsed_seconds", "sentences_per_sec",
                    "files_processed", "errors"):
            assert key in d

    def test_repr_contains_lang(self):
        s = PipelineStats(lang_iso="bem", sentences_written=5,
                          sentences_total=5, elapsed_seconds=1.0)
        assert "bem" in repr(s)

    def test_errors_list_starts_empty(self):
        s = PipelineStats()
        assert s.errors == []


# G19 — GobeloAnnotationPipeline.run_sentence (4 tests)
# --------------------------------------------------------------------------

class TestRunSentence:

    def setup_method(self):
        self.pipeline = GobeloAnnotationPipeline(loader=MockLoader())

    def test_returns_annotated_sentence(self):
        result = self.pipeline.run_sentence("Bakali balima.")
        assert isinstance(result, AnnotatedSentence)

    def test_sent_id_override(self):
        result = self.pipeline.run_sentence("Muntu abona.", sent_id="custom-001")
        assert result.sent_id == "custom-001"

    def test_tokens_not_empty(self):
        result = self.pipeline.run_sentence("Bakali balima.")
        assert len(result.tokens) > 0

    def test_pipeline_stages_recorded(self):
        result = self.pipeline.run_sentence("Bakali balima.")
        # At minimum the tagger stage should be registered
        assert any("GobeloPOSTagger" in s for s in result.pipeline)


# G20 — GobeloAnnotationPipeline.run (6 tests)
# --------------------------------------------------------------------------

class TestPipelineRun:

    def setup_method(self):
        self.pipeline = GobeloAnnotationPipeline(loader=MockLoader(), batch_size=5)

    def test_run_on_txt_file_produces_output(self, tmp_path):
        inp = tmp_path / "corpus.txt"
        inp.write_text("Bakali balima.\nMuntu abona.\n", encoding="utf-8")
        stats = self.pipeline.run(inp, tmp_path, lang_iso="toi")
        assert stats.sentences_written == 2
        assert stats.tokens_total >= 2

    def test_run_on_json_file(self, tmp_path):
        inp = tmp_path / "corpus.json"
        inp.write_text(json.dumps({
            "language_iso": "toi",
            "sentences": [
                {"sent_id": "s1", "text": "Bakali balima."},
                {"sent_id": "s2", "text": "Muntu abona."},
            ]
        }), encoding="utf-8")
        stats = self.pipeline.run(inp, tmp_path, lang_iso="toi")
        assert stats.sentences_written == 2

    def test_run_on_jsonl_file(self, tmp_path):
        inp = tmp_path / "corpus.jsonl"
        lines = [
            {"lang_iso": "toi", "sent_id": "s1", "text": "Bakali balima."},
            {"lang_iso": "toi", "sent_id": "s2", "text": "Muntu abona."},
        ]
        inp.write_text("\n".join(json.dumps(l) for l in lines) + "\n",
                       encoding="utf-8")
        stats = self.pipeline.run(inp, tmp_path, lang_iso="toi")
        assert stats.sentences_written == 2

    def test_output_files_created(self, tmp_path):
        inp = tmp_path / "corpus.txt"
        inp.write_text("Bakali balima.\n", encoding="utf-8")
        self.pipeline.run(inp, tmp_path, lang_iso="toi")
        jsonl = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        conllu = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        assert jsonl.exists()
        assert conllu.exists()

    def test_stats_sidecar_written(self, tmp_path):
        inp = tmp_path / "corpus.txt"
        inp.write_text("Bakali balima.\n", encoding="utf-8")
        self.pipeline.run(inp, tmp_path, lang_iso="toi")
        stats_file = tmp_path / "toi" / "annotations" / "toi_pipeline_run.json"
        assert stats_file.exists()
        data = json.loads(stats_file.read_text())
        assert data["sentences_written"] == 1

    def test_empty_directory_returns_zero_sentences(self, tmp_path):
        stats = self.pipeline.run(tmp_path, tmp_path / "out", lang_iso="toi")
        assert stats.sentences_written == 0
        assert stats.files_processed == 0


# =============================================================================
# Runner
# =============================================================================

if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "--tb=short"])
