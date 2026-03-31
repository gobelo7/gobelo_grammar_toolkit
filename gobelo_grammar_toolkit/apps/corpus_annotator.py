"""
apps/corpus_annotator.py
=========================
CorpusAnnotator — F-09 corpus annotation pipeline.

Accepts a plain-text corpus (as a string or file path), sentences every
token through :class:`MorphologicalAnalyzer` and :class:`UDFeatureMapper`,
and writes a CoNLL-U file with morphological annotation.

Pipeline
--------
1. Sentence segmentation (blank-line primary; punctuation fallback).
2. Per-sentence tokenisation via ``MorphologicalAnalyzer.segment_text()``.
3. Per-token UD feature extraction via ``UDFeatureMapper.map_segmented_token()``
   and ``to_conllu_feats_str()``.
4. CoNLL-U column assembly (ID, FORM, LEMMA, UPOS, XPOS, FEATS, HEAD,
   DEPREL, DEPS, MISC).
5. Serialisation to CoNLL-U text or file.

Design contract
---------------
- Accepts a single ``GobeloGrammarLoader`` as the only grammar dependency.
- ``MorphologicalAnalyzer`` and ``UDFeatureMapper`` are created internally.
- Never aborts the corpus for one bad token.  ``MorphAnalysisError`` and
  ``UDMappingError`` are caught per-token and written as ``UPOS=X`` rows
  with ``MISC=AnnotationFailed=<ClassName>``.
- Ambiguous parses are flagged with ``Ambiguous=Yes`` in ``MISC``.

Usage
-----
::

    from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    from gobelo_grammar_toolkit.apps.corpus_annotator import CorpusAnnotator

    loader    = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    annotator = CorpusAnnotator(loader)

    result = annotator.annotate_text("balya cilya.\\n\\ntwalya muntu.")
    print(annotator.to_conllu(result))

    annotator.write_conllu(result, "corpus.conllu")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from gobelo_grammar_toolkit.core.exceptions import GGTError
from gobelo_grammar_toolkit.apps.morphological_analyzer import (
    MorphAnalysisError,
    MorphologicalAnalyzer,
    SegmentedToken,
)
from gobelo_grammar_toolkit.apps.ud_feature_mapper import (
    UDFeatureBundle,
    UDFeatureMapper,
    UDMappingError,
)

__all__ = [
    "CorpusAnnotator",
    "AnnotatedToken",
    "AnnotatedSentence",
    "AnnotationResult",
    "CorpusAnnotationError",
]

# ─────────────────────────────────────────────────────────────────────────────
# Exception
# ─────────────────────────────────────────────────────────────────────────────


class CorpusAnnotationError(GGTError):
    """
    Raised for unrecoverable configuration errors (e.g. file not found,
    unreadable input).  Distinct from per-token failures, which are
    silently recorded in ``AnnotationResult.failed_tokens``.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ─────────────────────────────────────────────────────────────────────────────
# CoNLL-U constants
# ─────────────────────────────────────────────────────────────────────────────

_CONLLU_EMPTY = "_"
_GGT_VERSION  = "2.0.0"  # bumped for v2 morphological_analyzer

# Sentence boundary punctuation (used when no blank lines found)
_SENT_PUNCT_RE = re.compile(r"(?<=[.!?።。])\s+")

# Blank-line paragraph split
_BLANK_LINE_RE = re.compile(r"\n\s*\n")

# CoNLL-U MISC value: characters that must be escaped
_MISC_UNSAFE_RE = re.compile(r"[|\s]")


# ─────────────────────────────────────────────────────────────────────────────
# Frozen output types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AnnotatedToken:
    """
    One CoNLL-U token row with full GGT annotation.

    Parameters
    ----------
    conllu_id : int
        1-based token index within its sentence.
    form : str
        Original surface form from the input text.
    lemma : str
        Root morpheme form, or the surface form if no root was found.
    upos : str
        Universal POS tag (``"VERB"``, ``"NOUN"``, or ``"X"``).
    xpos : str
        Language-specific POS tag: ``"{language}-{upos}"``.
    feats : str
        CoNLL-U FEATS string (alphabetically sorted key=value pairs
        separated by ``|``), or ``"_"`` if empty.
    head : str
        Always ``"_"`` (syntax unavailable).
    deprel : str
        Always ``"_"`` (syntax unavailable).
    deps : str
        Always ``"_"`` (syntax unavailable).
    misc : str
        Composite field: ``Gloss=…|Segment=…`` and optionally
        ``|Ambiguous=Yes``, ``|Underlying=…``, ``|PhonRules=N``, or
        ``|AnnotationFailed=<ClassName>``.
    segmented_token : SegmentedToken
        The full parse output from ``MorphologicalAnalyzer``.
    ud_bundle : UDFeatureBundle
        The full UD feature bundle from ``UDFeatureMapper``.
    is_ambiguous : bool
        ``True`` when the token has more than one parse hypothesis.
    warnings : Tuple[str, ...]
        All warnings collected during annotation of this token.
    """

    conllu_id: int
    form: str
    lemma: str
    upos: str
    xpos: str
    feats: str
    head: str
    deprel: str
    deps: str
    misc: str
    segmented_token: SegmentedToken
    ud_bundle: UDFeatureBundle
    is_ambiguous: bool
    warnings: Tuple[str, ...]
    # v2: phonology provenance fields (default-safe for backward compat)
    underlying: str = ""
    rule_trace: Tuple[str, ...] = ()

    def to_conllu_row(self) -> str:
        """Return the 10-column tab-separated CoNLL-U row for this token."""
        return "\t".join([
            str(self.conllu_id),
            self.form,
            self.lemma,
            self.upos,
            self.xpos,
            self.feats,
            self.head,
            self.deprel,
            self.deps,
            self.misc,
        ])


@dataclass(frozen=True)
class AnnotatedSentence:
    """
    One CoNLL-U sentence block.

    Parameters
    ----------
    sent_id : str
        Sentence identifier written into the ``# sent_id`` comment.
    text : str
        The original sentence string.
    tokens : Tuple[AnnotatedToken, ...]
        All annotated tokens in sentence order.
    language : str
        Language identifier from the loader.
    """

    sent_id: str
    text: str
    tokens: Tuple[AnnotatedToken, ...]
    language: str

    def to_conllu_block(self, loader_version: str = _GGT_VERSION) -> str:
        """
        Render this sentence as a complete CoNLL-U block (comments +
        token rows + trailing blank line).

        Parameters
        ----------
        loader_version : str
            Written into the ``# ggt_annotated`` comment header.

        Returns
        -------
        str
        """
        lines: List[str] = [
            f"# sent_id = {self.sent_id}",
            f"# text = {self.text}",
            f"# language = {self.language}",
            f"# ggt_annotated = {loader_version}",
        ]
        for tok in self.tokens:
            lines.append(tok.to_conllu_row())
        lines.append("")  # trailing blank line
        return "\n".join(lines)


@dataclass(frozen=True)
class AnnotationResult:
    """
    Full annotation result for a corpus string or file.

    Parameters
    ----------
    language : str
        Language identifier from the loader.
    total_sentences : int
        Number of sentences annotated.
    total_tokens : int
        Total number of token rows produced.
    ambiguous_tokens : int
        Number of tokens with ``is_ambiguous=True``.
    failed_tokens : int
        Number of tokens where annotation failed
        (``MorphAnalysisError`` or ``UDMappingError``).
    sentences : Tuple[AnnotatedSentence, ...]
        All annotated sentences in order.
    """

    language: str
    total_sentences: int
    total_tokens: int
    ambiguous_tokens: int
    failed_tokens: int
    sentences: Tuple[AnnotatedSentence, ...]

    def summary(self) -> str:
        """
        One-line human-readable summary.

        Example
        -------
        ``"chitonga: 3 sentences, 12 tokens, 2 ambiguous, 0 failed"``
        """
        return (
            f"{self.language}: "
            f"{self.total_sentences} sentence{'s' if self.total_sentences != 1 else ''}, "
            f"{self.total_tokens} token{'s' if self.total_tokens != 1 else ''}, "
            f"{self.ambiguous_tokens} ambiguous, "
            f"{self.failed_tokens} failed"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CorpusAnnotator
# ─────────────────────────────────────────────────────────────────────────────


class CorpusAnnotator:
    """
    Corpus annotation pipeline: plain text → CoNLL-U.

    Parameters
    ----------
    loader : GobeloGrammarLoader
        An initialised loader for the target language.
        ``MorphologicalAnalyzer`` and ``UDFeatureMapper`` are built
        internally from this loader.

    Raises
    ------
    CorpusAnnotationError
        If the loader raises ``GGTError`` during init.

    Examples
    --------
    >>> from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    >>> from gobelo_grammar_toolkit.apps.corpus_annotator import CorpusAnnotator
    >>> loader    = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    >>> annotator = CorpusAnnotator(loader)
    >>> result    = annotator.annotate_text("balya cilya.")
    >>> print(annotator.to_conllu(result))
    """

    def __init__(self, loader) -> None:  # type: ignore[no-untyped-def]
        try:
            self._loader = loader
            meta = loader.get_metadata()
            self._language: str = meta.language
            self._loader_version: str = str(loader.loader_version)
            self._analyzer = MorphologicalAnalyzer(loader)
            self._ud_mapper = UDFeatureMapper(loader)
        except GGTError as exc:
            raise CorpusAnnotationError(
                f"CorpusAnnotator init failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def annotate_text(
        self,
        text: str,
        sent_id_prefix: str = "sent",
        max_hypotheses: int = 1,
    ) -> AnnotationResult:
        """
        Annotate a plain-text string.

        Sentence segmentation uses blank-line splitting as the primary
        strategy.  If no blank lines are found, the text is split on
        sentence-final punctuation (``. ! ? ። 。``).

        Parameters
        ----------
        text : str
            Plain text to annotate.  May contain multiple sentences.
        sent_id_prefix : str
            Prefix for ``# sent_id`` comments.  Sentences are numbered
            ``{prefix}_0001``, ``{prefix}_0002``, …
        max_hypotheses : int
            Passed to ``MorphologicalAnalyzer.segment_text()``.
            Default ``1`` selects only the best hypothesis per token,
            which also sets ``is_ambiguous=False`` for all tokens.

        Returns
        -------
        AnnotationResult

        Raises
        ------
        CorpusAnnotationError
            If ``text`` is not a string.
        """
        if not isinstance(text, str):
            raise CorpusAnnotationError(
                f"annotate_text expects a str; got {type(text).__name__!r}."
            )

        sentence_strings = _segment_sentences(text)
        return self._annotate_sentences(
            sentence_strings, sent_id_prefix, max_hypotheses
        )

    def annotate_file(
        self,
        path: Union[str, Path],
        encoding: str = "utf-8",
        sent_id_prefix: str = "sent",
        max_hypotheses: int = 1,
    ) -> AnnotationResult:
        """
        Annotate a plain-text file.

        The file is read in full before annotation begins.

        Parameters
        ----------
        path : str | Path
            Path to the input file.
        encoding : str
            File encoding (default ``"utf-8"``).
        sent_id_prefix : str
            Prefix for ``# sent_id`` comments.
        max_hypotheses : int
            Passed to ``MorphologicalAnalyzer.segment_text()``.

        Returns
        -------
        AnnotationResult

        Raises
        ------
        CorpusAnnotationError
            If the file cannot be read.
        """
        try:
            text = Path(path).read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError) as exc:
            raise CorpusAnnotationError(
                f"Cannot read file {path!r}: {exc}"
            ) from exc

        return self.annotate_text(
            text,
            sent_id_prefix=sent_id_prefix,
            max_hypotheses=max_hypotheses,
        )

    def to_conllu(self, result: AnnotationResult) -> str:
        """
        Serialise an :class:`AnnotationResult` to a CoNLL-U string.

        The output begins with a file-level comment block followed by
        one sentence block per sentence.

        Parameters
        ----------
        result : AnnotationResult

        Returns
        -------
        str
            Valid CoNLL-U text (UTF-8 compatible).
        """
        blocks: List[str] = [
            f"# global.columns = ID FORM LEMMA UPOS XPOS FEATS HEAD DEPREL DEPS MISC",
            f"# language = {result.language}",
            f"# ggt_annotated = {self._loader_version}",
            f"# total_sentences = {result.total_sentences}",
            f"# total_tokens = {result.total_tokens}",
            f"# ambiguous_tokens = {result.ambiguous_tokens}",
            f"# failed_tokens = {result.failed_tokens}",
            "",
        ]
        for sent in result.sentences:
            blocks.append(sent.to_conllu_block(self._loader_version))

        return "\n".join(blocks)

    def write_conllu(
        self,
        result: AnnotationResult,
        path: Union[str, Path],
        encoding: str = "utf-8",
    ) -> None:
        """
        Write an :class:`AnnotationResult` to a CoNLL-U file.

        Parameters
        ----------
        result : AnnotationResult
        path : str | Path
            Output file path.  Parent directories must exist.
        encoding : str
            File encoding (default ``"utf-8"``).

        Raises
        ------
        CorpusAnnotationError
            If the file cannot be written.
        """
        conllu = self.to_conllu(result)
        try:
            Path(path).write_text(conllu, encoding=encoding)
        except OSError as exc:
            raise CorpusAnnotationError(
                f"Cannot write CoNLL-U file {path!r}: {exc}"
            ) from exc

    @property
    def language(self) -> str:
        """Language identifier from the grammar loader."""
        return self._language

    @property
    def loader(self):  # type: ignore[return]
        """The ``GobeloGrammarLoader`` used by this annotator."""
        return self._loader

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _annotate_sentences(
        self,
        sentence_strings: List[str],
        sent_id_prefix: str,
        max_hypotheses: int,
    ) -> AnnotationResult:
        """Run the full annotation pipeline on a list of sentence strings."""
        annotated_sentences: List[AnnotatedSentence] = []
        total_tokens = 0
        ambiguous_tokens = 0
        failed_tokens = 0

        for i, sent_text in enumerate(sentence_strings, start=1):
            sent_id = f"{sent_id_prefix}_{i:04d}"
            sent_tokens, n_amb, n_fail = self._annotate_sentence(
                sent_text, max_hypotheses
            )
            annotated_sentences.append(
                AnnotatedSentence(
                    sent_id=sent_id,
                    text=sent_text,
                    tokens=tuple(sent_tokens),
                    language=self._language,
                )
            )
            total_tokens += len(sent_tokens)
            ambiguous_tokens += n_amb
            failed_tokens += n_fail

        return AnnotationResult(
            language=self._language,
            total_sentences=len(annotated_sentences),
            total_tokens=total_tokens,
            ambiguous_tokens=ambiguous_tokens,
            failed_tokens=failed_tokens,
            sentences=tuple(annotated_sentences),
        )

    def _annotate_sentence(
        self,
        sent_text: str,
        max_hypotheses: int,
    ) -> Tuple[List[AnnotatedToken], int, int]:
        """
        Annotate one sentence string.

        Returns
        -------
        (tokens, n_ambiguous, n_failed)
        """
        # segment_text does tokenisation + analysis in one call
        try:
            seg_tokens = self._analyzer.segment_text(
                sent_text, max_hypotheses=max_hypotheses
            )
        except MorphAnalysisError as exc:
            # If the entire segment_text call fails, create one failed token
            # covering the whole sentence text
            failed_tok = _make_failed_token(
                conllu_id=1,
                form=sent_text,
                error_class=type(exc).__name__,
                language=self._language,
                seg_tok=None,
                ud_bundle=None,
            )
            return [failed_tok], 0, 1

        tokens: List[AnnotatedToken] = []
        n_ambiguous = 0
        n_failed = 0

        for conllu_id, seg_tok in enumerate(seg_tokens, start=1):
            tok, failed, ambiguous = self._annotate_token(conllu_id, seg_tok)
            tokens.append(tok)
            if failed:
                n_failed += 1
            if ambiguous:
                n_ambiguous += 1

        return tokens, n_ambiguous, n_failed

    def _annotate_token(
        self,
        conllu_id: int,
        seg_tok: SegmentedToken,
    ) -> Tuple[AnnotatedToken, bool, bool]:
        """
        Annotate a single ``SegmentedToken``.

        Returns
        -------
        (AnnotatedToken, is_failed, is_ambiguous)
        """
        form = seg_tok.token
        all_warnings: List[str] = []

        # ── UD feature mapping ────────────────────────────────────────
        ud_bundle: Optional[UDFeatureBundle] = None
        feats_str = _CONLLU_EMPTY
        ud_failed = False
        try:
            ud_bundle = self._ud_mapper.map_segmented_token(seg_tok)
            feats_str = self._ud_mapper.to_conllu_feats(ud_bundle)
            all_warnings.extend(ud_bundle.warnings)
        except (UDMappingError, GGTError) as exc:
            ud_failed = True
            all_warnings.append(f"{type(exc).__name__}: {exc}")

        # ── CoNLL-U column derivation ─────────────────────────────────
        best = seg_tok.best
        is_failed = best is None or ud_failed

        if is_failed:
            # Fall back to a failed-token row
            err_class = "MorphAnalysisError" if best is None else "UDMappingError"
            tok = _make_failed_token(
                conllu_id=conllu_id,
                form=form,
                error_class=err_class,
                language=self._language,
                seg_tok=seg_tok,
                ud_bundle=ud_bundle,
            )
            return tok, True, False

        # ── Derive LEMMA, UPOS from best hypothesis ────────────────────
        root_morphemes = [
            m for m in best.morphemes if m.content_type == "verb_root"
        ]
        nc_morphemes = [
            m for m in best.morphemes if m.nc_id is not None
        ]

        lemma = root_morphemes[0].form if root_morphemes else form

        if root_morphemes:
            upos = "VERB"
        elif nc_morphemes and not root_morphemes:
            upos = "NOUN"
        else:
            upos = "X"

        xpos = f"{self._language}-{upos}"

        # ── MISC ──────────────────────────────────────────────────────
        is_ambiguous = seg_tok.is_ambiguous
        # v2: extract phonology provenance from ParseHypothesis
        phon_underlying: str = getattr(best, "underlying", "")
        phon_rule_trace: Tuple[str, ...] = getattr(best, "rule_trace", ())
        misc = _build_misc(
            gloss_line=best.gloss_line,
            segmented=best.segmented,
            is_ambiguous=is_ambiguous,
            failed=False,
            underlying=phon_underlying,
            rule_trace=phon_rule_trace,
        )

        # Collect warnings from seg_tok best hypothesis
        all_warnings.extend(best.warnings)

        tok = AnnotatedToken(
            conllu_id=conllu_id,
            form=form,
            lemma=lemma,
            upos=upos,
            xpos=xpos,
            feats=feats_str,
            head=_CONLLU_EMPTY,
            deprel=_CONLLU_EMPTY,
            deps=_CONLLU_EMPTY,
            misc=misc,
            segmented_token=seg_tok,
            ud_bundle=ud_bundle,
            is_ambiguous=is_ambiguous,
            warnings=tuple(all_warnings),
            underlying=phon_underlying,
            rule_trace=phon_rule_trace,
        )
        return tok, False, is_ambiguous


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────


def _segment_sentences(text: str) -> List[str]:
    """
    Split a corpus string into sentence strings.

    Strategy
    --------
    1. Try blank-line splitting (``\\n\\n`` or ``\\n   \\n``).
    2. If that produces only one non-empty segment, fall back to
       punctuation splitting on ``. ! ? ። 。``.
    3. Empty strings are removed.
    """
    text = text.strip()
    if not text:
        return []

    # Pass 1: blank-line split
    candidates = _BLANK_LINE_RE.split(text)
    non_empty = [c.strip() for c in candidates if c.strip()]
    if len(non_empty) > 1:
        return non_empty

    # Pass 2: punctuation split
    candidates = _SENT_PUNCT_RE.split(text)
    non_empty = [c.strip() for c in candidates if c.strip()]
    return non_empty if non_empty else [text]


def _escape_misc_value(value: str) -> str:
    """
    Escape a MISC field value for CoNLL-U compliance.

    CoNLL-U MISC values must not contain literal ``|`` (used as
    key-value pair separator) or whitespace (the field is
    whitespace-terminated in the 10-column format).

    We replace ``|`` with ``\\|`` and spaces with ``_``.
    """
    return value.replace("|", "\\|").replace(" ", "_").replace("\t", "_")


def _build_misc(
    gloss_line: str,
    segmented: str,
    is_ambiguous: bool,
    failed: bool,
    error_class: str = "",
    underlying: str = "",
    rule_trace: Tuple[str, ...] = (),
) -> str:
    """
    Construct the CoNLL-U MISC field.

    For normal tokens:
        ``Gloss=…|Segment=…[|Ambiguous=Yes][|Underlying=…][|PhonRules=N]``
    For failed tokens:
        ``AnnotationFailed=<ClassName>``

    ``Underlying`` is omitted when it is identical to the surface or empty.
    ``PhonRules`` records the count of phonological rules that fired (v2).
    """
    if failed:
        cls = error_class or "UnknownError"
        return f"AnnotationFailed={cls}"

    parts = [
        f"Gloss={_escape_misc_value(gloss_line)}",
        f"Segment={_escape_misc_value(segmented)}",
    ]
    if is_ambiguous:
        parts.append("Ambiguous=Yes")
    # v2: phonology provenance
    if underlying and underlying != segmented.replace("-", ""):
        parts.append(f"Underlying={_escape_misc_value(underlying)}")
    if rule_trace:
        parts.append(f"PhonRules={len(rule_trace)}")
    return "|".join(parts)


def _make_failed_token(
    conllu_id: int,
    form: str,
    error_class: str,
    language: str,
    seg_tok: Optional[SegmentedToken],
    ud_bundle: Optional[UDFeatureBundle],
) -> AnnotatedToken:
    """
    Construct an ``AnnotatedToken`` for a token whose annotation failed.

    Uses ``LEMMA=_``, ``UPOS=X``, ``FEATS=_``, and
    ``MISC=AnnotationFailed=<ClassName>``.
    """
    # Build a minimal SegmentedToken stub if none provided
    if seg_tok is None:
        from gobelo_grammar_toolkit.apps.morphological_analyzer import SegmentedToken as ST
        # We can't construct a SegmentedToken easily without an analyzer,
        # so we use a sentinel object with duck-typing
        class _FakeST:
            token = form
            language = language
            hypotheses: tuple = ()
            best = None
            is_ambiguous = False
        seg_tok_to_use: SegmentedToken = _FakeST()  # type: ignore[assignment]
    else:
        seg_tok_to_use = seg_tok

    # Build a minimal UDFeatureBundle stub
    if ud_bundle is None:
        from gobelo_grammar_toolkit.apps.ud_feature_mapper import UDFeatureBundle as UDB
        ud_bundle_to_use = UDB(
            token=form,
            language=language,
            nounclass=None, number=None, person=None,
            tense=None, aspect=None, mood=None,
            voice=None, polarity=None, gender=None,
            source_nc_id=None, source_tam_id=None,
            source_ext_ids=(), warnings=(),
        )
    else:
        ud_bundle_to_use = ud_bundle

    return AnnotatedToken(
        conllu_id=conllu_id,
        form=form,
        lemma=_CONLLU_EMPTY,
        upos="X",
        xpos=f"{language}-X",
        feats=_CONLLU_EMPTY,
        head=_CONLLU_EMPTY,
        deprel=_CONLLU_EMPTY,
        deps=_CONLLU_EMPTY,
        misc=_build_misc("", "", False, True, error_class),
        segmented_token=seg_tok_to_use,  # type: ignore[arg-type]
        ud_bundle=ud_bundle_to_use,
        is_ambiguous=False,
        warnings=(f"Annotation failed: {error_class}",),
    )
