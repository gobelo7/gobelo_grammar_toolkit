"""
test_phase2.py — GGT Phase 2 smoke tests
=========================================
Tests for GobelloMorphAnalyser, GobeloVerbParser, and GobeloNounAnalyser.

Run with:  python test_phase2.py

All tests pass with zero external dependencies beyond the standard library
and the three GGT modules (models.py, word_tokenizer.py, morph_analyser.py).

Test strategy
-------------
Because the analyser is driven entirely by grammar tables loaded at
construction time, we use a rich MockLoader that supplies:
  - SM prefixes for NC1, NC2, NC3, NC4, NC14 (generic Bantu paradigm)
  - Three TAM prefixes (past, recent past, future)
  - Final vowels: indicative "a", perfective "ile" / "ile" variant
  - Three verb extensions (applicative -el-, causative -is-, reciprocal -an-)
  - NC1/NC2 noun prefixes
  - A small verb lexicon (8 roots) and noun lexicon (4 stems)
  - has_augment = False  (ChiTonga-style: no augment)

This exercises the full parse path without requiring a real YAML file.
"""

import sys
import unicodedata

sys.path.insert(0, ".")

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
from morph_analyser import (
    GobelloMorphAnalyser,
    GobeloVerbParser,
    GobeloNounAnalyser,
    _AnalyserConfig,
    _build_config,
    _build_morpheme_spans,
    _NullLoader,
    VERSION,
)

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

failures = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS} {name}")
    else:
        msg = f" — {detail}" if detail else ""
        print(f"  {FAIL} {name}{msg}")
        failures.append(name)


def section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ===================================================================== #
# Mock grammar loader
# ===================================================================== #

def _make_verb_entry(root, gloss, verified=True):
    return LexiconEntry(
        lang_iso="toi", category=LexiconCategory.VERB,
        root=root, gloss=gloss, verified=verified,
    )


def _make_noun_entry(stem, gloss, nc, pl_nc):
    return LexiconEntry(
        lang_iso="toi", category=LexiconCategory.NOUN,
        root=stem, gloss=gloss, noun_class=nc, plural_class=pl_nc, verified=True,
    )


VERB_LEXICON = {
    "lim"   : _make_verb_entry("lim",    "cultivate/till"),
    "bon"   : _make_verb_entry("bon",    "see"),
    "bik"   : _make_verb_entry("bik",    "put"),
    "end"   : _make_verb_entry("end",    "go"),
    "ly"    : _make_verb_entry("ly",     "eat"),
    "tond"  : _make_verb_entry("tond",   "love"),
    "imb"   : _make_verb_entry("imb",    "sing"),
    "lang"  : _make_verb_entry("lang",   "read"),
}

NOUN_LEXICON = {
    "kali"   : _make_noun_entry("kali",   "woman",   "NC1", "NC2"),
    "ana"    : _make_noun_entry("ana",    "child",   "NC1", "NC2"),
    "nkoko"  : _make_noun_entry("nkoko",  "chicken", "NC9", "NC10"),
    "munda"  : _make_noun_entry("munda",  "garden",  "NC3", "NC4"),
}


class MockLoader:
    lang_iso     = "toi"
    grammar      : dict = {}
    lexicon_verb  = VERB_LEXICON
    lexicon_noun  = NOUN_LEXICON

    def get(self, key: str, default=None):
        data = {
            "phonology.vowels_nfc": ["a", "e", "i", "o", "u"],
            "phonology.tone_marks": [],    # ChiTonga marks tones but we omit for testing
            "engine_features": {
                "augment": False,
                "extended_H_spread": False,
            },
            "morphology.augment": {},

            # Negation
            "morphology.negation": {
                "negative": {"form": "ta", "gloss": "NEG"},
            },

            # Subject Markers — generic Bantu NC1/2/3/4 + 1SG/2SG/1PL/2PL
            "morphology.subject_markers": {
                "NC1"  : {"form": "a",   "gloss": "SM.NC1"},
                "NC2"  : {"form": "ba",  "gloss": "SM.NC2"},
                "NC3"  : {"form": "u",   "gloss": "SM.NC3"},
                "NC4"  : {"form": "i",   "gloss": "SM.NC4"},
                "SM1SG": {"form": "n",   "gloss": "1SG.SM"},
                "SM2SG": {"form": "u",   "gloss": "2SG.SM"},
                "SM1PL": {"form": "tu",  "gloss": "1PL.SM"},
                "SM2PL": {"form": "mu",  "gloss": "2PL.SM"},
            },

            # TAM prefixes
            "morphology.tense_aspect": {
                "PAST_REMOTE" : {"form": "aaka", "gloss": "PAST.REMOTE"},
                "PAST_HOD"    : {"form": "aka",  "gloss": "PAST.HOD"},
                "FUTURE"      : {"form": "la",   "gloss": "FUT"},
                "RECENT_PAST" : {"form": "a",    "gloss": "PAST.RECENT"},
            },

            # Object Markers
            "morphology.object_markers": {
                "NC1" : {"form": "m",  "gloss": "OM.NC1"},
                "NC2" : {"form": "ba", "gloss": "OM.NC2"},
            },

            # Final Vowels
            "morphology.final_vowels": {
                "indicative" : {"form": "a",   "gloss": "FV.IND"},
                "perfective" : {"form": "ile", "gloss": "FV.PERF"},
                "subjunctive": {"form": "e",   "gloss": "FV.SUBJ"},
                "imperative" : {"form": "a",   "gloss": "FV.IMP"},
            },

            # Extensions
            "morphology.extensions": {
                "applicative": {"form": "el", "gloss": "APPL", "zone": "A"},
                "causative"  : {"form": "is", "gloss": "CAUS", "zone": "A"},
                "reciprocal" : {"form": "an", "gloss": "RECIP","zone": "B"},
                "passive"    : {"form": "iw", "gloss": "PASS", "zone": "B"},
            },

            # Noun Classes
            "morphology.noun_classes": {
                "NC1" : {"prefix": "mu",  "gloss": "NC1.SG"},
                "NC2" : {"prefix": "ba",  "gloss": "NC2.PL"},
                "NC3" : {"prefix": "mu",  "gloss": "NC3.SG"},   # same prefix → ambiguous
                "NC4" : {"prefix": "mi",  "gloss": "NC4.PL"},
                "NC9" : {"prefix": "",    "gloss": "NC9.SG"},   # zero prefix
                "NC10": {"prefix": "",    "gloss": "NC10.PL"},
            },
        }
        return data.get(key, default)


loader = MockLoader()

# ===================================================================== #
# _AnalyserConfig  tests
# ===================================================================== #
section("_build_config")

cfg = _build_config(loader)

check("cfg.lang_iso", cfg.lang_iso == "toi")
check("cfg.vowels populated", len(cfg.vowels) == 5)
check("cfg.has_augment False", cfg.has_augment is False)
check("SM table has NC2", "NC2" in cfg.sm_table)
check("SM NC2 form is 'ba'", "ba" in cfg.sm_table.get("NC2", []))
check("SM reverse 'ba' → NC2", any(
    nc == "NC2" for nc, _ in cfg.sm_reverse.get("ba", [])
))
check("TAM table has FUTURE", "FUTURE" in cfg.tam_table)
check("TAM reverse 'la' → FUTURE", any(
    k == "FUTURE" for k, _ in cfg.tam_reverse.get("la", [])
))
check("FV reverse 'ile' → perfective", cfg.fv_reverse.get("ile") == "perfective")
check("ext_reverse has applicative 'el'", any(f == "el" for f, *_ in cfg.ext_reverse))
check("NC reverse has NC2 prefix 'ba'", any(p == "ba" and nc == "NC2" for p, nc, _ in cfg.nc_reverse))


# ===================================================================== #
# GobeloVerbParser tests
# ===================================================================== #
section("GobeloVerbParser")

vp = GobeloVerbParser(cfg, VERB_LEXICON)

# --- balima: ba (NC2 SM) + lim (root) + a (FV)
hyps = vp.parse("balima")
check("balima: returns hypotheses", len(hyps) > 0)
best = hyps[0] if hyps else None
check("balima: best root is 'lim'", best is not None and best.root_form() == "lim")
check("balima: SLOT2 filled", best is not None and not best.get("SLOT2").is_empty())
check("balima: score > 0.4", best is not None and best.score > 0.4,
      f"score={best.score:.3f}" if best else "no hyp")
check("balima: LEXICON_HIT flag", best is not None and "LEXICON_HIT" in best.parse_flags)

# --- balima: SLOT10 (FV) identified
check("balima: FV identified", best is not None and not best.get("SLOT10").is_empty(),
      f"SLOT10={best.get('SLOT10')!r}" if best else "no hyp")

# --- balimile: perfective FV
hyps_perf = vp.parse("balimile")
best_perf  = hyps_perf[0] if hyps_perf else None
check("balimile: parsed", best_perf is not None)
check("balimile: FV 'ile'", best_perf is not None and best_perf.get("SLOT10").form == "ile",
      f"FV={best_perf.get('SLOT10').form!r}" if best_perf else "no hyp")

# --- balimela: with applicative extension
hyps_appl = vp.parse("balimela")
best_appl  = hyps_appl[0] if hyps_appl else None
check("balimela: parsed", best_appl is not None)
check("balimela: APPL extension or root 'limel'",
      best_appl is not None and (
          not best_appl.get("SLOT6").is_empty() or
          best_appl.root_form() in ("limel", "lim")
      ))

# --- tabona: negation prefix + SM + root + FV
hyps_neg = vp.parse("tabona")
best_neg  = hyps_neg[0] if hyps_neg else None
check("tabona: parsed", best_neg is not None)
check("tabona: score > 0.2", best_neg is not None and best_neg.score > 0.2)

# --- Score ordering: highest first
check("Hypotheses sorted descending", all(
    hyps[i].score >= hyps[i+1].score
    for i in range(len(hyps)-1)
))

# --- Short / unparseable form
hyps_short = vp.parse("x")
check("Single char: handled gracefully", isinstance(hyps_short, list))

# --- NullLoader: no crash
null_vp = GobeloVerbParser(_build_config(_NullLoader()), {})
check("NullLoader verb parser: no crash", isinstance(null_vp.parse("balima"), list))


# ===================================================================== #
# GobeloNounAnalyser tests
# ===================================================================== #
section("GobeloNounAnalyser")

na = GobeloNounAnalyser(cfg, NOUN_LEXICON)

# --- mukali: mu (NC1) + kali (woman)
results = na.analyse("mukali")
check("mukali: returns results", len(results) > 0)
top = results[0] if results else None
check("mukali: NC1 identified", top is not None and top[0] == "NC1",
      f"got NC={top[0]!r}" if top else "no result")
check("mukali: stem is 'kali'", top is not None and top[1] == "kali")
check("mukali: lexicon entry found", top is not None and top[2] is not None)
check("mukali: score > 0.5", top is not None and top[3] > 0.5)

# --- bakali: ba (NC2) + kali (woman) — plural form
results_pl = na.analyse("bakali")
check("bakali: returns results", len(results_pl) > 0)
top_pl = results_pl[0] if results_pl else None
check("bakali: NC2 identified", top_pl is not None and top_pl[0] == "NC2",
      f"got NC={top_pl[0]!r}" if top_pl else "no result")

# --- NullLoader: no crash
null_na = GobeloNounAnalyser(_build_config(_NullLoader()), {})
check("NullLoader noun analyser: no crash", isinstance(null_na.analyse("mukali"), list))


# ===================================================================== #
# _build_morpheme_spans tests
# ===================================================================== #
section("_build_morpheme_spans")

sp_test = SlotParse(lang_iso="toi")
sp_test.set("SLOT2",  SlotFill("ba",  "SM.NC2",  "SM.NC2",  ConfidenceLevel.HIGH, 0, 2))
sp_test.set("SLOT5",  SlotFill("lim", "cultivate","LEX:lim", ConfidenceLevel.HIGH, 2, 5))
sp_test.set("SLOT10", SlotFill("a",   "FV.IND",  "FV.ind",  ConfidenceLevel.HIGH, 5, 6))

spans = _build_morpheme_spans(sp_test, "balima")
check("morpheme spans built", len(spans) == 3, f"got {len(spans)}")
check("SM span label", any(ms.label == "SM" for ms in spans))
check("ROOT span form", any(ms.form == "lim" and ms.label == "ROOT" for ms in spans))
check("FV span label", any(ms.label == "FV" for ms in spans))
check("no overlapping spans", all(
    not spans[i].overlaps(spans[j])
    for i in range(len(spans))
    for j in range(i+1, len(spans))
))


# ===================================================================== #
# GobelloMorphAnalyser  integration tests
# ===================================================================== #
section("GobelloMorphAnalyser — integration")

ana = GobelloMorphAnalyser(loader)

# describe() / repr
desc = ana.describe()
check("describe() runs", "GobelloMorphAnalyser" in desc)
check("describe() shows SM count", "SM entries" in desc)
check("repr", "GobelloMorphAnalyser" in repr(ana))

# Single-token sentence
sent = AnnotatedSentence(sent_id="toi-test-001", text="Balima.", lang_iso="toi")
tok_v = WordToken(form="Balima", token_id="1", lang_iso="toi",
                  token_type=TokenType.WORD, char_start=0, char_end=6)
tok_p = WordToken(form=".", token_id="2", lang_iso="toi",
                  token_type=TokenType.PUNCT, char_start=6, char_end=7)
sent.add_token(tok_v)
sent.add_token(tok_p)

result = ana.analyse(sent)

check("analyse() returns AnnotatedSentence", isinstance(result, AnnotatedSentence))
check("pipeline recorded", any("GobelloMorphAnalyser" in s for s in result.pipeline))
check("punct token unchanged", tok_p.upos == POSTag.PUNCT or tok_p.upos is None)
check("verb token has slot parse", tok_v.has_slot_analysis)
check("verb token upos=VERB", tok_v.upos == POSTag.VERB)
check("verb token lemma set", tok_v.lemma is not None and len(tok_v.lemma) > 0)
check("verb token morpheme spans built", len(tok_v.morpheme_spans) > 0)
check("VERB_ANALYSED flag", "VERB_ANALYSED" in tok_v.flags)

# Batch analysis
sentences = [
    AnnotatedSentence(sent_id="toi-test-002", text="Balima.", lang_iso="toi"),
    AnnotatedSentence(sent_id="toi-test-003", text="Babona.", lang_iso="toi"),
]
for s in sentences:
    s.add_token(WordToken(form=s.text.rstrip("."), token_id="1",
                          lang_iso="toi", token_type=TokenType.WORD,
                          char_start=0, char_end=len(s.text)-1))
results_batch = ana.analyse_batch(sentences)
check("analyse_batch: 2 sentences", len(results_batch) == 2)
check("analyse_batch: both pipeline stamped", all(
    any("GobelloMorphAnalyser" in st for st in s.pipeline)
    for s in results_batch
))

# Noun token
sent2 = AnnotatedSentence(sent_id="toi-test-004", text="Bakali", lang_iso="toi")
tok_n = WordToken(form="Bakali", token_id="1", lang_iso="toi",
                  token_type=TokenType.WORD, char_start=0, char_end=6)
sent2.add_token(tok_n)
ana.analyse(sent2)
# "Bakali" could be parsed as noun (bakali = ba+kali) or verb (ba+...).
# Either a slot parse OR noun_class is acceptable.
check("Bakali: analysed (verb or noun)", tok_n.has_slot_analysis or tok_n.noun_class is not None)

# NullLoader: no crash
null_ana = GobelloMorphAnalyser(_NullLoader())
sent_null = AnnotatedSentence(sent_id="null-001", text="Balima.", lang_iso="und")
tok_null  = WordToken(form="Balima", token_id="1", lang_iso="und",
                      token_type=TokenType.WORD, char_start=0, char_end=6)
sent_null.add_token(tok_null)
check("NullLoader: analyse() no crash", isinstance(null_ana.analyse(sent_null), AnnotatedSentence))


# ===================================================================== #
# UD features
# ===================================================================== #
section("UD feature population")

# Analyse a sentence with a known TAM prefix to check feats dict
ana2 = GobelloMorphAnalyser(loader)
sent3 = AnnotatedSentence(sent_id="toi-test-005", text="balalima", lang_iso="toi")
tok_fut = WordToken(form="balalima", token_id="1", lang_iso="toi",
                    token_type=TokenType.WORD, char_start=0, char_end=8)
sent3.add_token(tok_fut)
ana2.analyse(sent3)
# "balalima" = ba (SM.NC2) + la (FUT) + lim (root) + a (FV)
check("Future: slot parse found", tok_fut.has_slot_analysis)
if tok_fut.has_slot_analysis:
    best_f = tok_fut.best_slot_parse
    check("Future: VerbForm=Fin in feats", tok_fut.feats.get("VerbForm") == "Fin")
    # Tense may or may not be populated depending on TAM key match
    check("Future: feats dict non-empty", len(tok_fut.feats) > 0)

# Negation feats
sent4 = AnnotatedSentence(sent_id="toi-test-006", text="tabona", lang_iso="toi")
tok_neg2 = WordToken(form="tabona", token_id="1", lang_iso="toi",
                     token_type=TokenType.WORD, char_start=0, char_end=6)
sent4.add_token(tok_neg2)
ana2.analyse(sent4)
check("Negation: slot parse found", tok_neg2.has_slot_analysis)
if tok_neg2.has_slot_analysis and tok_neg2.best_slot_parse:
    check("Negation: Polarity=Neg in feats (if SLOT1 filled)",
          tok_neg2.feats.get("Polarity") == "Neg" or "SLOT1" not in tok_neg2.best_slot_parse.slots)


# ===================================================================== #
# CoNLL-U output after analysis
# ===================================================================== #
section("CoNLL-U serialisation after analysis")

sent5 = AnnotatedSentence(sent_id="toi-conllu-001", text="Balima.", lang_iso="toi")
tv = WordToken(form="Balima", token_id="1", lang_iso="toi",
               token_type=TokenType.WORD, char_start=0, char_end=6)
tp = WordToken(form=".",      token_id="2", lang_iso="toi",
               token_type=TokenType.PUNCT, char_start=6, char_end=7)
sent5.add_token(tv)
sent5.add_token(tp)
ana.analyse(sent5)

conllu = sent5.to_conllu()
check("CoNLL-U output produced", isinstance(conllu, str) and len(conllu) > 10)
check("CoNLL-U has sent_id", "sent_id = toi-conllu-001" in conllu)
check("CoNLL-U has VERB row", "VERB" in conllu)

# to_dict smoke test
d = sent5.to_dict()
check("to_dict: analysed=1 in stats",
      d["stats"].get("analysed", 0) >= 1)


# ===================================================================== #
# Final report
# ===================================================================== #
section("Summary")

if failures:
    print(f"\n  {FAIL} {len(failures)} test(s) FAILED:")
    for f in failures:
        print(f"      · {f}")
    sys.exit(1)
else:
    print(f"\n  {PASS} All Phase 2 tests passed.\n")
    sys.exit(0)
