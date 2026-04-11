"""
word_tokenizer.py — GobeloWordTokenizer
=======================================
Language-agnostic word tokeniser for the Gobelo Grammar Toolkit (GGT).

Replaces ChitongaTokenizer.  All language-specific behaviour is driven
exclusively by:
  1. The GGT YAML grammar file (loaded via GobeloGrammarLoader).
  2. The corpus_config.yaml (per-language overrides for clitic lists,
     special-token patterns, OCR corrections, etc.).

No language-specific logic lives in this file.  Adding a new language
requires zero Python changes.

Architecture
------------
The tokeniser is a six-stage pipeline:

  Stage 1 · Pre-normalisation
        NFC normalise; apply OCR correction map; strip configured noise
        characters.

  Stage 2 · Special-token detection
        Identify verse markers, chapter headings, abbreviations, numbers,
        and any regex patterns configured in corpus_config.yaml.

  Stage 3 · Whitespace splitting
        Split on Unicode whitespace, preserve original offsets.

  Stage 4 · Punctuation splitting
        Split punctuation away from word forms according to configured
        punctuation sets and protected patterns (URLs, abbreviations,
        decimal numbers).

  Stage 5 · Clitic splitting
        Detach clitics (proclitics and enclitics) defined in the YAML
        grammar under ``clitics:`` and corpus_config overrides.

  Stage 6 · Post-processing
        Reduplification detection; code-switch flagging; token-id
        assignment; lexicon stub lookup; return List[WordToken].

The tokeniser does NOT perform morphological analysis (that is Phase 2).
It does, however, flag tokens for downstream stages (e.g. REDUPLICATED,
LEXICON_CANDIDATE) and annotates each WordToken with its char offsets.

Usage
-----
    loader = GobeloGrammarLoader("toi")            # ChiTonga
    cfg    = CorpusConfig.load("corpus_config.yaml")
    tok    = GobeloWordTokenizer(loader, cfg, lang_iso="toi")

    sentence = tok.tokenize("Bakali bàlìzyà kùkàla kwàbo.")
    for token in sentence.tokens:
        print(token)

GobeloGrammarLoader interface assumed
--------------------------------------
The tokeniser calls the following attributes / methods on the loader object.
If you supply a mock, implement these:

    loader.lang_iso              : str
    loader.grammar               : dict          # raw YAML dict
    loader.get("clitics", {})    : dict          # {proclitic: …, enclitic: …}
    loader.get("phonology.vowels_nfc", []) : list[str]
    loader.get("phonology.tone_marks", []) : list[str]
    loader.get("engine_features", {}) : dict
    loader.lexicon_verb          : dict[str, LexiconEntry]   # root → entry
    loader.lexicon_noun          : dict[str, LexiconEntry]   # root → entry

CorpusConfig interface assumed
-------------------------------
    cfg.get(lang_iso, key, default)  # per-language config lookup
    cfg.global_get(key, default)     # global config lookup

Both return the value or default if missing.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from models import (
    AnnotatedSentence,
    ConfidenceLevel,
    LexiconEntry,
    MorphemeSpan,
    POSTag,
    SlotFill,
    SlotParse,
    TokenType,
    WordToken,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _is_all_punct(s: str) -> bool:
    return bool(s) and all(
        unicodedata.category(c).startswith("P") or
        unicodedata.category(c).startswith("S")
        for c in s
    )


def _is_numeric(s: str) -> bool:
    """True if token is a number (including Roman numerals up to XXXIX)."""
    if re.fullmatch(r"\d[\d,.\u2019]*", s):   # includes thousands/decimal
        return True
    # Simple Roman numerals (used in Bible chapter headings)
    if re.fullmatch(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})",
                    s, re.IGNORECASE) and len(s) > 0:
        return True
    return False


# ---------------------------------------------------------------------------
# Lightweight config façades  (used when real loaders aren't available)
# ---------------------------------------------------------------------------

class _NullGrammarLoader:
    """Stub loader — returns empty structures for every grammar key.
    Useful for unit-testing the tokeniser in isolation."""
    lang_iso     = "und"
    grammar      : Dict = {}
    lexicon_verb : Dict = {}
    lexicon_noun : Dict = {}

    def get(self, key: str, default: Any = None) -> Any:
        return default


class _NullCorpusConfig:
    """Stub corpus config."""
    def get(self, lang_iso: str, key: str, default: Any = None) -> Any:
        return default
    def global_get(self, key: str, default: Any = None) -> Any:
        return default


# ---------------------------------------------------------------------------
# TokeniserConfig  — built once from loader + corpus config
# ---------------------------------------------------------------------------

@dataclass
class _TokeniserConfig:
    """Pre-computed, language-specific tokeniser settings.

    All fields are plain Python types (str, set, list, dict, re.Pattern)
    so the inner loop never touches YAML objects.
    """
    lang_iso: str

    # Punctuation
    sentence_final_punct : Set[str]       = field(default_factory=set)
    inline_punct         : Set[str]       = field(default_factory=set)
    protect_patterns     : List[re.Pattern] = field(default_factory=list)

    # OCR corrections  {wrong: right}
    ocr_map             : Dict[str, str]  = field(default_factory=dict)

    # Noise characters to strip (Unicode category codes, e.g. "Cf")
    noise_categories    : Set[str]        = field(default_factory=set)
    noise_chars         : Set[str]        = field(default_factory=set)

    # Clitics
    proclitics          : List[str]       = field(default_factory=list)
    enclitics           : List[str]       = field(default_factory=list)

    # Special-token patterns  [(compiled_pattern, TokenType, xpos_tag)]
    special_patterns    : List[Tuple[re.Pattern, TokenType, str]] = \
                          field(default_factory=list)

    # Abbreviations that should NOT be split at their trailing full stop
    abbreviations       : Set[str]        = field(default_factory=set)

    # Vowels and tone marks (for reduplification detection)
    vowels              : Set[str]        = field(default_factory=set)
    tone_marks          : Set[str]        = field(default_factory=set)

    # Code-switch: list of other-language ISO codes to flag
    cs_lang_isos        : List[str]       = field(default_factory=list)

    # Misc engine flags
    has_augment         : bool = False
    extended_h_spread   : bool = False


def _build_config(
    loader,
    corpus_cfg,
    lang_iso: str,
) -> _TokeniserConfig:
    """Construct a _TokeniserConfig from the loader and corpus config."""

    cfg = _TokeniserConfig(lang_iso=lang_iso)

    # ---- OCR map --------------------------------------------------------
    ocr = corpus_cfg.get(lang_iso, "ocr_corrections", {})
    if not isinstance(ocr, dict):
        ocr = {}
    cfg.ocr_map = {_nfc(k): _nfc(v) for k, v in ocr.items()}

    # ---- Noise ----------------------------------------------------------
    noise_cats  = corpus_cfg.get(lang_iso, "noise_unicode_categories", [])
    noise_chars = corpus_cfg.get(lang_iso, "noise_chars", [])
    cfg.noise_categories = set(noise_cats) if noise_cats else set()
    cfg.noise_chars      = set(noise_chars) if noise_chars else set()

    # ---- Punctuation ----------------------------------------------------
    sf_punct = corpus_cfg.get(lang_iso, "sentence_final_punct",
                               [".", "!", "?", "…", "\u2026"])
    il_punct = corpus_cfg.get(lang_iso, "inline_punct",
                               [",", ";", ":", "(", ")", "[", "]",
                                "\u201c", "\u201d", "\u2018", "\u2019",
                                "\u00ab", "\u00bb",
                                "\u2014", "\u2013", "-"])
    cfg.sentence_final_punct = set(sf_punct)
    cfg.inline_punct         = set(il_punct)

    # Protected patterns (URLs, abbreviations with dots, decimal numbers)
    protect_pats = corpus_cfg.get(lang_iso, "protect_patterns", [])
    default_protect = [
        r"https?://\S+",
        r"\d+\.\d+",               # decimal numbers
        r"[A-Z][a-z]*\.",          # Title-case abbreviation  e.g. "Mk."
        r"[A-Z]{2,}",              # ALL-CAPS acronym
    ]
    for p in (protect_pats or default_protect):
        try:
            cfg.protect_patterns.append(re.compile(p))
        except re.error:
            pass  # skip malformed patterns

    # ---- Abbreviations --------------------------------------------------
    abbrevs = corpus_cfg.get(lang_iso, "bible_book_abbreviations", {})
    cfg.abbreviations = set(abbrevs.keys()) if isinstance(abbrevs, dict) else set()

    # ---- Clitics --------------------------------------------------------
    clitic_data = loader.get("clitics", {}) or {}
    cfg.proclitics = sorted(
        [_nfc(c) for c in clitic_data.get("proclitics", []) or []],
        key=len, reverse=True,   # longest-first for greedy matching
    )
    cfg.enclitics  = sorted(
        [_nfc(c) for c in clitic_data.get("enclitics", []) or []],
        key=len, reverse=True,
    )
    # corpus_config may add more clitics
    extra_enc = corpus_cfg.get(lang_iso, "extra_enclitics", [])
    cfg.enclitics  = sorted(
        list({*cfg.enclitics, *[_nfc(e) for e in (extra_enc or [])]}),
        key=len, reverse=True,
    )

    # ---- Special-token patterns -----------------------------------------
    verse_pat  = corpus_cfg.get(lang_iso, "verse_pattern",
                                 r"^\d+:\d+$")
    chap_pat   = corpus_cfg.get(lang_iso, "chapter_heading_pattern",
                                 r"^[A-Z][A-Za-z0-9 ]+\s+\d+$")
    special_raw = [
        (verse_pat,  TokenType.SPECIAL, "VERSE_REF"),
        (chap_pat,   TokenType.SPECIAL, "CHAP_HEAD"),
    ] + [
        (p, TokenType.SPECIAL, "CUSTOM")
        for p in (corpus_cfg.get(lang_iso, "special_token_patterns", []) or [])
    ]
    for pattern, ttype, xpos in special_raw:
        try:
            cfg.special_patterns.append((re.compile(pattern), ttype, xpos))
        except re.error:
            pass

    # ---- Phonology ------------------------------------------------------
    vowels     = loader.get("phonology.vowels_nfc", []) or []
    tone_marks = loader.get("phonology.tone_marks", []) or []
    cfg.vowels     = set(vowels)
    cfg.tone_marks = set(tone_marks)

    # ---- Engine features ------------------------------------------------
    eng = loader.get("engine_features", {}) or {}
    cfg.has_augment       = bool(eng.get("augment", False))
    cfg.extended_h_spread = bool(eng.get("extended_H_spread", False))

    # ---- Code-switching -------------------------------------------------
    cfg.cs_lang_isos = corpus_cfg.get(lang_iso, "code_switch_langs", []) or []

    return cfg


# ---------------------------------------------------------------------------
# Reduplification detector
# ---------------------------------------------------------------------------

def _detect_reduplication(form: str, cfg: _TokeniserConfig) -> bool:
    """Heuristic test: is *form* a potential reduplication?

    Strategy: check if the form contains an exact doubled substring of
    length >= 3.  This catches patterns like "bulubulubu" or "lyalya"
    without needing the full phonological system.

    A language's YAML can also specify explicit reduplification patterns
    (not yet implemented here — flagged for Phase 2 grammar integration).
    """
    n = len(form)
    if n < 4:
        return False
    # Try all half-lengths >= 2
    for half in range(2, n // 2 + 1):
        if form[:half] == form[half: 2 * half]:
            return True
    return False


# ---------------------------------------------------------------------------
# Punctuation splitter
# ---------------------------------------------------------------------------

class _PunctSplitter:
    """Split punctuation characters away from word strings.

    Returns a list of (substring, is_punct) pairs preserving the original
    character content exactly.
    """

    def __init__(self, cfg: _TokeniserConfig) -> None:
        self._all_punct = cfg.sentence_final_punct | cfg.inline_punct
        self._protect   = cfg.protect_patterns

    def _is_protected(self, form: str) -> bool:
        return any(p.fullmatch(form) for p in self._protect)

    def split(self, form: str) -> List[Tuple[str, bool]]:
        """Return list of (chunk, is_punct) pairs."""
        if self._is_protected(form):
            return [(form, False)]

        result: List[Tuple[str, bool]] = []
        buf = []
        for ch in form:
            if ch in self._all_punct:
                if buf:
                    result.append(("".join(buf), False))
                    buf = []
                result.append((ch, True))
            else:
                buf.append(ch)
        if buf:
            result.append(("".join(buf), False))
        return [(s, p) for s, p in result if s]  # drop empties


# ---------------------------------------------------------------------------
# Clitic splitter
# ---------------------------------------------------------------------------

class _CliticSplitter:
    """Detach proclitics and enclitics from a word form.

    Returns a list of (substring, is_clitic) pairs.  The host form is
    always present; clitics are prepended (proclitic) or appended
    (enclitic).

    Longest-match is applied because cfg.proclitics / cfg.enclitics are
    already sorted longest-first.
    """

    def __init__(self, cfg: _TokeniserConfig) -> None:
        self._proclitics = cfg.proclitics
        self._enclitics  = cfg.enclitics

    def split(self, form: str) -> List[Tuple[str, bool]]:
        """Return [(chunk, is_clitic), …]."""
        # Strip proclitics (left to right, one pass)
        pre_clitics: List[str] = []
        rest = form
        for cli in self._proclitics:
            if rest.startswith(cli) and len(rest) > len(cli):
                pre_clitics.append(cli)
                rest = rest[len(cli):]
                break   # one proclitic per token (extend if needed)

        # Strip enclitics (right to left, one pass)
        post_clitics: List[str] = []
        for cli in self._enclitics:
            if rest.endswith(cli) and len(rest) > len(cli):
                post_clitics.append(cli)
                rest = rest[:-len(cli)]
                break   # one enclitic per token

        result: List[Tuple[str, bool]] = []
        for cli in pre_clitics:
            result.append((cli, True))
        result.append((rest, False))
        for cli in post_clitics:
            result.append((cli, True))
        return result


# ---------------------------------------------------------------------------
# Lexicon stub lookup
# ---------------------------------------------------------------------------

class _LexiconProbe:
    """Check a form against the loaded verb and noun lexicons.

    In Phase 1 this is a *stub* lookup: we check whether the form or a
    plausible stem matches any lexicon key.  Full morpheme-aware lookup
    happens in Phase 2.

    Heuristic: strip up to 3 final vowels and check against verb roots.
    For nouns: check direct root match.
    """

    def __init__(self, loader) -> None:
        self._verbs = getattr(loader, "lexicon_verb", {}) or {}
        self._nouns = getattr(loader, "lexicon_noun", {}) or {}

    def probe(self, form: str) -> List[LexiconEntry]:
        hits: List[LexiconEntry] = []
        norm = _nfc(form.lower())

        # Direct noun match
        if norm in self._nouns:
            hits.append(self._nouns[norm])

        # Direct verb match
        if norm in self._verbs:
            hits.append(self._verbs[norm])

        # Stem approximation for verbs: strip 1-3 final vowels
        if not hits:
            for strip in range(1, 4):
                stem = norm[:-strip] if len(norm) > strip + 2 else norm
                if stem in self._verbs:
                    hits.append(self._verbs[stem])
                    break

        return hits


# ---------------------------------------------------------------------------
# Main tokeniser
# ---------------------------------------------------------------------------

class GobeloWordTokenizer:
    """Language-agnostic word tokeniser for GGT.

    Parameters
    ----------
    loader : GobeloGrammarLoader (or compatible mock)
        Provides grammar data for the target language.
    corpus_cfg : CorpusConfig (or compatible mock)
        Provides corpus-specific overrides.
    lang_iso : str
        ISO 639-3 code.  Defaults to loader.lang_iso.
    sent_id_prefix : str
        Prefix for auto-generated sentence ids.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        loader=None,
        corpus_cfg=None,
        lang_iso: str = "",
        sent_id_prefix: str = "",
    ) -> None:
        self._loader     = loader     or _NullGrammarLoader()
        self._corpus_cfg = corpus_cfg or _NullCorpusConfig()
        self._lang_iso   = lang_iso   or getattr(self._loader, "lang_iso", "und")
        self._prefix     = sent_id_prefix or self._lang_iso

        self._cfg = _build_config(self._loader, self._corpus_cfg, self._lang_iso)
        self._punct_splitter  = _PunctSplitter(self._cfg)
        self._clitic_splitter = _CliticSplitter(self._cfg)
        self._lexicon_probe   = _LexiconProbe(self._loader)

        self._sent_counter = 0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def tokenize(
        self,
        text: str,
        sent_id: str = "",
        source: str = "",
    ) -> AnnotatedSentence:
        """Tokenise *text* and return an AnnotatedSentence.

        Parameters
        ----------
        text     : Raw input sentence string.
        sent_id  : Optional explicit sentence id.
        source   : Provenance tag (e.g. "Bible:Mk.1.1").
        """
        self._sent_counter += 1
        if not sent_id:
            sent_id = f"{self._prefix}-{self._sent_counter:06d}"

        # ---- Stage 1: Pre-normalisation ----
        normalised = self._stage1_normalise(text)

        # ---- Stage 2: Special-token pass over raw string ----
        # (Returns list of raw spans so offsets are pre-split)
        pre_spans = self._stage2_prescan(normalised)

        # ---- Stages 3-6: Split, punct, clitics, post-process ----
        tokens = list(self._stage3456_pipeline(normalised, pre_spans))

        # Assign token ids
        idx = 1
        for tok in tokens:
            tok.token_id = str(idx)
            idx += 1

        sent = AnnotatedSentence(
            sent_id  = sent_id,
            text     = normalised,
            lang_iso = self._lang_iso,
            tokens   = tokens,
            source   = source,
        )
        sent.add_pipeline_stage(f"GobeloWordTokenizer-{self.VERSION}")
        return sent

    def tokenize_batch(
        self,
        texts: List[str],
        source: str = "",
    ) -> List[AnnotatedSentence]:
        """Tokenise a list of sentences."""
        return [
            self.tokenize(t, source=source)
            for t in texts
            if t.strip()
        ]

    # ------------------------------------------------------------------ #
    # Stage 1 · Pre-normalisation
    # ------------------------------------------------------------------ #

    def _stage1_normalise(self, text: str) -> str:
        """NFC → OCR correction → noise strip."""
        text = _nfc(text)

        # OCR corrections (longest key first to avoid partial replacements)
        for wrong, right in sorted(
            self._cfg.ocr_map.items(), key=lambda kv: -len(kv[0])
        ):
            text = text.replace(wrong, right)

        # Strip noise characters
        if self._cfg.noise_chars or self._cfg.noise_categories:
            cleaned = []
            for ch in text:
                cat = unicodedata.category(ch)
                if ch in self._cfg.noise_chars:
                    continue
                if cat in self._cfg.noise_categories:
                    continue
                cleaned.append(ch)
            text = "".join(cleaned)

        return text

    # ------------------------------------------------------------------ #
    # Stage 2 · Pre-scan for special tokens (returns raw string spans)
    # ------------------------------------------------------------------ #

    def _stage2_prescan(
        self, text: str
    ) -> List[Tuple[int, int, TokenType, str]]:
        """Find special token spans in *text*.

        Returns sorted list of (start, end, TokenType, xpos) tuples.
        Overlapping spans are resolved: first match wins.
        """
        hits: List[Tuple[int, int, TokenType, str]] = []
        for pattern, ttype, xpos in self._cfg.special_patterns:
            for m in pattern.finditer(text):
                hits.append((m.start(), m.end(), ttype, xpos))

        # Remove overlaps (keep earliest start; on tie keep longest)
        hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
        non_overlapping: List[Tuple[int, int, TokenType, str]] = []
        last_end = -1
        for h in hits:
            if h[0] >= last_end:
                non_overlapping.append(h)
                last_end = h[1]
        return non_overlapping

    # ------------------------------------------------------------------ #
    # Stage 3-6 combined pipeline
    # ------------------------------------------------------------------ #

    def _stage3456_pipeline(
        self,
        text: str,
        special_spans: List[Tuple[int, int, TokenType, str]],
    ) -> Iterator[WordToken]:
        """Yield WordToken objects for the full text."""

        # Build a lookup of special span positions for O(1) checking
        special_by_start: Dict[int, Tuple[int, int, TokenType, str]] = {
            s[0]: s for s in special_spans
        }

        # Stage 3: whitespace-split with offset tracking
        for chunk, c_start, c_end in self._ws_split(text):
            # Is this chunk (or a sub-range) a special token?
            if c_start in special_by_start:
                _, sp_end, sp_type, sp_xpos = special_by_start[c_start]
                if sp_end == c_end:
                    yield self._make_special_token(
                        chunk, c_start, c_end, sp_type, sp_xpos
                    )
                    continue

            # Stage 4: punctuation splitting
            yield from self._stage4_punct_split(chunk, c_start)

    def _ws_split(
        self, text: str
    ) -> Iterator[Tuple[str, int, int]]:
        """Yield (chunk, start, end) for each whitespace-delimited token."""
        pos = 0
        n   = len(text)
        while pos < n:
            # Skip whitespace
            while pos < n and text[pos].isspace():
                pos += 1
            if pos >= n:
                break
            # Collect non-whitespace
            start = pos
            while pos < n and not text[pos].isspace():
                pos += 1
            yield text[start:pos], start, pos

    def _stage4_punct_split(
        self, chunk: str, base_offset: int
    ) -> Iterator[WordToken]:
        """Split punctuation from *chunk* and emit WordTokens."""
        parts = self._punct_splitter.split(chunk)

        offset = base_offset
        for (sub, is_punct) in parts:
            start = offset
            end   = offset + len(sub)
            offset = end

            if not sub:
                continue

            if is_punct:
                yield self._make_punct_token(sub, start, end)
            else:
                # Stage 5: clitic splitting
                yield from self._stage5_clitic_split(sub, start)

    def _stage5_clitic_split(
        self, chunk: str, base_offset: int
    ) -> Iterator[WordToken]:
        """Split clitics from *chunk* and emit WordTokens."""
        parts  = self._clitic_splitter.split(chunk)
        offset = base_offset

        host_token_id: Optional[str] = None  # filled after host is emitted

        for i, (sub, is_clitic) in enumerate(parts):
            start = offset
            end   = offset + len(sub)
            offset = end

            if not sub:
                continue

            tok = self._stage6_make_word_token(sub, start, end)

            if is_clitic:
                tok.token_type = TokenType.CLITIC
                tok.add_flag("CLITIC")
                # host_token_id will be set below after all tokens are emitted
                # We mark it provisionally with the preceding token index
                if host_token_id is not None:
                    tok.clitic_of = host_token_id
            else:
                host_token_id = tok.token_id  # will be overwritten by caller

            yield tok

    # ------------------------------------------------------------------ #
    # Stage 6 · Post-processing helpers
    # ------------------------------------------------------------------ #

    def _stage6_make_word_token(
        self, form: str, start: int, end: int
    ) -> WordToken:
        """Create a WordToken and run post-processing checks."""
        tok = WordToken(
            form       = form,
            lang_iso   = self._lang_iso,
            char_start = start,
            char_end   = end,
        )

        # Numeric check
        if _is_numeric(form):
            tok.token_type = TokenType.NUMBER
            tok.upos       = POSTag.NUM
            tok.add_flag("NUMERIC")
            return tok

        # All-punct check
        if _is_all_punct(form):
            tok.token_type = TokenType.PUNCT
            tok.upos       = POSTag.PUNCT
            return tok

        # Reduplification
        if _detect_reduplication(form.lower(), self._cfg):
            tok.is_reduplicated = True
            tok.add_flag("REDUPLICATED")

        # Lexicon probe
        matches = self._lexicon_probe.probe(form)
        for entry in matches:
            tok.add_lexicon_match(entry)
        if matches:
            tok.add_flag("LEXICON_HIT")
            self._apply_lexicon_hint(tok, matches[0])
        else:
            tok.add_flag("OOV")

        # Code-switch detection (simple heuristic: compare script)
        if self._cfg.cs_lang_isos and self._detect_code_switch(form):
            tok.token_type      = TokenType.CODE_SWITCH
            tok.add_flag("CODE_SWITCH")

        # Store normalised form in misc for CoNLL-U
        tok.set_misc("NFC", _nfc(form))

        return tok

    def _apply_lexicon_hint(
        self, tok: WordToken, entry: LexiconEntry
    ) -> None:
        """Set preliminary upos and noun_class from a lexicon hit."""
        from models import LexiconCategory  # local import to avoid circularity
        if entry.is_verb():
            tok.upos  = POSTag.VERB
            tok.lemma = entry.root
        elif entry.is_noun():
            tok.upos       = POSTag.NOUN
            tok.lemma      = entry.root
            tok.noun_class = entry.noun_class or None

    def _detect_code_switch(self, form: str) -> bool:
        """Very conservative heuristic: Latin-only chars in a form that would
        otherwise be expected to carry tone marks.

        A proper code-switch detector requires a separate language model
        (Phase 3).  For now this flags obvious cases.
        """
        # If the language uses tone marks and the form has none but is
        # all-Latin and not in the lexicon, it might be a code-switch.
        # This is intentionally conservative — false negatives are better
        # than false positives at this stage.
        if not self._cfg.tone_marks:
            return False  # language doesn't mark tones on the surface
        has_tone = any(
            unicodedata.combining(ch) or ch in self._cfg.tone_marks
            for ch in unicodedata.normalize("NFD", form)
        )
        # Flag only if form is all-Latin letters and 4+ chars
        is_latin = all("LATIN" in unicodedata.name(ch, "") or ch.isdigit()
                       for ch in form)
        return not has_tone and is_latin and len(form) >= 4

    # ------------------------------------------------------------------ #
    # Token factory helpers
    # ------------------------------------------------------------------ #

    def _make_special_token(
        self,
        form     : str,
        start    : int,
        end      : int,
        ttype    : TokenType,
        xpos     : str,
    ) -> WordToken:
        return WordToken(
            form       = form,
            lang_iso   = self._lang_iso,
            token_type = ttype,
            xpos       = xpos,
            upos       = POSTag.SYM,
            char_start = start,
            char_end   = end,
            flags      = ["SPECIAL"],
        )

    def _make_punct_token(
        self, form: str, start: int, end: int
    ) -> WordToken:
        return WordToken(
            form       = form,
            lang_iso   = self._lang_iso,
            token_type = TokenType.PUNCT,
            upos       = POSTag.PUNCT,
            char_start = start,
            char_end   = end,
        )

    # ------------------------------------------------------------------ #
    # Diagnostics / repr
    # ------------------------------------------------------------------ #

    def describe(self) -> str:
        """Return a human-readable summary of this tokeniser's configuration."""
        lines = [
            f"GobeloWordTokenizer v{self.VERSION}",
            f"  lang_iso   : {self._lang_iso}",
            f"  proclitics : {self._cfg.proclitics or '(none)'}",
            f"  enclitics  : {self._cfg.enclitics  or '(none)'}",
            f"  ocr_map    : {len(self._cfg.ocr_map)} entries",
            f"  sp_patterns: {len(self._cfg.special_patterns)} patterns",
            f"  abbreviations: {len(self._cfg.abbreviations)} entries",
            f"  vowels     : {sorted(self._cfg.vowels) or '(none)'}",
            f"  tone_marks : {sorted(self._cfg.tone_marks) or '(none)'}",
            f"  augment    : {self._cfg.has_augment}",
            f"  H_spread   : {self._cfg.extended_h_spread}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"GobeloWordTokenizer(lang={self._lang_iso!r}, "
            f"v={self.VERSION})"
        )
