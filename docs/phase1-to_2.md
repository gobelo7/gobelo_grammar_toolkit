
gobelo_corpus
/

chitonga_tokenizer.py
py


To the gcbt  toolkit, want add a language agnostic (not only chitonga language) tokenizer plus POS tagger which builds on the output of gcbt (i.e text files) and uses the grammar YAML  to POS tag and segment the tokens into morphemes.  I have attached files for a single/mono language  tokenizer as a background. See pipeline example below. Let us discuss this.

GGT YAML (languages/chitonga.yaml, etc.)
    ↓  Layer 1: linguistic authority
    ↓  phonology, morphology, noun classes, verb agreement, POS inventory

corpus_config.yaml
    ↓  Layer 2: corpus-processing settings (already exists in gcbt)
    ↓  clitics, false_positives, code-switching word lists, OCR corrections

gcbt pipeline
    ↓  produces output/chitonga/literature/novel1.txt  (one sentence per line)
    ↓           output/chitonga/literature/novel1.json (language_iso, sentences[])
    ↓           corpus_manifest.json                   (files grouped by language)

GobeloTokenizer  ← what we're building
    reads gcbt output, inherits language_iso from JSON metadata
    per-sentence: tokenise → morpheme-segment → POS-tag
    drives all language-specific rules from the same GGT YAML that gcbt uses

GobeloTokenizerCLI
    extends existing production CLI pattern (streaming, workers, checkpoint)

Advise onthe way forward.
Show less
4 Apr

Architected language-agnostic tokenizer leveraging GGT YAML grammar specifications
Architected language-agnostic tokenizer leveraging GGT YAML grammar specifications
Good — this is a rich design conversation. Let me lay out what I see in the existing tokenizer, the gaps, and a proposed architecture before we make any code decisions.

What the existing tokenizer does and doesn't do
The ChitongaTokenizer is a solid word-level tokenizer. It handles:

Whitespace splitting + punctuation detachment
Clitic segmentation (proclitics, enclitics)
Reduplication detection
Code-switching / language ID
Special token types (numbers, URLs, dates)
What it doesn't do — and what you want to add:

Morpheme segmentation — splitting baya → [ba-|ya] using NC prefix/verb slot knowledge
POS tagging — assigning VERB.3PL or NOUN.NC6 driven by the GGT YAML
Language-agnosticism — it's wired to TOI; adding a second language requires forking the class
It also has a hard dependency on chitonga_grammar (an FST module) that doesn't exist for other languages.

Proposed architecture — three questions first
Before I sketch the full design, I need your answers on three things that will determine the shape of everything else:

Q1 — POS tagset depth

Which of these is closest to what you want?

Shallow — NOUN, VERB, ADJ, ADV, PRON, CONJ, PUNCT, NUM, DISC, LOAN
NC-aware — NOUN.NC1, NOUN.NC6, VERB.FIN, VERB.INF, DET.PROX.NC3, etc.
Full UD — Universal Dependencies UPOS + language-specific FEATS fields (compatible with UD treebanks)
Q2 — Morpheme segmentation granularity

Prefix+root+suffix only — ku|tek|a (three segments)
Full slot analysis — Ø|ba|Ø|a|Ø|Ø|tek|a mapping to SLOT1–SLOT11
Full slot analysis is linguistically richer but much harder to get right without ambiguity resolution. Prefix+root+suffix is achievable rule-based and sufficient for most NLP uses.

Q3 — Output format

Extend the existing gcbt .json format (add morphemes and pos keys per token)
Produce CoNLL-U alongside .json (standard for NLP pipelines)
Both
The architecture I'd propose (regardless of those answers)
GobeloGrammarLoader (existing)
    ↓  loads language YAML → NounClass[], ConcordSet[], VerbSlot[], PhonologyRules, etc.

GobeloTokenizer                          ← replaces ChitongaTokenizer
    __init__(language_iso, corpus_config_path)
        - loads GGT YAML via GobeloGrammarLoader
        - loads corpus_config.yaml (clitics, false_positives, code-switch lists)
        - builds all rule tables from the union of both
    
    tokenize(sentence: str) → List[WordToken]
        - word splitting (whitespace + punctuation, same as existing)
        - special token detection (numbers, URLs — language-agnostic already)
        - clitic segmentation driven by corpus_config per-language block

GobeloMorphSegmenter
    __init__(loader: GobeloGrammarLoader)
        - builds prefix trie from noun_class_system prefixes + allomorphs
        - builds verb prefix trie from subject_concords + TAM markers
        - builds extension suffix list from verb_extensions
    
    segment(word_token: WordToken) → MorphemeSpan[]
        - try noun analysis: NC prefix match → root → (optional derivational suffix)
        - try verb analysis: SM → (NEG) → TAM → (OM) → root → extensions → FV
        - return ranked analyses (best first)

GobeloPOSTagger
    __init__(loader: GobeloGrammarLoader)
        - indexes which NC prefixes signal which POS
        - loads verb slot obligatoriness to distinguish VERB vs NOUN.NC15
    
    tag(word_token: WordToken, morphemes: MorphemeSpan[]) → POSTag
        - rule-based: morpheme parse → POS deterministically
        - fallback: phonotactic heuristics from PhonologyRules

GobeloAnnotationPipeline
    tokenize → segment → tag → serialize
    reads gcbt JSON/TXT output, writes annotated JSON (+ optional CoNLL-U)
    inherits language_iso from gcbt JSON metadata
    CLI: mirrors existing gcbt CLI (--lang, --all, --list-langs, streaming, workers)
The key linguistic engine — the prefix trie
All three Bantu morpheme categories (NC nominal prefixes, SM/OM concords, TAM prefixes) are short (1–4 characters). A prefix trie built from the GGT YAML covers them all without any FST dependency. The trie is built once per language at __init__ time from:

noun_class_system.noun_classes[*].prefix + .allomorphs
concord_system.subject_concords[*].forms
verb_system.tam
The suffix side (final vowels, verb extensions) is a suffix trie on the reversed string.

The hard problem — ambiguity
Chitonga baya could be:

ba- (NC2 SM) + ya (root "go") → VERB.3PL.go
ba- (NC2 prefix) + ya (root noun?) → NOUN.NC2
Resolution requires either (a) a minimal lexicon of roots, or (b) a bigram/context rule (verbs follow subjects, nouns follow determiners). Option (a) is more tractable initially.

Does your corpus already have any annotated sentences we could use as a seed lexicon? Or are we going fully un-lexiconed (pure structural/morphological analysis)?

What are your answers to Q1–Q3, and the ambiguity question? That shapes whether this is a 3-week build or a 3-month one.

Q1 — POS tagset depth :Full UD — Universal Dependencies UPOS + language-specific FEATS fields
Q2 — Morpheme segmentation granularity: Full slot analysis — Ø|ba|Ø|a|Ø|Ø|tek|a mapping to SLOT1–SLOT11
Q3 — Output format: Both

4 Apr

Architected comprehensive morphological analysis system with phased implementation strategy
Architected comprehensive morphological analysis system with phased implementation strategy
Good. Those three answers significantly increase the scope but also the linguistic value. Let me lay out the full architecture before we write a line of code.

What Full UD + Full Slot + Both formats actually means
Full slot analysis means the verb baya doesn't just become two tokens — it becomes a structured parse across 11 positional slots, most of which are Ø (empty) for any given form. That's the hardest part: distinguishing filled slots from absent ones without a lexicon.

Full UD means the output must be valid CoNLL-U, with UPOS from the UD tagset and language-specific FEATS. For Bantu, the key UD-compatible features are:

GGT source	UD FEATS
Subject concord class	`Person=3
TAM marker	`Tense=Past
Verb extension PASS	Voice=Pass
Verb extension CAUS	Voice=Caus
Verb extension APPL	Voice=Appl
Augment present	Definite=Def
NC class of noun	`NounClass=NC9
Negation slot filled	Polarity=Neg
Final vowel = subjunctive	Mood=Sub
NC15 prefix (infinitive)	VerbForm=Inf
Both output formats means every annotated sentence exists in two synchronized representations:

# gcbt JSON annotated
{
  "sentence_id": "novel1_001",
  "language_iso": "toi",
  "text": "baya",
  "tokens": [{
    "form": "baya",
    "upos": "VERB",
    "feats": {"Person":"3","Number":"Plur","NounClass":"NC2","Tense":"Pres","Mood":"Ind"},
    "slots": {
      "SLOT3": {"form":"ba","gloss":"3PL.SM","concord_class":"NC2"},
      "SLOT5": {"form":"a","gloss":"PRES"},
      "SLOT8": {"form":"ya","gloss":"go.ROOT"},
      "SLOT10": {"form":"Ø","gloss":"IND.FV"}
    },
    "lemma": "ya"
  }]
}

# CoNLL-U
1  baya  ya  VERB  _  Aspect=Imp|Mood=Ind|NounClass=NC2|Number=Plur|Person=3|Tense=Pres  _  _  _  MorphSegm=ba+a+ya;SlotParse=SLOT3:ba|SLOT5:a|SLOT8:ya
The five modules
gobelo_tokenizer/
├── word_tokenizer.py       # GobeloWordTokenizer  — replaces ChitongaTokenizer
├── morph_segmenter.py      # GobeloMorphSegmenter — prefix/suffix trie + slot parser
├── pos_tagger.py           # GobeloPOSTagger      — slot parse → UD UPOS + FEATS
├── output_writers.py       # JsonWriter, CoNLLUWriter
└── annotation_pipeline.py  # GobeloAnnotationPipeline + CLI
GobeloWordTokenizer
Near-identical to the existing tokenizer but language_iso-parameterized. The language-specific data (clitic inventory, false positives, code-switch wordlists) comes from corpus_config.yaml per-language block — exactly the Layer 2 config that already exists in gcbt. No language-specific Python.

GobeloMorphSegmenter
The core engine. Takes a word token and returns a SlotParse — a dict mapping SLOT1–SLOT11 to a SlotFill (form, gloss, source_rule). Built from:

Prefix trie — all NC prefixes + allomorphs from noun_class_system
SM trie — all subject concord forms from concord_system.subject_concords
TAM trie — all TAM marker forms from verb_system.tam
OM trie — object concord forms
Extension suffix trie — all verb extensions by zone (Z1→Z4)
Final vowel set — from verb_system.final_vowels
Two analysis paths — nominal and verbal — are tried in parallel, scored, and returned ranked.

GobeloPOSTagger
Deterministic rule-based: given a SlotParse, maps to UPOS + FEATS using a small rule table that is the same for all languages (because the GGT YAML already uses canonical slot codes). SLOT3 filled + SLOT8 filled = VERB. NC prefix matched + no SLOT3/5 = NOUN. NC15 prefix = VERB with VerbForm=Inf.

Output writers
JsonWriter extends the existing gcbt JSON schema by adding slots, upos, feats, lemma per token. CoNLLUWriter produces standard CoNLL-U with morpheme segmentation in the MISC field.

GobeloAnnotationPipeline
Reads gcbt .json output (which already carries language_iso), runs the three-stage pipeline per sentence, writes annotated JSON + CoNLL-U. CLI mirrors gcbt: --lang, --all, --input-dir, --output-dir, streaming, worker pool.

The slot analysis algorithm
This is the hard core. Left-to-right greedy with backtracking over 11 positions:

Noun path (for each word):
  1. Try augment strip (i-/a- depending on language from YAML)
  2. Try NC prefix match from prefix trie (longest match wins)
  3. Remainder = nominal stem → SLOT8
  4. Score = prefix_confidence × stem_length_heuristic

Verb path:
  1. Check SLOT1-2: pre-initial negation/conditional (separate words usually)
  2. Try SM match from left (SLOT3): greedy longest match in SM trie
  3. Try NEG infix (SLOT4): check negation_infix forms
  4. Try TAM match (SLOT5): TAM trie
  5. Try modal/progressive (SLOT6)
  6. Try OM match (SLOT7): OM trie
  7. Strip suffixes from right:
     a. Final vowel (SLOT10) — known finite set per language
     b. Post-final clitics (SLOT11)
     c. Verb extensions (SLOT9) — peel Z4→Z3→Z2→Z1 order
  8. Remainder = verb root (SLOT8)
  9. Score = slots_filled / max_possible_slots
When both paths produce a parse, the higher-scoring one wins. When scores are equal, nominal analysis is preferred for sentence-initial position, verbal for post-noun.

The still-open ambiguity question
You didn't answer this and it determines how far the slot parser can go without a lexicon. Three options:

A — Structural only, no lexicon. Return all valid parses ranked by coverage. Mark low-confidence parses with confidence < 1.0. Best for a corpus annotation tool where human review is expected.

B — Seed lexicon from gcbt corpus. After running gcbt on a language, mine the most frequent word types, manually tag a few hundred, use that as a disambiguation prior. More accurate but requires initial human effort per language.

C — Agreement chain resolution. Within a sentence, track NC agreement: if ba- (NC2 SM) appears on a verb, find the NC2 noun it agrees with. This works without a lexicon but requires a sentence-level pass after initial word-by-word parse. This is linguistically the right approach for Bantu and is fully driven by the GGT YAML's concord tables.

My recommendation: start with A, implement C in Phase 2. Option C is elegant because the GGT concord tables are exactly the data needed — you're not adding anything outside the YAML.

Phased build plan
Phase	Deliverable	New code	Depends on
1	GobeloWordTokenizer + data models	~400 lines	corpus_config.yaml (existing)
2	GobeloMorphSegmenter (prefix/suffix tries)	~600 lines	GobeloGrammarLoader (existing)
3	GobeloPOSTagger + UD FEATS mapping	~350 lines	Phase 2 output
4	Output writers (JSON + CoNLL-U)	~250 lines	Phase 3 output
5	GobeloAnnotationPipeline + CLI	~300 lines	All above
6	Agreement chain disambiguation	~400 lines	Phase 5
Total: ~2,300 lines across 5 files. Phases 1–5 are the MVP; Phase 6 is the linguistic enhancement.

One decision needed before Phase 1
The existing Token dataclass in chitonga_tokenizer.py needs extending. The new WordToken model needs to carry slots, feats, and morpheme spans from the beginning — retrofitting these later is painful.

Should the new WordToken replace Token entirely (clean break), or extend it for backward compatibility with any code that already consumes ChitongaTokenizer output? If gcbt currently uses the tokenizer output directly in its pipeline, extending is safer.

Answer that and I'll build Phase 1 — the data models and GobeloWordTokenizer — as the first concrete output.

Clean break- replace Token entirely. I also have 2000 plus lexicon each for Chitonga verbs and nouns each

5 Apr

Check available skills
Check available skills
Claude's response could not be fully generated
Continue

5 Apr

Architected Phase 1 data models and tokenizer implementation
Architected Phase 1 data models and tokenizer implementation
Good — the lexicons change the ambiguity resolution story significantly. With 2000+ verb roots and 2000+ noun stems, the morpheme segmenter (Phase 2) can do real disambiguation. I'll design the models now to accommodate lexicon lookups from the start.

Phase 1 delivers three files: models.py, lexicon_store.py, and word_tokenizer.py.


Ran a command, created a file
Ran a command, created a file
Claude's response could not be fully generated
Continue

6 Apr

The  arhitecture proposed:
GobeloGrammarLoader (existing)
    ↓  loads language YAML → NounClass[], ConcordSet[], VerbSlot[], PhonologyRules, etc.

GobeloTokenizer                          ← replaces ChitongaTokenizer
    __init__(language_iso, corpus_config_path)
        - loads GGT YAML via GobeloGrammarLoader
        - loads corpus_config.yaml (clitics, false_positives, code-switch lists)
        - builds all rule tables from the union of both
    
    tokenize(sentence: str) → List[WordToken]
        - word splitting (whitespace + punctuation, same as existing)
        - special token detection (numbers, URLs — language-agnostic already)
        - clitic segmentation driven by corpus_config per-language block

GobeloMorphSegmenter
    __init__(loader: GobeloGrammarLoader)
        - builds prefix trie from noun_class_system prefixes + allomorphs
        - builds verb prefix trie from subject_concords + TAM markers
        - builds extension suffix list from verb_extensions
    
    segment(word_token: WordToken) → MorphemeSpan[]
        - try noun analysis: NC prefix match → root → (optional derivational suffix)
        - try verb analysis: SM → (NEG) → TAM → (OM) → root → extensions → FV
        - return ranked analyses (best first)

GobeloPOSTagger
    __init__(loader: GobeloGrammarLoader)
        - indexes which NC prefixes signal which POS
        - loads verb slot obligatoriness to distinguish VERB vs NOUN.NC15
    
    tag(word_token: WordToken, morphemes: MorphemeSpan[]) → POSTag
        - rule-based: morpheme parse → POS deterministically
        - fallback: phonotactic heuristics from PhonologyRules

GobeloAnnotationPipeline
    tokenize → segment → tag → serialize
    reads gcbt JSON/TXT output, writes annotated JSON (+ optional CoNLL-U)
    inherits language_iso from gcbt JSON metadata
    CLI: mirrors existing gcbt CLI (--lang, --all, --list-langs, streaming, workers)

    Good — this is a rich design conversation. Let me lay out what I see in the existing tokenizer, the gaps, and a proposed architecture before we make any code decisions.

---

## What the existing tokenizer does and doesn't do

The `ChitongaTokenizer` is a solid word-level tokenizer. It handles:

- Whitespace splitting + punctuation detachment
- Clitic segmentation (proclitics, enclitics)
- Reduplication detection
- Code-switching / language ID
- Special token types (numbers, URLs, dates)

What it **doesn't** do — and what you want to add:

- **Morpheme segmentation** — splitting `baya` → `[ba-|ya]` using NC prefix/verb slot knowledge
- **POS tagging** — assigning `VERB.3PL` or `NOUN.NC6` driven by the GGT YAML
- **Language-agnosticism** — it's wired to `TOI`; adding a second language requires forking the class

It also has a hard dependency on `chitonga_grammar` (an FST module) that doesn't exist for other languages.

---

## Proposed architecture — three questions first

Before I sketch the full design, I need your answers on three things that will determine the shape of everything else:

**Q1 — POS tagset depth**

Which of these is closest to what you want?

- **Shallow** — `NOUN`, `VERB`, `ADJ`, `ADV`, `PRON`, `CONJ`, `PUNCT`, `NUM`, `DISC`, `LOAN`
- **NC-aware** — `NOUN.NC1`, `NOUN.NC6`, `VERB.FIN`, `VERB.INF`, `DET.PROX.NC3`, etc.
- **Full UD** — Universal Dependencies UPOS + language-specific FEATS fields (compatible with UD treebanks)

**Q2 — Morpheme segmentation granularity**

- **Prefix+root+suffix** only — `ku|tek|a` (three segments)
- **Full slot analysis** — `Ø|ba|Ø|a|Ø|Ø|tek|a` mapping to SLOT1–SLOT11

Full slot analysis is linguistically richer but much harder to get right without ambiguity resolution. Prefix+root+suffix is achievable rule-based and sufficient for most NLP uses.

**Q3 — Output format**

- Extend the existing gcbt `.json` format (add `morphemes` and `pos` keys per token)
- Produce [CoNLL-U](https://universaldependencies.org/format.html) alongside `.json` (standard for NLP pipelines)
- Both

---

## The architecture I'd propose (regardless of those answers)

```
GobeloGrammarLoader (existing)
    ↓  loads language YAML → NounClass[], ConcordSet[], VerbSlot[], PhonologyRules, etc.

GobeloTokenizer                          ← replaces ChitongaTokenizer
    __init__(language_iso, corpus_config_path)
        - loads GGT YAML via GobeloGrammarLoader
        - loads corpus_config.yaml (clitics, false_positives, code-switch lists)
        - builds all rule tables from the union of both
    
    tokenize(sentence: str) → List[WordToken]
        - word splitting (whitespace + punctuation, same as existing)
        - special token detection (numbers, URLs — language-agnostic already)
        - clitic segmentation driven by corpus_config per-language block

GobeloMorphSegmenter
    __init__(loader: GobeloGrammarLoader)
        - builds prefix trie from noun_class_system prefixes + allomorphs
        - builds verb prefix trie from subject_concords + TAM markers
        - builds extension suffix list from verb_extensions
    
    segment(word_token: WordToken) → MorphemeSpan[]
        - try noun analysis: NC prefix match → root → (optional derivational suffix)
        - try verb analysis: SM → (NEG) → TAM → (OM) → root → extensions → FV
        - return ranked analyses (best first)

GobeloPOSTagger
    __init__(loader: GobeloGrammarLoader)
        - indexes which NC prefixes signal which POS
        - loads verb slot obligatoriness to distinguish VERB vs NOUN.NC15
    
    tag(word_token: WordToken, morphemes: MorphemeSpan[]) → POSTag
        - rule-based: morpheme parse → POS deterministically
        - fallback: phonotactic heuristics from PhonologyRules

GobeloAnnotationPipeline
    tokenize → segment → tag → serialize
    reads gcbt JSON/TXT output, writes annotated JSON (+ optional CoNLL-U)
    inherits language_iso from gcbt JSON metadata
    CLI: mirrors existing gcbt CLI (--lang, --all, --list-langs, streaming, workers)
```

---

## The key linguistic engine — the prefix trie

All three Bantu morpheme categories (NC nominal prefixes, SM/OM concords, TAM prefixes) are short (1–4 characters). A prefix trie built from the GGT YAML covers them all without any FST dependency. The trie is built once per language at `__init__` time from:

- `noun_class_system.noun_classes[*].prefix` + `.allomorphs`
- `concord_system.subject_concords[*].forms`
- `verb_system.tam`

The suffix side (final vowels, verb extensions) is a suffix trie on the reversed string.

---

## The hard problem — ambiguity

Chitonga `baya` could be:
- `ba-` (NC2 SM) + `ya` (root "go") → `VERB.3PL.go`
- `ba-` (NC2 prefix) + `ya` (root noun?) → `NOUN.NC2`

Resolution requires either (a) a minimal lexicon of roots, or (b) a bigram/context rule (verbs follow subjects, nouns follow determiners). Option (a) is more tractable initially.

Does your corpus already have any annotated sentences we could use as a seed lexicon? Or are we going fully un-lexiconed (pure structural/morphological analysis)?

---

What are your answers to Q1–Q3, and the ambiguity question? That shapes whether this is a 3-week build or a 3-month one.
The answers to Q1-q3: 
Q1 — POS tagset depth :Full UD — Universal Dependencies UPOS + language-specific FEATS fields
Q2 — Morpheme segmentation granularity: Full slot analysis — `Ø|ba|Ø|a|Ø|Ø|tek|a` mapping to SLOT1–SLOT11
Q3 — Output format: Both

Good. Those three answers significantly increase the scope but also the linguistic value. Let me lay out the full architecture before we write a line of code.

---

## What Full UD + Full Slot + Both formats actually means

**Full slot analysis** means the verb `baya` doesn't just become two tokens — it becomes a structured parse across 11 positional slots, most of which are Ø (empty) for any given form. That's the hardest part: distinguishing filled slots from absent ones without a lexicon.

**Full UD** means the output must be valid CoNLL-U, with UPOS from the UD tagset and language-specific FEATS. For Bantu, the key UD-compatible features are:

| GGT source | UD FEATS |
|---|---|
| Subject concord class | `Person=3|Number=Plur|NounClass=NC2` |
| TAM marker | `Tense=Past|Aspect=Perf|Mood=Ind` |
| Verb extension PASS | `Voice=Pass` |
| Verb extension CAUS | `Voice=Caus` |
| Verb extension APPL | `Voice=Appl` |
| Augment present | `Definite=Def` |
| NC class of noun | `NounClass=NC9|Number=Sing` |
| Negation slot filled | `Polarity=Neg` |
| Final vowel = subjunctive | `Mood=Sub` |
| NC15 prefix (infinitive) | `VerbForm=Inf` |

**Both output formats** means every annotated sentence exists in two synchronized representations:

```
# gcbt JSON annotated
{
  "sentence_id": "novel1_001",
  "language_iso": "toi",
  "text": "baya",
  "tokens": [{
    "form": "baya",
    "upos": "VERB",
    "feats": {"Person":"3","Number":"Plur","NounClass":"NC2","Tense":"Pres","Mood":"Ind"},
    "slots": {
      "SLOT3": {"form":"ba","gloss":"3PL.SM","concord_class":"NC2"},
      "SLOT5": {"form":"a","gloss":"PRES"},
      "SLOT8": {"form":"ya","gloss":"go.ROOT"},
      "SLOT10": {"form":"Ø","gloss":"IND.FV"}
    },
    "lemma": "ya"
  }]
}

# CoNLL-U
1  baya  ya  VERB  _  Aspect=Imp|Mood=Ind|NounClass=NC2|Number=Plur|Person=3|Tense=Pres  _  _  _  MorphSegm=ba+a+ya;SlotParse=SLOT3:ba|SLOT5:a|SLOT8:ya
```

---

## The five modules

```
gobelo_tokenizer/
├── word_tokenizer.py       # GobeloWordTokenizer  — replaces ChitongaTokenizer
├── morph_segmenter.py      # GobeloMorphSegmenter — prefix/suffix trie + slot parser
├── pos_tagger.py           # GobeloPOSTagger      — slot parse → UD UPOS + FEATS
├── output_writers.py       # JsonWriter, CoNLLUWriter
└── annotation_pipeline.py  # GobeloAnnotationPipeline + CLI
```

### GobeloWordTokenizer
Near-identical to the existing tokenizer but `language_iso`-parameterized. The language-specific data (clitic inventory, false positives, code-switch wordlists) comes from `corpus_config.yaml` per-language block — exactly the Layer 2 config that already exists in gcbt. No language-specific Python.

### GobeloMorphSegmenter
The core engine. Takes a word token and returns a `SlotParse` — a dict mapping SLOT1–SLOT11 to a `SlotFill` (form, gloss, source_rule). Built from:

- **Prefix trie** — all NC prefixes + allomorphs from `noun_class_system`
- **SM trie** — all subject concord forms from `concord_system.subject_concords`
- **TAM trie** — all TAM marker forms from `verb_system.tam`
- **OM trie** — object concord forms
- **Extension suffix trie** — all verb extensions by zone (Z1→Z4)
- **Final vowel set** — from `verb_system.final_vowels`

Two analysis paths — **nominal** and **verbal** — are tried in parallel, scored, and returned ranked.

### GobeloPOSTagger
Deterministic rule-based: given a `SlotParse`, maps to UPOS + FEATS using a small rule table that is the same for all languages (because the GGT YAML already uses canonical slot codes). SLOT3 filled + SLOT8 filled = VERB. NC prefix matched + no SLOT3/5 = NOUN. NC15 prefix = VERB with `VerbForm=Inf`.

### Output writers
`JsonWriter` extends the existing gcbt JSON schema by adding `slots`, `upos`, `feats`, `lemma` per token. `CoNLLUWriter` produces standard CoNLL-U with morpheme segmentation in the MISC field.

### GobeloAnnotationPipeline
Reads gcbt `.json` output (which already carries `language_iso`), runs the three-stage pipeline per sentence, writes annotated JSON + CoNLL-U. CLI mirrors gcbt: `--lang`, `--all`, `--input-dir`, `--output-dir`, streaming, worker pool.

---

## The slot analysis algorithm

This is the hard core. Left-to-right greedy with backtracking over 11 positions:

```
Noun path (for each word):
  1. Try augment strip (i-/a- depending on language from YAML)
  2. Try NC prefix match from prefix trie (longest match wins)
  3. Remainder = nominal stem → SLOT8
  4. Score = prefix_confidence × stem_length_heuristic

Verb path:
  1. Check SLOT1-2: pre-initial negation/conditional (separate words usually)
  2. Try SM match from left (SLOT3): greedy longest match in SM trie
  3. Try NEG infix (SLOT4): check negation_infix forms
  4. Try TAM match (SLOT5): TAM trie
  5. Try modal/progressive (SLOT6)
  6. Try OM match (SLOT7): OM trie
  7. Strip suffixes from right:
     a. Final vowel (SLOT10) — known finite set per language
     b. Post-final clitics (SLOT11)
     c. Verb extensions (SLOT9) — peel Z4→Z3→Z2→Z1 order
  8. Remainder = verb root (SLOT8)
  9. Score = slots_filled / max_possible_slots
```

When both paths produce a parse, the higher-scoring one wins. When scores are equal, nominal analysis is preferred for sentence-initial position, verbal for post-noun.

---

## The still-open ambiguity question

You didn't answer this and it determines how far the slot parser can go without a lexicon. Three options:

**A — Structural only, no lexicon.** Return all valid parses ranked by coverage. Mark low-confidence parses with `confidence < 1.0`. Best for a corpus annotation tool where human review is expected.

**B — Seed lexicon from gcbt corpus.** After running gcbt on a language, mine the most frequent word types, manually tag a few hundred, use that as a disambiguation prior. More accurate but requires initial human effort per language.

**C — Agreement chain resolution.** Within a sentence, track NC agreement: if `ba-` (NC2 SM) appears on a verb, find the NC2 noun it agrees with. This works without a lexicon but requires a sentence-level pass after initial word-by-word parse. This is linguistically the right approach for Bantu and is fully driven by the GGT YAML's concord tables.

My recommendation: **start with A, implement C in Phase 2**. Option C is elegant because the GGT concord tables are exactly the data needed — you're not adding anything outside the YAML.

---

## Phased build plan

| Phase | Deliverable | New code | Depends on |
|---|---|---|---|
| 1 | GobeloWordTokenizer + data models | ~400 lines | corpus_config.yaml (existing) |
| 2 | GobeloMorphSegmenter (prefix/suffix tries) | ~600 lines | GobeloGrammarLoader (existing) |
| 3 | GobeloPOSTagger + UD FEATS mapping | ~350 lines | Phase 2 output |
| 4 | Output writers (JSON + CoNLL-U) | ~250 lines | Phase 3 output |
| 5 | GobeloAnnotationPipeline + CLI | ~300 lines | All above |
| 6 | Agreement chain disambiguation | ~400 lines | Phase 5 |

Total: ~2,300 lines across 5 files. Phases 1–5 are the MVP; Phase 6 is the linguistic enhancement.

---

## One decision needed before Phase 1

The existing `Token` dataclass in `chitonga_tokenizer.py` needs extending. The new `WordToken` model needs to carry slots, feats, and morpheme spans from the beginning — retrofitting these later is painful.

Should the new `WordToken` **replace** `Token` entirely (clean break), or **extend** it for backward compatibility with any code that already consumes `ChitongaTokenizer` output? If gcbt currently uses the tokenizer output directly in its pipeline, extending is safer.

Answer that and I'll build Phase 1 — the data models and `GobeloWordTokenizer` — as the first concrete output.



Good — the lexicons change the ambiguity resolution story significantly. With 2000+ verb roots and 2000+ noun stems, the morpheme segmenter (Phase 2) can do real disambiguation. I'll design the models now to accommodate lexicon lookups from the start.

Phase 1 delivered three files: models.py, lexicon_store.py, and word_tokenizer.py.

Now I'll build morph_analyser.py — the Phase 2 morphological analyser. This is the most linguistically significant component: it takes AnnotatedSentence from the tokeniser and populates SlotParse objects with real verb slot-filling and noun class identification, driven entirely by the YAML grammar data.

Phase 2 deliverables: morph_analyser.py — GobelloMorphAnalyser v2.0.0
Architecture
Three internal components, all driven exclusively by grammar tables from the loader:
_AnalyserConfig — built once at construction time. Flattens all YAML grammar sections into fast Python dicts/lists: SM table, SM reverse index, TAM table+reverse, OM table+reverse, FV reverse (longest-first), extension reverse (longest-first by form), NC prefix table (longest-first), UD TAM feature mapping. No YAML objects in the analysis inner loop.
GobeloVerbParser — left-to-right prefix-peeling strategy across the 11-slot template. Strategy per slot: try all candidates longest-first; branch on optional slots (TAM, OM, extensions) up to _MAX_HYPOTHESES=5; root-matching against lexicon_verb; FV stripping from the right side. Produces ranked SlotParse hypotheses.
GobeloNounAnalyser — tries all NC prefixes longest-first; optionally strips augment first; matches remainder against lexicon_noun; returns top-3 (nc_key, stem, entry, score) tuples.
Scoring (verb hypotheses)
ComponentScoreLexicon root hit+0.40Verified root bonus+0.02Final vowel identified+0.15TAM prefix identified+0.10SM identified+0.08OM identified+0.05Extension zone identified+0.05Negation prefix+0.03Exact surface reconstruction+0.05
Public API
pythonana = GobelloMorphAnalyser(loader)            # one per language
sentence = ana.analyse(sentence)              # mutates in place, returns same obj
sentences = ana.analyse_batch([s1, s2, ...])  # list version
print(ana.describe())                         # config summary
What gets populated per token

token.slot_parses — ranked SlotParse list, best at index token.best_parse
token.upos — VERB or NOUN (updated from best parse)
token.lemma — verb root or noun stem
token.feats — UD morphological features from TAM + SM
token.morpheme_spans — character-aligned spans for each morpheme
token.noun_class — for noun tokens
token.is_oov — cleared when a lexicon match is confirmed
token.flags — VERB_ANALYSED or NOUN_ANALYSED

Key design note
The analyser accepts any GobeloGrammarLoader-compatible object and works across all 7 Zambian languages with zero Python changes. SiLozi's periphrastic TAM (NE auxiliary) will be handled naturally once its YAML grammar loads the appropriate TAM entries — the engine sees it as just another TAM prefix form.Morph analyserPY DownloadTest phase2PY DownloadDownload allif done with Phase 2, Proceed with Phase 3Sonnet 4.6

now Continue with the GGT gobelo_tokenizer project- Phase 3 to deliver: pos_tagger.py.

