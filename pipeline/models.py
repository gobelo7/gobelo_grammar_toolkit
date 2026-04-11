"""
models.py — Gobelo Grammar Toolkit (GGT) pipeline data models (Phase 1)
========================================================================
Central data layer for the annotation pipeline.  All pipeline stages
(tokenizer, morph analyser, PoS tagger, dependency parser) operate on
these structures.

Design principles
-----------------
* UD-aligned at the sentence level (WordToken mirrors CoNLL-U columns).
* Language-agnostic: no language-specific hard-coding anywhere.
* Lexicon-ready: LexiconEntry carries enough info for Phase 2 disambiguation.
* Slot-aware: the eleven-slot Bantu verb template is a first-class concept.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class POSTag(str, Enum):
    ADJ    = "ADJ";  ADP   = "ADP";  ADV   = "ADV";  AUX   = "AUX"
    CCONJ  = "CCONJ";DET   = "DET";  INTJ  = "INTJ"; NOUN  = "NOUN"
    NUM    = "NUM";  PART  = "PART"; PRON  = "PRON"; PROPN = "PROPN"
    PUNCT  = "PUNCT";SCONJ = "SCONJ";SYM   = "SYM";  VERB  = "VERB"
    X      = "X";   IDEOPH = "IDEOPH"; COP = "COP";  NEG   = "NEG"


class TokenType(str, Enum):
    WORD        = "word"
    PUNCT       = "punct"
    NUMBER      = "number"
    ABBREV      = "abbrev"
    SPECIAL     = "special"
    CLITIC      = "clitic"
    REDUPLICATE = "reduplicate"
    CODE_SWITCH = "code_switch"
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
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"
    NONE   = "none"


# ---------------------------------------------------------------------------
# Slot constants
# ---------------------------------------------------------------------------

VALID_SLOTS = {
    "SLOT1","SLOT2","SLOT3","SLOT4","SLOT5",
    "SLOT6","SLOT7","SLOT8","SLOT9","SLOT10","SLOT11",
}

SLOT_LABELS = {
    "SLOT1" : "Pre-SM / Negation",      "SLOT2" : "Subject Marker",
    "SLOT3" : "TAM prefix / Relative",  "SLOT4" : "Object Marker",
    "SLOT5" : "Verb root",              "SLOT6" : "Extension A (appl/caus)",
    "SLOT7" : "Extension B (recip/pass)","SLOT8" : "Extension C (neuter)",
    "SLOT9" : "Extension D (revers)",   "SLOT10": "Final Vowel",
    "SLOT11": "Post-FV",
}


# ---------------------------------------------------------------------------
# SlotFill
# ---------------------------------------------------------------------------

@dataclass
class SlotFill:
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
        return f"SlotFill({self.form!r}={self.gloss!r} [{self.confidence.value}])"


# ---------------------------------------------------------------------------
# SlotParse
# ---------------------------------------------------------------------------

@dataclass
class SlotParse:
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
        return self.slots.get(slot, SlotFill())

    def set(self, slot: str, fill: SlotFill) -> None:
        if slot not in VALID_SLOTS:
            raise ValueError(f"Invalid slot: {slot!r}")
        self.slots[slot] = fill

    def root_form(self) -> str:
        return self.get("SLOT5").form

    def surface(self) -> str:
        def _n(k): return int(k[4:])
        return "".join(
            self.slots[s].form
            for s in sorted(VALID_SLOTS, key=_n)
            if s in self.slots and not self.slots[s].is_empty()
        )

    def gloss_string(self) -> str:
        def _n(k): return int(k[4:])
        parts = [
            self.slots[s].gloss
            for s in sorted(VALID_SLOTS, key=_n)
            if s in self.slots and not self.slots[s].is_empty()
        ]
        return "-".join(parts)

    def add_flag(self, flag: str) -> None:
        if flag not in self.parse_flags:
            self.parse_flags.append(flag)

    def filled_slots(self) -> List[str]:
        def _n(k): return int(k[4:])
        return [s for s in sorted(VALID_SLOTS, key=_n)
                if s in self.slots and not self.slots[s].is_empty()]

    def average_confidence(self) -> ConfidenceLevel:
        weights = {ConfidenceLevel.HIGH:3, ConfidenceLevel.MEDIUM:2,
                   ConfidenceLevel.LOW:1, ConfidenceLevel.NONE:0}
        fills = [f for f in self.slots.values() if not f.is_empty()]
        if not fills:
            return ConfidenceLevel.NONE
        avg = sum(weights[f.confidence] for f in fills) / len(fills)
        if avg >= 2.5: return ConfidenceLevel.HIGH
        if avg >= 1.5: return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def __repr__(self) -> str:
        return (f"SlotParse(score={self.score:.3f}, "
                f"slots_filled={len(self.filled_slots())}, "
                f"root={self.root_form()!r})")


# ---------------------------------------------------------------------------
# MorphemeSpan
# ---------------------------------------------------------------------------

@dataclass
class MorphemeSpan:
    start: int
    end  : int
    form : str
    label: str
    gloss: str           = ""
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
# LexiconEntry
# ---------------------------------------------------------------------------

@dataclass
class LexiconEntry:
    lang_iso    : str
    category    : LexiconCategory
    root        : str
    gloss       : str          = ""
    noun_class  : str          = ""
    plural_class: str          = ""
    tone_pattern: str          = ""
    derivations : List[str]    = field(default_factory=list)
    source      : str          = ""
    verified    : bool         = False
    notes       : str          = ""

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
        return (f"LexiconEntry({self.lang_iso} {self.category.value} "
                f"{self.root!r}={self.gloss!r})")


# ---------------------------------------------------------------------------
# WordToken
# ---------------------------------------------------------------------------

@dataclass
class WordToken:
    # CoNLL-U core
    token_id : str                   = "0"
    form     : str                   = ""
    lemma    : Optional[str]         = None
    upos     : Optional[POSTag]      = None
    xpos     : Optional[str]         = None
    feats    : Dict[str, str]        = field(default_factory=dict)
    head     : Optional[int]         = None
    deprel   : Optional[str]         = None
    deps     : List[Tuple[int, str]] = field(default_factory=list)
    misc     : Dict[str, str]        = field(default_factory=dict)

    # GGT core
    lang_iso        : str            = ""
    token_type      : TokenType      = TokenType.WORD
    char_start      : int            = -1
    char_end        : int            = -1
    original_form   : str            = ""

    # Lexicon
    is_oov          : bool           = True
    lexicon_matches : List[LexiconEntry]  = field(default_factory=list)

    # Morphological analysis
    slot_parses     : List[SlotParse]     = field(default_factory=list)
    best_parse      : int                 = 0
    morpheme_spans  : List[MorphemeSpan]  = field(default_factory=list)

    # Noun analysis
    noun_class      : Optional[str]  = None

    # Special flags
    is_reduplicated : bool           = False
    clitic_of       : Optional[str]  = None
    code_switch_lang: Optional[str]  = None
    flags           : List[str]      = field(default_factory=list)

    def __post_init__(self) -> None:
        self.form = unicodedata.normalize("NFC", self.form)
        if not self.original_form:
            self.original_form = self.form

    @property
    def is_verb(self) -> bool:
        return self.upos in (POSTag.VERB, POSTag.AUX)

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

    def add_flag(self, flag: str) -> None:
        if flag not in self.flags:
            self.flags.append(flag)

    def set_misc(self, key: str, value: str) -> None:
        self.misc[key] = value

    def add_morpheme_span(self, span: MorphemeSpan) -> None:
        self.morpheme_spans.append(span)

    def add_slot_parse(self, parse: SlotParse) -> None:
        self.slot_parses.append(parse)
        self.best_parse = max(
            range(len(self.slot_parses)),
            key=lambda i: self.slot_parses[i].score,
        )

    def add_lexicon_match(self, entry: LexiconEntry) -> None:
        self.lexicon_matches.append(entry)
        self.is_oov = False

    def to_conllu_line(self) -> str:
        feats_str = ("|".join(f"{k}={v}" for k,v in sorted(self.feats.items())) or "_")
        deps_str  = ("|".join(f"{h}:{r}" for h,r in self.deps) or "_")
        misc_str  = ("|".join(f"{k}={v}" for k,v in sorted(self.misc.items())) or "_")
        return "\t".join([
            str(self.token_id), self.form or "_",
            self.lemma or "_",
            self.upos.value if self.upos else "_",
            self.xpos or "_", feats_str,
            str(self.head) if self.head is not None else "_",
            self.deprel or "_", deps_str, misc_str,
        ])

    def to_dict(self) -> dict:
        return {
            "token_id": self.token_id, "form": self.form,
            "lemma": self.lemma,
            "upos": self.upos.value if self.upos else None,
            "lang_iso": self.lang_iso,
            "token_type": self.token_type.value,
            "char_start": self.char_start, "char_end": self.char_end,
            "is_oov": self.is_oov, "noun_class": self.noun_class,
            "flags": list(self.flags),
            "feats": dict(self.feats),
            "slot_parses": [
                {"score": sp.score, "root": sp.root_form(),
                 "gloss": sp.gloss_string(), "flags": sp.parse_flags}
                for sp in self.slot_parses
            ],
            "morpheme_spans": [
                {"start": ms.start, "end": ms.end,
                 "form": ms.form, "label": ms.label, "gloss": ms.gloss}
                for ms in self.morpheme_spans
            ],
        }

    def __repr__(self) -> str:
        upos = self.upos.value if self.upos else "?"
        oov  = " OOV" if self.is_oov else ""
        return (f"WordToken(id={self.token_id} {self.form!r} "
                f"[{upos}]{oov} @{self.char_start}:{self.char_end})")


# ---------------------------------------------------------------------------
# AnnotatedSentence
# ---------------------------------------------------------------------------

@dataclass
class AnnotatedSentence:
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

    def __len__(self)          -> int:       return len(self.tokens)
    def __iter__(self):                      return iter(self.tokens)
    def __getitem__(self, i)   -> WordToken: return self.tokens[i]

    def word_tokens(self) -> List[WordToken]:
        return [t for t in self.tokens
                if t.token_type not in (TokenType.PUNCT, TokenType.SPECIAL)]

    def oov_tokens(self) -> List[WordToken]:
        return [t for t in self.tokens
                if t.is_oov and not t.is_special and not t.is_punct]

    def verb_tokens(self) -> List[WordToken]:
        return [t for t in self.tokens if t.is_verb]

    def noun_tokens(self) -> List[WordToken]:
        return [t for t in self.tokens if t.is_noun]

    def code_switch_tokens(self) -> List[WordToken]:
        return [t for t in self.tokens if t.token_type == TokenType.CODE_SWITCH]

    def add_token(self, token: WordToken) -> None:
        self.tokens.append(token)

    def add_comment(self, comment: str) -> None:
        self.comments.append(comment)

    def add_pipeline_stage(self, stage: str) -> None:
        if stage not in self.pipeline:
            self.pipeline.append(stage)

    def token_count(self) -> int:
        return len(self.word_tokens())

    def oov_rate(self) -> float:
        wt = self.word_tokens()
        if not wt: return 0.0
        return sum(1 for t in wt if t.is_oov) / len(wt)

    def coverage_stats(self) -> Dict[str, int]:
        wt = self.word_tokens()
        return {
            "total"   : len(wt),
            "oov"     : sum(1 for t in wt if t.is_oov),
            "lexicon" : sum(1 for t in wt if not t.is_oov),
            "analysed": sum(1 for t in wt if t.has_slot_analysis),
            "punct"   : sum(1 for t in self.tokens if t.is_punct),
            "special" : sum(1 for t in self.tokens if t.is_special),
        }

    def to_conllu(self) -> str:
        lines = []
        if self.sent_id:  lines.append(f"# sent_id = {self.sent_id}")
        if self.text:     lines.append(f"# text = {self.text}")
        if self.source:   lines.append(f"# source = {self.source}")
        if self.lang_iso: lines.append(f"# lang = {self.lang_iso}")
        for c in self.comments:
            lines.append(f"# {c}")
        for tok in self.tokens:
            lines.append(tok.to_conllu_line())
        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "sent_id": self.sent_id, "text": self.text,
            "lang_iso": self.lang_iso, "source": self.source,
            "pipeline": list(self.pipeline), "has_cs": self.has_cs,
            "stats": self.coverage_stats(),
            "tokens": [t.to_dict() for t in self.tokens],
        }

    def __repr__(self) -> str:
        return (f"AnnotatedSentence(id={self.sent_id!r}, "
                f"lang={self.lang_iso!r}, tokens={len(self.tokens)})")
