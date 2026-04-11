"""
test_phase1.py — GGT Phase 1 smoke tests
=========================================
Run with:  python test_phase1.py
All tests should pass with zero imports beyond the standard library and
the two GGT Phase 1 modules (models.py, word_tokenizer.py).
"""

import sys
import traceback
import unicodedata

# ---- adjust path if running from project root --------------------------
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
    VALID_SLOTS,
)
from word_tokenizer import (
    GobeloWordTokenizer,
    _NullGrammarLoader,
    _NullCorpusConfig,
    _detect_reduplication,
    _TokeniserConfig,
)

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

failures = []

def check(name, condition, detail=""):
    if condition:
        print(f"  {PASS} {name}")
    else:
        print(f"  {FAIL} {name}" + (f" — {detail}" if detail else ""))
        failures.append(name)

def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ===================================================================== #
# models.py tests
# ===================================================================== #
section("SlotFill")

sf_empty = SlotFill()
check("SlotFill empty is_empty", sf_empty.is_empty())
check("SlotFill default confidence NONE", sf_empty.confidence == ConfidenceLevel.NONE)

sf = SlotFill(form="ba", gloss="3PL.SM", source_rule="SM.NC2",
              confidence=ConfidenceLevel.HIGH, start=0, end=2)
check("SlotFill non-empty not is_empty", not sf.is_empty())
check("SlotFill repr contains form", "ba" in repr(sf))


section("SlotParse")

sp = SlotParse(lang_iso="toi", analyser_version="0.1")
sp.set("SLOT2", SlotFill("ba", "3PL.SM", "SM.NC2", ConfidenceLevel.HIGH, 0, 2))
sp.set("SLOT5", SlotFill("lim", "cultivate", "LEX:lim", ConfidenceLevel.HIGH, 2, 5))
sp.set("SLOT10", SlotFill("a", "FV.FINAL", "FV.default", ConfidenceLevel.MEDIUM, 5, 6))

check("SlotParse root_form", sp.root_form() == "lim")
check("SlotParse filled_slots count", len(sp.filled_slots()) == 3)
check("SlotParse surface concat", sp.surface() == "balima")
check("SlotParse gloss_string", "SM" in sp.gloss_string())
check("SlotParse average_confidence HIGH", sp.average_confidence() in (
    ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM))

# Invalid slot should raise
try:
    SlotParse(slots={"SLOTX": SlotFill()})
    check("SlotParse rejects bad slot key", False, "should have raised")
except ValueError:
    check("SlotParse rejects bad slot key", True)

# add_flag
sp.add_flag("LEXICON_HIT")
sp.add_flag("LEXICON_HIT")   # idempotent
check("SlotParse add_flag idempotent", sp.parse_flags.count("LEXICON_HIT") == 1)


section("MorphemeSpan")

ms = MorphemeSpan(start=0, end=2, form="ba", label="SM", gloss="3PL.SM", slot="SLOT2")
check("MorphemeSpan length", ms.length() == 2)

ms2 = MorphemeSpan(start=2, end=5, form="lim", label="ROOT")
check("MorphemeSpan non-overlap", not ms.overlaps(ms2))

ms3 = MorphemeSpan(start=1, end=3, form="al", label="INFIX")
check("MorphemeSpan overlap detected", ms.overlaps(ms3))

# start > end should raise
try:
    MorphemeSpan(start=5, end=2, form="x", label="ERR")
    check("MorphemeSpan start>end raises", False, "should have raised")
except ValueError:
    check("MorphemeSpan start>end raises", True)


section("LexiconEntry")

le_verb = LexiconEntry(
    lang_iso="toi", category=LexiconCategory.VERB,
    root="lim", gloss="cultivate", source="Hoch1960:99",
)
check("LexiconEntry is_verb", le_verb.is_verb())
check("LexiconEntry not is_noun", not le_verb.is_noun())
check("LexiconEntry NFC root", le_verb.root == unicodedata.normalize("NFC", "lim"))

le_noun = LexiconEntry(
    lang_iso="toi", category=LexiconCategory.NOUN,
    root="nkoko", gloss="grandmother", noun_class="NC1a", plural_class="NC2",
)
check("LexiconEntry is_noun", le_noun.is_noun())
check("LexiconEntry noun_class", le_noun.noun_class == "NC1a")

le_verb.derivations = ["lim-il-a", "lim-an-a"]
check("LexiconEntry has_derivation", le_verb.has_derivation("lim-il-a"))
check("LexiconEntry no_derivation", not le_verb.has_derivation("lim-ish-a"))


section("WordToken")

tok = WordToken(form="balima", lang_iso="toi", char_start=0, char_end=6)
check("WordToken NFC normalised", tok.form == unicodedata.normalize("NFC", "balima"))
check("WordToken default is_oov", tok.is_oov)
check("WordToken default upos None", tok.upos is None)
check("WordToken span", tok.span == (0, 6))
check("WordToken not is_verb (unset)", not tok.is_verb)
check("WordToken not is_noun (unset)", not tok.is_noun)

tok.upos = POSTag.VERB
check("WordToken is_verb after set", tok.is_verb)

sp2 = SlotParse(score=0.9, lang_iso="toi")
sp2.set("SLOT5", SlotFill("lim", "cultivate", "LEX:lim", ConfidenceLevel.HIGH, 2, 5))
tok.add_slot_parse(sp2)
check("WordToken has_slot_analysis", tok.has_slot_analysis)
check("WordToken best_slot_parse score", tok.best_slot_parse.score == 0.9)

tok.add_lexicon_match(le_verb)
check("WordToken not oov after match", not tok.is_oov)
check("WordToken lexicon_matches count", len(tok.lexicon_matches) == 1)

tok.add_flag("TEST_FLAG")
check("WordToken add_flag", "TEST_FLAG" in tok.flags)

# CoNLL-U serialisation
tok.token_id = "1"
tok.lemma    = "lim"
tok.feats    = {"Tense": "Past", "Number": "Plur"}
conllu = tok.to_conllu_line()
cols = conllu.split("\t")
check("WordToken CoNLL-U 10 columns", len(cols) == 10)
check("WordToken CoNLL-U form", cols[1] == "balima")
check("WordToken CoNLL-U upos", cols[3] == "VERB")
check("WordToken CoNLL-U feats sorted", "Number=Plur|Tense=Past" in cols[5])

# JSON serialisation
d = tok.to_dict()
check("WordToken to_dict has form", d["form"] == "balima")
check("WordToken to_dict has slot_parses", isinstance(d["slot_parses"], list))


section("AnnotatedSentence")

sent = AnnotatedSentence(sent_id="toi-000001", text="Balima.", lang_iso="toi")
tok1 = WordToken(form="Balima", token_id="1", lang_iso="toi",
                 upos=POSTag.VERB, token_type=TokenType.WORD,
                 char_start=0, char_end=6)
tok2 = WordToken(form=".", token_id="2", lang_iso="toi",
                 upos=POSTag.PUNCT, token_type=TokenType.PUNCT,
                 char_start=6, char_end=7)
tok1.is_oov = True
sent.add_token(tok1)
sent.add_token(tok2)

check("AnnotatedSentence len", len(sent) == 2)
check("AnnotatedSentence word_tokens filters punct", len(sent.word_tokens()) == 1)
check("AnnotatedSentence oov_tokens", len(sent.oov_tokens()) == 1)
check("AnnotatedSentence oov_rate", sent.oov_rate() == 1.0)

stats = sent.coverage_stats()
check("coverage_stats total", stats["total"] == 1)
check("coverage_stats punct", stats["punct"] == 1)

conllu_block = sent.to_conllu()
check("AnnotatedSentence to_conllu has sent_id", "sent_id = toi-000001" in conllu_block)
check("AnnotatedSentence to_conllu blank line terminator", conllu_block.endswith("\n"))

sent_dict = sent.to_dict()
check("AnnotatedSentence to_dict tokens list", isinstance(sent_dict["tokens"], list))


# ===================================================================== #
# word_tokenizer.py tests
# ===================================================================== #
section("Reduplification detector")

cfg0 = _TokeniserConfig(lang_iso="toi")
check("Reduplication: 'lyalya'",    _detect_reduplication("lyalya", cfg0))
check("Reduplication: 'bulubulubu'", _detect_reduplication("bulubulubu", cfg0))
check("Reduplication: 'balima' no", not _detect_reduplication("balima", cfg0))
check("Reduplication: 'ab' too short", not _detect_reduplication("ab", cfg0))
check("Reduplication: 'abab'",      _detect_reduplication("abab", cfg0))


section("GobeloWordTokenizer — null loader (smoke)")

tok_eng = GobeloWordTokenizer(lang_iso="toi")
print(f"\n  {tok_eng.describe()}\n")

# Basic sentence
result = tok_eng.tokenize("Bakali balima.", sent_id="test-001")
check("Basic: AnnotatedSentence returned", isinstance(result, AnnotatedSentence))
check("Basic: sent_id preserved", result.sent_id == "test-001")
check("Basic: lang_iso", result.lang_iso == "toi")
check("Basic: pipeline recorded", any("GobeloWordTokenizer" in s for s in result.pipeline))

forms = [t.form for t in result.tokens]
check("Basic: 'Bakali' present", "Bakali" in forms)
check("Basic: 'balima' present", "balima" in forms)
check("Basic: '.' is punct", any(t.form == "." and t.is_punct for t in result.tokens))

# Numeric token
result_num = tok_eng.tokenize("1:1 Bakatanga.")
num_toks = [t for t in result_num.tokens if "NUMERIC" in t.flags]
check("Numeric: '1:1' detected", len(num_toks) >= 1 or
      any(t.upos == POSTag.NUM for t in result_num.tokens))

# Sentence counter increments
r1 = tok_eng.tokenize("A.")
r2 = tok_eng.tokenize("B.")
check("Counter increments", r1.sent_id != r2.sent_id)

# Empty / whitespace input
r_empty = tok_eng.tokenize("   ")
check("Empty input: no tokens", len(r_empty.tokens) == 0)

# NFC normalisation in stage 1
nfd_text = unicodedata.normalize("NFD", "bàlìzyà")
r_nfc = tok_eng.tokenize(nfd_text)
for t in r_nfc.tokens:
    check(f"NFC: '{t.form}' is NFC",
          t.form == unicodedata.normalize("NFC", t.form))

# Punctuation variants
result_punct = tok_eng.tokenize("Mwane, nkwe!")
punct_toks = [t for t in result_punct.tokens if t.is_punct]
check("Punct: comma split", any(t.form == "," for t in punct_toks))
check("Punct: exclamation split", any(t.form == "!" for t in punct_toks))


section("GobeloWordTokenizer — mock corpus_cfg")

class MockCorpusCfg:
    def get(self, lang_iso, key, default=None):
        overrides = {
            "ocr_corrections": {"vv": "w", "ii": "ī"},
            "bible_book_abbreviations": {"Mk": True, "Gen": True},
            "extra_enclitics": ["-bo"],
        }
        return overrides.get(key, default)
    def global_get(self, key, default=None):
        return default

mock_cfg = MockCorpusCfg()
tok_mock = GobeloWordTokenizer(corpus_cfg=mock_cfg, lang_iso="toi")

# OCR correction
r_ocr = tok_mock.tokenize("baalima")   # no ocr hit — just checking no crash
check("Mock cfg: tokenize runs", isinstance(r_ocr, AnnotatedSentence))

# Describe
desc = tok_mock.describe()
check("Mock cfg: describe() runs", "GobeloWordTokenizer" in desc)

# batch
batch_results = tok_mock.tokenize_batch(["Sentence one.", "Sentence two."])
check("Batch: 2 sentences returned", len(batch_results) == 2)

# repr
check("Tokenizer repr", "GobeloWordTokenizer" in repr(tok_mock))


# ===================================================================== #
# Final report
# ===================================================================== #
section("Summary")
total  = 0   # count lines with PASS/FAIL marks in output (approx)
passed = 0

# Just use the failures list we accumulated
if failures:
    print(f"\n  {FAIL} {len(failures)} test(s) FAILED:")
    for f in failures:
        print(f"      · {f}")
    sys.exit(1)
else:
    print(f"\n  {PASS} All tests passed.\n")
    sys.exit(0)
