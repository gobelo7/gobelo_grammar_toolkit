Good — I now have full clarity on every design decision. Here are the detailed modalities:

---

## F-04 · Paradigm Table Generator

### Purpose and scope
Produce a fully-inflected paradigm table for a given verb root (or noun stem) across all subject concords × all TAM markers × optional polarity, exporting in Markdown, CSV, or HTML.

### New module: `apps/paradigm_generator.py`

**Exported types** (all `frozen=True`):

| Type | Fields |
|---|---|
| `ParadigmCell` | `subject_nc_key: str`, `tam_id: str`, `polarity: str`, `surface: str`, `segmented: str`, `gloss: str`, `warnings: Tuple[str, ...]` |
| `ParadigmTable` | `root: str`, `language: str`, `paradigm_type: Literal["verb", "noun"]`, `rows: Tuple[str, ...]` (row labels = SC keys), `columns: Tuple[str, ...]` (col labels = TAM ids), `cells: Dict[Tuple[str, str], ParadigmCell]`, `metadata: Dict[str, str]` |
| `ParadigmGenerationError(GGTError)` | — |

**Class: `ParadigmGenerator`**

Constructor: `__init__(self, loader: GobeloGrammarLoader)` — calls `MorphologicalAnalyzer(loader)` internally. The `MorphologicalAnalyzer` is not a parameter; this keeps F-04 as a single-dependency app consistent with the other apps.

Public API:

```python
generate_verb_paradigm(
    root: str,
    extensions: Tuple[str, ...] = (),
    polarities: Tuple[str, ...] = ("affirmative",),
    exclude_sc_keys: Optional[FrozenSet[str]] = None,
) -> ParadigmTable

generate_noun_paradigm(
    stem: str,
    nc_id: str,
) -> ParadigmTable   # concord type × NC columns

to_markdown(table: ParadigmTable) -> str
to_csv(table: ParadigmTable) -> str
to_html(table: ParadigmTable, title: str = "") -> str
```

**Cell generation logic** — pure iteration over `get_subject_concords().entries` × `get_tam_markers()`:

```
for each (sc_key, sc_form) in subject_concords.entries:
    for each tam in get_tam_markers():
        bundle = MorphFeatureBundle(
            root=root,
            subject_nc=sc_key,
            tam_id=tam.id,
            extensions=extensions,
            polarity=polarity,
            final_vowel="a",         # default; override for TAM_PERF → "ide"
        )
        sf = analyzer.generate(bundle)
        → ParadigmCell
```

The `final_vowel` override: the `tam_fv_interactions` section of the verb template specifies which TAM ids need a non-default FV. Read this at `__init__` time via `get_verb_template()["tam_fv_interactions"]` and build a `Dict[str, str]` mapping `tam_id → final_vowel`. Fall back to `"a"` for any TAM not in the map.

**Row/column ordering** — rows (SC keys) appear in the insertion order of `subject_concords.entries` (the YAML preserves person/number order). Columns (TAM ids) appear sorted by `TAMMarker` list order from `get_tam_markers()`.

**Output formats:**
- `to_markdown`: `|` table with SC key as first column, TAM ids as headers, surface form in each cell. Append a `> ⚠ N sandhi warnings suppressed` line if `warnings` are non-empty.
- `to_csv`: RFC 4180, first row = header, `surface (segmented)` in each cell.
- `to_html`: `<table>` with `<th>` headers, `title` as `<caption>`, `data-gloss` attribute on each `<td>` populated from the cell's `gloss` field.

**Noun paradigm**: calls `get_all_concord_types()`, then for each type calls `get_concords(type).entries[nc_id]` if that key exists. This gives a "concord agreement table" — one row per concord type, one column per NC class the stem belongs to. Simpler than the verb paradigm; does not use `MorphologicalAnalyzer`.

**Error handling**: `generate()` may raise `MorphAnalysisError`; catch it per cell, record `surface="ERROR"` and the error message in `warnings`, and continue — never abort the entire table for one bad cell.

---

## F-09 · Corpus Annotation Pipeline

### Purpose and scope
Accept a plain-text corpus file or string, run `segment_text()` + `map_segmented_token()` on every token, and write a CoNLL-U file with morphological annotation.

### New module: `apps/corpus_annotator.py`

**Exported types** (all `frozen=True`):

| Type | Fields |
|---|---|
| `AnnotatedToken` | `conllu_id: int`, `form: str`, `lemma: str`, `upos: str`, `xpos: str`, `feats: str`, `head: str`, `deprel: str`, `deps: str`, `misc: str`, `segmented_token: SegmentedToken`, `ud_bundle: UDFeatureBundle`, `is_ambiguous: bool`, `warnings: Tuple[str, ...]` |
| `AnnotatedSentence` | `sent_id: str`, `text: str`, `tokens: Tuple[AnnotatedToken, ...]`, `language: str` |
| `AnnotationResult` | `language: str`, `total_sentences: int`, `total_tokens: int`, `ambiguous_tokens: int`, `failed_tokens: int`, `sentences: Tuple[AnnotatedSentence, ...]` |
| `CorpusAnnotationError(GGTError)` | — |

**Class: `CorpusAnnotator`**

Constructor: `__init__(self, loader: GobeloGrammarLoader)` — builds `MorphologicalAnalyzer(loader)` and `UDFeatureMapper(loader)` internally.

Public API:

```python
annotate_text(
    text: str,
    sent_id_prefix: str = "sent",
    max_hypotheses: int = 1,
) -> AnnotationResult

annotate_file(
    path: str | Path,
    encoding: str = "utf-8",
    sent_id_prefix: str = "sent",
    max_hypotheses: int = 1,
) -> AnnotationResult

to_conllu(result: AnnotationResult) -> str
write_conllu(result: AnnotationResult, path: str | Path, encoding: str = "utf-8") -> None

@property language: str
@property loader: GobeloGrammarLoader
```

**Sentence segmentation strategy** — the public API provides no sentence segmenter; the pipeline uses a two-pass approach:
1. Split on blank lines first (standard corpus format — blank line = sentence boundary).
2. If no blank lines found, split on `.`, `!`, `?`, `።` (Ethiopic), and `。` (fallback safe), stripping whitespace. This is intentionally minimal — the spec says to flag ambiguous parses, not to achieve perfect sentence splitting.

**Token-to-CoNLL-U column mapping:**

| Column | Source | Rule |
|---|---|---|
| `ID` | position counter | 1-indexed per sentence |
| `FORM` | `tok.token` | exact input form |
| `LEMMA` | root morpheme form | `m.form` where `m.content_type == "verb_root"`; fall back to `tok.token` |
| `UPOS` | parse path | `"VERB"` if best hypothesis has a `verb_root` morpheme; `"NOUN"` if `nc_id` present and no verb root; `"X"` otherwise |
| `XPOS` | language + UPOS | `"{language}-{UPOS}"` (e.g. `"chitonga-VERB"`) |
| `FEATS` | `UD.to_conllu_feats_str(tok)` | already alphabetically sorted and CoNLL-U compliant |
| `HEAD` | `"_"` | syntax not available |
| `DEPREL` | `"_"` | syntax not available |
| `DEPS` | `"_"` | syntax not available |
| `MISC` | composite | `Gloss=<gloss_line>|Segment=<segmented>|Ambiguous=Yes` (or omit `Ambiguous` key if not ambiguous) |

**Ambiguity handling** — per the spec, ambiguous parses are flagged rather than silently resolved. When `tok.is_ambiguous is True`, the best hypothesis is used for the CoNLL-U output and `Ambiguous=Yes` is written into `MISC`. The `AnnotatedToken.is_ambiguous` field carries this flag into `AnnotationResult.ambiguous_tokens` for the summary.

**Failed token handling** — if `MorphAnalysisError` or `UDMappingError` is caught for a token, write a CoNLL-U row with `LEMMA=_`, `UPOS=X`, `FEATS=_`, and `MISC=AnnotationFailed=<error class name>`. Increment `failed_tokens`. Never abort the whole corpus.

**CoNLL-U sentence header format:**
```
# sent_id = sent_0001
# text = balya cilya
# language = chitonga
# ggt_annotated = 1.0.0
```

**Large file handling** — `annotate_file()` reads the file in full (not streaming) since `segment_text()` operates on strings. For production scale this is sufficient given the spec's `Medium` priority and research-corpus use case. A streaming mode can be added later.

---

## F-05 · Cross-Language Feature Comparator

### Purpose and scope
Given a dot-notation feature path (e.g. `noun_class.NC8.prefix`, `extension.PASS.zone`, `tam.TAM_PRES.form`), query that path across all 7 language loaders and produce a comparison table.

### New module: `apps/feature_comparator.py`

**Exported types** (all `frozen=True`):

| Type | Fields |
|---|---|
| `FeatureValue` | `language: str`, `value: Any`, `value_str: str`, `found: bool`, `error: Optional[str]` |
| `ComparisonTable` | `feature_path: str`, `languages: Tuple[str, ...]`, `values: Dict[str, FeatureValue]`, `unique_values: FrozenSet[str]`, `is_uniform: bool` (all languages agree), `divergent_languages: FrozenSet[str]` |
| `FeatureComparatorError(GGTError)` | — |

**Class: `FeatureComparator`**

Constructor: `__init__(self, loaders: Dict[str, GobeloGrammarLoader])` — accepts a pre-built dict keyed by language name. This is the critical difference from the other apps: it takes multiple loaders, not one. A convenience factory is provided:

```python
@classmethod
def for_all_languages(cls) -> "FeatureComparator":
    return cls({
        lang: GobeloGrammarLoader(GrammarConfig(language=lang))
        for lang in GobeloGrammarLoader(GrammarConfig(language="chitonga"))
                        .list_supported_languages()
    })
```

Public API:

```python
compare(feature_path: str) -> ComparisonTable
compare_many(feature_paths: List[str]) -> Dict[str, ComparisonTable]
to_markdown(table: ComparisonTable) -> str
to_csv(table: ComparisonTable) -> str
to_markdown_multi(tables: Dict[str, ComparisonTable]) -> str
```

**Dot-notation path router** — the bounded set of entity types maps exactly to loader API calls. The router is a `_resolve(path, loader)` function using a 3-segment parse: `entity_type.entity_id.field_name`. Supported schemas:

| Path pattern | Resolution |
|---|---|
| `noun_class.<NC_ID>.<field>` | `loader.get_noun_class(NC_ID).<field>` |
| `tam.<TAM_ID>.<field>` | `{t for t in loader.get_tam_markers() if t.id == TAM_ID}[0].<field>` |
| `extension.<EXT_ID>.<field>` | `{e for e in loader.get_extensions() if e.id == EXT_ID}[0].<field>` |
| `concord.<concord_type>.<key>` | `loader.get_concords(concord_type).entries[key]` |
| `metadata.<field>` | `loader.get_metadata().<field>` (2-segment only) |
| `verb_slot.<SLOT_ID>.<field>` | `{s for s in loader.get_verb_slots() if s.id == SLOT_ID}[0].<field>` |

Each segment is validated against a hard-coded set of known `entity_type` prefixes. Any unknown prefix raises `FeatureComparatorError` with a clear message listing valid prefixes, rather than attempting open-ended YAML path resolution (which would violate the contract of no raw YAML access).

**`FeatureValue.found = False`** — returned when the entity id does not exist in a language (e.g. `extension.PASS` for stub languages). The comparison table still includes the language in `divergent_languages` so the caller can see the gap, without raising an exception.

**`is_uniform` computation** — `True` iff all `FeatureValue.value_str` strings are identical across all languages where `found=True`. Languages where `found=False` are excluded from the uniformity check but listed separately in the Markdown output as `— (not present)`.

**Markdown output format** — one row per language, one column per path, plus a `DIVERGES` column:

```markdown
| Language   | noun_class.NC1.prefix | tam.TAM_PRES.form | DIVERGES |
|------------|-----------------------|-------------------|----------|
| chitonga   | mu-                   | a                 |          |
| chibemba   | mu-                   | a                 |          |
| kaonde     | mu-                   | a                 |          |
| lunda      | mu-                   | a                 |          |
| luvale     | mu-                   | a                 |          |
| silozi     | mu-                   | a                 |          |
| chinyanja  | mu-                   | a                 |          |

> ✓ Feature is uniform across all 7 languages.
```

**`compare_many()`** — takes a list of paths, calls `compare()` for each, returns a dict. This is the primary entry point for the CLI `ggt compare --all-languages` command since a user will typically want to compare several features at once.

---

### Dependency graph and recommended build order

```
F-04 ParadigmGenerator
  └── MorphologicalAnalyzer (already built)
  └── GobeloGrammarLoader   (already built)

F-09 CorpusAnnotator
  └── MorphologicalAnalyzer (already built)
  └── UDFeatureMapper       (already built)
  └── GobeloGrammarLoader   (already built)

F-05 FeatureComparator
  └── GobeloGrammarLoader × N (already built)
  └── No other apps needed
```

**Build order**: F-04 → F-05 → F-09. F-04 is the most self-contained and validates that `generate()` is robust enough for batch use (200 cells/language). F-05 is the simplest structurally (pure data routing). F-09 is last because it composes two apps and introduces file I/O, which should be tested after the two apps it depends on are confirmed stable in batch mode.