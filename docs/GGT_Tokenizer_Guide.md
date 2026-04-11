# GobeloWordTokenizer — Implementation & User Guide
**Gobelo Grammar Toolkit (GGT) · Phase 1**
*Language-agnostic word tokeniser for all seven Zambian Bantu languages*

---

## 1. Architecture Overview

`GobeloWordTokenizer` is a six-stage pipeline that converts a raw sentence string into an `AnnotatedSentence` populated with `WordToken` objects. All language-specific knowledge flows from two external sources — the GGT YAML grammar file (via a loader) and `corpus_config.yaml` — so **adding a new language requires zero Python changes**.

```
raw text
   │
   ▼
Stage 1 · Pre-normalisation
   NFC → OCR corrections → noise-char stripping
   │
   ▼
Stage 2 · Special-token pre-scan
   Verse refs, chapter headings, custom regex patterns
   │
   ▼
Stage 3 · Whitespace splitting
   Unicode whitespace; offsets preserved
   │
   ▼
Stage 4 · Punctuation splitting
   Sentence-final and inline punct split away; protected patterns preserved
   │
   ▼
Stage 5 · Clitic splitting
   Proclitics / enclitics detached; longest-match, greedy
   │
   ▼
Stage 6 · Post-processing
   Numerics · reduplification · lexicon probe · code-switch flag · misc
   │
   ▼
AnnotatedSentence  →  List[WordToken]
```

---

## 2. Dependencies

| Module | Role |
|---|---|
| `models.py` | `AnnotatedSentence`, `WordToken`, `MorphemeSpan`, `SlotFill`, `SlotParse`, `LexiconEntry`, `POSTag`, `TokenType`, `ConfidenceLevel` |
| `GobeloGrammarLoader` (external) | Grammar YAML access via `.get(key, default)` |
| `CorpusConfig` (external) | Per-language corpus overrides via `.get(lang_iso, key, default)` |
| Python stdlib | `re`, `unicodedata`, `dataclasses` |

No third-party dependencies beyond the standard library.

---

## 3. Instantiation

```python
from word_tokenizer import GobeloWordTokenizer

# Full production setup
loader     = GobeloGrammarLoader("bem")      # ChiBemba
corpus_cfg = CorpusConfig.load("corpus_config.yaml")

tok = GobeloWordTokenizer(
    loader          = loader,
    corpus_cfg      = corpus_cfg,
    lang_iso        = "bem",          # overrides loader.lang_iso if given
    sent_id_prefix  = "bem-GEN-001",  # prefixes auto-generated sent_id
)

# Minimal / test setup — null stubs for both
tok = GobeloWordTokenizer()   # lang_iso defaults to "und"
```

### Constructor parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `loader` | grammar loader or mock | `_NullGrammarLoader()` | Provides grammar data |
| `corpus_cfg` | corpus config or mock | `_NullCorpusConfig()` | Per-language overrides |
| `lang_iso` | `str` | `loader.lang_iso` | ISO 639-3 code |
| `sent_id_prefix` | `str` | `lang_iso` | Prefix for auto-generated IDs |

---

## 4. Public API

### 4.1 `tokenize(text, sent_id="", source="") → AnnotatedSentence`

Tokenises a single sentence string.

```python
sent = tok.tokenize(
    "Bakali balima mu nganda.",
    sent_id = "bem-GEN-001-01",
    source  = "Bible:Mk.1.1",
)

for token in sent.tokens:
    print(token.token_id, token.form, token.upos, token.flags)
```

**Parameters**

| Name | Type | Description |
|---|---|---|
| `text` | `str` | Raw input sentence |
| `sent_id` | `str` | Optional explicit ID; auto-generated if omitted |
| `source` | `str` | Provenance tag (e.g. `"Bible:Mk.1.1"`) |

**Returns** `AnnotatedSentence` with:
- `.sent_id`, `.text` (NFC-normalised), `.lang_iso`, `.source`
- `.tokens` — ordered `List[WordToken]`
- `.pipeline` — audit trail e.g. `["GobeloWordTokenizer-1.0.0"]`

---

### 4.2 `tokenize_batch(texts, source="") → List[AnnotatedSentence]`

Tokenises a list of sentence strings. Empty strings are skipped.

```python
sentences = tok.tokenize_batch(
    ["Ni lata ku ya.", "Ba bona ndu yono."],
    source = "corpus:loz_001",
)
```

---

### 4.3 `describe() → str`

Returns a human-readable configuration summary for debugging.

```python
print(tok.describe())
# GobeloWordTokenizer v1.0.0
#   lang_iso   : bem
#   proclitics : (none)
#   enclitics  : ['mo', 'ni']
#   ocr_map    : 3 entries
#   ...
```

---

## 5. The `_TokeniserConfig` — what gets built at construction time

`_build_config(loader, corpus_cfg, lang_iso)` assembles a `_TokeniserConfig` dataclass once, pulling from both the YAML grammar and corpus config. All inner-loop operations then work with plain Python types.

| Config field | Source | Description |
|---|---|---|
| `ocr_map` | `corpus_cfg.get(lang, "ocr_corrections")` | `{wrong: right}` substitutions before any splitting |
| `noise_categories` | `corpus_cfg.get(lang, "noise_unicode_categories")` | Unicode category codes to strip (e.g. `"Cf"` for formatting chars) |
| `noise_chars` | `corpus_cfg.get(lang, "noise_chars")` | Explicit characters to strip |
| `sentence_final_punct` | `corpus_cfg.get(lang, "sentence_final_punct")` | Defaults: `. ! ? … \u2026` |
| `inline_punct` | `corpus_cfg.get(lang, "inline_punct")` | Defaults: `, ; : ( ) [ ] " " ' ' « » — –` |
| `protect_patterns` | `corpus_cfg.get(lang, "protect_patterns")` | Regex patterns for URLs, abbreviations, decimals — protected from punct-splitting |
| `proclitics` | `loader.get("clitics").get("proclitics")` | Sorted longest-first |
| `enclitics` | `loader.get("clitics").get("enclitics")` + `corpus_cfg.get(lang, "extra_enclitics")` | Merged, sorted longest-first |
| `special_patterns` | `corpus_cfg` verse/chapter patterns | Compiled `re.Pattern` objects |
| `abbreviations` | `corpus_cfg.get(lang, "bible_book_abbreviations")` | Keys of the abbreviation dict |
| `vowels` | `loader.get("phonology.vowels_nfc")` | Used in reduplification detection |
| `tone_marks` | `loader.get("phonology.tone_marks")` | Used in code-switch detection |
| `has_augment` | `loader.get("engine_features").get("augment")` | Boolean engine flag |
| `extended_h_spread` | `loader.get("engine_features").get("extended_H_spread")` | ChiBemba-specific flag |
| `cs_lang_isos` | `corpus_cfg.get(lang, "code_switch_langs")` | ISOs of languages to flag |

---

## 6. Stage-by-stage walkthrough

### Stage 1 — Pre-normalisation

1. **NFC normalise** the entire string via `unicodedata.normalize("NFC", text)`.
2. **OCR corrections**: apply `ocr_map` substitutions longest-key-first to avoid partial replacements.
3. **Noise strip**: remove any character whose Unicode category is in `noise_categories` or whose code point is in `noise_chars`.

---

### Stage 2 — Special-token pre-scan

Scans the *normalised* string with each compiled `special_pattern`. Returns a list of `(start, end, TokenType, xpos)` tuples. Overlapping spans are resolved: earliest start wins; on tie, the longer span wins.

Built-in patterns:
- Verse references: `^\d+:\d+$` → `TokenType.SPECIAL`, xpos `"VERSE_REF"`
- Chapter headings: `^[A-Z][A-Za-z0-9 ]+\s+\d+$` → `TokenType.SPECIAL`, xpos `"CHAP_HEAD"`

Custom patterns are added from `corpus_cfg.get(lang, "special_token_patterns")`.

---

### Stage 3 — Whitespace splitting

A simple character-walk yields `(chunk, start, end)` tuples preserving byte offsets into the normalised string. Chunks that exactly match a Stage 2 special span are emitted directly as special tokens.

---

### Stage 4 — Punctuation splitting (`_PunctSplitter`)

For each non-special chunk:
1. If the chunk matches any `protect_pattern` (URL, abbreviation, decimal number), emit as-is.
2. Otherwise scan character-by-character; when a punct character from `sentence_final_punct ∪ inline_punct` is found, flush the buffer as a word-chunk and emit the punct character as its own token.

---

### Stage 5 — Clitic splitting (`_CliticSplitter`)

Applied to each non-punct word chunk:
1. **Proclitics** (left side): try each proclitic in longest-first order; detach the first that matches *and* leaves a non-empty remainder.
2. **Enclitics** (right side): same logic applied from the right.
3. Each detached clitic becomes a `TokenType.CLITIC` token with `clitic_of` set to the host token's id.

> **Note**: currently one proclitic and one enclitic per token. Multiple stacked clitics would require multiple passes — extend `_CliticSplitter.split()` if needed.

---

### Stage 6 — Post-processing (`_stage6_make_word_token`)

For each word-form chunk:

1. **Numeric check** (`_is_numeric`): matches digit strings, decimal numbers, and Roman numerals I–XXXIX → sets `TokenType.NUMBER`, `upos=NUM`.
2. **All-punct check**: sets `TokenType.PUNCT`, `upos=PUNCT`.
3. **Reduplification** (`_detect_reduplication`): checks if `form[:n] == form[n:2n]` for any n ≥ 2 with overall length ≥ 4. Sets `is_reduplicated=True`, adds flag `"REDUPLICATED"`.
4. **Lexicon probe** (`_LexiconProbe.probe`):
   - Direct noun match in `lexicon_noun`
   - Direct verb match in `lexicon_verb`
   - Stem approximation for verbs: strip 1–3 final characters, check `lexicon_verb`
   - Sets `is_oov=False` and preliminary `upos`/`lemma`/`noun_class` on a hit.
   - Adds flag `"LEXICON_HIT"` or `"OOV"`.
5. **Code-switch detection**: if `tone_marks` is non-empty and the form has no combining diacritics/tone marks, is all-Latin, and ≥ 4 characters long → `TokenType.CODE_SWITCH`, flag `"CODE_SWITCH"`. (Conservative heuristic; full detection is Phase 3.)
6. **MISC field**: `NFC` = NFC-normalised form is stored in `token.misc`.

---

## 7. `WordToken` fields populated by the tokeniser

| Field | Type | Set by tokeniser? | Notes |
|---|---|---|---|
| `token_id` | `str` | ✅ | 1-based index within sentence |
| `form` | `str` | ✅ | NFC-normalised surface form |
| `original_form` | `str` | ✅ | Pre-normalisation form |
| `upos` | `POSTag` | ✅ (hint only) | Overridden by Phase 2 |
| `lang_iso` | `str` | ✅ | From constructor |
| `token_type` | `TokenType` | ✅ | WORD / PUNCT / NUMBER / CLITIC / SPECIAL / CODE_SWITCH |
| `char_start` | `int` | ✅ | Offset into normalised sentence string |
| `char_end` | `int` | ✅ | Exclusive end offset |
| `is_oov` | `bool` | ✅ | `True` until lexicon probe finds a hit |
| `lexicon_matches` | `List[LexiconEntry]` | ✅ (stub) | Phase 2 will populate fully |
| `lemma` | `Optional[str]` | ✅ (hint only) | From lexicon probe root |
| `noun_class` | `Optional[str]` | ✅ (hint only) | From lexicon probe |
| `is_reduplicated` | `bool` | ✅ | Heuristic detection |
| `clitic_of` | `Optional[str]` | ✅ | token_id of host token |
| `flags` | `List[str]` | ✅ | LEXICON_HIT / OOV / REDUPLICATED / CODE_SWITCH / CLITIC / NUMERIC / SPECIAL |
| `misc["NFC"]` | `str` | ✅ | NFC form |
| `slot_parses` | `List[SlotParse]` | ❌ | Phase 2 (`GobelloMorphAnalyser`) |
| `morpheme_spans` | `List[MorphemeSpan]` | ❌ | Phase 2 |
| `feats` | `Dict[str,str]` | ❌ | Phase 2 |
| `head`, `deprel` | — | ❌ | Phase 3 (dependency parser) |

---

## 8. `AnnotatedSentence` convenience methods

```python
sent = tok.tokenize("Bakali balima mu nganda.")

sent.word_tokens()          # excludes PUNCT and SPECIAL tokens
sent.oov_tokens()           # word tokens with is_oov=True
sent.verb_tokens()          # tokens with upos VERB or AUX
sent.noun_tokens()          # tokens with upos NOUN or PROPN
sent.code_switch_tokens()   # tokens flagged CODE_SWITCH

sent.token_count()          # number of word tokens
sent.oov_rate()             # float in [0.0, 1.0]
sent.coverage_stats()       # dict: total/oov/lexicon/analysed/punct/special

sent.to_conllu()            # full CoNLL-U block as string
sent.to_dict()              # JSON-safe dict
```

---

## 9. Loader interface contract

The tokeniser calls `loader.get(key, default)` with dot-separated YAML paths. Your loader must implement this. Supported keys:

| Key | Expected type | Used for |
|---|---|---|
| `"clitics"` | `dict` with `"proclitics"` / `"enclitics"` lists | Clitic splitting |
| `"phonology.vowels_nfc"` | `list[str]` | Reduplification / code-switch |
| `"phonology.tone_marks"` | `list[str]` | Code-switch detection |
| `"engine_features"` | `dict` | `augment`, `extended_H_spread` flags |

The tokeniser also accesses `loader.lang_iso` (str), `loader.lexicon_verb` (dict), and `loader.lexicon_noun` (dict) as direct attributes.

---

## 10. Corpus config interface contract

`corpus_cfg.get(lang_iso, key, default)` is called with these keys:

| Key | Type | Purpose |
|---|---|---|
| `"ocr_corrections"` | `dict[str,str]` | OCR fix map |
| `"noise_unicode_categories"` | `list[str]` | Unicode categories to strip |
| `"noise_chars"` | `list[str]` | Characters to strip |
| `"sentence_final_punct"` | `list[str]` | Sentence-final punctuation |
| `"inline_punct"` | `list[str]` | Inline punctuation |
| `"protect_patterns"` | `list[str]` | Regex patterns to protect from punct-splitting |
| `"bible_book_abbreviations"` | `dict` | Book abbreviations (keys only used) |
| `"extra_enclitics"` | `list[str]` | Additional enclitics beyond YAML |
| `"verse_pattern"` | `str` | Regex for verse references |
| `"chapter_heading_pattern"` | `str` | Regex for chapter headings |
| `"special_token_patterns"` | `list[str]` | Additional special-token patterns |
| `"code_switch_langs"` | `list[str]` | ISO codes of expected code-switch languages |

`corpus_cfg.global_get(key, default)` is available but not currently called by the tokeniser itself (reserved for future cross-language settings).

---

## 11. Writing a minimal mock loader

```python
class MockLoader:
    lang_iso     = "loz"
    grammar      = {}
    lexicon_verb = {
        "bon": LexiconEntry(lang_iso="loz", category=LexiconCategory.VERB,
                             root="bon", gloss="see"),
    }
    lexicon_noun = {}

    _data = {
        "clitics": {"proclitics": [], "enclitics": ["fo", "mo"]},
        "phonology.vowels_nfc": ["a", "e", "i", "o", "u"],
        "phonology.tone_marks": [],
        "engine_features": {"augment": False, "extended_H_spread": False},
    }

    def get(self, key, default=None):
        return self._data.get(key, default)
```

---

## 12. Language-specific notes

### ChiBemba (bem)
- `engine_features.extended_H_spread: true` — set in YAML; stored in `_cfg.extended_h_spread` but not acted on by the tokeniser (activated by Phase 2 tonal rules).
- NC7 prefix is `fi-` / `ifi-`; NC8 is `bi-` / `ibi-` — relevant to lexicon probe noun-class hints.
- Augment system (`i-` / `a-`) is present; `has_augment=True` propagates to the analyser.

### SiLozi (loz)
- `engine_features.extended_H_spread: false` — H-spread rule TS.2 does not fire.
- NC16 locative is `fa-` (not `pa-` as in other languages) — affects noun lexicon probe.
- No augment system; `has_augment=False`.
- `ne` auxiliary for past TAM is handled as a separate token by whitespace splitting.

---

## 13. Extending the tokeniser

### Adding a new language
1. Create a GGT YAML grammar file following the existing schema.
2. Add the language to `corpus_config.yaml` with its specific settings.
3. Register it in the loader registry.
4. **Zero Python changes required.**

### Adding a new special-token pattern
In `corpus_config.yaml` for the target language:
```yaml
special_token_patterns:
  - "^\\[\\d+\\]$"   # footnote markers like [1]
```

### Adding extra enclitics
```yaml
extra_enclitics:
  - "ni"
  - "ko"
```

### Stacking multiple clitics per token
Extend `_CliticSplitter.split()`: after detaching one proclitic, loop again on the remainder; same for enclitics. The current single-pass design is intentional for simplicity.

---

## 14. Output formats

### CoNLL-U

```python
print(sent.to_conllu())
# # sent_id = bem-GEN-001-01
# # text = Bakali balima mu nganda.
# # source = Bible:Mk.1.1
# # lang = bem
# 1	Bakali	_	NOUN	_	_	_	_	_	NFC=Bakali
# 2	balima	_	_	_	_	_	_	_	NFC=balima
# 3	mu	_	_	_	_	_	_	_	NFC=mu
# 4	nganda	_	_	_	_	_	_	_	NFC=nganda
# 5	.	_	PUNCT	_	_	_	_	_	_
```

### JSON

```python
import json
print(json.dumps(sent.to_dict(), ensure_ascii=False, indent=2))
```

---

## 15. Pipeline audit trail

Every `AnnotatedSentence` records which pipeline stages have been applied:

```python
sent.pipeline
# ["GobeloWordTokenizer-1.0.0"]

# After Phase 2:
# ["GobeloWordTokenizer-1.0.0", "GobelloMorphAnalyser-2.0.0"]
```

This enables idempotency checks and reproducibility audits.

---

## 16. Known limitations and Phase 3 hooks

| Limitation | Resolution |
|---|---|
| Code-switch detection is conservative (Latin + no tone marks) | Replace with language model in Phase 3 |
| Only one proclitic and one enclitic per token | Extend `_CliticSplitter.split()` for stacked clitics |
| Lexicon probe is a stub (strips 1–3 final chars) | `GobelloMorphAnalyser` in Phase 2 provides full analysis |
| Reduplification detection is length-based only | Phase 2 can add phonological patterns from YAML |
| `clitic_of` is set provisionally (no token_id yet at split time) | Re-resolved at token_id assignment step if needed |
| No sentence boundary detection | Caller responsibility; feed one sentence at a time |
