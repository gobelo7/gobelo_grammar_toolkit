Now I have a thorough picture of the entire codebase. Let me build the architectural overhaul.Now I have everything I need. This is a substantial architectural rewrite. Let me build it.Now I have enough. Let me write the full architectural rewrite.Now let's build the updated `concord_generator.py` and `paradigm_generator.py` — these need lighter changes (they delegate to `MorphologicalAnalyzer`), but `paradigm_generator.py` must pass phonology warnings through and include the `underlying` / `rule_trace` in `ParadigmCell`.Here's a full account of everything that changed and why.

---

## What was rebuilt and why

### The core shift: from string-based to structured + slot-aware

The v1 analyzer was essentially a fancy string-scanner with three independently broken concerns: phonology was ignored, the slot system was partially hardwired, and scoring had no phonological component. The v2 rewrite introduces three dedicated subsystems that each own exactly one concern.

---

### `morphological_analyzer.py` — the full overhaul

**`StructuredMorph` (new internal representation)**
The `+`/`-` joined string is gone. The intermediate representation is now a `Dict[slot_id → MorphNode]` with an explicit ordered slot list. Surface and underlying strings are derived lazily from this structure. Nothing in the pipeline ever concatenates morphemes directly — they stay as structured nodes until the phonology layer produces the final surface form.

**`PhonologyEngine` (new Layer 1)**
Rules are now *compiled*, not just stored as string identifiers. The engine has three methods:
- `forward(nodes)` — inserts boundary markers (`|`) between morphemes and applies rules left-to-right at boundary positions. Returns `(surface_string, rule_trace)`.
- `reverse(surface)` — applies rules right-to-left to recover candidate underlying forms for analysis. Returns multiple candidates when rules are ambiguous (e.g. both vowel elision and glide formation could explain the same surface).
- `score(surface, underlying)` — phonological plausibility as a float for the scoring stage.

Rule compilation follows a three-tier fallback: grammar-supplied rule objects (if the YAML includes them) → heuristics derived from rule ID names (`*_vowel_coalescence`, `*_glide_formation`, etc.) → universal Bantu safety-net rules (prenasalisation, vowel hiatus, glide insertion, final-vowel elision). This means something useful always happens even for grammars that only declare rule names.

**`SlotParser` (new Layer 2 — replaces the hardcoded SC→TAM→OC chain)**
Builds a dispatch table keyed on slot ID at construction time, one matcher per slot. Every slot in SLOT1–SLOT11 gets a matcher: slots the grammar doesn't populate (SLOT6, SLOT7, etc.) get a zero-match that keeps the lattice moving rather than silently being skipped. The parse itself is a two-phase DFS: pre-root slots are matched left-to-right; post-root slots (extensions, final vowel) are matched right-to-left; the root is the residue. Every hypothesis is then validated by the `ConstraintEngine` before entering the lattice.

**`ConstraintEngine` (new)**
Enforces structural validity: at most one subject concord, one TAM, one OC, one final vowel; slot positions must be strictly increasing; verb root must be non-empty. Custom constraints can be registered at runtime (`add_constraint(name, fn)`).

**`SlotFiller` (new Layer 3 — replaces the generate() if/elif chain)**
Walks all slots in position order and fills from `MorphFeatureBundle`. Handles the `extra_slots` field for anything not in the standard bundle (SLOT1 negation, SLOT4 negative infix, SLOT6 relative tense, SLOT7 long-distance OC, SLOT11 post-final) — these no longer produce warnings and disappear: they are first-class citizens of the slot template with an override pathway.

**`_score()` — phonology now contributes**
The scoring function previously had four components (coverage, obligatory slots, root present, root length). It now has a fifth: `PhonologyEngine.score(surface, underlying) × 0.20`. Hypotheses where the phonological derivation is well-explained rank higher than those where the surface-to-underlying mapping is unexplained.

**`MorphologicalAnalyzer.analyze()` — the new pipeline**
The `analyze` method now runs: `reverse phonology → SlotParser.parse() → _score()` instead of the flat prefix-chain scan. All public types (`Morpheme`, `ParseHypothesis`, `SegmentedToken`, `MorphFeatureBundle`, `SurfaceForm`) are backward-compatible; v2 adds `rule_trace` and `underlying` with default values so existing call sites don't break.

---

### `paradigm_generator.py` — phonology propagated into cells

`ParadigmCell` gains two new fields: `underlying` (pre-phonology concatenation) and `rule_trace` (the ordered list of rules that fired). `_generate_cell()` now reads these from `SurfaceForm`. The export methods are updated: `to_html()` adds `data-underlying` and `data-rules` attributes; `to_csv()` can interleave an `_underlying` column for each TAM column; `to_markdown()` reports rules applied rather than "warnings suppressed".

---

### `concord_generator.py` — unchanged

Its architecture was already sound (it never touched phonology or verbal slots) so the original file is passed through unmodified.