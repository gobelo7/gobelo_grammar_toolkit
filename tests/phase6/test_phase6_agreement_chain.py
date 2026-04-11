"""
test_phase6_agreement_chain.py — GobeloAgreementChain test suite
================================================================
57 tests across 7 groups:

  Group 1  · _ResolverConfig construction        ( 8 tests)
  Group 2  · NC extraction helpers               ( 8 tests)
  Group 3  · NC inventory (Pass 1)               ( 7 tests)
  Group 4  · Subject-chain resolution (Pass 2)   (12 tests)
  Group 5  · Object-chain resolution (Pass 3)    ( 8 tests)
  Group 6  · Modifier agreement (Pass 4)         ( 7 tests)
  Group 7  · Integration / annotation output     ( 7 tests)
"""

import sys
sys.path.insert(0, "/home/claude")

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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
from agreement_chain import (
    GobeloAgreementChain,
    VERSION,
    _NCSighting,
    _AgreementLink,
    _ResolverConfig,
    _build_resolver_config,
    _nc_from_source_rule,
    _nc_from_gloss,
    _get_sm_nc,
    _get_om_nc,
    _get_modifier_nc,
    _chain_score,
    _HUMAN_NCS,
    _LOCATIVE_NCS,
)


# ---------------------------------------------------------------------------
# Mock loader
# ---------------------------------------------------------------------------

class MockLoader:
    lang_iso = "toi"

    def get(self, key: str, default: Any = None) -> Any:
        return _MOCK_GRAMMAR.get(key, default)


_MOCK_GRAMMAR: Dict[str, Any] = {
    "morphology.noun_classes": {
        "NC1": {
            "prefix": {"canonical_form": "mu-"},
            "grammatical_number": "singular",
            "semantics": {"features": ["+human", "+animate", "+singular"]},
        },
        "NC2": {
            "prefix": {"canonical_form": "ba-"},
            "grammatical_number": "plural",
            "semantics": {"features": ["+human", "+animate", "+plural"]},
        },
        "NC3": {
            "prefix": {"canonical_form": "mu-"},
            "grammatical_number": "singular",
            "semantics": {"features": ["-human", "+singular"]},
        },
        "NC4": {
            "prefix": {"canonical_form": "mi-"},
            "grammatical_number": "plural",
            "semantics": {"features": ["-human", "+plural"]},
        },
        "NC7": {
            "prefix": {"canonical_form": "ci-"},
            "grammatical_number": "singular",
            "semantics": {"features": ["-human", "+singular"]},
        },
        "NC9": {
            "prefix": {"canonical_form": "N-"},
            "grammatical_number": "singular",
            "semantics": {"features": ["-human", "+singular"]},
        },
        "NC14": {
            "prefix": {"canonical_form": "bu-"},
            "grammatical_number": "singular",
        },
        "NC15": {
            "prefix": {"canonical_form": "ku-"},
            "grammatical_number": "singular",
        },
        "NC16": {
            "prefix": {"canonical_form": "pa-"},
            "class_type": "locative",
        },
    },
    "morphology.subject_markers": {
        "NC1": {"form": "a",  "gloss": "CL1.SM",  "person": "3", "number": "singular"},
        "NC2": {"form": "ba", "gloss": "CL2.SM",  "person": "3", "number": "plural"},
        "NC3": {"form": "u",  "gloss": "CL3.SM",  "person": "3", "number": "singular"},
        "NC7": {"form": "ci", "gloss": "CL7.SM",  "person": "3", "number": "singular"},
        "NC9": {"form": "i",  "gloss": "CL9.SM",  "person": "3", "number": "singular"},
        "1SG": {"form": "ndi","gloss": "1SG.SM",  "person": "1", "number": "singular"},
        "2SG": {"form": "u",  "gloss": "2SG.SM",  "person": "2", "number": "singular"},
        "3PL_HUMAN": {"form": "ba","gloss": "3PL.SM","person": "3","number": "plural"},
    },
    "morphology.object_markers": {
        "NC1": {"form": "mu", "gloss": "CL1.OM"},
        "NC3": {"form": "u",  "gloss": "CL3.OM"},
        "NC7": {"form": "ci", "gloss": "CL7.OM"},
        "NC9": {"form": "i",  "gloss": "CL9.OM"},
    },
}


# ---------------------------------------------------------------------------
# Token / sentence factories
# ---------------------------------------------------------------------------

def _make_slot_parse_with_sm(
    sm_nc: str = "NC3",
    om_nc: Optional[str] = None,
    root: str = "bon",
    score: float = 0.65,
) -> SlotParse:
    sp = SlotParse(lang_iso="toi", analyser_version="2.0.0", score=score)
    sp.set("SLOT2", SlotFill(
        form="a", gloss=f"CL{sm_nc[2:]}.SM",
        source_rule=f"SM.{sm_nc}",
        confidence=ConfidenceLevel.HIGH, start=0, end=1,
    ))
    if om_nc:
        sp.set("SLOT4", SlotFill(
            form="ci", gloss=f"CL{om_nc[2:]}.OM",
            source_rule=f"OM.{om_nc}",
            confidence=ConfidenceLevel.HIGH, start=1, end=3,
        ))
    sp.set("SLOT5", SlotFill(
        form=root, gloss=root,
        source_rule=f"LEX:{root}",
        confidence=ConfidenceLevel.HIGH, start=3, end=3 + len(root),
    ))
    sp.set("SLOT10", SlotFill(
        form="a", gloss="FV.IND", source_rule="indicative",
        confidence=ConfidenceLevel.HIGH, start=3 + len(root), end=4 + len(root),
    ))
    return sp


def _make_noun_tok(
    token_id: str,
    form: str,
    nc: str,
    with_lexicon: bool = True,
) -> WordToken:
    tok = WordToken(
        token_id=token_id,
        form=form,
        lang_iso="toi",
        token_type=TokenType.WORD,
        upos=POSTag.NOUN,
        xpos=f"NOUN.{nc}",
        noun_class=nc,
        feats={"NounClass": nc, "Number": "Sing"},
        char_start=0,
        char_end=len(form),
    )
    tok.add_morpheme_span(MorphemeSpan(0, 2, form[:2], "NC_PREFIX", nc))
    tok.add_flag("NOUN_ANALYSED")
    tok.is_oov = not with_lexicon
    if with_lexicon:
        entry = LexiconEntry(
            lang_iso="toi", category=LexiconCategory.NOUN,
            root=form[2:], gloss="test noun", noun_class=nc,
        )
        tok.add_lexicon_match(entry)
    return tok


def _make_verb_tok(
    token_id: str,
    form: str,
    sm_nc: str = "NC3",
    om_nc: Optional[str] = None,
    score: float = 0.65,
) -> WordToken:
    tok = WordToken(
        token_id=token_id,
        form=form,
        lang_iso="toi",
        token_type=TokenType.WORD,
        upos=POSTag.VERB,
        xpos=f"VERB.FIN.SM{sm_nc}",
        feats={"VerbForm": "Fin", "Tense": "Pres"},
        char_start=0,
        char_end=len(form),
    )
    sp = _make_slot_parse_with_sm(sm_nc=sm_nc, om_nc=om_nc, score=score)
    tok.add_slot_parse(sp)
    tok.add_flag("VERB_ANALYSED")
    tok.add_flag("TAGGED_V2")
    tok.is_oov = False
    return tok


def _make_adj_tok(
    token_id: str,
    form: str,
    nc: str,
) -> WordToken:
    tok = WordToken(
        token_id=token_id,
        form=form,
        lang_iso="toi",
        token_type=TokenType.WORD,
        upos=POSTag.ADJ,
        xpos=f"ADJ.{nc}",
        noun_class=nc,
        char_start=0,
        char_end=len(form),
    )
    tok.add_morpheme_span(MorphemeSpan(0, 2, form[:2], "NC_PREFIX", nc))
    return tok


def _make_sentence(
    tokens: List[WordToken],
    sent_id: str = "toi-test-001",
) -> AnnotatedSentence:
    sent = AnnotatedSentence(
        sent_id=sent_id,
        text=" ".join(t.form for t in tokens),
        lang_iso="toi",
        tokens=tokens,
    )
    for i, t in enumerate(tokens, 1):
        t.token_id = str(i)
    return sent


# ---------------------------------------------------------------------------
# Group 1 — _ResolverConfig construction (8 tests)
# ---------------------------------------------------------------------------

class TestResolverConfig:

    def setup_method(self):
        self.loader = MockLoader()
        self.cfg = _build_resolver_config(self.loader)

    def test_lang_iso_set(self):
        assert self.cfg.lang_iso == "toi"

    def test_active_ncs_populated(self):
        assert "NC1" in self.cfg.active_ncs
        assert "NC7" in self.cfg.active_ncs

    def test_human_ncs_includes_nc1_nc2(self):
        assert "NC1" in self.cfg.human_ncs
        assert "NC2" in self.cfg.human_ncs

    def test_non_human_nc_not_in_human_ncs(self):
        # NC7 has no +human feature in mock grammar
        assert "NC7" not in self.cfg.human_ncs

    def test_nc_number_singular_for_nc1(self):
        assert "sing" in self.cfg.nc_number.get("NC1", "").lower()

    def test_nc_number_plural_for_nc2(self):
        assert "plur" in self.cfg.nc_number.get("NC2", "").lower()

    def test_nc_number_fallback_odd_is_singular(self):
        # NC3 has grammatical_number = singular in mock
        assert "sing" in self.cfg.nc_number.get("NC3", "singular").lower()

    def test_nc_person_from_sm_data(self):
        # SM data has person=3 for NC1
        person = self.cfg.nc_person.get("NC1")
        assert person == "3"


# ---------------------------------------------------------------------------
# Group 2 — NC extraction helpers (8 tests)
# ---------------------------------------------------------------------------

class TestNcExtractionHelpers:

    def test_nc_from_source_rule_sm_nc3(self):
        assert _nc_from_source_rule("SM.NC3") == "NC3"

    def test_nc_from_source_rule_om_nc7(self):
        assert _nc_from_source_rule("OM.NC7") == "NC7"

    def test_nc_from_source_rule_handles_cl_prefix(self):
        assert _nc_from_source_rule("SM.CL9") == "NC9"

    def test_nc_from_source_rule_returns_none_for_lex(self):
        assert _nc_from_source_rule("LEX:bon") is None

    def test_nc_from_gloss_cl3_sm(self):
        assert _nc_from_gloss("CL3.SM") == "NC3"

    def test_nc_from_gloss_smnc2(self):
        assert _nc_from_gloss("SM.NC2") == "NC2"

    def test_get_sm_nc_from_slot_parse(self):
        sp = _make_slot_parse_with_sm(sm_nc="NC3")
        assert _get_sm_nc(sp) == "NC3"

    def test_get_om_nc_from_slot_parse(self):
        sp = _make_slot_parse_with_sm(sm_nc="NC1", om_nc="NC7")
        assert _get_om_nc(sp) == "NC7"


# ---------------------------------------------------------------------------
# Group 3 — NC inventory / Pass 1 (7 tests)
# ---------------------------------------------------------------------------

class TestNcInventory:

    def setup_method(self):
        self.resolver = GobeloAgreementChain(MockLoader())

    def test_noun_token_appears_in_inventory(self):
        noun = _make_noun_tok("1", "muntu", "NC1")
        sent = _make_sentence([noun])
        inv = self.resolver._build_nc_inventory(sent.tokens)
        assert any(s.nc_key == "NC1" for s in inv)

    def test_verb_token_without_noun_class_not_in_inventory(self):
        verb = _make_verb_tok("1", "abona", sm_nc="NC1")
        sent = _make_sentence([verb])
        # Verb has no noun_class; should not appear as a noun sighting
        # (unless its slot parse is penalised heavily)
        inv = self.resolver._build_nc_inventory(sent.tokens)
        # Either empty or very low score sighting
        high_score_sightings = [s for s in inv if s.score > 0.40]
        assert not high_score_sightings

    def test_locative_nc_excluded_from_inventory(self):
        loc_tok = WordToken(
            token_id="1", form="panshi", lang_iso="toi",
            token_type=TokenType.WORD, upos=POSTag.ADP,
            noun_class="NC16",
        )
        sent = _make_sentence([loc_tok])
        inv = self.resolver._build_nc_inventory(sent.tokens)
        assert not inv

    def test_multiple_nouns_all_sighted(self):
        n1 = _make_noun_tok("1", "muntu", "NC1")
        n2 = _make_noun_tok("2", "muti", "NC3")
        sent = _make_sentence([n1, n2])
        inv = self.resolver._build_nc_inventory(sent.tokens)
        nc_keys = {s.nc_key for s in inv}
        assert "NC1" in nc_keys
        assert "NC3" in nc_keys

    def test_lexicon_confirmed_noun_has_higher_score(self):
        n_lex = _make_noun_tok("1", "muntu", "NC1", with_lexicon=True)
        n_oov = _make_noun_tok("2", "xyz", "NC3",  with_lexicon=False)
        sent = _make_sentence([n_lex, n_oov])
        inv = self.resolver._build_nc_inventory(sent.tokens)
        lex_sighting = next(s for s in inv if s.nc_key == "NC1")
        oov_sighting = next(s for s in inv if s.nc_key == "NC3")
        assert lex_sighting.score > oov_sighting.score

    def test_human_nc_flagged_correctly(self):
        noun = _make_noun_tok("1", "bantu", "NC2")
        sent = _make_sentence([noun])
        inv = self.resolver._build_nc_inventory(sent.tokens)
        assert inv[0].is_human is True

    def test_punct_skipped_in_inventory(self):
        p = WordToken(token_id="1", form=".", lang_iso="toi",
                      token_type=TokenType.PUNCT, upos=POSTag.PUNCT)
        sent = _make_sentence([p])
        inv = self.resolver._build_nc_inventory(sent.tokens)
        assert not inv


# ---------------------------------------------------------------------------
# Group 4 — Subject-chain resolution (12 tests)
# ---------------------------------------------------------------------------

class TestSubjectChainResolution:

    def setup_method(self):
        self.resolver = GobeloAgreementChain(MockLoader(), min_score=0.10)

    def test_basic_subject_verb_agreement(self):
        """NC3 noun followed by NC3-SM verb → agreement confirmed."""
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert "AGREE_SUBJ_CONFIRMED" in verb.flags

    def test_subject_agreement_sets_agree_subj_misc(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert verb.misc.get("AgreeSubj") == noun.token_id

    def test_subject_agreement_sets_agree_verb_on_noun(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert noun.misc.get("AgreeVerb") == verb.token_id

    def test_agree_nc_set_on_both_tokens(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert verb.misc.get("AgreeNC") == "NC3"
        assert noun.misc.get("AgreeNC") == "NC3"

    def test_no_match_gives_unresolved_flag(self):
        """SM is NC7 but only NC3 noun in sentence → unresolved."""
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "cibona", sm_nc="NC7")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert "AGREE_SM_UNRESOLVED" in verb.flags

    def test_verb_without_slot_parse_not_processed(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = WordToken(
            token_id="2", form="ubona", lang_iso="toi",
            token_type=TokenType.WORD, upos=POSTag.VERB,
        )
        # No slot parse → should not crash; no flag set
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert "AGREE_SUBJ_CONFIRMED" not in verb.flags

    def test_post_verbal_noun_found_within_window(self):
        """Verb before noun (VSO order) — still within SM window."""
        verb = _make_verb_tok("1", "ubona", sm_nc="NC3")
        noun = _make_noun_tok("2", "muti", "NC3")
        sent = _make_sentence([verb, noun])
        self.resolver.resolve(sent)
        assert "AGREE_SUBJ_CONFIRMED" in verb.flags

    def test_noun_outside_window_not_matched(self):
        resolver = GobeloAgreementChain(MockLoader(), sm_window=1, min_score=0.05)
        # Place 5 filler tokens between noun and verb — beyond window=1
        filler = [
            WordToken(token_id=str(i), form=f"x{i}", lang_iso="toi",
                      token_type=TokenType.WORD, upos=POSTag.X)
            for i in range(2, 7)
        ]
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("7", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun] + filler + [verb])
        resolver.resolve(sent)
        assert "AGREE_SM_UNRESOLVED" in verb.flags

    def test_nearest_noun_preferred_over_distant(self):
        """Two NC3 nouns; nearest should be chosen."""
        n_near = _make_noun_tok("1", "muti", "NC3", with_lexicon=True)
        n_far  = _make_noun_tok("2", "muzi", "NC3", with_lexicon=True)
        verb   = _make_verb_tok("3", "ubona", sm_nc="NC3")
        sent = _make_sentence([n_near, n_far, verb])
        self.resolver.resolve(sent)
        # Should link to n_far (distance 1) not n_near (distance 2)
        linked_id = verb.misc.get("AgreeSubj")
        assert linked_id == n_far.token_id

    def test_human_nc_agreement_confirmed(self):
        noun = _make_noun_tok("1", "muntu", "NC1")
        verb = _make_verb_tok("2", "abona", sm_nc="NC1")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert "AGREE_SUBJ_CONFIRMED" in verb.flags

    def test_person_feature_set_from_nc_agreement(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        verb.feats.pop("Person", None)  # ensure not already set
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert verb.feats.get("Person") == "3"

    def test_number_feature_set_from_nc_agreement(self):
        noun = _make_noun_tok("1", "miti", "NC4")  # NC4 = plural
        verb = _make_verb_tok("2", "ibona", sm_nc="NC4")
        verb.feats.pop("Number", None)
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        # NC4 is plural in mock grammar
        assert verb.feats.get("Number") == "Plur"


# ---------------------------------------------------------------------------
# Group 5 — Object-chain resolution (8 tests)
# ---------------------------------------------------------------------------

class TestObjectChainResolution:

    def setup_method(self):
        self.resolver = GobeloAgreementChain(MockLoader(), min_score=0.10)

    def test_object_agreement_confirmed(self):
        """Verb with OM.NC7, followed by NC7 noun."""
        verb = _make_verb_tok("1", "acibon", sm_nc="NC1", om_nc="NC7")
        obj  = _make_noun_tok("2", "cintu", "NC7")
        sent = _make_sentence([verb, obj])
        self.resolver.resolve(sent)
        assert "AGREE_OBJ_CONFIRMED" in verb.flags

    def test_agree_obj_misc_set_on_verb(self):
        verb = _make_verb_tok("1", "acibon", sm_nc="NC1", om_nc="NC7")
        obj  = _make_noun_tok("2", "cintu", "NC7")
        sent = _make_sentence([verb, obj])
        self.resolver.resolve(sent)
        assert verb.misc.get("AgreeObj") == obj.token_id

    def test_agree_verb_obj_misc_set_on_noun(self):
        verb = _make_verb_tok("1", "acibon", sm_nc="NC1", om_nc="NC7")
        obj  = _make_noun_tok("2", "cintu", "NC7")
        sent = _make_sentence([verb, obj])
        self.resolver.resolve(sent)
        assert obj.misc.get("AgreeVerbObj") == verb.token_id

    def test_no_om_no_object_chain(self):
        """Verb without OM slot → no object chain attempted."""
        verb = _make_verb_tok("1", "abona", sm_nc="NC1")  # no om_nc
        noun = _make_noun_tok("2", "cintu", "NC7")
        sent = _make_sentence([verb, noun])
        self.resolver.resolve(sent)
        assert "AGREE_OBJ_CONFIRMED" not in verb.flags

    def test_om_mismatch_gives_unresolved_flag(self):
        verb = _make_verb_tok("1", "acibon", sm_nc="NC1", om_nc="NC7")
        noun = _make_noun_tok("2", "muti", "NC3")   # NC3, not NC7
        sent = _make_sentence([verb, noun])
        self.resolver.resolve(sent)
        assert "AGREE_OM_UNRESOLVED" in verb.flags

    def test_enhanced_dep_written_for_object(self):
        verb = _make_verb_tok("1", "acibon", sm_nc="NC1", om_nc="NC7")
        obj  = _make_noun_tok("2", "cintu", "NC7")
        sent = _make_sentence([verb, obj])
        self.resolver.resolve(sent)
        # obj token should have a deps entry pointing to verb
        assert any(deprel == "obj" for _, deprel in obj.deps)

    def test_topicalised_object_before_verb_also_matched(self):
        """Pre-verbal object (topicalised) within window."""
        obj  = _make_noun_tok("1", "cintu", "NC7")
        verb = _make_verb_tok("2", "acibon", sm_nc="NC1", om_nc="NC7")
        sent = _make_sentence([obj, verb])
        self.resolver.resolve(sent)
        assert "AGREE_OBJ_CONFIRMED" in verb.flags

    def test_chain_score_written_on_verb(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert "ChainScore" in verb.misc
        score = float(verb.misc["ChainScore"])
        assert 0.0 < score <= 1.0


# ---------------------------------------------------------------------------
# Group 6 — Modifier agreement (7 tests)
# ---------------------------------------------------------------------------

class TestModifierAgreement:

    def setup_method(self):
        self.resolver = GobeloAgreementChain(MockLoader(), min_score=0.10)

    def test_adjective_agrees_with_head_noun(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        adj  = _make_adj_tok("2", "mulaale", "NC3")
        sent = _make_sentence([noun, adj])
        self.resolver.resolve(sent)
        assert "AGREE_MOD_CONFIRMED" in adj.flags

    def test_adj_agree_adj_misc_set(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        adj  = _make_adj_tok("2", "mulaale", "NC3")
        sent = _make_sentence([noun, adj])
        self.resolver.resolve(sent)
        assert adj.misc.get("AgreeAdj") == noun.token_id

    def test_adj_nc_mismatch_not_linked(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        adj  = _make_adj_tok("2", "cilaale", "NC7")  # NC7 != NC3
        sent = _make_sentence([noun, adj])
        self.resolver.resolve(sent)
        assert "AGREE_MOD_CONFIRMED" not in adj.flags

    def test_demonstrative_agreement(self):
        noun = _make_noun_tok("1", "cintu", "NC7")
        dem  = WordToken(
            token_id="2", form="eci", lang_iso="toi",
            token_type=TokenType.WORD, upos=POSTag.DET,
            xpos="DET.DEM.NC7", noun_class="NC7",
        )
        sent = _make_sentence([noun, dem])
        self.resolver.resolve(sent)
        assert "AGREE_MOD_CONFIRMED" in dem.flags

    def test_noun_flagged_as_nc_donor(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        adj  = _make_adj_tok("2", "mulaale", "NC3")
        sent = _make_sentence([noun, adj])
        self.resolver.resolve(sent)
        assert "AGREE_NC_DONOR" in noun.flags

    def test_modifier_outside_window_not_linked(self):
        resolver = GobeloAgreementChain(MockLoader(), mod_window=1, min_score=0.05)
        noun = _make_noun_tok("1", "muti", "NC3")
        fillers = [
            WordToken(token_id=str(i), form=f"x{i}", lang_iso="toi",
                      token_type=TokenType.WORD)
            for i in range(2, 5)
        ]
        adj = _make_adj_tok("5", "mulaale", "NC3")
        sent = _make_sentence([noun] + fillers + [adj])
        resolver.resolve(sent)
        # distance > 1, window = 1 → not linked
        assert "AGREE_MOD_CONFIRMED" not in adj.flags

    def test_verb_tokens_not_processed_as_modifiers(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        # Verb should NOT get AGREE_MOD_CONFIRMED
        assert "AGREE_MOD_CONFIRMED" not in verb.flags


# ---------------------------------------------------------------------------
# Group 7 — Integration / annotation output (7 tests)
# ---------------------------------------------------------------------------

class TestIntegration:

    def setup_method(self):
        self.resolver = GobeloAgreementChain(MockLoader(), min_score=0.10)

    def test_pipeline_stage_added_to_sentence(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        assert any("GobeloAgreementChain" in s for s in sent.pipeline)

    def test_resolve_batch_processes_all_sentences(self):
        sents = [
            _make_sentence([_make_noun_tok("1", "muti", "NC3"),
                             _make_verb_tok("2", "ubona", sm_nc="NC3")],
                           f"s{i}")
            for i in range(3)
        ]
        results = self.resolver.resolve_batch(sents)
        assert len(results) == 3
        assert all(any("GobeloAgreementChain" in s for s in r.pipeline)
                   for r in results)

    def test_upos_disambiguated_for_x_token_with_nc(self):
        unknown = WordToken(
            token_id="1", form="muti", lang_iso="toi",
            token_type=TokenType.WORD, upos=POSTag.X,
            noun_class="NC3",
        )
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([unknown, verb])
        self.resolver.resolve(sent)
        # After agreement resolution, unknown token should get NOUN upos
        assert unknown.upos == POSTag.NOUN
        assert "UPOS_DISAMBIG_NC" in unknown.flags

    def test_enhanced_deps_written_for_subject(self):
        noun = _make_noun_tok("1", "muti", "NC3")
        verb = _make_verb_tok("2", "ubona", sm_nc="NC3")
        sent = _make_sentence([noun, verb])
        self.resolver.resolve(sent)
        # noun.deps should contain (verb_id, "nsubj")
        assert any(deprel == "nsubj" for _, deprel in noun.deps)

    def test_no_crash_on_empty_sentence(self):
        sent = AnnotatedSentence(sent_id="empty", text="", lang_iso="toi")
        result = self.resolver.resolve(sent)
        assert result is sent

    def test_describe_returns_string(self):
        desc = self.resolver.describe()
        assert isinstance(desc, str)
        assert "GobeloAgreementChain" in desc
        assert "toi" in desc

    def test_full_sentence_three_tokens(self):
        """Bakali(NC2) abona(SM.NC2) cintu(NC7) — two chains."""
        n_subj = _make_noun_tok("1", "bakali", "NC2")  # subject
        verb   = _make_verb_tok("2", "abona",  sm_nc="NC2", om_nc="NC7")
        n_obj  = _make_noun_tok("3", "cintu",  "NC7")   # object
        sent   = _make_sentence([n_subj, verb, n_obj], "bakali-test")
        self.resolver.resolve(sent)

        assert "AGREE_SUBJ_CONFIRMED" in verb.flags
        assert "AGREE_OBJ_CONFIRMED"  in verb.flags
        assert verb.misc.get("AgreeSubj") == n_subj.token_id
        assert verb.misc.get("AgreeObj")  == n_obj.token_id


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
