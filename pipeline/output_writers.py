"""
output_writers.py — GobeloJsonWriter + GobeloCoNLLUWriter  (GGT Phase 4)
========================================================================
Serialises AnnotatedSentence objects produced by the three-stage pipeline
(tokenise → morpheme-analyse → POS-tag) to two output formats:

  GobeloJsonWriter
      Extends the existing gcbt JSON schema.  Each token gains ``slots``,
      ``upos``, ``feats``, ``xpos``, ``lemma``, ``morphemes`` keys.
      Produces one JSON file per language per corpus run, mirroring gcbt's
      output directory layout.

  GobeloCoNLLUWriter
      Standard CoNLL-U 2.0 format.  Morpheme segmentation is stored in the
      MISC column (``Morphemes=SM=ba|ROOT=lim|FV=a``).  Multi-word tokens
      and empty nodes are not produced (this is a single-word token pipeline).

Both writers share a common base class ``_BaseWriter`` that handles:
  - Output directory creation
  - Sentence streaming (one sentence at a time, no full-corpus buffering)
  - Checkpoint support (append mode with a skip-list of sent_ids)
  - Parallel worker compatibility (each worker writes its own shard)
  - Language-namespaced output paths mirroring gcbt conventions

Architecture
------------
Writers are context managers:

    with GobeloJsonWriter(output_dir, lang_iso="toi") as w:
        for sentence in sentences:
            w.write(sentence)

Or used standalone:

    w = GobeloJsonWriter(output_dir, lang_iso="toi")
    w.open()
    for sentence in sentences:
        w.write(sentence)
    w.close()
    print(w.stats())

Output directory layout (mirrors gcbt)
---------------------------------------
    output_dir/
      toi/
        annotations/
          toi_annotations.json       ← GobeloJsonWriter (one object per line)
          toi_annotations.conllu     ← GobeloCoNLLUWriter
          toi_annotations_stats.json ← written by writer.close()

JSON schema extension
---------------------
The gcbt format already produces:

    {
      "language_iso": "toi",
      "sentences": [
        {
          "sent_id": "toi-001-001",
          "text": "Bakali balima.",
          "tokens": [
            {"form": "Bakali", "start": 0, "end": 6}
          ]
        }
      ]
    }

GobeloJsonWriter extends each token object with:

    {
      "form": "balima",
      "start": 7,
      "end": 13,
      "token_id": "2",
      "token_type": "word",
      "upos": "VERB",
      "xpos": "VERB.FIN.SMNC2",
      "lemma": "lim",
      "feats": {"VerbForm": "Fin", "Person": "3", "Number": "Plur",
                "Tense": "Pres", "Mood": "Ind"},
      "deprel": null,
      "noun_class": null,
      "is_oov": false,
      "morphemes": [
        {"start": 0, "end": 2, "form": "ba", "label": "SM",  "gloss": "SM.NC2"},
        {"start": 2, "end": 5, "form": "lim","label": "ROOT","gloss": "cultivate"},
        {"start": 5, "end": 6, "form": "a",  "label": "FV",  "gloss": "FV.IND"}
      ],
      "slot_parses": [
        {
          "score": 0.72,
          "root": "lim",
          "gloss": "SM.NC2-cultivate-FV.IND",
          "flags": ["LEXICON_HIT", "FV_IDENTIFIED"]
        }
      ],
      "flags": ["VERB_ANALYSED", "TAGGED_V2"]
    }

CoNLL-U format
--------------
Standard 10-column TSV.  MISC column carries:
  Morphemes=SM=ba|ROOT=lim|FV=a
  Gloss=SM.NC2-cultivate-FV.IND
  SlotScore=0.720
  NounClass=NC3  (noun tokens)
  OOV=Yes        (out-of-vocabulary tokens)
  AgreeNC=NC2    (agreement chain, from Phase 3 Pass C)
"""

from __future__ import annotations

import json
import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set

from models import AnnotatedSentence, MorphemeSpan, POSTag, SlotParse, WordToken

__all__ = [
    "GobeloJsonWriter",
    "GobeloCoNLLUWriter",
    "WriterStats",
    "load_checkpoint",
]

VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# WriterStats — accumulated per-run statistics
# ---------------------------------------------------------------------------

@dataclass
class WriterStats:
    """Statistics accumulated across a writing session.

    Attributes
    ----------
    sentences_written : int
        Total sentences flushed to disk.
    tokens_written : int
        Total word tokens written (all types).
    oov_tokens : int
        Tokens flagged is_oov = True.
    verb_tokens : int
        Tokens with upos == VERB.
    noun_tokens : int
        Tokens with upos == NOUN.
    tagged_tokens : int
        Tokens with a non-None, non-X upos.
    untagged_tokens : int
        Tokens with upos == X or upos == None.
    bytes_written : int
        Cumulative bytes written to the primary output file.
    skipped_sentences : int
        Sentences skipped due to checkpoint.
    """
    sentences_written : int = 0
    tokens_written    : int = 0
    oov_tokens        : int = 0
    verb_tokens       : int = 0
    noun_tokens       : int = 0
    tagged_tokens     : int = 0
    untagged_tokens   : int = 0
    bytes_written     : int = 0
    skipped_sentences : int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentences_written": self.sentences_written,
            "tokens_written":    self.tokens_written,
            "oov_tokens":        self.oov_tokens,
            "verb_tokens":       self.verb_tokens,
            "noun_tokens":       self.noun_tokens,
            "tagged_tokens":     self.tagged_tokens,
            "untagged_tokens":   self.untagged_tokens,
            "bytes_written":     self.bytes_written,
            "skipped_sentences": self.skipped_sentences,
            "tagging_rate":      round(
                self.tagged_tokens / self.tokens_written, 4
            ) if self.tokens_written else 0.0,
            "oov_rate": round(
                self.oov_tokens / self.tokens_written, 4
            ) if self.tokens_written else 0.0,
        }

    def __repr__(self) -> str:
        return (
            f"WriterStats(sents={self.sentences_written}, "
            f"toks={self.tokens_written}, "
            f"tagged={self.tagged_tokens}, "
            f"oov={self.oov_tokens})"
        )


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def load_checkpoint(checkpoint_path: str | Path) -> Set[str]:
    """Load a set of already-written sent_ids from a checkpoint file.

    Checkpoint files are plain text, one sent_id per line.
    Returns an empty set if the file does not exist.
    """
    p = Path(checkpoint_path)
    if not p.exists():
        return set()
    with p.open("r", encoding="utf-8") as fh:
        return {line.strip() for line in fh if line.strip()}


def _append_checkpoint(checkpoint_path: Path, sent_id: str) -> None:
    with checkpoint_path.open("a", encoding="utf-8") as fh:
        fh.write(sent_id + "\n")


# ---------------------------------------------------------------------------
# Internal serialisation helpers
# ---------------------------------------------------------------------------

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _token_to_dict(token: WordToken) -> Dict[str, Any]:
    """Serialise a WordToken to the extended gcbt JSON token format."""
    morphemes = [
        {
            "start": ms.start,
            "end":   ms.end,
            "form":  ms.form,
            "label": ms.label,
            "gloss": ms.gloss,
            "slot":  ms.slot,
        }
        for ms in token.morpheme_spans
    ]

    slot_parses = [
        {
            "score": round(sp.score, 4),
            "root":  sp.root_form(),
            "gloss": sp.gloss_string(),
            "flags": list(sp.parse_flags),
        }
        for sp in token.slot_parses
    ]

    lexicon_matches = [
        {
            "root":  le.root,
            "gloss": le.gloss,
            "cat":   le.category.value,
            "nc":    le.noun_class or None,
        }
        for le in token.lexicon_matches
    ]

    return {
        "token_id":       token.token_id,
        "form":           token.form,
        "original_form":  token.original_form if token.original_form != token.form else None,
        "token_type":     token.token_type.value,
        "char_start":     token.char_start,
        "char_end":       token.char_end,
        "lemma":          token.lemma,
        "upos":           token.upos.value if token.upos else None,
        "xpos":           token.xpos,
        "feats":          dict(sorted(token.feats.items())),
        "head":           token.head,
        "deprel":         token.deprel,
        "noun_class":     token.noun_class,
        "is_oov":         token.is_oov,
        "is_reduplicated":token.is_reduplicated,
        "clitic_of":      token.clitic_of,
        "flags":          list(token.flags),
        "morphemes":      morphemes,
        "slot_parses":    slot_parses,
        "lexicon_matches":lexicon_matches,
        "misc":           dict(token.misc) if token.misc else {},
    }


def _sentence_to_dict(sentence: AnnotatedSentence) -> Dict[str, Any]:
    """Serialise an AnnotatedSentence to the extended gcbt JSON sentence format."""
    return {
        "sent_id":   sentence.sent_id,
        "text":      sentence.text,
        "lang_iso":  sentence.lang_iso,
        "source":    sentence.source,
        "pipeline":  list(sentence.pipeline),
        "has_cs":    sentence.has_cs,
        "comments":  list(sentence.comments),
        "stats":     sentence.coverage_stats(),
        "tokens":    [_token_to_dict(t) for t in sentence.tokens],
    }


def _feats_str(feats: Dict[str, str]) -> str:
    """Render feats dict as CoNLL-U feature string (sorted, pipe-separated)."""
    if not feats:
        return "_"
    return "|".join(f"{k}={v}" for k, v in sorted(feats.items()))


def _misc_str(token: WordToken) -> str:
    """Build the CoNLL-U MISC string from token.misc plus morpheme spans."""
    misc: Dict[str, str] = dict(token.misc)

    # Morpheme segmentation in MISC
    if token.morpheme_spans:
        morph_str = "|".join(
            f"{ms.label}={ms.form}"
            for ms in token.morpheme_spans
            if ms.form
        )
        if morph_str:
            misc.setdefault("Morphemes", morph_str)

    # Gloss from best slot parse
    if token.slot_parses:
        best = token.slot_parses[token.best_parse]
        g = best.gloss_string()
        if g:
            misc.setdefault("Gloss", g)
        misc.setdefault("SlotScore", f"{best.score:.3f}")

    # NounClass
    if token.noun_class:
        misc.setdefault("NounClass", token.noun_class)

    # OOV flag
    if token.is_oov:
        misc.setdefault("OOV", "Yes")

    if not misc:
        return "_"
    return "|".join(f"{k}={v}" for k, v in sorted(misc.items()))


def _token_to_conllu(token: WordToken) -> str:
    """Render a WordToken as a single CoNLL-U tab-separated line."""
    return "\t".join([
        str(token.token_id),
        token.form      or "_",
        token.lemma     or "_",
        token.upos.value if token.upos else "_",
        token.xpos      or "_",
        _feats_str(token.feats),
        str(token.head) if token.head is not None else "_",
        token.deprel    or "_",
        "_",                              # enhanced deps — Phase 5
        _misc_str(token),
    ])


def _sentence_to_conllu(sentence: AnnotatedSentence) -> str:
    """Render an AnnotatedSentence as a complete CoNLL-U block."""
    lines: List[str] = []
    lines.append(f"# sent_id = {sentence.sent_id}")
    lines.append(f"# text = {sentence.text}")
    if sentence.source:
        lines.append(f"# source = {sentence.source}")
    if sentence.lang_iso:
        lines.append(f"# lang = {sentence.lang_iso}")
    if sentence.pipeline:
        lines.append(f"# pipeline = {' | '.join(sentence.pipeline)}")
    for comment in sentence.comments:
        lines.append(f"# {comment}")
    for token in sentence.tokens:
        lines.append(_token_to_conllu(token))
    lines.append("")   # blank line terminator
    return "\n".join(lines) + "\n"  # final \n ensures blank line between blocks


# ---------------------------------------------------------------------------
# Base writer
# ---------------------------------------------------------------------------

class _BaseWriter:
    """Shared infrastructure for JSON and CoNLL-U writers.

    Handles directory creation, file open/close, checkpoint management,
    stats accumulation, and the context-manager protocol.
    """

    #: Subclasses set this to the file extension they produce.
    _EXTENSION: str = ".txt"

    def __init__(
        self,
        output_dir    : str | Path,
        lang_iso      : str,
        filename      : Optional[str]  = None,
        append        : bool           = False,
        checkpoint_path: Optional[str | Path] = None,
        encoding      : str            = "utf-8",
    ) -> None:
        """
        Parameters
        ----------
        output_dir : str | Path
            Root output directory.  Writer creates:
            ``output_dir/<lang_iso>/annotations/<filename>``.
        lang_iso : str
            ISO 639-3 language code (e.g. ``"toi"``).
        filename : str, optional
            Override the default output filename.  Defaults to
            ``<lang_iso>_annotations<extension>``.
        append : bool
            If True, open the file in append mode instead of write mode.
        checkpoint_path : str | Path, optional
            Path to a checkpoint file.  Sentences whose sent_id is in the
            checkpoint are skipped.  New sent_ids are appended to the file
            after being written.
        encoding : str
            File encoding (default UTF-8).
        """
        self._lang_iso   = lang_iso
        self._encoding   = encoding
        self._append     = append
        self._stats      = WriterStats()
        self._fh         = None   # file handle; set by open()

        # Resolve output path
        root = Path(output_dir)
        lang_dir = root / lang_iso / "annotations"
        lang_dir.mkdir(parents=True, exist_ok=True)
        if filename:
            self._path = lang_dir / filename
        else:
            self._path = lang_dir / f"{lang_iso}_annotations{self._EXTENSION}"

        # Stats file is always alongside the primary output
        self._stats_path = self._path.with_suffix(".stats.json")

        # Checkpoint
        self._checkpoint_path: Optional[Path] = (
            Path(checkpoint_path) if checkpoint_path else None
        )
        self._seen_ids: Set[str] = (
            load_checkpoint(self._checkpoint_path)
            if self._checkpoint_path
            else set()
        )

    # ------------------------------------------------------------------ #
    # Context manager
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "_BaseWriter":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
        return False  # do not suppress exceptions

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def open(self) -> None:
        """Open the output file for writing."""
        mode = "a" if self._append else "w"
        self._fh = open(self._path, mode, encoding=self._encoding)

    def close(self) -> None:
        """Flush, close the output file, and write the stats sidecar."""
        if self._fh:
            self._fh.flush()
            self._fh.close()
            self._fh = None
        self._write_stats()

    def write(self, sentence: AnnotatedSentence) -> bool:
        """Write one sentence.  Returns False if the sentence was skipped.

        Parameters
        ----------
        sentence : AnnotatedSentence
            The fully annotated sentence to serialise.

        Returns
        -------
        bool
            True if the sentence was written, False if skipped (checkpoint).
        """
        if not self._fh:
            raise RuntimeError("Writer is not open. Call open() or use as context manager.")

        # Checkpoint check
        if sentence.sent_id in self._seen_ids:
            self._stats.skipped_sentences += 1
            return False

        raw = self._serialise(sentence)
        self._fh.write(raw)
        nbytes = len(raw.encode(self._encoding))
        self._stats.bytes_written += nbytes

        # Update stats
        self._stats.sentences_written += 1
        self._accumulate_stats(sentence)

        # Checkpoint write
        if self._checkpoint_path:
            _append_checkpoint(self._checkpoint_path, sentence.sent_id)
            self._seen_ids.add(sentence.sent_id)

        return True

    def write_batch(self, sentences: List[AnnotatedSentence]) -> int:
        """Write a list of sentences.  Returns count of sentences written."""
        written = 0
        for sent in sentences:
            if self.write(sent):
                written += 1
        return written

    def stats(self) -> WriterStats:
        """Return the accumulated statistics for this session."""
        return self._stats

    @property
    def output_path(self) -> Path:
        """Path to the primary output file."""
        return self._path

    # ------------------------------------------------------------------ #
    # Subclass hooks
    # ------------------------------------------------------------------ #

    def _serialise(self, sentence: AnnotatedSentence) -> str:
        """Return the string representation of one sentence.  Override in subclass."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _accumulate_stats(self, sentence: AnnotatedSentence) -> None:
        for tok in sentence.tokens:
            self._stats.tokens_written += 1
            if tok.is_oov:
                self._stats.oov_tokens += 1
            if tok.upos == POSTag.VERB:
                self._stats.verb_tokens += 1
            elif tok.upos == POSTag.NOUN:
                self._stats.noun_tokens += 1
            if tok.upos and tok.upos != POSTag.X:
                self._stats.tagged_tokens += 1
            else:
                self._stats.untagged_tokens += 1

    def _write_stats(self) -> None:
        with open(self._stats_path, "w", encoding="utf-8") as fh:
            json.dump(self._stats.to_dict(), fh, indent=2, ensure_ascii=False)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(lang={self._lang_iso!r}, "
            f"path={self._path}, open={self._fh is not None})"
        )


# ---------------------------------------------------------------------------
# GobeloJsonWriter
# ---------------------------------------------------------------------------

class GobeloJsonWriter(_BaseWriter):
    """Writes annotated sentences to newline-delimited JSON (JSON-Lines).

    Each line is a complete JSON object representing one sentence with all
    token-level annotations (UPOS, FEATS, XPOS, morpheme spans, slot parses,
    etc.).  This extends the existing gcbt JSON schema transparently.

    The file begins with a single header line (a JSON comment-style sentinel)
    followed by one sentence object per line.  Readers can use standard
    JSON-Lines parsing.

    Parameters
    ----------
    output_dir : str | Path
        Root output directory.
    lang_iso : str
        ISO 639-3 language code.
    filename : str, optional
        Override default filename ``<lang_iso>_annotations.jsonl``.
    append : bool
        Append to an existing file rather than overwriting.
    checkpoint_path : str | Path, optional
        Checkpoint file path for resuming interrupted runs.
    indent : int | None
        If set, pretty-print each JSON object with that indent level.
        Default None (compact one-line-per-sentence).
    include_raw_tokens : bool
        If False, strip raw token fields not needed for downstream NLP
        (original_form, char offsets).  Default True.
    """

    _EXTENSION = ".jsonl"

    def __init__(
        self,
        output_dir    : str | Path,
        lang_iso      : str,
        filename      : Optional[str]  = None,
        append        : bool           = False,
        checkpoint_path: Optional[str | Path] = None,
        indent        : Optional[int]  = None,
        include_raw_tokens: bool       = True,
    ) -> None:
        super().__init__(
            output_dir=output_dir,
            lang_iso=lang_iso,
            filename=filename or f"{lang_iso}_annotations.jsonl",
            append=append,
            checkpoint_path=checkpoint_path,
        )
        self._indent = indent
        self._include_raw = include_raw_tokens

    def _serialise(self, sentence: AnnotatedSentence) -> str:
        d = _sentence_to_dict(sentence)
        if not self._include_raw:
            for tok in d.get("tokens", []):
                tok.pop("original_form", None)
                tok.pop("char_start", None)
                tok.pop("char_end", None)
        line = json.dumps(d, ensure_ascii=False, indent=self._indent)
        return line + "\n"

    def write_corpus_header(self, lang_iso: str, metadata: Dict[str, Any]) -> None:
        """Write an optional corpus-level header object as the first line.

        The header is a JSON object with ``_type: "corpus_header"`` so that
        readers can detect and skip it.

        Parameters
        ----------
        lang_iso : str
            Language ISO code.
        metadata : dict
            Any key-value pairs to include (e.g. grammar version, run date).
        """
        if not self._fh:
            raise RuntimeError("Writer is not open.")
        header = {
            "_type":     "corpus_header",
            "lang_iso":  lang_iso,
            "writer":    f"GobeloJsonWriter-{VERSION}",
            **metadata,
        }
        line = json.dumps(header, ensure_ascii=False) + "\n"
        self._fh.write(line)
        self._stats.bytes_written += len(line.encode(self._encoding))


# ---------------------------------------------------------------------------
# GobeloCoNLLUWriter
# ---------------------------------------------------------------------------

class GobeloCoNLLUWriter(_BaseWriter):
    """Writes annotated sentences in standard CoNLL-U 2.0 format.

    Produces valid CoNLL-U files consumable by tools such as UDPipe,
    Stanza, spaCy, and the UD treebank validator.

    Each sentence is rendered as:
      # sent_id = <id>
      # text = <raw text>
      # source = <provenance>  (if set)
      # lang = <iso>
      # pipeline = <stage1> | <stage2> | ...
      1  form  lemma  UPOS  XPOS  Feat=s  head  deprel  _  MISC
      ...
      (blank line)

    Multi-word tokens (MWTs) and empty nodes are not produced by this
    pipeline.  Enhanced dependencies (column 9) are always ``_`` until
    Phase 5.

    The MISC column carries morpheme segmentation and alignment data:
      Morphemes=SM=ba|ROOT=lim|FV=a
      Gloss=SM.NC2-cultivate-FV.IND
      SlotScore=0.720
      NounClass=NC3
      OOV=Yes
      AgreeNC=NC2
      AgreeWith=1
    """

    _EXTENSION = ".conllu"

    def __init__(
        self,
        output_dir    : str | Path,
        lang_iso      : str,
        filename      : Optional[str]  = None,
        append        : bool           = False,
        checkpoint_path: Optional[str | Path] = None,
        include_projective_order: bool = False,
    ) -> None:
        super().__init__(
            output_dir=output_dir,
            lang_iso=lang_iso,
            filename=filename or f"{lang_iso}_annotations.conllu",
            append=append,
            checkpoint_path=checkpoint_path,
        )
        self._proj_order = include_projective_order

    def _serialise(self, sentence: AnnotatedSentence) -> str:
        return _sentence_to_conllu(sentence)

    def write_global_comments(self, comments: List[str]) -> None:
        """Write CoNLL-U global.columns or other document-level comments.

        Parameters
        ----------
        comments : list of str
            Lines to write (without leading ``#``).
            E.g. ``["global.columns = ID FORM LEMMA UPOS XPOS FEATS HEAD DEPREL DEPS MISC"]``
        """
        if not self._fh:
            raise RuntimeError("Writer is not open.")
        for c in comments:
            line = f"# {c}\n"
            self._fh.write(line)
            self._stats.bytes_written += len(line.encode(self._encoding))


# ---------------------------------------------------------------------------
# Dual writer convenience class
# ---------------------------------------------------------------------------

class GobeloDualWriter:
    """Writes to both JSON and CoNLL-U simultaneously.

    Convenience wrapper that mirrors the API of the individual writers.

    Parameters
    ----------
    output_dir : str | Path
    lang_iso : str
    append : bool
    checkpoint_path : str | Path, optional
        Shared checkpoint path — a sentence written to both formats
        is only checkpointed once (after both writes succeed).
    json_kwargs : dict
        Extra kwargs forwarded to GobeloJsonWriter.
    conllu_kwargs : dict
        Extra kwargs forwarded to GobeloCoNLLUWriter.

    Examples
    --------
    ::

        with GobeloDualWriter("/out", lang_iso="bem") as w:
            for sentence in pipeline:
                w.write(sentence)
        print(w.stats())
    """

    def __init__(
        self,
        output_dir      : str | Path,
        lang_iso        : str,
        append          : bool = False,
        checkpoint_path : Optional[str | Path] = None,
        json_kwargs     : Optional[Dict[str, Any]] = None,
        conllu_kwargs   : Optional[Dict[str, Any]] = None,
    ) -> None:
        self._json_writer = GobeloJsonWriter(
            output_dir=output_dir,
            lang_iso=lang_iso,
            append=append,
            checkpoint_path=checkpoint_path,
            **(json_kwargs or {}),
        )
        self._conllu_writer = GobeloCoNLLUWriter(
            output_dir=output_dir,
            lang_iso=lang_iso,
            append=append,
            # CoNLL-U writer does NOT manage its own checkpoint —
            # the JSON writer owns it so sentences aren't double-counted.
            checkpoint_path=None,
            **(conllu_kwargs or {}),
        )
        # Mirror checkpoint from JSON writer so CoNLL-U skips same sents
        self._json_writer._seen_ids   # shared reference after open()

    def __enter__(self) -> "GobeloDualWriter":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
        return False

    def open(self) -> None:
        self._json_writer.open()
        self._conllu_writer.open()
        # Sync seen_ids so CoNLL-U respects JSON writer's checkpoint
        self._conllu_writer._seen_ids = self._json_writer._seen_ids

    def close(self) -> None:
        self._json_writer.close()
        self._conllu_writer.close()

    def write(self, sentence: AnnotatedSentence) -> bool:
        """Write sentence to both formats.

        Checkpointing is delegated to the JSON writer; CoNLL-U
        skips any sentence the JSON writer skips.
        """
        written_json = self._json_writer.write(sentence)
        if written_json:
            # JSON writer already appended to checkpoint; CoNLL-U just writes
            self._conllu_writer._seen_ids = self._json_writer._seen_ids
            self._conllu_writer._serialise_and_flush(sentence)
        else:
            self._conllu_writer._stats.skipped_sentences += 1
        return written_json

    def write_batch(self, sentences: List[AnnotatedSentence]) -> int:
        return sum(1 for s in sentences if self.write(s))

    def stats(self) -> Dict[str, WriterStats]:
        return {"json": self._json_writer.stats(), "conllu": self._conllu_writer.stats()}

    @property
    def json_path(self) -> Path:
        return self._json_writer.output_path

    @property
    def conllu_path(self) -> Path:
        return self._conllu_writer.output_path


# Patch _BaseWriter with a helper used by GobeloDualWriter
def _serialise_and_flush(self: _BaseWriter, sentence: AnnotatedSentence) -> None:
    """Write sentence directly without checkpoint logic (used by DualWriter)."""
    raw = self._serialise(sentence)
    self._fh.write(raw)
    self._stats.bytes_written += len(raw.encode(self._encoding))
    self._stats.sentences_written += 1
    self._accumulate_stats(sentence)

_BaseWriter._serialise_and_flush = _serialise_and_flush  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Public utility: read back a jsonl annotation file
# ---------------------------------------------------------------------------

def iter_jsonl(path: str | Path) -> Iterator[Dict[str, Any]]:
    """Iterate over sentence dicts from a GobeloJsonWriter output file.

    Skips the corpus-header line (``_type == "corpus_header"``).
    Ignores blank lines and lines starting with ``#``.

    Parameters
    ----------
    path : str | Path
        Path to the ``.jsonl`` file.

    Yields
    ------
    dict
        One sentence dict per yield.
    """
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            obj = json.loads(line)
            if obj.get("_type") == "corpus_header":
                continue
            yield obj


def iter_conllu(path: str | Path) -> Iterator[List[str]]:
    """Iterate over raw CoNLL-U sentence blocks from a ``.conllu`` file.

    Each block is a list of non-blank lines (comments + token lines).
    The trailing blank line is not included.

    Parameters
    ----------
    path : str | Path
        Path to the ``.conllu`` file.

    Yields
    ------
    list of str
        Lines of one CoNLL-U sentence block.
    """
    with open(path, "r", encoding="utf-8") as fh:
        block: List[str] = []
        for line in fh:
            line = line.rstrip("\n")
            if line == "":
                if block:
                    yield block
                    block = []
            else:
                block.append(line)
        if block:
            yield block
