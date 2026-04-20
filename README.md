# Gobelo Grammar Toolkit (GGTK)

A grammar-driven NLP library for the 7 official Zambian Bantu languages, built on a single YAML grammar file as the authoritative linguistic source.

**Languages:** chiTonga · chiBemba · chiNyanja · siLozi · Luvale · Lunda · Kaonde  
**Status:** v1.0.0 — chiTonga fully implemented; 6 languages registered, grammar data in progress  
**Python:** 3.8+  **License:** MIT

---

## Quick start

```bash
git clone https://github.com/gobelo/gobelo-grammar-toolkit
cd ggtk
pip install -e .              # installs ggt CLI + library
```

```python
from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig

loader   = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
analyzer = MorphologicalAnalyzer(loader)

tok = analyzer.analyze("cilya")
print(tok.best.segmented)   # ci-ly-a
print(tok.best.gloss_line)  # NC7.SUBJ-ly-FV
```

---

## Architecture

The grammar YAML is the single source of truth. No morpheme forms are hardcoded anywhere in the apps — every segmentation, generation, and concord lookup reads from the loader.

```
chitonga.yaml
    └── GobeloGrammarLoader          ← the only grammar dependency
            ├── MorphologicalAnalyzer    analyze(), generate()
            ├── ParadigmGenerator        generate_verb_paradigm()
            ├── ConcordGenerator         cross_tab(), generate_all_concords()
            ├── CorpusAnnotator          annotate_text() → CoNLL-U
            ├── UDFeatureMapper          map_segmented_token() → UD FEATS
            ├── VerbSlotValidator        validate()
            └── FeatureComparator        compare() across languages
```

Adding a new language requires only one grammar YAML and one registry entry — no app code changes.

---

## CLI

```bash
ggt info chitonga                         # grammar stats
ggt noun-classes chitonga                 # NC inventory table
ggt concords chitonga subject_concords    # SM paradigm
ggt validate languages/chitonga.yaml      # schema check
ggt verify-flags chitonga                 # VERIFY annotations
ggt diff chitonga chibemba --feature nc   # cross-language diff
```

---

## Web UI

```bash
cd web/backend
pip install -r requirements.txt
python app.py                     # http://localhost:5000/
```

The single-page app at `web/frontend/index.html` provides:

- **TeacherView** — paradigm tables, concord matrix, morpheme analysis, corpus annotator (CoNLL-U), language comparator, VERIFY flag inspector
- **StudentView** — word analyser with plain-English explanations, grammar quiz, vocabulary cards, noun class reference, concords table

---

## Developer scripts

```bash
# Validate a grammar YAML
python scripts/validate_grammar.py languages/chitonga.yaml
python scripts/validate_grammar.py languages/ --all --strict

# Add a new language
python scripts/add_language.py chibemba
python scripts/add_language.py kaonde --iso kqn --guthrie L.41

# Build HFST analysers (requires hfst tools)
./scripts/build_hfst.sh
./scripts/build_hfst.sh chitonga --no-test
```

---

## Running tests

```bash
pytest tests/unit/test_loader_chitonga.py -v       # 46 loader checks
pytest tests/integration/test_apps_chitonga.py -v  # 61 app checks
pytest tests/ -v                                   # full suite
```

---

## Project structure

```
gobelo/
├── gobelo_grammar_toolkit/
│   ├── core/          loader.py, normalizer.py, validator.py, models.py
│   ├── apps/          7 NLP app modules
│   ├── cli/           ggt_cli.py (6 commands)
│   ├── languages/     chitonga.yaml (4 236 lines, fully verified)
│   └── hfst/          lexc, twolc, build_fst.py, hfst_backend.py
├── web/
│   ├── backend/       app.py (Flask, 15 routes)
│   └── frontend/      index.html (1 418 lines, TeacherView + StudentView)
├── tests/
│   ├── unit/          test_loader_chitonga.py
│   ├── integration/   test_apps_chitonga.py
│   └── fixtures/      minimal_chitonga.yaml, stub_chibemba.yaml
├── scripts/           validate_grammar.py, add_language.py, build_hfst.sh
├── pyproject.toml
├── CHANGELOG.md
└── README.md
```

---

## Adding a language

1. Run `python scripts/add_language.py <language>` — generates a valid stub YAML and registers it
2. Open `languages/<language>.yaml` — fill every REQUIRED section
3. Run `python scripts/validate_grammar.py languages/<language>.yaml` — fix all errors
4. VERIFY flags may remain; resolve them against primary-source grammars over time
5. Commit — all 7 apps automatically pick up the new language at next loader construction

---

## Grammar YAML schema

Key sections (all REQUIRED unless noted):

| Section | Key fields |
|---|---|
| `metadata` | `language`, `iso_code`, `guthrie`, `grammar_version`, loader compatibility window |
| `phonology` | `vowels`, `consonants`, `tone_system`, `sandhi_rules` (OPTIONAL) |
| `noun_classes` | `id`, `prefix`, `semantic_domain`, `active`, counterpart links |
| `concord_systems` | `subject_concords`, `object_concords` (minimum); any additional paradigms |
| `verb_system.tam_markers` | `id`, `form`, `tense`, `aspect`, `mood` |
| `verb_system.verb_extensions` | `id`, `canonical_form`, `zone` (Z1–Z4), `semantic_value` |
| `verb_system.verb_slots` | `id`, `name`, `position`, `obligatory`, `allowed_content_types` |
| `tokenization` | `word_boundary_pattern` |

---

## HFST pipeline (Phase 2)

The FST layer translates between surface forms and tagged lexical representations:

```
hfst-lexc chitonga.lexc     → morphotactics.hfst
hfst-twolc chitonga.twolc   → phonology.hfst
hfst-compose-intersect      → analyser.hfst
hfst-invert                 → generator.hfst
```

`parse_tag()` in `hfst_backend.py` bridges raw `hfst-lookup` output to the `UDFeatureMapper` vocabulary (3 mismatches resolved: TAM prefix, SM/OM format, flag diacritics). Phase 2 adds autosegmental tone overlay.

---

## Citation

If you use this toolkit in research, please cite:

```
Gobelo Grammar Toolkit v1.0.0.
https://github.com/gobelo/gobelo-grammar-toolkit
```
