gobelo_corpus/
│
├── gobelo_grammar_toolkit/          # installable Python package
│   │                                # (package path used in loader.py imports)
│   ├── __init__.py
│   │
│   ├── core/                        # grammar engine — zero language logic
│   │   ├── __init__.py
│   │   ├── config.py                # GrammarConfig dataclass            [✅ Phase 0]
│   │   ├── loader.py                # GobeloGrammarLoader — 14-method API [✅ Phase 0]
│   │   ├── models.py                # frozen dataclasses: NounClass,
│   │   │                            #   ConcordSet, TAMMarker, VerbSlot,
│   │   │                            #   PhonologyRules, VerifyFlag, etc.  [✅ Phase 0]
│   │   ├── normalizer.py            # GrammarNormalizer, _ParsedGrammar   [✅ Phase 0]
│   │   ├── registry.py              # lang_id → yaml filename map         [✅ Phase 0]
│   │   ├── validator.py             # GrammarValidator, LOADER_VERSION    [✅ Phase 0]
│   │   └── exceptions.py           # LanguageNotFoundError,
│   │                                #   NounClassNotFoundError,
│   │                                #   ConcordTypeNotFoundError,
│   │                                #   UnverifiedFormError               [✅ Phase 0]
│   │
│   └── languages/                   # GGT YAML grammar files
│       │                            # (loaded via importlib.resources)
│       ├── chibemba.yaml            #                                     [✅ complete]
│       ├── silozi.yaml              #                                     [✅ complete]
│       ├── chitonga.yaml            #                                     [✅ complete]
│       ├── chinyanja.yaml           #                                     [⏳ pending]
│       ├── cilunda.yaml             #                                     [⏳ pending]
│       ├── ciluvale.yaml            #                                     [⏳ pending]
│       └── cikaonde.yaml            #                                     [⏳ pending]
│
├── pipeline/                        # annotation pipeline — all six phases
│   ├── models.py                    # WordToken, AnnotatedSentence,
│   │                                #   SlotParse, SlotFill, MorphemeSpan,
│   │                                #   LexiconEntry (pipeline data layer) [✅ Phase 1]
│   ├── word_tokenizer.py            # GobeloWordTokenizer — 6-stage        [✅ Phase 1]
│   ├── morph_analyser.py            # GobelloMorphAnalyser — slot fills,
│   │                                #   noun-class ID, UD feats            [✅ Phase 2]
│   ├── pos_tagger.py                # GobeloPOSTagger — UPOS/FEATS/XPOS,
│   │                                #   closed-class, agreement Pass C     [✅ Phase 3]
│   ├── output_writers.py            # GobeloJsonWriter, GobeloCoNLLUWriter,
│   │                                #   GobeloDualWriter, WriterStats      [✅ Phase 4]
│   ├── annotation_pipeline.py       # GobeloAnnotationPipeline + CLI,
│   │                                #   orchestrates Phases 1–4, streaming,
│   │                                #   checkpointing, multiprocessing     [✅ Phase 5]
│   ├── agreement_chain.py           # GobeloAgreementChain — 4-pass
│   │                                #   SM/OM/modifier agreement resolver  [✅ Phase 6]
│   └── ggt_loader_adapter.py        # GGTLoaderAdapter — bridges raw YAML
│                                    #   dict → pipeline loader interface   [✅ bridge]
│
├── gcbt/                            # Gobelo Corpus Building Toolkit
│   ├── zambian_corpus_builder_v40.py  # corpus ingestion & segmentation   [✅ complete]
│   └── corpus_config.yaml           # per-language corpus settings        [✅ complete]
│
├── lexicons/                        # per-language lexicon data
│   ├── toi_verbs.json               # 2000+ ChiTonga verb roots            [✅ confirmed]
│   ├── toi_nouns.json               # 2000+ ChiTonga noun stems            [✅ confirmed]
│   └── ...                          # bem, loz, nya, lun, lue, kqn TBD
│
├── tests/
│   ├── phase1/
│   │   ├── test_models.py           #                                     [57 ✅ passing]
│   │   └── test_word_tokenizer.py
│   ├── phase2/
│   │   └── test_morph_analyser.py   #                                     [52 ✅ passing]
│   ├── phase3/
│   │   └── test_pos_tagger.py
│   ├── phase4/
│   │   └── test_output_writers.py
│   ├── phase5/
│   │   └── test_annotation_pipeline.py
│   ├── phase6/
│   │   └── test_agreement_chain.py
│   └── grammars/
│       └── test_loader.py
│
├── docs/
│   ├── GGT_Tokenizer_Guide.md               # Phase 1 implementation guide [✅]
│   ├── GGT_Tokenizer_Guide_2.md             # Phase 1–2 extended guide     [✅]
│   ├── GGT_Tokenizer_Interactive_Guide.html # interactive HTML guide        [✅]
│   └── grammar_documentation.yaml          # referenced in YAML metadata
│
├── outputs/                         # pipeline run artefacts (gitignored)
│   └── <lang_iso>/
│       └── annotations/
│           ├── <lang>_annotations.jsonl
│           ├── <lang>_annotations.conllu
│           ├── <lang>_annotations.stats.json
│           └── <lang>_pipeline.checkpoint
│
├── pyproject.toml
├── README.md
└── LICENSE