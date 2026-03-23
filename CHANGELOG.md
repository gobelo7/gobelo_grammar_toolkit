# Changelog

All notable changes to the Gobelo Grammar Toolkit are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-03-21

### Added — Core library (`gobelo_grammar_toolkit/core/`)

- `GobeloGrammarLoader` — single grammar dependency for all apps (14 public methods)
- `GrammarConfig` dataclass — language identifier + optional override path
- `GrammarMetadata` — version and identity fields with loader compatibility window
- `NounClass`, `TAMMarker`, `VerbExtension`, `VerbSlot`, `ConcordSet` — typed domain models
- `PhonologyRules`, `TokenizationRules`, `DerivationalPattern` — supplementary models
- `VerifyFlag` — unresolved VERIFY annotation model for F-06 resolver workflow
- `GobeloGrammarNormalizer` — handles two YAML formats transparently:
  - **Canonical format** — schema used by new languages (from `canonical_grammar_template.yaml`)
  - **Reference-grammar format** — chiTonga's existing YAML with nested `noun_class_system`, `concord_system`, `phonology_rules` structure
- `GobeloGrammarValidator` — schema validation + VERIFY flag extraction + version compatibility check
- `language_registry` — maps 7 language identifiers to grammar YAML filenames
- `GGTError` exception hierarchy — `LanguageNotFoundError`, `VersionIncompatibleError`, `SchemaValidationError`, `UnverifiedFormError`

### Added — Grammar data (`gobelo_grammar_toolkit/languages/`)

- `chitonga.yaml` — pilot grammar, 4 236 lines, fully verified (0 VERIFY flags)
  - 21 noun classes (NC1–NC18 + NC1a, NC2a, NC2b), all active
  - 8 TAM markers (PRES, PST, REC_PST, REM_PST, FUT_NEAR, FUT_REM, HAB, PERF)
  - 18 concord paradigm types (subject, object, possessive, demonstrative, …)
  - 14 verb extensions across 4 zones (Z1 APPL/CAUS/TRANS/CONT, Z2 RECIP/STAT, Z3 PASS, Z4 aspectual)
  - 11-slot verb template with flag-diacritic co-occurrence constraints
  - Phonological rules: VH.1 (vowel harmony), CA.1–CA.2 (consonant alternation), SND.1–SND.4 (sandhi), MP.1, VL.2
  - Tone system: four-level; Phase 1 uses tag-distinguished disambiguation (PST vs REM_PST)
- `chibemba.yaml` — stub grammar registered for development; data TBD
- Stubs registered for: `chinyanja`, `silozi`, `luvale`, `lunda`, `kaonde`

### Added — NLP apps (`gobelo_grammar_toolkit/apps/`)

- `MorphologicalAnalyzer` (F-01, F-02) — `analyze()`, `generate()`, `segment_text()`, `generate_interlinear()`
  - Verbal path: strips SM → TAM → root → extensions → FV; produces ranked `ParseHypothesis` list
  - Nominal path: prefix scan over all NC classes; fallback to single-morpheme hypothesis
  - 4 verbal hypotheses for `cilya`, best segmented as `ci-ly-a`
- `ParadigmGenerator` (F-04) — `generate_verb_paradigm()`, `generate_noun_paradigm()`, `to_csv()`, `to_markdown()`, `to_html()`
  - 25 SC rows × 8 TAM columns for chiTonga; `(NC7, TAM_PRES)` → `alyaa`
- `ConcordGenerator` (F-03) — `generate_all_concords()`, `generate_all_concords_rich()`, `cross_tab()`, `generate_paradigm()`
  - Full cross-tab: 21 NCs × 18 paradigm types; NC1a subclass fallback to NC1
- `CorpusAnnotator` (F-09) — `annotate_text()`, `annotate_file()`, `to_conllu()`, `write_conllu()`
  - CoNLL-U output: 10 columns, `# sent_id` / `# text` comments, UPOS and FEATS populated
- `UDFeatureMapper` (F-07) — `map_nc()`, `map_tam()`, `map_concord_key()`, `map_extension()`, `map_segmented_token()`, `to_conllu_feats()`
  - `NC7` → `Bantu7 Sing`; `TAM_PRES` → `Tense=Pres Aspect=Imp Mood=Ind`
  - `PASS` → `Voice=Pass`; `APPL` → `Voice=Appl`
- `VerbSlotValidator` — `validate()`, `check_extension_ordering()`, `obligatory_slots()`, `extension_zone()`
  - Validates 11-slot template; obligatory: SLOT3/SLOT8/SLOT10; zone ordering Z1<Z2<Z3
- `FeatureComparator` — `compare()`, `compare_many()`, `to_markdown()`, `to_csv()`
  - Cross-language comparison: `noun_class.NC1.prefix` chiTonga=`mu-` vs chiBemba=`u-`

### Added — HFST pipeline (`gobelo_grammar_toolkit/hfst/`)

- `chitonga.lexc` — 11-slot morphotactics with 185 multichar symbols
  - Flag diacritics: `@P/R/D.NC.1–18@` (NC agreement), `@P/R/D.NEG.ON@` (negation), `@P/R.MOOD.SUBJ@` (mood-FV), `@P/R.NUM.PL@` (reciprocal plural)
  - Continuation class chain enforces zone Z1→Z2→Z3→FV ordering
- `chitonga.twolc` — 9 phonological rules in 4 processing stages: morphophonology (VH.1, CA.1, CA.2), sandhi (SND.1–4), prosodic (MP.1, VL.2 deferred), tonal (deferred to Phase 2)
- `hfst_config.yaml` — build parameters, multichar symbol inventory, flag diacritic declarations, tone strategy
- `build_fst.py` — reads `verbs.yaml`/`nouns.yaml`/`closed_class.yaml`, generates `chitonga-full.lexc`, compiles via HFST pipeline
- `hfst_backend.py` — `parse_tag()` translates raw `hfst-lookup` output to mapper-compatible `ParsedTag` objects; resolves 3 vocabulary mismatches (TAM prefix, SM/OM format, flag diacritics); 20/20 tag translation tests pass
- Lexicon files: `verbs.yaml`, `nouns.yaml`, `auxiliary_verbs.yaml`, `closed_class.yaml`
- `chitonga_transform.py` — CSV → structured YAML lexicon pipeline with morphological pre-analysis and stem confidence scoring

### Added — CLI (`gobelo_grammar_toolkit/cli/ggt_cli.py`)

- `ggt info <language>` — metadata + feature-count summary table
- `ggt noun-classes <language> [--active-only]` — formatted NC table
- `ggt concords <language> <type> [--all-types]` — concord paradigm
- `ggt validate <path> [--strict]` — schema validation + VERIFY flag report
- `ggt verify-flags <language> [--resolved] [--field PREFIX] [--count]` — VERIFY flag listing
- `ggt diff <lang_a> <lang_b> [--feature]` — semantic diff across 5 feature sections
- Exit codes: 0 = success, 1 = load error, 2 = validation failure, 3 = unknown concord type

### Added — Web layer (`web/`)

- `web/backend/app.py` — Flask 3 REST API, 15 routes (CORS, per-language lazy cache, structured errors)
  - `GET  /api/languages` — registry list
  - `GET  /api/metadata/<lang>` — grammar stats
  - `GET  /api/noun-classes/<lang>` — NC inventory
  - `GET  /api/tam/<lang>` — TAM markers
  - `GET  /api/extensions/<lang>` — verb extensions
  - `POST /api/analyze` — `MorphologicalAnalyzer.analyze()` → morphemes + UD
  - `POST /api/generate` — `MorphologicalAnalyzer.generate()` → surface form
  - `GET  /api/paradigm/<lang>/<root>` — SM×TAM table, CSV/Markdown/HTML export
  - `GET  /api/concords/<lang>/<nc>` — all concord forms for one NC
  - `GET  /api/concords/<lang>` — full cross-tab, CSV export
  - `POST /api/annotate` — CoNLL-U annotation
  - `GET  /api/validate/<lang>/<word>` — slot validation
  - `GET  /api/compare` — cross-language feature diff
  - `GET  /api/verify-flags/<lang>` — unresolved flags
  - `GET  /api/interlinear` — interlinear gloss
  - 21/21 route tests pass, including error cases
- `web/frontend/index.html` — single-file SPA, 1 418 lines
  - **TeacherView**: Grammar Info, Verb Paradigms, Concord Matrix, Morpheme Analysis, Corpus Annotator, Language Comparator, Verify Flags
  - **StudentView**: Analyse a Word, Grammar Quiz (10 Qs), Vocabulary Cards, Noun Classes, Concords
  - All views call real API; no static grammar data; lazy per-language cache
  - Morpheme ribbon with slot-coloured blocks; UD FEATS tags; CoNLL-U syntax highlighting; downloadable output

### Added — Developer tooling (`scripts/`, `tests/`, `pyproject.toml`)

- `scripts/validate_grammar.py` — validate any grammar YAML; `--strict`, `--all`, `--json`
- `scripts/add_language.py` — scaffold new grammar from canonical template + register in registry
- `scripts/build_hfst.sh` — compile all 7 language FSTs
- `tests/unit/test_loader_chitonga.py` — 46 loader round-trip checks (all pass)
- `tests/integration/test_apps_chitonga.py` — 61 app integration checks (60 pass; 1 known API variance fixed)
- `tests/fixtures/minimal_chitonga.yaml` — 4-NC / 2-TAM / 4-ext fixture; loads in < 50 ms
- `tests/fixtures/stub_chibemba.yaml` — 2-NC stub for multi-language tests; NC1 prefix `u-` ≠ chiTonga `mu-`
- `pyproject.toml` — setuptools build, entry point `ggt`, package-data `languages/*.yaml`

### Known limitations (Phase 2)

- Tone not represented on surface strings; PST/REM_PST share `aka`, disambiguated by tag only
- Penultimate lengthening (VL.2) not applied; citation forms lack automatic length
- Grammar YAMLs for 6 languages (chibemba, chinyanja, silozi, luvale, lunda, kaonde) are stubs — linguistic data to be added
- `FeatureComparator.for_all_languages()` requires all 7 grammars to be populated
- HFST Phase 2 (autosegmental tone overlay) deferred
