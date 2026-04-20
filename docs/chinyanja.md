# GOBELO GRAMMAR YAML GENERATION PROMPT
## Version 2.0 — Aligned to chitonga.yaml v1.0 (RC) Reference Schema
### For use with: Claude Sonnet / Opus | Gobelo Grammar Toolkit (GGT)

---

## HOW TO USE THIS TEMPLATE
##
## 1. Fill in every <ANGLE_BRACKET> value in Section 3 (Target Language Spec).
## 2. Complete Section 4 fill-in tables BEFORE generating — treat as a pre-flight
##    checklist. Incomplete tables produce incorrect output.
## 3. Attach the `chitonga.yaml` file to your prompt as the structural reference.
## 4. Send the completed prompt to Claude as a single message.
## 5. Run the Post-Generation Verification Checklist (Section 9) on receipt.
##
## Target languages for this project:
##   [ ] Chibemba        (Zambia — Guthrie M.42 — ~4.1M speakers)
##   [ ] Chichewa/Nyanja  (Zambia/Malawi — Guthrie N.31 — ~12M speakers)
##   [ ] Lunda (ciLunda)  (Zambia/DRC/Angola — Guthrie L.52 — ~1.5M speakers)
##   [ ] Luvale (ciLuvale)(Zambia/Angola — Guthrie K.14 — ~700K speakers)
##   [ ] Kaonde (ciKaonde)(Zambia/DRC — Guthrie L.41 — ~400K speakers)
##   [ ] SiLozi           (Zambia — Guthrie K.21 — ~700K speakers)
##   [ ] Mambwe-Namwanga  (Zambia/Tanzania — Guthrie M.15 — ~400K speakers)

---

# SECTION 1 — SYSTEM ROLE

You are an expert computational linguist and NLP systems architect specialising
in Bantu language morphology. You are building a production-grade, multi-language
grammar infrastructure library called the Gobelo Grammar Toolkit (GGT). Your
task is to generate a linguistically accurate grammar YAML file for **<LANGUAGE_NAME>**,
following the exact schema structure of the attached `chitonga.yaml` reference file.

---

# SECTION 2 — PRIMARY OBJECTIVE

Generate a complete grammar YAML file for **<LANGUAGE_NAME>** that:

1. Preserves every structural key from `chitonga.yaml` exactly — all nested
   sections, section IDs, field names, ordering constraints, processing stages,
   slot architecture, and concord types.
2. Replaces only the language-specific values — phoneme inventories,
   prefix/suffix forms, allomorphs, concord paradigms, TAM markers, examples,
   and metalinguistic notes.
3. Maintains schema compatibility so the output loads with the same Python
   parser that processes `chitonga.yaml`.
4. Is linguistically accurate — all morphological forms, allomorphs, and
   examples must reflect attested grammar of <LANGUAGE_NAME>.

---

# SECTION 3 — TARGET LANGUAGE SPECIFICATION

```
Language Name:          ChiNyanja
ISO 639-3 Code:         nya     # e.g., bem, nya, loz, lun, lue, kqn, mgr
Guthrie Classification: N.31     # e.g., M.42, N.31, K.21, L.52, K.14, L.41, M.15
Primary Region:         Eastern Province
Approximate Speakers:   1.2m
Major Dialects:         Chichewa 
Reference Grammar:      Mchombo (2004) The Syntax of Chichewa; Mtenje (1986) | Watkins (1937); CBOLD 
Reference Dictionary:   <AUTHOR_YEAR_TITLE>
```

---

# SECTION 4 — EXACT SCHEMA STRUCTURE (from chitonga.yaml)

## CRITICAL: The actual chitonga.yaml structure differs significantly from
## older prompt versions. Study this section before generating.

### 4.1 TOP-LEVEL STRUCTURE

The `chitonga.yaml` file has 6 flat top-level keys with no language-name wrapper.
Generated files use the **same flat structure** — no language-name root wrapper.
Language identity is carried entirely by the `metadata.language` block.

```yaml
# Generated file convention — flat top-level keys, NO wrapper:
metadata:
phonology:
noun_class_system:
concord_system:
verb_system:
tokenization:
```

### 4.2 COMPLETE SCHEMA MAP

```
metadata:
|
+-- language: {name, iso_code, guthrie, primary_region,
+--     approximate_speakers, family, description, dialects}
|     orthography: {base, standard, alternative}
|     tone_marking, date_created, last_updated, version
|     schema_compatibility: {min_parser_version, max_parser_version}
|     maintainer: {name, email}
|     framework: {name, version, template_for, Yaml_version, license}
|     documentation, Target_audience, reference_grammar, editing_instructions
|
+-- phonology:                    <-- "phonology" NOT "phonology_rules"
|     phonology_metadata: {language, framework, module, version,
|                          last_updated, status, design_goals,
|                          sources, integration_notes, schema_compatibility}
|     vowels: {segments, short, long, features: {height, backness, round}}
|     consonants: {segments, features: {place, manner, voicing}}
|     syllable_structure: {pattern, variants}
|     tones: {levels, notation}
|     boundaries: {morpheme, zone, word, phrase}
|     engine_features: {extended_H_spread, reduced_H_spread, initial_H_lowering}
|     processing_stages: [4 items: morphophonology, sandhi, prosody, tone]
|     morphophonology: [VH.1, CA.1, CA.2]
|     sandhi_rules: [SND.1, SND.2, SND.3, SND.4]
|     prosody: [MP.1, VL.2]
|     tone: [TBU.1, TS.1, TS.2, OCP.1, TL.1, TL.2]
|     rule_interactions: {feeding, bleeding, counterfeeding, opacity}
|     global_ordering: [{morphophonology:[1-9]},{sandhi:[10-19]},
|                        {prosody:[20-29]},{tone:[30-39]}]
|     notes, constraints: [R.1, R.2, R.3, R.4, R.5]
|
+-- noun_class_system:            <-- top-level, NOT inside morphology:
|     noun_class_metadata: {language, framework, module, version, last_updated,
|                           status, default_pos_tag, augment_system,
|                           loanword_assignment, sources, integration_notes,
|                           schema_compatibility}
|     noun_classes:
|       NC1: {class_number, class_type, grammatical_number, paired_class,
|             frequency, active, prefix, augment, triggers_rules, semantics}
|       NC1a, NC2, NC2a, NC2b, NC3-NC18  (same field structure)
|     noun_class_features:
|       cross_class_patterns:
|         high_vowel_classes, low_vowel_classes, nasal_classes
|         human_classes, locative_classes, homophonous_prefixes
|         derivational_patterns:      <-- NESTED inside cross_class_patterns
|           diminutive_formation, augmentative_formation, language_names,
|           abstract_nouns, infinitives, manner_nouns, locative_derivation
|         semantic_notes:             <-- NESTED inside cross_class_patterns
|           class_pairing_semantics, loanword_assignment, homonymy_disambiguation
|         dialectal_variation:        <-- NESTED inside cross_class_patterns
|           description, major_dialects, phonological_variation, lexical_variation
|         usage_notes:                <-- NESTED inside cross_class_patterns
|           register_variation, contemporary_changes, cultural_notes, special_rules
|
+-- concord_system:               <-- top-level, NOT inside morphology:
|     concords_metadata: {description}
|     concords:              (18 types — see Section 4.3)
|       subject_concords, object_concords, relative_concords,
|       possessive_concords, demonstrative_concords,
|       adjectival_concords, adverbial_concords,
|       relative_subject_concords, relative_object_concords,
|       enumerative_concords, independent_pronouns,
|       quantifier_concords, interrogative_concords,
|       connective_concords, reflexive_concords,
|       copula_concords, comitative_concords, emphatic_concords
|
+-- verb_system:
|     verb_system_metadata: {name, version, date, description, changelog,
|                            schema_compatibility}
|     constants: {subject_number, agreement_features,
|                 zones: {Z1, Z2, Z3, Z4}}
|     verbal_system_components:   <-- WRAPPER KEY (required)
|       negation_pre: {present, past, subjunctive}
|       pre_initial: {COND, TEMP1, TEMP2}
|       negation_infix: {negative}
|       tam: {PRES, PST, REC_PST, REM_PST, FUT_NEAR, FUT_REM, HAB, PERF}
|       modal: {COND, POT, PROG}
|       derivational_extensions:  <-- key is "derivational_extensions" NOT "extensions"
|         APPL, CAUS, TRANS, CONT       (Z1)
|         RECIP, STAT                   (Z2)
|         PASS                          (Z3)
|         INTENS, REDUP, PERF, REV, REPET, FREQ, POS  (Z4)
|         extension_ordering:    <-- NESTED inside derivational_extensions
|         semantic_composition:  <-- NESTED inside derivational_extensions
|       final_vowels: {indicative, subjunctive, negative,
|                      imperative_singular, imperative_plural,
|                      perfective, infinitive}
|       post_final: {relativizer, question, emphasis, negation, locative}
|     constraints:
|       {description, negation, mood_tam, agreement}
|       -- SCHEMA QUIRK: the keys below appear BOTH nested inside
|          constraints AND duplicated at verb_system top level.
|          Both copies must be present for parser compatibility.
|       tam_fv_interactions  (copy 1, inside constraints)
|       morphophonology      (copy 1, inside constraints)
|       slot_order           (copy 1, inside constraints)
|       verb_slots           (copy 1, inside constraints)
|       validation           (copy 1, inside constraints)
|     tam_fv_interactions    (copy 2, verb_system top level)
|     morphophonology        (copy 2, verb_system top level)
|     prosody                (verb_system top level only -- not in constraints)
|     slot_order             (copy 2, verb_system top level)
|     verb_slots             (copy 2, verb_system top level)
|     validation             (copy 2, verb_system top level)
|
+-- tokenization:
      tokenization_metadata: {schema_compatibility, external_file, description}
      syllable: {pattern, description}
      word_boundary, morpheme_separators
      special_tokens: {punctuation, discourse_markers}
      preserve_case: boolean
```

### 4.3 THE 18 CONCORD TYPES

All 18 must be present under `concord_system.concords` in this order:

```
 1. subject_concords          Personal (NEG.SG, 1SG-3PL_HUMAN) + NC3-NC18
 2. object_concords           Personal (1SG-3PL) + NC3-NC18
 3. relative_concords         NC1-NC18 (high tone)
 4. possessive_concords       NC1-NC18 + NC1a/NC2a/NC2b
 5. demonstrative_concords    proximal / medial / distal x NC1-NC18
 6. adjectival_concords       3SG/3PL (human) + NC3-NC18
 7. adverbial_concords        NC1-NC18
 8. relative_subject_concords Personal + NC3-NC18
 9. relative_object_concords  3SG/3PL + NC3-NC18
10. enumerative_concords      NC1-NC18
11. independent_pronouns      Personal + NC1-NC18
12. quantifier_concords       {all: NC1-NC15, many: NC1-NC10}
13. interrogative_concords    {which: NC1-NC10, what_kind: NC1-NC2}
14. connective_concords       NC1-NC18
15. reflexive_concords        NC1-NC10
16. copula_concords           NC1, NC2, NC5, NC7 (select forms)
17. comitative_concords       Personal + NC5/6/7/9
18. emphatic_concords         NC1, NC2, NC3, NC7 (select)
```

### 4.4 VERB SLOT ARCHITECTURE (SLOT1-SLOT11)

Defined inside `verbal_system_components` AND duplicated at `verb_system.verb_slots`:

```
SLOT1  negation_pre         false   Pre-verbal negation
SLOT2  pre_initial          false   Conditional/temporal pre-initial
SLOT3  subject_concords     TRUE    SM; ref: concord_system
SLOT4  negation_infix       false   Post-SM negation infix
SLOT5  tense_aspect_mood    false   TAM marker
SLOT6  modal_aux            false   Modal/progressive
SLOT7  object_concord       false   OM
SLOT8  root                 TRUE    Verb root (REQUIRED)
SLOT9  verb_ext             false   Extensions (repeatable=true)
SLOT10 final_vowel          TRUE    Final vowel (REQUIRED)
SLOT11 post_final           false   Post-verbal clitics
```

### 4.5 EXTENSION ZONES (inside `derivational_extensions`)

```
Z1 VALENCY_INCREASING   APPL, CAUS, TRANS, CONT    order: APPL < CAUS < TRANS < CONT
Z2 VALENCY_ADJUSTING    RECIP, STAT                 order: RECIP < STAT
Z3 VOICE                PASS                        always final extension
Z4 ASPECTUAL_LEXICAL    INTENS, REDUP, PERF, REV, REPET, FREQ, POS

extension_ordering and semantic_composition are nested AFTER POS inside
derivational_extensions (not at verb_system level).
```

### 4.6 PHONOLOGICAL RULE IDs (must be preserved exactly)

```
morphophonology rules: VH.1, CA.1, CA.2          (global order 1-9)
sandhi rules:          SND.1, SND.2, SND.3, SND.4 (global order 10-19)
prosody rules:         MP.1, VL.2                  (global order 20-29)
tone rules:            TBU.1, TS.1, TS.2, OCP.1, TL.1, TL.2  (30-39)
reversibility:         R.1, R.2, R.3, R.4, R.5
```

---

# SECTION 5 — WHAT MUST CHANGE (Language-specific Values)

## 5.1 METADATA

```yaml
metadata:
  language:
    name:                 "<LANGUAGE_NAME>"
    iso_code:             "<ISO_CODE>"
    guthrie:              "<GUTHRIE_CODE>"
    primary_region:       "<REGION>"
    approximate_speakers: "<NUMBER>"
    family:               "Niger-Congo, Bantu (<ZONE>)"
    dialects:             [<D1>, <D2>, <D3>]
  orthography:
    base:      "<BASE>"
    standard:  "<CURRENT_STANDARD>"
  reference_grammar: "<AUTHOR (YEAR) TITLE>"
  framework:
    Yaml_version: 1.0
```

## 5.2 PHONOLOGICAL INVENTORY

```
Vowels:       <LIST>
              Chitonga baseline: [i, e, a, o, u]
              Note if language has contrastive long vowels (ii, ee, aa, oo, uu)

Consonants:   <LIST>
              Include all prenasalised stops, affricates, labiodentals
              No clicks in any of the 7 target languages

Tones:        ALL 7 languages use 2-tone H/L system
              levels: ["high", "low", "falling", "rising"]

engine_features:
  extended_H_spread: <true ONLY for Chibemba; false for all others>
```

## 5.3 PHONOLOGICAL RULE ADAPTATIONS

```
VH.1  Vowel harmony:      Does the language condition extensions for vowel height?
      Chitonga: il/el     Nyanja: ir/er    All others: il/el
      Set: high_or_low: <il or ir>;  mid: <el or er>

CA.1  l/d alternation:    l -> d before high vowels? <YES/NO + environments>
CA.2  Palatalization:     k -> c/ch before front vowels? <YES/NO + reflex>
                          Chitonga: c-;  Nyanja: ch-;  Bemba: sh-

SND.1 Glide formation:    i->y, u->w at morpheme boundaries? <YES/NO>
SND.2 Vowel coalescence:  a+i->e, a+u->o? <YES/NO + language mappings>
SND.3 Nasal assimilation: NC9/10 N- prefix assimilation? <surface forms>
SND.4 Vowel elision:      Word-boundary deletion? <YES/NO + conditions>
```

## 5.4 NOUN CLASS PREFIXES — Fill in before generating

NC1a, NC2a, NC2b MUST be present even when prefix equals NC1/NC2.

| Class | Canonical Prefix | Allomorph | Condition | Augment | Domain |
|-------|-----------------|-----------|-----------|---------|--------|
| NC1 | <PREFIX> | <ALLO> | before_vowels | <i- or null> | human SG |
| NC1a | <PREFIX> | — | — | null | kinship/proper names SG |
| NC2 | <PREFIX> | <ALLO> | before_vowels | <i- or null> | human PL |
| NC2a | <PREFIX> | — | — | null | kinship PL |
| NC2b | <PREFIX> | — | — | null | honorific |
| NC3 | <PREFIX> | <ALLO> | before_vowels | <i- or null> | trees/plants SG |
| NC4 | <PREFIX> | <ALLO> | before_vowels | <i- or null> | trees/plants PL |
| NC5 | <PREFIX> | <ALLO> | <COND> | <i- or null> | body parts/augment SG |
| NC6 | <PREFIX> | <ALLO> | <COND> | <i- or null> | mass/liquids/PL |
| NC7 | <PREFIX> | <ALLO> | <COND> | <i- or null> | things SG |
| NC8 | <PREFIX> | <ALLO> | <COND> | <i- or null> | things PL |
| NC9 | N- | m/n/ng/Ø | place assimilation | <i- or null> | animals SG |
| NC10 | N- | m/n/ng/Ø | place assimilation | <i- or null> | animals PL |
| NC11 | <PREFIX> | <ALLO> | before_vowels | <i- or null> | long objects SG |
| NC12 | <PREFIX> | <ALLO> | before_vowels | <i- or null> | diminutive SG |
| NC13 | <PREFIX> | <ALLO> | before_vowels | <i- or null> | diminutive PL |
| NC14 | <PREFIX> | <ALLO> | before_vowels | <i- or null> | abstract/mass |
| NC15 | ku- | kw- | before_vowels | null | infinitives |
| NC16 | <PREFIX> | <ALLO> | <COND> | null | locative definite/surface |
| NC17 | ku- | kw- | before_vowels | null | locative directional |
| NC18 | mu- | mw- | before_vowels | null | locative interior |

## 5.5 SUBJECT CONCORDS

```
Personal:  NEG.SG: <F>   1SG: <F>   2SG: <F>   3SG: <F>
           NEG.1PL: <F>  1PL_EXCL: <F>  1PL_INCL: <F>
           2PL: <F>      3PL_HUMAN: <F>

NC classes (NC3-NC18):
NC3: <SC>  NC4: <SC>  NC5: <SC>  NC6: <SC>
NC7: <SC>  NC8: <SC>  NC9: <SC>  NC10: <SC>
NC11: <SC> NC12: <SC> NC13: <SC> NC14: <SC>
NC15: <SC> NC16: <SC> NC17: <SC> NC18: <SC>
```

## 5.6 OBJECT CONCORDS

```
1SG: <OC>  2SG: <OC>  3SG: <OC>  1PL: <OC>  2PL: <OC>  3PL: <OC>

NC3: <OC>  NC4: <OC>  NC5: <OC>  NC6: <OC>
NC7: <OC>  NC8: <OC>  NC9: <OC>  NC10: <OC>
NC11: <OC> NC12: <OC> NC13: <OC> NC14: <OC>
NC15: <OC> NC16: <OC> NC17: <OC> NC18: <OC>
```

## 5.7 POSSESSIVE CONCORDS

```
NC1: <PC>  NC1a: <PC>  NC2: <PC>  NC2a: <PC>  NC2b: <PC>
NC3: <PC>  NC4: <PC>   NC5: <PC>  NC6: <PC>
NC7: <PC>  NC8: <PC>   NC9: <PC>  NC10: <PC>
NC11: <PC> NC12: <PC>  NC13: <PC> NC14: <PC>
NC15: <PC> NC16: <PC>  NC17: <PC> NC18: <PC>
```

## 5.8 DEMONSTRATIVE CONCORDS (proximal / medial / distal)

```
Proximal (this):  NC1-NC18 forms
Medial (that):    NC1-NC18 forms  (also NC1a/NC2a/NC2b)
Distal (yonder):  NC1-NC18 forms  (also NC1a/NC2a/NC2b)
```

## 5.9 TAM MARKERS

```
Present habitual:    <FORM>    Chitonga: a      Bemba: -ma-     Nyanja: -ma-
General past:        <FORM>    Chitonga: aka    Bemba: -na-     Nyanja: -na-
Recent past:         <FORM>    Chitonga: ali    (verify per language)
Remote past:         <FORM>    Chitonga: aka H  (verify per language)
Near future:         <FORM>    Chitonga: yo     Bemba: -laa-    Nyanja: -dza-
Remote future:       <FORM>    Chitonga: za     (verify per language)
Habitual:            <FORM>    Chitonga: la
Perfect:             <FORM>    Chitonga: a+FV-ide  Bemba: a+FV-ile  Nyanja: a-H+FV-a
```

## 5.10 VERB EXTENSION FORMS

```
APPL (applicative):    <FORM>   Chitonga: -il-/-el-    Nyanja: -ir-/-er-
CAUS (causative):      <FORM>   Chitonga: -is-/-y-     Nyanja: -its-/-ets-
                                 Bemba: -ish-/-esh-
PASS (passive):        <FORM>   Chitonga: -w-/-iw-     Nyanja: -idw-/-edw-
                                 Luvale/SiLozi: -w-/-aw-
RECIP (reciprocal):    <FORM>   Chitonga: -an-         (consistent across most)
STAT (stative):        <FORM>   Chitonga: -ik-/-ek-
REV (reversive):       <FORM>   Chitonga: -ul-/-ol-/-uk-
INTENS (intensive):    <FORM>   Chitonga: -isy-/-esy-
PERF.EXT:              <FORM>   Chitonga: -ilil-/-elel-
```

## 5.11 FINAL VOWELS

```
Indicative:       <FV>   Chitonga: -a (consistent)
Subjunctive:      <FV>   Chitonga: -e (consistent)
Negative:         <FV>   Chitonga: -i;  Nyanja: -a (with -sa- infix)
Perfective:       <FV>   Chitonga: -ide;  Bemba: -ile;  Nyanja: tonal -a
Imperative SG:    <FV>   Chitonga: -a
Imperative PL:    <FV>   Chitonga: -eni;  Nyanja: -ani
```

## 5.12 NEGATION

```
Pre-initial negation (present): <FORM>   Chitonga: ta;  Nyanja: si;  Luvale: ka
Pre-initial negation (past):    <FORM>   Chitonga: tee/tii
Negation infix:                 <FORM>   Chitonga: -ta-;  Nyanja: -sa-;  Bemba: -ta-
```

## 5.13 CULTURALLY-SPECIFIC NOTES

```
Augment/definiteness system:  <DESCRIPTION or NOT_APPLICABLE>
Respect/honorific system:     <DESCRIPTION>
Kinship register variation:   <DESCRIPTION>
```

---

# SECTION 6 — KNOWN STRUCTURAL DIVERGENCES BY LANGUAGE

Study this table before generating. These affect large portions of the output.

## 6.1 AUGMENT SYSTEM

| Language | Has Augment | Form | Usage |
|----------|------------|------|-------|
| Chitonga | YES | i- | optional |
| Chibemba | YES | i-/a- | optional |
| Nyanja/Chichewa | NO | null | set all augment fields to null |
| Lunda | YES | a- | optional, definite contexts |
| Luvale | YES | a-/i- | optional |
| Kaonde | NO | null | set all augment fields to null |
| SiLozi | NO | null | set all augment fields to null |
| Namwanga | YES | i- | optional (like Bemba) |

## 6.2 NC2 HUMAN PLURAL PREFIX (cascades to ALL NC2 concords in concord_system)

| Language | NC2 prefix |
|----------|-----------|
| Chitonga, Chibemba, Namwanga | ba- |
| Nyanja/Chichewa | a- (CRITICAL — all NC2 concords change) |
| Lunda, Luvale | a- (VERIFY) |
| Kaonde, SiLozi | ba- (VERIFY) |

## 6.3 NC7/NC8 PREFIXES (things / instruments)

| Language | NC7 | NC8 | Zone |
|----------|-----|-----|------|
| Chitonga | ci- | zi- | M |
| Chibemba | fi- | bi- | M.42 — DIFFERENT |
| Nyanja/Chichewa | chi- | zi- | N — same as Chitonga |
| Luvale | chi-/tʃi- | vi- | K — NC8 is vi- |
| Kaonde | ci- | bi-/fi- | L — VERIFY |
| SiLozi | si- | li- | K — both different |
| Namwanga | ci-/ki- | fi- | M.15 — NC8 is fi- |

## 6.4 NC14 ABSTRACT PREFIX

| Language | NC14 prefix | Allomorph |
|----------|------------|-----------|
| Chitonga, Chibemba, Luvale, SiLozi, Namwanga | bu- | bw- before V |
| Nyanja/Chichewa | u- | w- before V |

## 6.5 NC16 LOCATIVE PREFIX

| Language | NC16 | Note |
|----------|------|------|
| All except SiLozi | pa- | standard Bantu |
| SiLozi | fa- | Sotho influence — VERIFY Givón (1970) |

NC17 = ku- and NC18 = mu- are consistent across all 7 languages.

## 6.6 TONE ENGINE

| Language | extended_H_spread | Note |
|----------|------------------|------|
| Chibemba | TRUE | Unbounded H spreading; activates TS.2 |
| All others | FALSE | |

## 6.7 VERB EXTENSIONS — KEY DIVERGENCES

| Ext | Chitonga | Chibemba | Nyanja | SiLozi | Luvale | Namwanga |
|-----|----------|----------|--------|--------|--------|---------|
| APPL | -il-/-el- | -il-/-el- | -ir-/-er- | -el-/-al- | -il-/-el- | -il-/-el- |
| CAUS | -is-/-y- | -ish-/-esh- | -its-/-ets- | -is- | -is-/-ish- | -ish-/-y- |
| PASS | -w-/-iw- | -w-/-iiw- | -idw-/-edw- | -w-/-aw- | -w-/-aw- | -w-/-iw- |

## 6.8 NEGATION STRATEGY

| Language | Main clause negation | Slot |
|----------|---------------------|------|
| Chitonga | ta- pre-initial | SLOT1 |
| Chibemba | ta-/si- | SLOT1 |
| Nyanja | -sa- infix (replaces TAM) | SLOT4 |
| SiLozi | si- | SLOT1 (VERIFY) |
| Luvale | ka- pre-initial | SLOT1 (VERIFY) |

## 6.9 PERFECT ASPECT / PERFECTIVE FV

| Language | Perfective FV |
|----------|--------------|
| Chitonga | -ide |
| Chibemba, Namwanga | -ile |
| Nyanja | tonal -a (H on TAM marker; FV stays -a) |

## 6.10 TAM SYSTEM

| Language | Special features |
|----------|-----------------|
| Chibemba | Multiple remote past degrees; add PST_HODIERNAL, PST_HESTERNAL |
| Nyanja | PRES=-ma-; PST=-na-; FUT=-dza- |
| SiLozi | More periphrastic constructions; auxiliary verbs prominent |
| Namwanga | Multiple past degrees; close to Bemba |

---

# SECTION 7 — GENERATION INSTRUCTIONS

Using the attached `chitonga.yaml` as the structural template:

## 7.1 OUTPUT FORMAT

```
- Pure YAML only — no markdown fences, no explanatory prose outside YAML comments
- First line: # <LANGUAGE_NAME_UPPERCASE> LANGUAGE - COMPREHENSIVE GRAMMAR
- NO language-name root wrapper — first YAML key is: metadata:
- File name:  <language_name>.yaml
```

## 7.2 GENERATION ORDER

Generate section by section in this exact sequence:

```
1.  metadata:
2.  phonology:
          phonology_metadata
          vowels > consonants > syllable_structure > tones
          boundaries > engine_features > processing_stages
          morphophonology [VH.1, CA.1, CA.2]
          sandhi_rules [SND.1-SND.4]
          prosody [MP.1, VL.2]
          tone [TBU.1-TL.2]
          rule_interactions > global_ordering > notes
          constraints [R.1-R.5]
4.  noun_class_system:
          noun_class_metadata
          noun_classes: NC1, NC1a, NC2, NC2a, NC2b, NC3-NC18
          noun_class_features:
            cross_class_patterns:
              [phonological patterns]
              derivational_patterns   <-- NESTED here, not at morphology level
              semantic_notes          <-- NESTED here
              dialectal_variation     <-- NESTED here
              usage_notes             <-- NESTED here
5.  concord_system:
          concords_metadata
          concords: [all 18 types in order from Section 4.3]
6.  verb_system:
          verb_system_metadata > constants
          verbal_system_components:       <-- WRAPPER key
            negation_pre > pre_initial > negation_infix > tam > modal
            derivational_extensions:      <-- key name (not "extensions")
              [APPL CAUS TRANS CONT RECIP STAT PASS INTENS REDUP PERF REV REPET FREQ POS]
              extension_ordering:         <-- nested inside derivational_extensions
              semantic_composition:       <-- nested inside derivational_extensions
            final_vowels > post_final
          constraints:
            [negation, mood_tam, agreement]
            tam_fv_interactions  <-- copy 1, inside constraints
            morphophonology      <-- copy 1
            slot_order           <-- copy 1
            verb_slots [SLOT1-SLOT11]  <-- copy 1
            validation           <-- copy 1
          tam_fv_interactions    <-- copy 2, verb_system top level
          morphophonology        <-- copy 2
          prosody                <-- only here (not in constraints)
          slot_order             <-- copy 2
          verb_slots [SLOT1-SLOT11]  <-- copy 2
          validation             <-- copy 2
7.  tokenization:
```

## 7.3 VERIFY FLAG PROTOCOL

When a form cannot be confirmed from available primary sources:

```yaml
canonical_form: Ø-   # VERIFY: some sources give a- prefix here
```

Rules:
- Use `# VERIFY: <short description>` as an inline YAML comment
- Never fabricate forms — use null or "UNKNOWN" with a verify comment
- Prioritise the reference grammar listed in Section 3
- If sources conflict, encode the conservative/default form and note the conflict

## 7.4 ABSOLUTE PROHIBITIONS

```
DO NOT use "phonology_rules:" — use "phonology:"
DO NOT use "extensions:" — use "derivational_extensions:"
DO NOT omit the "verbal_system_components:" wrapper key
DO NOT place derivational_patterns, semantic_notes, dialectal_variation,
    or usage_notes directly under noun_class_system — they belong nested
    inside noun_class_features.cross_class_patterns
DO NOT omit either copy of the duplicated sections
    (tam_fv_interactions, morphophonology, slot_order, verb_slots, validation)
DO NOT add new top-level sections not in chitonga.yaml
DO NOT remove required fields — mark them null if not applicable
DO NOT change slot numbering (SLOT1-SLOT11)
DO NOT change rule IDs (VH.1, SND.1-4, R.1-5, etc.)
DO NOT change extension zone assignments (Z1-Z4)
DO NOT set extended_H_spread: true unless the language is Chibemba
```

---

# SECTION 8 — SELF-VERIFICATION (run before submitting output)

```
STRUCTURAL CHECKS:
[ ] NO language-name root wrapper — first YAML key is: metadata:
[ ] 6 flat top-level keys present: metadata, phonology, noun_class_system,
    concord_system, verb_system, tokenization
[ ] phonology: present (not phonology_rules:)
[ ] noun_class_system: at top level (not inside morphology:)
[ ] concord_system: at top level
[ ] verbal_system_components: wrapper key present inside verb_system
[ ] derivational_extensions: (not extensions:) inside verbal_system_components
[ ] extension_ordering and semantic_composition nested inside derivational_extensions
[ ] derivational_patterns, semantic_notes, dialectal_variation, usage_notes all
    nested under noun_class_system.noun_class_features.cross_class_patterns
[ ] All 4 processing stages present
[ ] All 11 verb slots present (SLOT1-SLOT11)
[ ] All 4 extension zones (Z1-Z4) present with correct extensions
[ ] NC1-NC18 all present (active: false for unused classes if any)
[ ] NC1a, NC2a, NC2b all present
[ ] All 18 concord types present in concord_system.concords
[ ] TAM section: PRES, PST, REC_PST, REM_PST, FUT_NEAR, FUT_REM, HAB, PERF
[ ] Final vowels: indicative, subjunctive, negative, perfective, imperative_singular,
    imperative_plural, infinitive
[ ] Duplicate sections present BOTH inside constraints AND at verb_system top level:
    tam_fv_interactions, morphophonology, slot_order, verb_slots, validation
[ ] prosody: present at verb_system top level only
[ ] tokenization section present
[ ] Constraints R.1-R.5 all present in phonology
[ ] All rule IDs: VH.1, CA.1, CA.2, SND.1-4, MP.1, VL.2,
    TBU.1, TS.1, TS.2, OCP.1, TL.1, TL.2

LINGUISTIC ACCURACY CHECKS:
[ ] NC1/NC2 are human classes
[ ] NC9/10 carry nasal assimilation rules (SND.3)
[ ] NC15 is infinitive class (ku- prefix)
[ ] NC16/17/18 are locative classes
[ ] PASS extension assigned to Z3 (not Z1/Z4)
[ ] APPL/CAUS in Z1; RECIP/STAT in Z2
[ ] NC2 prefix correct for this language (ba- vs a-)
[ ] NC7 prefix correct for language zone (ci- / chi- / fi- / si-)
[ ] NC14 prefix correct (bu- vs u-)
[ ] NC16 locative prefix correct (pa- vs fa-)
[ ] Augment: all null fields if language has no augment system
[ ] extended_H_spread: true ONLY for Chibemba; false all others
[ ] Perfective FV matches language form (-ide / -ile / tonal)
[ ] Negation marker in correct slot (SLOT1 vs SLOT4)

YAML SYNTAX CHECKS:
[ ] No bare colons inside unquoted string values
[ ] Booleans are bare true/false (not "true"/"false")
[ ] Null fields are bare null (not "null")
[ ] All rule IDs referenced in triggers_rules exist in phonology
```

---

# SECTION 9 — POST-GENERATION VERIFICATION CHECKLIST

## Step 1 — Parse Test

```python
import yaml

with open('<language_name>.yaml', 'r', encoding='utf-8') as f:
    grammar = yaml.safe_load(f)

assert 'metadata' in grammar, "Top-level 'metadata' key missing — check for accidental root wrapper"
assert 'phonology' in grammar, "Top-level 'phonology' key missing"
assert 'noun_class_system' in grammar, "Top-level 'noun_class_system' key missing"
assert 'concord_system' in grammar, "Top-level 'concord_system' key missing"
assert 'verb_system' in grammar, "Top-level 'verb_system' key missing"
assert 'tokenization' in grammar, "Top-level 'tokenization' key missing"
print("✓ YAML parses successfully")
print(f"✓ 6 flat top-level keys confirmed — no root wrapper")
```

## Step 2 — Schema Completeness Test

```python
import yaml

with open('<language_name>.yaml', 'r', encoding='utf-8') as f:
    grammar = yaml.safe_load(f)

lang = grammar   # flat root — no wrapper to unwrap

def deep_get(d, path):
    for k in path.split('.'):
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return None
    return d

required_paths = [
    'metadata',
    'phonology.phonology_metadata',
    'phonology.sandhi_rules',
    'phonology.tone',
    'noun_class_system.noun_class_metadata',
    'noun_class_system.noun_classes.NC1',
    'noun_class_system.noun_classes.NC15',
    'noun_class_system.noun_class_features.cross_class_patterns.derivational_patterns',
    'noun_class_system.noun_class_features.cross_class_patterns.semantic_notes',
    'noun_class_system.noun_class_features.cross_class_patterns.dialectal_variation',
    'noun_class_system.noun_class_features.cross_class_patterns.usage_notes',
    'concord_system.concords.subject_concords',
    'concord_system.concords.possessive_concords',
    'concord_system.concords.demonstrative_concords',
    'concord_system.concords.emphatic_concords',
    'verb_system.verbal_system_components.derivational_extensions.APPL',
    'verb_system.verbal_system_components.derivational_extensions.PASS',
    'verb_system.verbal_system_components.derivational_extensions.extension_ordering',
    'verb_system.verbal_system_components.final_vowels',
    'verb_system.verbal_system_components.tam',
    'verb_system.tam_fv_interactions',
    'verb_system.morphophonology',
    'verb_system.slot_order',
    'verb_system.verb_slots',
    'verb_system.validation',
    'tokenization',
]

all_ok = True
for path in required_paths:
    val = deep_get(lang, path)
    status = 'OK' if val is not None else 'MISSING'
    if val is None:
        all_ok = False
    print(f'{status}: {path}')
print(f'\nAll OK: {all_ok}')
```

## Step 3 — Concord Count Check (18 required)

```python
concords = deep_get(lang, 'concord_system.concords')
if concords:
    expected = [
        'subject_concords', 'object_concords', 'relative_concords',
        'possessive_concords', 'demonstrative_concords', 'adjectival_concords',
        'adverbial_concords', 'relative_subject_concords', 'relative_object_concords',
        'enumerative_concords', 'independent_pronouns', 'quantifier_concords',
        'interrogative_concords', 'connective_concords', 'reflexive_concords',
        'copula_concords', 'comitative_concords', 'emphatic_concords'
    ]
    for c in expected:
        status = 'OK' if c in concords else 'MISSING'
        print(f'{status}: {c}')
```

## Step 4 — Extension Zone Check

```python
de = deep_get(lang, 'verb_system.verbal_system_components.derivational_extensions')
if de:
    z1 = [k for k, v in de.items() if isinstance(v, dict) and v.get('zone') == 'Z1']
    z2 = [k for k, v in de.items() if isinstance(v, dict) and v.get('zone') == 'Z2']
    z3 = [k for k, v in de.items() if isinstance(v, dict) and v.get('zone') == 'Z3']
    z4 = [k for k, v in de.items() if isinstance(v, dict) and v.get('zone') == 'Z4']
    print(f"Z1: {z1}")   # expect: APPL, CAUS, TRANS, CONT
    print(f"Z2: {z2}")   # expect: RECIP, STAT
    print(f"Z3: {z3}")   # expect: PASS
    print(f"Z4: {z4}")   # expect: INTENS, REDUP, PERF, REV, REPET, FREQ, POS
    assert 'extension_ordering' in de, "extension_ordering missing from derivational_extensions"
    assert 'semantic_composition' in de, "semantic_composition missing"
```

## Step 5 — Cross-Compatibility with chitonga.yaml

```python
with open('chitonga.yaml', 'r') as f:
    chitonga = yaml.safe_load(f)   # flat root — no language wrapper

def get_deep_keys(d, prefix='', depth=3):
    keys = set()
    if depth == 0 or not isinstance(d, dict):
        return keys
    for k, v in d.items():
        full_key = f'{prefix}.{k}' if prefix else k
        keys.add(full_key)
        keys |= get_deep_keys(v, full_key, depth - 1)
    return keys

ck = get_deep_keys(chitonga)        # chitonga keys (flat root)
nk = get_deep_keys(lang)            # generated file (also flat root)

missing = ck - nk
print(f"Keys in chitonga.yaml MISSING in generated file: {len(missing)}")
for k in sorted(missing)[:20]:
    print(f"  MISSING: {k}")

# Target: 0 missing keys
```

## Step 6 — Linguistic Spot Check (manual, against reference grammar)

```
 1. NC1 subject concord on verb:   _______________
 2. NC2 subject concord on verb:   _______________
 3. NC7 prefix and SC form:        _______________
 4. NC9 noun surface form:         _______________ (nasal prefix)
 5. NC14 abstract noun example:    _______________
 6. Applicative suffix form:       _______________
 7. Causative suffix form:         _______________
 8. Passive suffix form:           _______________
 9. NC2 demonstrative proximal:    _______________
10. NC16 locative prefix:          _______________
11. Perfective final vowel:        _______________
12. Negation marker + slot:        _______________
```

---

# SECTION 10 — REFERENCE GRAMMAR SOURCES

| Language | Primary Reference | Secondary Sources |
|----------|-------------------|-------------------|
| Chitonga | Carter (1982) An Outline of Chitonga | Collins (1962); Goldsmith (1984) |
| Chibemba | Spitulnik & Kashoki (1992); Hoch (1960) | CBOLD; Jones (1943) |
| Nyanja/Chichewa | Mchombo (2004) The Syntax of Chichewa; Mtenje (1986) | Watkins (1937); CBOLD |
| Lunda (ciLunda) | Kawasha (2003) Lunda Grammar (PhD UO) | Doke (1945); White Fathers dict. |
| Luvale (ciLuvale) | Horton (1949) A Grammar of Luvale | Pearson (1908); SIL Luvale |
| Kaonde (ciKaonde) | Stevick (1965) Kaonde Language Course | Doke (1945); SIL Kaonde |
| SiLozi | Givón (1970) The Si-Luyana Language; Jacottet (1896) | Mulenga (2000); Fortune (1971) |
| Namwanga | Stirnimann (1983) Praktische Grammatik der Mambwe-Sprache | Doke (1945); SIL Tanzania |

---
# END OF PROMPT TEMPLATE
