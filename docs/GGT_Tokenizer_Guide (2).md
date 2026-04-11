# Gobelo Grammar Toolkit — Tokenizer & Annotation Pipeline User Guide

**Version:** Phase 1–2 (tokenizer + morphological analyser)  
**Languages covered:** ChiBemba (bem · M.42), SiLozi (loz · K.21)  
**Remaining in queue:** ChiNyanja, ciLunda, ciLuvale, ciKaonde  

---

## Table of Contents

1. [Architecture overview](#1-architecture-overview)
2. [File inventory](#2-file-inventory)
3. [Quick start](#3-quick-start)
4. [The GGTLoaderAdapter](#4-the-ggtloaderadapter)
5. [GobeloWordTokenizer — Phase 1](#5-gobelowordtokenizer--phase-1)
6. [GobelloMorphAnalyser — Phase 2](#6-gobellomorphanalyser--phase-2)
7. [Working with output](#7-working-with-output)
8. [Supplying a lexicon](#8-supplying-a-lexicon)
9. [Adding a new language (zero Python changes)](#9-adding-a-new-language-zero-python-changes)
10. [Known limitations and VERIFY flags](#10-known-limitations-and-verify-flags)
11. [Scoring reference](#11-scoring-reference)
12. [Slot template reference](#12-slot-template-reference)
13. [Language-specific divergences quick-reference](#13-language-specific-divergences-quick-reference)

---

## 1. Architecture overview

The GGT annotation pipeline is a three-layer stack. This guide covers the
bottom two layers.

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 3+  PoS tagger · dependency parser · CS detector     │  ← future
├─────────────────────────────────────────────────────────────┤
│  Phase 2   GobelloMorphAnalyser                             │  ← this guide
│            verb slot-filling · noun-class assignment ·      │
│            MorphemeSpan · UD feats · scoring                │
├─────────────────────────────────────────────────────────────┤
│  Phase 1   GobeloWordTokenizer                              │  ← this guide
│            NFC · OCR fix · whitespace · punct · clitics ·  │
│            special tokens · lexicon stub · flags           │
├─────────────────────────────────────────────────────────────┤
│  Data      GGTLoaderAdapter  ←  YAML grammar file          │  ← bridge
│            models.py         ←  AnnotatedSentence etc.     │
└─────────────────────────────────────────────────────────────┘
```

**Design invariant: zero Python changes to add a language.** All
language-specific knowledge — noun-class prefixes, subject/object concords,
TAM markers, verb extensions, negation, augment — lives exclusively in the
GGT YAML grammar file. The tokenizer and analyser are fully language-agnostic.

---

## 2. File inventory

```
project/
│
│  Grammar files (read-only input)
├── chibemba.yaml          GGT grammar for ChiBemba (bem)
├── silozi.yaml            GGT grammar for SiLozi (loz)
│
│  Pipeline source files
├── models.py              Pipeline data layer: AnnotatedSentence, WordToken,
│                          SlotParse, SlotFill, MorphemeSpan, LexiconEntry, …
├── word_tokenizer.py      Phase 1 tokenizer (GobeloWordTokenizer)
├── morph_analyser.py      Phase 2 morphological analyser (GobelloMorphAnalyser)
│
│  Adapter (new — this session)
└── ggt_loader_adapter.py  GGTLoaderAdapter: bridges YAML ↔ pipeline interface
```

> **Important:** `models.py` in the pipeline directory is the *pipeline* data
> layer (contains `AnnotatedSentence`, `WordToken`, `SlotParse`, etc.) and is
> distinct from `core/models.py` in the `GobeloGrammarLoader` package
> (contains frozen dataclasses like `NounClass`, `ConcordSet`, etc.).
> Keep them in separate directories to avoid import shadowing.

---

## 3. Quick start

### 3.1 Minimal — no lexicon, no corpus config

```python
import yaml
from ggt_loader_adapter import GGTLoaderAdapter
from word_tokenizer      import GobeloWordTokenizer
from morph_analyser      import GobelloMorphAnalyser

# Load grammar
with open("chibemba.yaml") as f:
    grammar = yaml.safe_load(f)

# Build pipeline
loader = GGTLoaderAdapter(grammar, lang_iso="bem")
tok    = GobeloWordTokenizer(loader)
ana    = GobelloMorphAnalyser(loader)

# Analyse a sentence
sentence = tok.tokenize("Umuntu alima.")
sentence = ana.analyse(sentence)

# Inspect results
for token in sentence.word_tokens():
    sp = token.best_slot_parse
    print(token.form,
          "upos:", token.upos.value if token.upos else "?",
          "NC:", token.noun_class or "—",
          "score:", f"{sp.score:.2f}" if sp else "—",
          "gloss:", sp.gloss_string() if sp else "")
```

**Output (no lexicon — heuristic mode):**
```
Umuntu  upos: NOUN  NC: NC1   score: —     gloss:
alima   upos: VERB  NC: —     score: 0.28  gloss: SM.3SG-OM.NC5-m-FV.INFINITIVE
```

Without a lexicon the root slot is heuristically identified and scored low.
Once `"lim"` is added to the verb lexicon (see section 8), the score rises
to 0.65 and the gloss reads `SM.3SG-cultivate/farm-FV.INFINITIVE`.

### 3.2 Batch tokenisation

```python
sentences = [
    "Balima amasaka.",
    "Nabona abantu balima.",
    "Tabalimi fye.",
]
for sent in tok.tokenize_batch(sentences, source="corpus:bem_001"):
    sent = ana.analyse(sent)
    print(sent.sent_id, "—", sent.coverage_stats())
```

### 3.3 SiLozi

```python
with open("silozi.yaml") as f:
    loz_grammar = yaml.safe_load(f)

loader_loz = GGTLoaderAdapter(loz_grammar, lang_iso="loz")
tok_loz    = GobeloWordTokenizer(loader_loz)
ana_loz    = GobelloMorphAnalyser(loader_loz)

sentence = tok_loz.tokenize("Sicintu sona sinde.")
sentence = ana_loz.analyse(sentence)
```

`Sicintu` will receive `NC=NC7` (prefix `si-`); the analyser correctly
uses the SiLozi `si-` paradigm rather than the ChiBemba `fi-` paradigm.

---

## 4. The GGTLoaderAdapter

`GGTLoaderAdapter` is the bridge between the GGT YAML grammar files and the
pipeline. It translates on-demand between the YAML key hierarchy and the
dotted-key interface that `GobeloWordTokenizer` and `GobelloMorphAnalyser`
both call via `loader.get(key, default)`.

### 4.1 Constructor

```python
GGTLoaderAdapter(
    grammar:      dict,              # yaml.safe_load(grammar_file)
    lang_iso:     str  = "und",      # ISO 639-3 code
    lexicon_verb: dict = None,       # {root_str: LexiconEntry}  (optional)
    lexicon_noun: dict = None,       # {stem_str: LexiconEntry}  (optional)
)
```

### 4.2 Key mapping reference

The table below shows every dotted key the pipeline calls and where in the
YAML structure the adapter finds the data.

| `loader.get(key)` | YAML path |
|---|---|
| `phonology.vowels_nfc` | `phonology.vowels.segments` (single-char only) |
| `phonology.tone_marks` | always `[]` (GGT corpus text is un-toned) |
| `engine_features` | `phonology.engine_features[*].default` + augment detection |
| `clitics` | `tokenization.clitics` |
| `morphology.subject_markers` | `concord_system.concords.subject_concords` |
| `morphology.object_markers` | `concord_system.concords.object_concords` |
| `morphology.tense_aspect` | `verb_system.verbal_system_components.tam` |
| `morphology.final_vowels` | `verb_system.verbal_system_components.final_vowels` |
| `morphology.extensions` | `verb_system.verbal_system_components.derivational_extensions` |
| `morphology.noun_classes` | `noun_class_system.noun_classes` |
| `morphology.negation` | `verb_system.verbal_system_components.negation_pre` |
| `morphology.augment` | `noun_class_system.noun_classes[*].augment` |

### 4.3 Engine feature flags

Two engine flags matter for the analyser:

| Flag | ChiBemba | SiLozi | Effect |
|---|---|---|---|
| `extended_H_spread` | `true` | `false` | activates tonal rule TS.2 (metadata only in Phase 1–2; used by Phase 3+ tonal rules) |
| `augment` | `true` | `false` | if true, the analyser attempts to strip the augment `i-` before noun-class prefix matching |

### 4.4 Diagnostics

```python
print(loader.describe())
```

```
GGTLoaderAdapter  lang='bem'
  subject markers   : 25
  object markers    : 22
  TAM markers       : 10
  final vowels      : 7
  extensions        : 14
  noun classes      : 20
  negation contexts : 3
  augment forms     : ['i']
  engine.augment    : True
  engine.H_spread   : True
  verb lexicon      : 5 roots
  noun lexicon      : 3 stems
```

### 4.5 Caching

The adapter memoises every translated key on first access. Subsequent calls
to `loader.get(same_key)` return the cached result at O(1). The cache is
per-instance; create a new adapter instance if you reload or switch grammars.

---

## 5. GobeloWordTokenizer — Phase 1

The tokenizer runs a six-stage pipeline on every input string and returns an
`AnnotatedSentence` containing `WordToken` objects with character offsets.

### 5.1 Pipeline stages

| Stage | What it does |
|---|---|
| 1 · Pre-normalise | NFC normalise; apply OCR correction map; strip noise characters |
| 2 · Special scan | Mark verse references, chapter headings, custom regex patterns |
| 3 · Whitespace split | Split on Unicode whitespace; track char offsets |
| 4 · Punct split | Split sentence-final and inline punctuation away from word forms |
| 5 · Clitic split | Detach proclitics and enclitics (driven by YAML + corpus config) |
| 6 · Post-process | Numeric check; reduplication detection; lexicon probe; code-switch flag |

### 5.2 Token types

Every `WordToken` has a `token_type` field:

| `TokenType` | Meaning |
|---|---|
| `WORD` | Ordinary lexical token |
| `PUNCT` | Standalone punctuation character |
| `NUMBER` | Numeric string or Roman numeral |
| `SPECIAL` | Verse reference (`1:1`), chapter heading, custom pattern |
| `CLITIC` | Split-off clitic; `clitic_of` holds the host token id |
| `CODE_SWITCH` | Heuristically detected code-switch (conservative) |

### 5.3 Token flags

Flags accumulated during tokenisation (accessible as `token.flags`):

| Flag | Set when |
|---|---|
| `OOV` | Form not found in either lexicon |
| `LEXICON_HIT` | Stub match in verb or noun lexicon |
| `NUMERIC` | Token classified as a number |
| `REDUPLICATED` | Doubled-substring heuristic fired (e.g. *lyalya*, *bulubulubu*) |
| `CLITIC` | Token is a split-off clitic |
| `CODE_SWITCH` | Code-switch heuristic fired |
| `SPECIAL` | Special-token pattern matched |

### 5.4 Using a CorpusConfig

The tokenizer accepts an optional second argument implementing the
`CorpusConfig` interface (`cfg.get(lang_iso, key, default)` and
`cfg.global_get(key, default)`). Without one, all corpus-config paths return
their defaults. For Bible corpus work a minimal config covers the most
important overrides:

```python
class SimpleCfg:
    """Minimal CorpusConfig for Bible corpus work."""

    _PER_LANG = {
        "bem": {
            "verse_pattern"    : r"^\d+:\d+$",
            "bible_book_abbreviations": {
                "Gen":"Genesis","Exo":"Exodus","Mat":"Matthew",
                "Mar":"Mark","Luk":"Luke","Joh":"John",
            },
            "ocr_corrections"  : {"—": " ", "\u2014": " "},
        },
        "loz": {
            "verse_pattern"    : r"^\d+:\d+$",
        },
    }

    def get(self, lang, key, default=None):
        return self._PER_LANG.get(lang, {}).get(key, default)

    def global_get(self, key, default=None):
        return default
```

### 5.5 Sentence IDs

Auto-generated IDs follow the pattern `{lang_iso}-{counter:06d}` (e.g.
`bem-000001`). Supply an explicit `sent_id` for deterministic corpus
provenance:

```python
sentence = tok.tokenize(
    "Balima amasaka.",
    sent_id="bem-GEN-001-01",
    source="Bible:Gen.1.1",
)
```

---

## 6. GobelloMorphAnalyser — Phase 2

The analyser takes an `AnnotatedSentence` from the tokenizer and enriches
every non-punctuation token. It makes **two passes** per sentence.

### 6.1 Pass A — Verb analysis

For every `WORD`, `CLITIC`, or `UNKNOWN` token the `GobeloVerbParser` runs a
left-to-right prefix-peeling strategy across eleven verb template slots:

```
SLOT1  pre-SM negation     ta-, si-, ha- …
SLOT2  subject marker      a- (3SG), ba- (3PL), ni- (1SG SiLozi), fi-/bi- (NC7/NC8 ChiBemba) …
SLOT3  TAM prefix          a (PRES), ali (HOD.PST), laa (FUT.NEAR), ta (FUT SiLozi) …
SLOT4  object marker       mu- (3SG.OM), ba- (3PL.OM), fi- (NC7.OM ChiBemba) …
SLOT5  verb root           matched against lexicon
SLOT6  extension zone A    -il-/-el- APPL, -ish-/-esh- CAUS (ChiBemba)
SLOT7  extension zone B    -an- RECIP, -ik-/-ek- STAT
SLOT8  extension zone C    -w-/-iw- PASS
SLOT9  extension zone D    -ul-/-ol- REV
SLOT10 final vowel         -a (IND), -e (SUBJ), -i (NEG), -ile (PERF)
SLOT11 post-FV             locative -ni, question -nzi …
```

The analyser keeps up to five hypotheses per token (configurable via
`max_hypotheses`). Hypotheses are scored and ranked; see section 11 for the
scoring weights.

### 6.2 Pass B — Noun analysis

Tokens where Pass A produced no hypothesis scoring ≥ 0.20 are passed to the
`GobeloNounAnalyser`. It tries every NC prefix (longest-first) against the
form and matches the remainder against the noun lexicon.

The ChiBemba augment (`i-`) is stripped before prefix matching when
`engine_features.augment` is true. SiLozi has no augment, so this step is
skipped automatically.

### 6.3 What the analyser writes to each token

After `ana.analyse(sentence)` each token carries:

| Field | Type | Content |
|---|---|---|
| `upos` | `POSTag` | `VERB` or `NOUN` (or `None` if unanalysed) |
| `lemma` | `str` | root form from best parse |
| `feats` | `dict` | UD morphological features (Tense, Aspect, VerbForm, Polarity, NounClass) |
| `slot_parses` | `List[SlotParse]` | ranked hypotheses (verbs) |
| `best_slot_parse` | `SlotParse` | highest-scored hypothesis |
| `morpheme_spans` | `List[MorphemeSpan]` | character-level morpheme segments |
| `noun_class` | `str` | e.g. `"NC7"` (nouns) |
| `lexicon_matches` | `List[LexiconEntry]` | confirmed lexicon entries |
| `is_oov` | `bool` | `False` once a lexicon match is confirmed |
| `misc["Morphemes"]` | `str` | pipe-separated `LABEL=form` (CoNLL-U MISC) |
| `misc["Score"]` | `str` | `"0.700"` |

### 6.4 Reading the best parse

```python
sentence = tok.tokenize("Nabona abantu balima.")
sentence = ana.analyse(sentence)

for token in sentence.word_tokens():
    sp = token.best_slot_parse
    if sp:
        print(f"{token.form:20s}  root={sp.root_form():<10s}  "
              f"score={sp.score:.2f}  gloss={sp.gloss_string()}")
        for slot_key in sp.filled_slots():
            fill = sp.get(slot_key)
            print(f"    {slot_key}: {fill.form!r:<10s}  {fill.gloss}")
```

**Output (with `bon` and `lim` in the lexicon):**
```
Nabona                root=bon        score=0.75  SM.1SG-PRES-see-FV.INFINITIVE
    SLOT2: 'n'        1SG.SM
    SLOT3: 'a'        PRES
    SLOT5: 'bon'      see
    SLOT10: 'a'       FV.INDICATIVE

balima                root=lim        score=0.70  SM.3PL_HUMAN-OM.NC6-cultivate-FV.INFINITIVE
    SLOT2: 'b'        3PL.SM
    SLOT4: 'a'        CL6.OM
    SLOT5: 'lim'      cultivate
    SLOT10: 'a'       FV.INDICATIVE
```

### 6.5 Reading morpheme spans

```python
for ms in token.morpheme_spans:
    segment = token.form[ms.start:ms.end]
    print(f"  [{ms.start}:{ms.end}] {segment!r:8s}  label={ms.label:<10s}  gloss={ms.gloss}")
```

---

## 7. Working with output

### 7.1 CoNLL-U export

```python
sentence = tok.tokenize("Umuntu alima.", sent_id="bem-001", source="Bible:Gen.1.1")
sentence = ana.analyse(sentence)
print(sentence.to_conllu())
```

```conllu
# sent_id = bem-001
# text = Umuntu alima.
# source = Bible:Gen.1.1
# lang = bem
1	Umuntu	muntu	NOUN	_	NounClass=NC1	_	_	_	NCScore=0.950|NFC=Umuntu|NounClass=NC1
2	alima	lim	VERB	_	VerbForm=Fin	_	_	_	Morphemes=SM=a|ROOT=lim|FV=a|NFC=alima|Score=0.650
3	.	_	PUNCT	_	_	_	_	_	_	_
```

### 7.2 JSON export

```python
import json
data = sentence.to_dict()
print(json.dumps(data, indent=2, ensure_ascii=False))
```

The dict includes `stats`, `pipeline`, `tokens` (each with `slot_parses`,
`morpheme_spans`, `lexicon_matches`).

### 7.3 Coverage statistics

```python
stats = sentence.coverage_stats()
# {'total': 2, 'oov': 0, 'lexicon': 2, 'analysed': 2, 'punct': 1, 'special': 0}
```

`oov_rate()` returns the fraction of word tokens not found in any lexicon —
useful for monitoring lexicon coverage across a corpus.

### 7.4 Filtering by analysis type

```python
# All verb tokens in the sentence
verbs = sentence.verb_tokens()

# All noun tokens
nouns = sentence.noun_tokens()

# All OOV word tokens (excludes punct/special)
oov   = sentence.oov_tokens()

# Tokens with a completed slot analysis
analysed = [t for t in sentence.word_tokens() if t.has_slot_analysis]
```

### 7.5 Iterating multiple hypotheses

The analyser stores up to five ranked hypotheses per verb token:

```python
for hyp in sorted(token.slot_parses, key=lambda s: s.score, reverse=True):
    print(f"  score={hyp.score:.3f}  root={hyp.root_form()!r}  {hyp.gloss_string()}")
    print(f"  flags: {hyp.parse_flags}")
```

Parse flags on each hypothesis include `LEXICON_HIT`, `ROOT_HEURISTIC`,
`FV_IDENTIFIED`.

---

## 8. Supplying a lexicon

Without a lexicon the analyser still runs (heuristic mode), but root
identification scores are capped at ~0.35 and lemmas will be unreliable.
A lexicon lifts the score ceiling to 0.80+ and provides verified glosses.

### 8.1 Building a LexiconEntry

```python
from models import LexiconEntry, LexiconCategory

# Verb entry
lim_entry = LexiconEntry(
    lang_iso    = "bem",
    category    = LexiconCategory.VERB,
    root        = "lim",          # bare root, no FV
    gloss       = "cultivate/farm",
    verified    = True,
    source      = "Hoch1960:42",
)

# Noun entry
muntu_entry = LexiconEntry(
    lang_iso     = "bem",
    category     = LexiconCategory.NOUN,
    root         = "muntu",       # stem without NC prefix
    gloss        = "person",
    noun_class   = "NC1",
    plural_class = "NC2",
    verified     = True,
)
```

### 8.2 Passing lexicons to the adapter

```python
verb_lex = {
    "lim":  lim_entry,
    "bon":  LexiconEntry("bem", LexiconCategory.VERB, "bon",  "see",   verified=True),
    "end":  LexiconEntry("bem", LexiconCategory.VERB, "end",  "go",    verified=True),
    "fwa":  LexiconEntry("bem", LexiconCategory.VERB, "fwa",  "die",   verified=True),
    "lil":  LexiconEntry("bem", LexiconCategory.VERB, "lil",  "cry",   verified=True),
    "shib": LexiconEntry("bem", LexiconCategory.VERB, "shib", "know",  verified=True),
}

noun_lex = {
    "muntu": muntu_entry,
    "ntu":   LexiconEntry("bem", LexiconCategory.NOUN, "ntu",   "person", "NC1", "NC2"),
    "kolwe": LexiconEntry("bem", LexiconCategory.NOUN, "kolwe", "thing",  "NC7", "NC8"),
}

loader = GGTLoaderAdapter(grammar, lang_iso="bem",
                          lexicon_verb=verb_lex,
                          lexicon_noun=noun_lex)
```

> **ChiTonga lexicon note:** 2 000+ verb roots and noun stems are available
> for ChiTonga (toi). Once ChiTonga's YAML grammar file is added, the same
> LexiconEntry structure applies directly — only the `lang_iso` field changes.

### 8.3 Loading from TSV

A simple helper for loading a tab-separated verb lexicon
(`root\tgloss\tsource`):

```python
def load_verb_tsv(path: str, lang_iso: str) -> dict:
    from models import LexiconEntry, LexiconCategory
    lex = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            root  = parts[0].strip()
            gloss = parts[1].strip() if len(parts) > 1 else ""
            src   = parts[2].strip() if len(parts) > 2 else ""
            lex[root] = LexiconEntry(
                lang_iso=lang_iso, category=LexiconCategory.VERB,
                root=root, gloss=gloss, source=src, verified=bool(src),
            )
    return lex
```

---

## 9. Adding a new language (zero Python changes)

The architecture guarantees that adding ChiNyanja, ciLunda, ciLuvale, or
ciKaonde requires no Python edits. The steps are:

1. **Create the YAML grammar file** using an existing file as template
   (the most recently completed file is the preferred template). The file must
   include, at minimum:
   - `metadata.language.{name, iso_code, guthrie}`
   - `phonology.vowels.segments`
   - `phonology.engine_features`
   - `noun_class_system.noun_classes` with prefix data for each active NC
   - `concord_system.concords.{subject_concords, object_concords}`
   - `verb_system.verbal_system_components.{tam, final_vowels, derivational_extensions, negation_pre}`

2. **Instantiate the adapter** with the new YAML and the new ISO code:

   ```python
   with open("chinyanja.yaml") as f:
       nya_grammar = yaml.safe_load(f)

   loader = GGTLoaderAdapter(nya_grammar, lang_iso="nya")
   tok    = GobeloWordTokenizer(loader)
   ana    = GobelloMorphAnalyser(loader)
   ```

3. **Verify the adapter tables** using `loader.describe()`. Confirm that
   NC7 prefix, TAM markers, and negation forms match the reference grammar.

4. **Supply a lexicon** (optional at first; heuristic mode works for initial
   smoke tests).

5. **Run the pipeline** on a sample sentence and inspect CoNLL-U output.

No YAML changes are needed in existing files. No Python changes anywhere.

---

## 10. Known limitations and VERIFY flags

### 10.1 VERIFY annotations

Both grammar files contain `# VERIFY:` annotations on forms that require
confirmation against the primary linguistic reference before production use.
The count for each language:

| Language | Approx. VERIFY count | Primary references |
|---|---|---|
| ChiBemba (bem) | ~45 | Spitulnik & Kashoki 1992; Hoch 1960 |
| SiLozi (loz) | ~90 | Givón 1970; Jacottet 1896/1927 |

These do not prevent the pipeline from running, but flagged forms may be
incorrect. VERIFY-flagged areas include: ChiBemba NC1 prefix (u- vs mu-),
past tense degree boundaries (hodiernal vs hesternal), copula forms, and
several SiLozi demonstratives and pronouns.

### 10.2 Analyser limitations (Phase 2)

- **Context-free scoring.** Subject-marker agreement with a nearby noun
  (the +0.20 bonus in the scoring spec) is deferred to Phase 3 (PoS tagger
  context layer). All Phase 2 scores are therefore capped near 0.80.

- **Homophonous prefixes.** Several NC prefixes are identical:
  - ChiBemba: `u-` is shared by NC1 (human singular) and NC3 (trees/plants);
    `ku-` is shared by NC15 (infinitive) and NC17 (directional locative).
  - SiLozi: `li-` is shared by NC5 (augmentative) and NC8 (NC7 plural).
  - The analyser generates competing hypotheses for these cases. Disambiguation
    requires Phase 3 concord tracking.

- **Noun-only tokens below score 0.15** may fall through both passes and
  remain unanalysed (`upos=None`). This is expected for short function words,
  particles, and discourse markers not yet in the noun lexicon.

- **Extension stacking ambiguity.** The greedy right-to-left extension
  peeler may mis-segment complex stacked forms (e.g. APPL+CAUS+PASS) when
  the root is not in the lexicon. Lexicon coverage is the primary remedy.

### 10.3 SiLozi periphrastic TAM

SiLozi past tense uses the auxiliary `ne` before the subject concord
(`ne a bona` = "he/she saw"). The current Phase 2 analyser parses `ne` as a
single-token verb form rather than an auxiliary. Phase 3 will handle
multi-word TAM constructions. Concretely: `ne` will appear in the output as
`VERB` with a low score rather than `AUX`.

---

## 11. Scoring reference

Each verb hypothesis is scored on a 0–1 scale. The weights below are the
current production values in `morph_analyser.py`:

| Criterion | Weight |
|---|---|
| Lexicon root hit (SLOT5 confirmed) | +0.40 |
| Lexicon entry is `verified=True` | +0.02 (bonus) |
| Final vowel identified (SLOT10) | +0.15 |
| TAM prefix identified (SLOT3) | +0.10 |
| Subject marker identified (SLOT2) | +0.08 |
| Object marker identified (SLOT4) | +0.05 |
| At least one extension zone found | +0.05 |
| Negation prefix identified (SLOT1) | +0.03 |
| Surface reconstruction matches exactly | +0.05 |
| **Maximum without concord bonus** | **~0.80** |
| SM-noun concord agreement (Phase 3) | +0.20 (deferred) |

**Interpreting scores:**

| Score range | Interpretation |
|---|---|
| 0.60 – 0.80 | High confidence: lexicon root + FV + at least SM or TAM confirmed |
| 0.40 – 0.59 | Medium: lexicon root confirmed but some slots missing |
| 0.20 – 0.39 | Low: heuristic parse, no lexicon hit |
| < 0.20 | Not accepted as a verb parse (token routed to noun analysis) |

---

## 12. Slot template reference

The eleven-slot Bantu verb template as used by `GobeloVerbParser`:

| Slot | Code | Description | Example (ChiBemba) |
|---|---|---|---|
| SLOT1 | `negation_pre` | Pre-subject negation | `ta-`, `si-` |
| SLOT2 | `subject_concords` | Subject marker | `a-` (3SG), `ba-` (3PL), `fi-` (NC7 bem) |
| SLOT3 | `tense_aspect_mood` | TAM prefix | `a` (PRES), `ali` (HOD.PST), `laa` (FUT.NEAR) |
| SLOT4 | `object_concord` | Object marker | `mu-` (3SG.OM), `fi-` (NC7.OM bem) |
| SLOT5 | `root` | Verb root | `lim`, `bon`, `end` |
| SLOT6 | `verb_ext` Zone A | Valency-increasing ext | `-il-` (APPL), `-ish-` (CAUS bem) |
| SLOT7 | `verb_ext` Zone B | Valency-adjusting ext | `-an-` (RECIP), `-ik-` (STAT) |
| SLOT8 | `verb_ext` Zone C | Voice | `-w-`/`-iw-` (PASS) |
| SLOT9 | `verb_ext` Zone D | Aspectual/lexical | `-ul-` (REV), `-ilil-` (PERF.EXT) |
| SLOT10 | `fv` | Final vowel | `-a` (IND), `-e` (SUBJ), `-i` (NEG), `-ile` (PERF) |
| SLOT11 | `post_final` | Post-final clitics | `-ni` (LOC), `-nzi` (Q) |

---

## 13. Language-specific divergences quick-reference

The table below summarises the features that differ between ChiBemba and
SiLozi relative to the ChiTonga baseline. These directly affect how the
adapter and analyser behave for each language.

| Feature | ChiTonga (baseline) | ChiBemba | SiLozi |
|---|---|---|---|
| NC1/NC3 prefix | `mu-` | `u-` | `mo-` (Sotho-influenced) |
| NC7 prefix | `ci-` | `fi-`/`ifi-` | `si-` |
| NC8 prefix | `zi-` | `bi-`/`ibi-` | `li-` (homophonous with NC5) |
| NC16 locative | `pa-` | `pa-` | `fa-` (Sotho-influenced) |
| Augment | `i-` (optional) | `i-`/`a-` (optional) | none |
| Perfective FV | `-ide` | `-ile` | `-ile` |
| Causative | `-is-`/`-y-` | `-ish-`/`-esh-` | `-is-`/`-ish-` |
| Passive | `-iw-` | `-iiw-` (lengthening) | `-w-`/`-aw-` |
| Applicative | `-il-`/`-el-` | `-il-`/`-el-` | `-el-`/`-al-` |
| Past degrees | 1 (general) | 3 (hod./hest./remote) | periphrastic `ne` aux |
| H-tone spread | bounded | unbounded (TS.2) | bounded |
| `extended_H_spread` flag | `false` | `true` | `false` |

---

*This guide covers Phase 1 (tokenizer) and Phase 2 (morphological analyser).
Phase 3 (PoS tagger, dependency parser, code-switch detector) is the next
development milestone. All architecture decisions in this guide are designed
to remain stable across Phase 3 additions.*
