"""
models.py — Gobelo Grammar Toolkit (GGT) core data models
==========================================================
Phase 1 data layer. All downstream phases (morphological parsing, PoS tagging,
dependency parsing) operate on these structures.

Design principles
-----------------
* UD-aligned at the sentence level (WordToken mirrors CoNLL-U columns).
* Language-agnostic: no ChiTonga-specific hard-coding anywhere.
* Immutable-by-convention: dataclasses with frozen=True where practical;
  mutable containers (dicts, lists) are intentional where mutability is needed
  during the annotation pipeline.
* Lexicon-ready: LexiconEntry carries enough info for Phase 2 disambiguation.
* Slot-aware: the eleven-slot Bantu verb template is a first-class concept.

Slot numbering follows the GGT YAML convention  (models.py / VerbSlot)
-----------------------------------------------------------------------
SLOT1  : Augment / initial vowel
SLOT2  : Negation prefix (pre-subject)
SLOT3  : Subject concord (SM)
SLOT4  : TAM marker (pre-root)
SLOT5  : Relative / subordinator marker
SLOT6  : Negation (post-subject)
SLOT7  : Object concord (OM)
SLOT8  : Verb root
SLOT9  : Extension field (Z1–Z4)
SLOT10 : TAM marker (post-root / aspect)
SLOT11 : Final vowel (FV)
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class POSTag(str, Enum):
    """Universal POS tags (UPOS), extended with Bantu-specific categories."""
    # UD core
    ADJ   = "ADJ"
    ADP   = "ADP"
    ADV   = "ADV"
    AUX   = "AUX"
    CCONJ = "CCONJ"
    DET   = "DET"
    INTJ  = "INTJ"
    NOUN  = "NOUN"
    NUM   = "NUM"
    PART  = "PART"
    PRON  = "PRON"
    PROPN = "PROPN"
    PUNCT = "PUNCT"
    SCONJ = "SCONJ"
    SYM   = "SYM"
    VERB  = "VERB"
    X     = "X"          # foreign / unknown
    # GGT extensions (stored as xpos; upos falls back to nearest UD)
    IDEOPH = "IDEOPH"    # ideophone
    COP    = "COP"       # copula (often AUX in UD but useful to distinguish)
    NEG    = "NEG"       # sentential negator particle


class TokenType(str, Enum):
    """Broad token classification, set during word tokenisation."""
    WORD        = "word"         # ordinary lexical word
    PUNCT       = "punct"        # standalone punctuation
    NUMBER      = "number"       # numeric token
    ABBREV      = "abbrev"       # abbreviation (e.g. "Mk" for Mark)
    SPECIAL     = "special"      # special token (verse markers, headings …)
    CLITIC      = "clitic"       # clitic split-off from host
    REDUPLICATE = "reduplicate"  # reduplicated form flagged for special handling
    CODE_SWITCH = "code_switch"  # detected code-switch token
    UNKNOWN     = "unknown"


class LexiconCategory(str, Enum):
    VERB  = "verb"
    NOUN  = "noun"
    ADJ   = "adj"
    ADV   = "adv"
    PRON  = "pron"
    PART  = "part"
    OTHER = "other"


class ConfidenceLevel(str, Enum):
    HIGH   = "high"    # rule- or lexicon-confirmed
    MEDIUM = "medium"  # pattern-matched, no lexicon hit
    LOW    = "low"     # heuristic / fallback
    NONE   = "none"    # slot not filled


# ---------------------------------------------------------------------------
# Slot-level models
# ---------------------------------------------------------------------------

VALID_SLOTS = {
    "SLOT1", "SLOT2", "SLOT3", "SLOT4", "SLOT5",
    "SLOT6", "SLOT7", "SLOT8", "SLOT9", "SLOT10", "SLOT11",
}

# Labels aligned with models.py VerbSlot table
SLOT_LABELS = {
    "SLOT1" : "Augment / initial vowel",
    "SLOT2" : "Negation prefix (pre-subject)",
    "SLOT3" : "Subject concord",
    "SLOT4" : "TAM marker (pre-root)",
    "SLOT5" : "Relative / subordinator",
    "SLOT6" : "Negation (post-subject)",
    "SLOT7" : "Object concord",
    "SLOT8" : "Verb root",
    "SLOT9" : "Extension field (Z1–Z4)",
    "SLOT10": "TAM marker (post-root)",
    "SLOT11": "Final vowel",
}


@dataclass
class SlotFill:
    """The content of a single verb-template slot.

    Attributes
    ----------
    form : str
        The surface substring occupying this slot (may be empty string "").
    gloss : str
        Short Leipzig-style gloss (e.g. "3SG.SM", "PERF", "APPL").
    source_rule : str
        The YAML rule id or lexicon key that produced this fill
        (e.g. "SM.NC3", "FV.PERF", "LEX:lim").
    confidence : ConfidenceLevel
        How confident the analyser is in this particular fill.
    start : int
        Byte/character offset within the *token* form (not the sentence).
    end : int
        Exclusive end offset within the token form.
    notes : str
        Free-text annotation (e.g. "VERIFY: form unconfirmed").
    """
    form       : str             = ""
    gloss      : str             = ""
    source_rule: str             = ""
    confidence : ConfidenceLevel = ConfidenceLevel.NONE
    start      : int             = -1
    end        : int             = -1
    notes      : str             = ""

    def is_empty(self) -> bool:
        return self.form == "" and self.confidence == ConfidenceLevel.NONE

    def __repr__(self) -> str:
        flag = "" if self.confidence != ConfidenceLevel.NONE else "∅"
        return f"SlotFill({flag}{self.form!r}={self.gloss!r} [{self.confidence.value}])"


@dataclass
class SlotParse:
    """A complete verb-slot analysis for one word form.

    This is one *hypothesis* — multiple SlotParses may exist per WordToken
    when the form is morphologically ambiguous.

    Slot numbering follows models.py VerbSlot (GGT canonical):

    +--------+----------------------------------+
    | SLOT   | Canonical content                |
    +========+==================================+
    | SLOT1  | Augment / initial vowel          |
    +--------+----------------------------------+
    | SLOT2  | Negation prefix (pre-subject)    |
    +--------+----------------------------------+
    | SLOT3  | Subject concord (SM)             |
    +--------+----------------------------------+
    | SLOT4  | TAM marker (pre-root)            |
    +--------+----------------------------------+
    | SLOT5  | Relative / subordinator          |
    +--------+----------------------------------+
    | SLOT6  | Negation (post-subject)          |
    +--------+----------------------------------+
    | SLOT7  | Object concord (OM)              |
    +--------+----------------------------------+
    | SLOT8  | Verb root                        |
    +--------+----------------------------------+
    | SLOT9  | Extension field (Z1–Z4)          |
    +--------+----------------------------------+
    | SLOT10 | TAM marker (post-root / aspect)  |
    +--------+----------------------------------+
    | SLOT11 | Final vowel (FV)                 |
    +--------+----------------------------------+

    Attributes
    ----------
    slots : Dict[str, SlotFill]
        Keys are "SLOT1"–"SLOT11".  Missing keys mean slot not applicable or
        not yet analysed.
    score : float
        Composite confidence score in [0.0, 1.0].  Higher is better.
    lang_iso : str
        ISO 639-3 code of the language this parse was produced for.
    analyser_version : str
        Version tag of the rule file / model that produced this parse.
    parse_flags : List[str]
        Diagnostic flags set during parsing (e.g. "REDUPLICATED",
        "LEXICON_HIT", "VERIFY_NEEDED").
    """
    slots           : Dict[str, SlotFill] = field(default_factory=dict)
    score           : float               = 0.0
    lang_iso        : str                 = ""
    analyser_version: str                 = ""
    parse_flags     : List[str]           = field(default_factory=list)

    def __post_init__(self) -> None:
        bad = set(self.slots) - VALID_SLOTS
        if bad:
            raise ValueError(f"Unknown slot key(s): {bad}")

    def get(self, slot: str) -> SlotFill:
        """Return SlotFill for a slot, or an empty one if absent."""
        return self.slots.get(slot, SlotFill())

    def set(self, slot: str, fill: SlotFill) -> None:
        if slot not in VALID_SLOTS:
            raise ValueError(f"Invalid slot: {slot!r}")
        self.slots[slot] = fill

    def root_form(self) -> str:
        """Convenience: return the verb root (SLOT8) form, or ''."""
        return self.get("SLOT8").form

    def surface(self) -> str:
        """Reconstruct surface form by concatenating filled slots in order."""
        def _slot_num(key: str) -> int:
            return int(key[4:])

        return "".join(
            self.slots[s].form
            for s in sorted(VALID_SLOTS, key=_slot_num)
            if s in self.slots and not self.slots[s].is_empty()
        )

    def gloss_string(self) -> str:
        """Leipzig-style gloss line, e.g. 'SM.NC2-PAST-lim-FV'."""
        parts = []
        for s in sorted(VALID_SLOTS, key=lambda k: int(k[4:])):
            if s in self.slots and not self.slots[s].is_empty():
                parts.append(self.slots[s].gloss)
        return "-".join(parts)

    def add_flag(self, flag: str) -> None:
        if flag not in self.parse_flags:
            self.parse_flags.append(flag)

    def filled_slots(self) -> List[str]:
        return [s for s in sorted(VALID_SLOTS, key=lambda k: int(k[4:]))
                if s in self.slots and not self.slots[s].is_empty()]

    def average_confidence(self) -> ConfidenceLevel:
        weights = {
            ConfidenceLevel.HIGH:   3,
            ConfidenceLevel.MEDIUM: 2,
            ConfidenceLevel.LOW:    1,
            ConfidenceLevel.NONE:   0,
        }
        fills = [f for f in self.slots.values() if not f.is_empty()]
        if not fills:
            return ConfidenceLevel.NONE
        avg = sum(weights[f.confidence] for f in fills) / len(fills)
        if avg >= 2.5:
            return ConfidenceLevel.HIGH
        if avg >= 1.5:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def __repr__(self) -> str:
        filled = len(self.filled_slots())
        return (
            f"SlotParse(score={self.score:.3f}, slots_filled={filled}, "
            f"root={self.root_form()!r})"
        )


# ---------------------------------------------------------------------------
# Character-span model
# ---------------------------------------------------------------------------

@dataclass
class MorphemeSpan:
    """A morpheme with its character offsets inside a token form.

    Used to populate the CoNLL-U ``misc`` field and for highlighting in UIs.

    Attributes
    ----------
    start : int
        Inclusive start character offset within the **token** form.
    end : int
        Exclusive end character offset within the token form.
    form : str
        The morpheme surface form (should equal token.form[start:end]).
    label : str
        Morpheme label, e.g. "SM", "TAM", "ROOT", "FV", "EXT".
    gloss : str
        Leipzig-style gloss for this morpheme.
    slot : Optional[str]
        If the morpheme maps to a verb template slot, the slot key
        (using the v1 numbering: SLOT3=SM, SLOT8=ROOT, SLOT11=FV, etc.).
    """
    start: int
    end  : int
    form : str
    label: str
    gloss: str          = ""
    slot : Optional[str] = None

    def __post_init__(self) -> None:
        if self.slot and self.slot not in VALID_SLOTS:
            raise ValueError(f"Invalid slot reference: {self.slot!r}")
        if self.start > self.end:
            raise ValueError(f"start ({self.start}) > end ({self.end})")

    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: "MorphemeSpan") -> bool:
        return self.start < other.end and other.start < self.end

    def __repr__(self) -> str:
        return f"MorphemeSpan({self.start}:{self.end} {self.form!r}={self.label})"


# ---------------------------------------------------------------------------
# Lexicon entry
# ---------------------------------------------------------------------------

@dataclass
class LexiconEntry:
    """A single entry in a GGT verb or noun lexicon.

    Noun entries
    ------------
    For nouns, ``root`` is the stem (without class prefix).
    ``noun_class`` is the singular NC (e.g. "NC3") and
    ``plural_class`` is the plural NC (e.g. "NC4").

    Verb entries
    ------------
    ``root`` is the bare verb root (no extensions, no FV).
    ``derivations`` lists confirmed derived forms (e.g. ["lim-il-a", "lim-an-a"]).

    Attributes
    ----------
    lang_iso      : ISO 639-3 code.
    category      : VERB | NOUN | ADJ | …
    root          : Canonical root/stem form (NFC-normalised).
    gloss         : English gloss.
    noun_class    : For nouns: singular NC (e.g. "NC3").
    plural_class  : For nouns: plural NC (e.g. "NC4").
    tone_pattern  : Lexical tone pattern string as used in the GGT YAML
                    (e.g. "H", "L", "HL", "LH", etc.)  Empty if unknown.
    derivations   : List of attested derived / inflected forms (strings).
    source        : Reference shorthand (e.g. "Hoch1960:42").
    verified      : True if form confirmed against a primary reference.
    notes         : Free-text.
    """
    lang_iso    : str
    category    : LexiconCategory
    root        : str
    gloss       : str       = ""
    noun_class  : str       = ""    # e.g. "NC1", "NC3" — nouns only
    plural_class: str       = ""    # e.g. "NC2", "NC4" — nouns only
    tone_pattern: str       = ""
    derivations : List[str] = field(default_factory=list)
    source      : str       = ""
    verified    : bool      = False
    notes       : str       = ""

    def __post_init__(self) -> None:
        self.root = unicodedata.normalize("NFC", self.root)

    def is_verb(self) -> bool:
        return self.category == LexiconCategory.VERB

    def is_noun(self) -> bool:
        return self.category == LexiconCategory.NOUN

    def has_derivation(self, form: str) -> bool:
        norm = unicodedata.normalize("NFC", form)
        return norm in [unicodedata.normalize("NFC", d) for d in self.derivations]

    def __repr__(self) -> str:
        return (
            f"LexiconEntry({self.lang_iso} {self.category.value} "
            f"{self.root!r}={self.gloss!r})"
        )


# ---------------------------------------------------------------------------
# WordToken — the central token object
# ---------------------------------------------------------------------------

@dataclass
class WordToken:
    """A single word token in an annotated sentence.

    Mirrors CoNLL-U column semantics where possible, with GGT extensions.

    CoNLL-U fields
    --------------
    token_id  : 1-based index within the sentence (int or "1-2" for MWTs).
    form      : Surface form (NFC-normalised).
    lemma     : Lemma / dictionary headword.
    upos      : Universal POS tag (POSTag enum or None if untagged).
    xpos      : Language-specific POS (free string, optional).
    feats     : Morphological features as ordered dict
                (e.g. {"Tense": "Past", "Number": "Sing"}).
    head      : Token id of dependency head (0 = root).
    deprel    : Dependency relation label (UD or GGT-extended).
    deps      : Enhanced dependencies list of (head_id, deprel) tuples.
    misc      : CoNLL-U MISC field encoded as key=value pairs dict.

    GGT extensions
    --------------
    lang_iso        : ISO 639-3 code for the token's language.
    token_type      : TokenType enum.
    char_start      : Character offset of token in the original sentence string.
    char_end        : Exclusive end offset.
    original_form   : Pre-normalisation form (preserved for audit trail).
    is_oov          : True if token not found in any loaded lexicon.
    lexicon_matches : LexiconEntry objects whose root matches this token.
    slot_parses     : List of SlotParse hypotheses (verb tokens only).
    best_parse      : Index into slot_parses for the top-scored hypothesis.
    morpheme_spans  : Character spans for morpheme segmentation.
    noun_class      : For noun tokens: the parsed noun class (e.g. "NC5").
    is_reduplicated : True if token was detected as a reduplicated form.
    clitic_of       : Token id this clitic is attached to (if TokenType.CLITIC).
    code_switch_lang: Detected language of a code-switched token.
    flags           : Miscellaneous flags set by any pipeline stage.
    """

    # ---------- CoNLL-U core ----------
    token_id  : str                   = "0"
    form      : str                   = ""
    lemma     : Optional[str]         = None
    upos      : Optional[POSTag]      = None
    xpos      : Optional[str]         = None
    feats     : Dict[str, str]        = field(default_factory=dict)
    head      : Optional[int]         = None
    deprel    : Optional[str]         = None
    deps      : List[Tuple[int, str]] = field(default_factory=list)
    misc      : Dict[str, str]        = field(default_factory=dict)

    # ---------- GGT core ----------
    lang_iso      : str  = ""
    token_type    : TokenType = TokenType.WORD
    char_start    : int  = -1
    char_end      : int  = -1
    original_form : str  = ""

    # ---------- Lexicon ----------
    is_oov          : bool               = True
    lexicon_matches : List[LexiconEntry] = field(default_factory=list)

    # ---------- Morphological analysis ----------
    slot_parses    : List[SlotParse]    = field(default_factory=list)
    best_parse     : int                = 0        # index into slot_parses
    morpheme_spans : List[MorphemeSpan] = field(default_factory=list)

    # ---------- Noun analysis ----------
    noun_class : Optional[str] = None   # e.g. "NC3"

    # ---------- Special flags ----------
    is_reduplicated  : bool          = False
    clitic_of        : Optional[str] = None   # token_id of host
    code_switch_lang : Optional[str] = None   # ISO code
    flags            : List[str]     = field(default_factory=list)

    # ------------------------------------------------------------------ #

    def __post_init__(self) -> None:
        self.form = unicodedata.normalize("NFC", self.form)
        if not self.original_form:
            self.original_form = self.form

    # -- Convenience properties ---------------------------------------- #

    @property
    def is_verb(self) -> bool:
        return self.upos == POSTag.VERB or self.upos == POSTag.AUX

    @property
    def is_noun(self) -> bool:
        return self.upos in (POSTag.NOUN, POSTag.PROPN)

    @property
    def is_punct(self) -> bool:
        return self.token_type == TokenType.PUNCT

    @property
    def is_special(self) -> bool:
        return self.token_type == TokenType.SPECIAL

    @property
    def has_slot_analysis(self) -> bool:
        return bool(self.slot_parses)

    @property
    def best_slot_parse(self) -> Optional[SlotParse]:
        if not self.slot_parses:
            return None
        return self.slot_parses[self.best_parse]

    @property
    def span(self) -> Tuple[int, int]:
        return (self.char_start, self.char_end)

    # -- Mutation helpers ---------------------------------------------- #

    def add_flag(self, flag: str) -> None:
        if flag not in self.flags:
            self.flags.append(flag)

    def set_misc(self, key: str, value: str) -> None:
        self.misc[key] = value

    def add_morpheme_span(self, span: MorphemeSpan) -> None:
        self.morpheme_spans.append(span)

    def add_slot_parse(self, parse: SlotParse) -> None:
        """Add a SlotParse hypothesis and update best_parse index."""
        self.slot_parses.append(parse)
        best_idx = max(
            range(len(self.slot_parses)),
            key=lambda i: self.slot_parses[i].score,
        )
        self.best_parse = best_idx

    def add_lexicon_match(self, entry: LexiconEntry) -> None:
        self.lexicon_matches.append(entry)
        self.is_oov = False

    # -- Serialisation helpers ----------------------------------------- #

    def to_conllu_line(self) -> str:
        """Render the token as a single CoNLL-U tab-separated line."""
        feats_str = (
            "|".join(f"{k}={v}" for k, v in sorted(self.feats.items()))
            or "_"
        )
        deps_str = (
            "|".join(f"{h}:{r}" for h, r in self.deps) or "_"
        )
        misc_str = (
            "|".join(f"{k}={v}" for k, v in sorted(self.misc.items()))
            or "_"
        )
        return "\t".join([
            str(self.token_id),
            self.form or "_",
            self.lemma or "_",
            self.upos.value if self.upos else "_",
            self.xpos or "_",
            feats_str,
            str(self.head) if self.head is not None else "_",
            self.deprel or "_",
            deps_str,
            misc_str,
        ])

    def to_dict(self) -> dict:
        """Serialise to a plain Python dict (JSON-safe subset)."""
        return {
            "token_id"        : self.token_id,
            "form"            : self.form,
            "original_form"   : self.original_form,
            "lemma"           : self.lemma,
            "upos"            : self.upos.value if self.upos else None,
            "xpos"            : self.xpos,
            "feats"           : dict(self.feats),
            "lang_iso"        : self.lang_iso,
            "token_type"      : self.token_type.value,
            "char_start"      : self.char_start,
            "char_end"        : self.char_end,
            "is_oov"          : self.is_oov,
            "noun_class"      : self.noun_class,
            "is_reduplicated" : self.is_reduplicated,
            "flags"           : list(self.flags),
            "slot_parses"     : [
                {
                    "score": sp.score,
                    "root" : sp.root_form(),
                    "gloss": sp.gloss_string(),
                    "flags": sp.parse_flags,
                }
                for sp in self.slot_parses
            ],
            "morpheme_spans"  : [
                {
                    "start": ms.start,
                    "end"  : ms.end,
                    "form" : ms.form,
                    "label": ms.label,
                    "gloss": ms.gloss,
                }
                for ms in self.morpheme_spans
            ],
            "lexicon_matches" : [
                {
                    "root" : le.root,
                    "gloss": le.gloss,
                    "cat"  : le.category.value,
                    "nc"   : le.noun_class,
                }
                for le in self.lexicon_matches
            ],
        }

    def __repr__(self) -> str:
        upos = self.upos.value if self.upos else "?"
        oov  = " OOV" if self.is_oov else ""
        return (
            f"WordToken(id={self.token_id} {self.form!r} "
            f"[{upos}]{oov} @{self.char_start}:{self.char_end})"
        )


# ---------------------------------------------------------------------------
# Sentence-level container
# ---------------------------------------------------------------------------

@dataclass
class AnnotatedSentence:
    """A sentence with its full annotation.

    Mirrors CoNLL-U sentence-level fields and adds GGT provenance.

    Attributes
    ----------
    sent_id  : Sentence identifier string (e.g. "bem-GEN-001-01").
    text     : Original sentence string (NFC-normalised).
    lang_iso : Primary language ISO code.
    tokens   : Ordered list of WordToken objects.
    comments : CoNLL-U-style comment lines (without leading "# ").
    source   : Provenance tag (e.g. "Bible:Mk.1.1", "corpus:bem_001").
    pipeline : List of pipeline-stage names applied (audit trail).
    has_cs   : True if code-switching detected in this sentence.
    """
    sent_id  : str             = ""
    text     : str             = ""
    lang_iso : str             = ""
    tokens   : List[WordToken] = field(default_factory=list)
    comments : List[str]       = field(default_factory=list)
    source   : str             = ""
    pipeline : List[str]       = field(default_factory=list)
    has_cs   : bool            = False

    def __post_init__(self) -> None:
        self.text = unicodedata.normalize("NFC", self.text)

    # -- Accessors ----------------------------------------------------- #

    def __len__(self) -> int:
        return len(self.tokens)

    def __iter__(self):
        return iter(self.tokens)

    def __getitem__(self, idx: int) -> WordToken:
        return self.tokens[idx]

    def word_tokens(self) -> List[WordToken]:
        """Return only non-special, non-punct tokens."""
        return [t for t in self.tokens
                if t.token_type not in (TokenType.PUNCT, TokenType.SPECIAL)]

    def oov_tokens(self) -> List[WordToken]:
        """Return word tokens not found in any lexicon (excludes punct/special)."""
        return [t for t in self.tokens
                if t.is_oov and not t.is_special and not t.is_punct]

    def verb_tokens(self) -> List[WordToken]:
        return [t for t in self.tokens if t.is_verb]

    def noun_tokens(self) -> List[WordToken]:
        return [t for t in self.tokens if t.is_noun]

    def code_switch_tokens(self) -> List[WordToken]:
        return [t for t in self.tokens
                if t.token_type == TokenType.CODE_SWITCH]

    # -- Mutation ------------------------------------------------------ #

    def add_token(self, token: WordToken) -> None:
        self.tokens.append(token)

    def add_comment(self, comment: str) -> None:
        self.comments.append(comment)

    def add_pipeline_stage(self, stage: str) -> None:
        if stage not in self.pipeline:
            self.pipeline.append(stage)

    # -- Statistics ---------------------------------------------------- #

    def token_count(self) -> int:
        return len(self.word_tokens())

    def oov_rate(self) -> float:
        wt = self.word_tokens()
        if not wt:
            return 0.0
        return sum(1 for t in wt if t.is_oov) / len(wt)

    def coverage_stats(self) -> Dict[str, int]:
        wt = self.word_tokens()
        return {
            "total"    : len(wt),
            "oov"      : sum(1 for t in wt if t.is_oov),
            "lexicon"  : sum(1 for t in wt if not t.is_oov),
            "analysed" : sum(1 for t in wt if t.has_slot_analysis),
            "punct"    : sum(1 for t in self.tokens if t.is_punct),
            "special"  : sum(1 for t in self.tokens if t.is_special),
        }

    # -- Serialisation ------------------------------------------------- #

    def to_conllu(self) -> str:
        """Render as a complete CoNLL-U sentence block."""
        lines = []
        if self.sent_id:
            lines.append(f"# sent_id = {self.sent_id}")
        if self.text:
            lines.append(f"# text = {self.text}")
        if self.source:
            lines.append(f"# source = {self.source}")
        if self.lang_iso:
            lines.append(f"# lang = {self.lang_iso}")
        for c in self.comments:
            lines.append(f"# {c}")
        for tok in self.tokens:
            lines.append(tok.to_conllu_line())
        lines.append("")   # blank line terminator
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "sent_id"  : self.sent_id,
            "text"     : self.text,
            "lang_iso" : self.lang_iso,
            "source"   : self.source,
            "pipeline" : list(self.pipeline),
            "has_cs"   : self.has_cs,
            "stats"    : self.coverage_stats(),
            "tokens"   : [t.to_dict() for t in self.tokens],
        }

    def __repr__(self) -> str:
        return (
            f"AnnotatedSentence(id={self.sent_id!r}, "
            f"lang={self.lang_iso!r}, tokens={len(self.tokens)})"
        )
