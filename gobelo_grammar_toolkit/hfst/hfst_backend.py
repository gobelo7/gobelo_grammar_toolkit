"""
hfst/hfst_backend.py
====================
Adapter layer between raw ``hfst-lookup`` output and the GGT public API.

Architecture
------------
``hfst-lookup`` returns tag strings like::

    balya   ba+SM2@P.NC.2@@P.NUM.PL@+PRES+ly+V+a+FV_IND   0.0

The tag vocabulary is defined in ``hfst_config.yaml`` and written into
``chitonga.lexc`` during the FST build.  The GGT mapper layer
(``UDFeatureMapper``) expects a different vocabulary — ``TAMMarker`` ids
(``"TAM_PRES"``), concord keys (``"NC2"``, ``"1SG"``), and extension ids
(``"APPL"``).

This module bridges that gap in ``parse_tag()``, which translates one raw
hfst-lookup lexical form into a list of ``ParsedTag`` objects whose
``mapped_id`` values can be passed directly to::

    mapper.map_tam(mapped_id)
    mapper.map_concord_key(mapped_id, concord_type)
    mapper.map_nc(mapped_id)
    mapper.map_extension(mapped_id)

The Mismatch Inventory
----------------------
Three categories of mismatch exist between the FST tag vocabulary and the
mapper vocabulary.  All three are resolved by the translation tables in this
module.

**1. TAM prefix**
  FST emits bare TAM labels (``+PRES``, ``+REM_PST``).
  ``map_tam()`` expects the ``TAM_`` prefix (``"TAM_PRES"``, ``"TAM_REM_PST"``).
  Fix: ``_FST_TO_TAM_ID`` prepends ``"TAM_"`` for every TAM tag.

**2. Subject/object marker format**
  FST encodes subject agreement in two sub-families:

  * *Personal* — ``+SM1SG``, ``+SM2SG``, ``+SM1PL``, ``+SM1PL_IN``,
    ``+SM2PL`` for 1st/2nd person.
  * *NC-numbered* — ``+SM1`` … ``+SM18`` (and ``+SM1a``, ``+SM2a``,
    ``+SM2b``) for noun-class 3rd-person agreement.

  ``map_concord_key()`` expects the concord key format used in the grammar
  YAML: ``"1SG"``, ``"2PL"``, ``"NC7"``, ``"NC1a"``.

  Fix:
  * ``_FST_SM_PERSONAL`` maps personal SM tags by name.
  * ``_SM_NC_RE`` regex maps ``SM<N>`` → ``NC<N>`` (and ``SM1a`` → ``NC1a``).
  * ``_FST_OM_PERSONAL`` and ``_OM_NC_RE`` apply the same logic for OM tags.

**3. Everything else passes through unchanged**
  NC prefix tags (``+NC7``), extension tags (``+APPL``, ``+PASS``), and
  POS tags (``+V``, ``+N``) already match what the mapper expects after
  stripping the ``+`` delimiter.  No translation needed.

Flag diacritics (``@P.NC.2@``, ``@R.NEG.ON@``) are stripped silently — they
carry agreement enforcement state for the FST but carry no information needed
by the mapper.

Usage
-----
::

    from gobelo_grammar_toolkit.hfst.hfst_backend import parse_tag, HFSTBackend

    # Direct tag parsing
    tags = parse_tag("ba+SM2@P.NC.2@+PRES+ly+V+a+FV_IND")
    for t in tags:
        if t.content_type == "tam":
            feats = mapper.map_tam(t.mapped_id)
        elif t.content_type == "subject_concord":
            feats = mapper.map_concord_key(t.mapped_id, t.concord_type)

    # Full analyser (requires compiled hfst binary)
    backend = HFSTBackend(analyser_path="build/chitonga-analyser.hfst")
    results = backend.analyse("balya")
    for r in results:
        print(r.surface, r.tags, r.weight)
"""

from __future__ import annotations

import re
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional

__all__ = [
    "parse_tag",
    "ParsedTag",
    "AnalysisResult",
    "HFSTBackend",
]


# ===========================================================================
# TAG TRANSLATION TABLES
# Source:  hfst_config.yaml  multichar_symbols + flag_diacritics
# Target:  ud_feature_mapper.py  map_tam() / map_concord_key() / map_extension()
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. TAM  —  FST emits +PRES, mapper wants "TAM_PRES"
# ---------------------------------------------------------------------------

_FST_TO_TAM_ID: Dict[str, str] = {
    # present and habitual
    "PRES":     "TAM_PRES",    # form: a    tone: L
    "HAB":      "TAM_HAB",     # form: la

    # past
    "PST":      "TAM_PST",     # form: aka  tone: L-L   (ambiguous with REM_PST)
    "REC_PST":  "TAM_REC_PST", # form: ali  tone: L-L
    "REM_PST":  "TAM_REM_PST", # form: aka  tone: H-L   (ambiguous with PST)

    # future
    "FUT_NEAR": "TAM_FUT_NEAR", # form: yo
    "FUT_REM":  "TAM_FUT_REM",  # form: za

    # aspect
    "PERF":     "TAM_PERF",    # form: a  + FV_PERF (-ide) disambiguates from PRES
    "PROG":     "TAM_PROG",    # form: la-/ci-

    # mood-only (zero tense, zero aspect — only mood tag present)
    "SUBJ":     "TAM_SUBJ",    # zero TAM + FV_SUBJ (-e)
    "IMP_SG":   "TAM_IMP_SG",  # imperative singular
    "IMP_PL":   "TAM_IMP_PL",  # imperative plural
    "COND":     "TAM_COND",    # form: nga
    "POT":      "TAM_POT",     # form: nga  (same surface as COND)
}

# ---------------------------------------------------------------------------
# 2. Subject markers — personal pronouns
#    FST emits +SM1SG, mapper wants "1SG"
# ---------------------------------------------------------------------------

_FST_SM_PERSONAL: Dict[str, str] = {
    "SM1SG":    "1SG",      # ndi-
    "SM2SG":    "2SG",      # u-/w-
    "SM1PL":    "1PL",      # tu-/tw-  (exclusive)
    "SM1PL_IN": "1PL_INCL", # tw-      (inclusive)
    "SM2PL":    "2PL",      # mu-/mw-
}

# NC-numbered SM pattern: SM<digits><optional letter>  →  NC<digits><letter>
# Handles: SM1→NC1, SM7→NC7, SM10→NC10, SM1a→NC1a, SM2a→NC2a, SM2b→NC2b
_SM_NC_RE = re.compile(r"^SM(\d+[a-z]?)$")

# ---------------------------------------------------------------------------
# 3. Object markers — personal pronouns
#    FST emits +OM1SG, mapper wants "1SG"
# ---------------------------------------------------------------------------

_FST_OM_PERSONAL: Dict[str, str] = {
    "OM1SG": "1SG",
    "OM2SG": "2SG",
    "OM1PL": "1PL",
    "OM2PL": "2PL",
}

# NC-numbered OM pattern: OM<digits>  →  NC<digits>
# (OM subclasses like OM1a do not exist in hfst_config — OM always uses base NC)
_OM_NC_RE = re.compile(r"^OM(\d+)$")

# ---------------------------------------------------------------------------
# Classification sets for tags that pass through unchanged
# ---------------------------------------------------------------------------

# Final-vowel tags — classified as content_type="final_vowel", no mapper call
_FV_TAGS: FrozenSet[str] = frozenset({
    "FV_IND",    # -a   indicative / active
    "FV_SUBJ",   # -e   subjunctive (requires @R.MOOD.SUBJ@)
    "FV_NEG",    # -i   negative (requires @R.NEG.ON@)
    "FV_PERF",   # -ide perfective / perfect
    "FV_IMP_SG", # -a   imperative singular
    "FV_IMP_PL", # -eni imperative plural
    "FV_INF",    # -a   infinitive (NC15 nouns)
})

# Post-final clitic tags
_POST_TAGS: FrozenSet[str] = frozenset({
    "REL",        # -yo/-o  relative clause marker
    "Q",          # -na/-nzi question
    "EMP",        # -ko     emphatic
    "NEG_POST",   # -pe     negation reinforcement
    "LOC_CLITIC", # -mo     locative (in/at)
})

# Verb extension tags — pass to mapper.map_extension() unchanged
# (extension ids already match between FST and mapper)
_EXTENSION_TAGS: FrozenSet[str] = frozenset({
    # Zone Z1 — valency increasing
    "APPL",     # applicative    -il-/-el-
    "CAUS",     # causative      -is-/-y-
    "TRANS",    # transitiviser  -ol-/-ok-
    "CONT",     # contactive     -at-
    # Zone Z2 — valency adjusting
    "RECIP",    # reciprocal     -an-
    "STAT",     # stative        -ik-/-ek-
    # Zone Z3 — voice
    "PASS",     # passive        -w-/-iw-/-ew-
    # Zone Z4 — aspectual / lexical
    "INTENS",   # intensive      -isy-
    "REDUP",    # reduplicative
    "PERF_EXT", # perfective ext -ilil-/-elel-
    "REV",      # reversive      -ul-/-ol-
    "REPET",    # repetitive     -ulul-
    "FREQ",     # frequentative  -aul-
    "POS",      # positional     -am-
})

# POS tags — classified, no mapper call
_POS_TAGS: FrozenSet[str] = frozenset({
    "V", "N", "ADJ", "ADV", "CONJ", "PREP",
    "PRON", "DEM", "INTERJ", "LOC", "AUX",
})

# Noun class prefix tag pattern: NC<digits><optional letter>
# (already in the correct form for mapper.map_nc())
_NC_TAG_RE = re.compile(r"^NC\d+[a-z]?$")

# Flag diacritic pattern — stripped before any other processing
_FLAG_RE = re.compile(r"@[PDR]\.[A-Z_]+\.[^@]+@")


# ===========================================================================
# ParsedTag dataclass
# ===========================================================================


@dataclass
class ParsedTag:
    """
    One classified tag from an hfst-lookup analysis string.

    Parameters
    ----------
    raw : str
        The token as it appeared in the lexical string (``+`` stripped).
    content_type : str
        Mapper-compatible content-type label.  Values:

        ``"tam"``
            A TAM marker.  Pass ``mapped_id`` to ``mapper.map_tam()``.
        ``"subject_concord"``
            A subject marker.  Pass ``mapped_id`` and ``concord_type``
            to ``mapper.map_concord_key()``.  ``nc_id`` is set when the
            SM is NC-indexed.
        ``"object_concord"``
            An object marker.  Same API as ``subject_concord``.
        ``"noun_prefix"``
            A noun class prefix on a nominal token.  Pass ``mapped_id``
            (= ``nc_id``) to ``mapper.map_nc()``.
        ``"verb_extension"``
            A derivational extension.  Pass ``mapped_id`` to
            ``mapper.map_extension()``.
        ``"final_vowel"``
            A final-vowel tag.  Not passed to any mapper method; used
            for TAM disambiguation (e.g. ``FV_PERF`` signals
            ``TAM_PERF`` vs ``TAM_PRES`` when both have surface ``a``).
        ``"pos"``
            A POS tag (``V``, ``N``, etc.).
        ``"negation"``
            A negation marker.  Set ``Polarity=Neg`` in the bundle.
        ``"number"``
            A bare number tag on a noun (``SG``, ``PL``).
        ``"post_final"``
            A post-final clitic tag.
        ``"surface"``
            A surface phoneme segment (not a morphological tag).
        ``"unknown"``
            An unrecognised token.  Log and skip.

    mapped_id : str
        The identifier to pass to the relevant mapper method.  For TAM
        this is ``"TAM_PRES"`` etc.; for concords it is ``"1SG"`` or
        ``"NC7"``; for extensions it is ``"APPL"`` etc.
    concord_type : Optional[str]
        ``"subject_concords"`` or ``"object_concords"``.  Only set for
        ``content_type`` in ``("subject_concord", "object_concord")``.
    nc_id : Optional[str]
        The NC identifier (``"NC7"``) when this tag carries NC
        information — set for NC-numbered SM/OM and for noun prefix tags.
    """

    raw: str
    content_type: str
    mapped_id: str
    concord_type: Optional[str] = None
    nc_id: Optional[str] = None


# ===========================================================================
# parse_tag
# ===========================================================================


def parse_tag(analysis_string: str) -> List[ParsedTag]:
    """
    Translate one hfst-lookup lexical form into ``ParsedTag`` objects
    compatible with ``UDFeatureMapper``.

    This is the central translation function.  It handles every mismatch
    between the FST tag vocabulary (``hfst_config.yaml``) and the mapper
    vocabulary (``ud_feature_mapper.py``):

    * **TAM prefix** — ``+PRES`` → ``"TAM_PRES"``
    * **SM/OM format** — ``+SM7`` → ``"NC7"``, ``+SM1SG`` → ``"1SG"``
    * **Flag diacritics** — ``@P.NC.2@`` stripped silently
    * **Everything else** — NC, extension, POS tags pass through after
      ``+`` stripping

    Parameters
    ----------
    analysis_string : str
        The *lexical* (tag-annotated) field from one ``hfst-lookup``
        output line.  Both raw lines and pre-split analysis fields are
        accepted:

        * Raw line:      ``"balya\\tba+SM2+PRES+ly+V+a+FV_IND\\t0.0"``
        * Analysis field: ``"ba+SM2@P.NC.2@+PRES+ly+V+a+FV_IND"``

    Returns
    -------
    List[ParsedTag]
        One entry per meaningful token.  Surface phonemes produce
        ``content_type="surface"``; flag diacritics are silently
        discarded.

    Raises
    ------
    Nothing — unrecognised tokens produce ``content_type="unknown"``
    entries so callers can log them without crashing.

    Examples
    --------
    Verb: ``balya`` "they eat" (NC2 present)

    >>> tags = parse_tag("ba+SM2+PRES+ly+V+a+FV_IND")
    >>> [(t.content_type, t.mapped_id) for t in tags if t.content_type != "surface"]
    [('subject_concord', 'NC2'), ('tam', 'TAM_PRES'), ('pos', 'V'), ('final_vowel', 'FV_IND')]

    Verb with applicative extension:

    >>> tags = parse_tag("ba+SM2+PRES+ly+V+il+APPL+a+FV_IND")
    >>> [(t.content_type, t.mapped_id) for t in tags if t.content_type != "surface"]
    [('subject_concord', 'NC2'), ('tam', 'TAM_PRES'), ('pos', 'V'),
     ('verb_extension', 'APPL'), ('final_vowel', 'FV_IND')]

    Negative: ``tabalyi`` "they do not eat"

    >>> tags = parse_tag("ta+NEG+ba+SM2+PRES+ly+V+i+FV_NEG")
    >>> [(t.content_type, t.mapped_id) for t in tags if t.content_type != "surface"]
    [('negation', 'NEG'), ('subject_concord', 'NC2'), ('tam', 'TAM_PRES'),
     ('pos', 'V'), ('final_vowel', 'FV_NEG')]

    Noun: ``cintu`` "thing" (NC7)

    >>> tags = parse_tag("ci+NC7+SG+ntu+N")
    >>> [(t.content_type, t.mapped_id) for t in tags if t.content_type != "surface"]
    [('noun_prefix', 'NC7'), ('number', 'SG'), ('pos', 'N')]

    Object marker + NC flag diacritics:

    >>> tags = parse_tag("ba+SM2@P.NC.2@+ci+OM7@R.NC.7@+FUT_NEAR+lya+V+a+FV_IND")
    >>> [(t.content_type, t.mapped_id) for t in tags if t.content_type != "surface"]
    [('subject_concord', 'NC2'), ('object_concord', 'NC7'),
     ('tam', 'TAM_FUT_NEAR'), ('pos', 'V'), ('final_vowel', 'FV_IND')]
    """
    # ── Step 1: normalise input ──────────────────────────────────────────
    text = analysis_string.strip()

    # Handle raw hfst-lookup line: "word TAB analysis TAB weight"
    if "\t" in text:
        parts = text.split("\t")
        text = parts[1].strip() if len(parts) >= 2 else parts[0].strip()

    # Strip trailing weight column: " 0.0", " +inf", " -inf"
    text = re.sub(r"\s+[-+]?[\d.]+(?:e[-+]?\d+)?\s*$", "", text).strip()
    text = re.sub(r"\s+[-+]?inf\s*$", "", text, flags=re.IGNORECASE).strip()

    # ── Step 2: strip flag diacritics (@P.NC.2@, @R.NEG.ON@, etc.) ─────
    text = _FLAG_RE.sub("", text)

    # ── Step 3: split on + ──────────────────────────────────────────────
    tokens = text.split("+")
    if tokens and tokens[0] == "":
        tokens = tokens[1:]

    result: List[ParsedTag] = []

    for token in tokens:
        token = token.strip()
        if not token:
            continue

        # ── TAM (mismatch 1: prepend TAM_) ──────────────────────────────
        if token in _FST_TO_TAM_ID:
            result.append(ParsedTag(
                raw=token,
                content_type="tam",
                mapped_id=_FST_TO_TAM_ID[token],
            ))
            continue

        # ── Subject marker — personal (mismatch 2a) ─────────────────────
        if token in _FST_SM_PERSONAL:
            result.append(ParsedTag(
                raw=token,
                content_type="subject_concord",
                mapped_id=_FST_SM_PERSONAL[token],
                concord_type="subject_concords",
                nc_id=None,
            ))
            continue

        # ── Subject marker — NC-numbered (mismatch 2b) ──────────────────
        m = _SM_NC_RE.match(token)
        if m:
            nc_key = "NC" + m.group(1)
            result.append(ParsedTag(
                raw=token,
                content_type="subject_concord",
                mapped_id=nc_key,
                concord_type="subject_concords",
                nc_id=nc_key,
            ))
            continue

        # ── Object marker — personal (mismatch 3a) ──────────────────────
        if token in _FST_OM_PERSONAL:
            result.append(ParsedTag(
                raw=token,
                content_type="object_concord",
                mapped_id=_FST_OM_PERSONAL[token],
                concord_type="object_concords",
                nc_id=None,
            ))
            continue

        # ── Object marker — NC-numbered (mismatch 3b) ───────────────────
        m = _OM_NC_RE.match(token)
        if m:
            nc_key = "NC" + m.group(1)
            result.append(ParsedTag(
                raw=token,
                content_type="object_concord",
                mapped_id=nc_key,
                concord_type="object_concords",
                nc_id=nc_key,
            ))
            continue

        # ── Noun class prefix tag (nominal path) — pass through ─────────
        if _NC_TAG_RE.match(token):
            result.append(ParsedTag(
                raw=token,
                content_type="noun_prefix",
                mapped_id=token,
                nc_id=token,
            ))
            continue

        # ── Final vowel ──────────────────────────────────────────────────
        if token in _FV_TAGS:
            result.append(ParsedTag(
                raw=token,
                content_type="final_vowel",
                mapped_id=token,
            ))
            continue

        # ── Post-final clitics ───────────────────────────────────────────
        if token in _POST_TAGS:
            result.append(ParsedTag(
                raw=token,
                content_type="post_final",
                mapped_id=token,
            ))
            continue

        # ── Verb extension — pass through unchanged ──────────────────────
        if token in _EXTENSION_TAGS:
            result.append(ParsedTag(
                raw=token,
                content_type="verb_extension",
                mapped_id=token,
            ))
            continue

        # ── POS tag ─────────────────────────────────────────────────────
        if token in _POS_TAGS:
            result.append(ParsedTag(
                raw=token,
                content_type="pos",
                mapped_id=token,
            ))
            continue

        # ── Negation / affirmation ───────────────────────────────────────
        if token == "NEG":
            result.append(ParsedTag(
                raw=token,
                content_type="negation",
                mapped_id=token,
            ))
            continue
        if token == "AFF":
            result.append(ParsedTag(
                raw=token,
                content_type="affirmation",
                mapped_id=token,
            ))
            continue

        # ── Bare number tag on noun ──────────────────────────────────────
        if token in ("SG", "PL"):
            result.append(ParsedTag(
                raw=token,
                content_type="number",
                mapped_id=token,
            ))
            continue

        # ── Surface phoneme ──────────────────────────────────────────────
        if re.match(r"^[a-z']+$", token):
            result.append(ParsedTag(
                raw=token,
                content_type="surface",
                mapped_id=token,
            ))
            continue

        # ── Unknown — never crash, always log ───────────────────────────
        result.append(ParsedTag(
            raw=token,
            content_type="unknown",
            mapped_id=token,
        ))

    return result


# ===========================================================================
# AnalysisResult and HFSTBackend
# ===========================================================================


@dataclass
class AnalysisResult:
    """
    One analysis hypothesis returned by ``hfst-lookup``.

    Parameters
    ----------
    surface : str
        The original surface form that was looked up.
    lexical : str
        The raw lexical string as returned by hfst-lookup (before
        ``parse_tag`` translation).
    tags : List[ParsedTag]
        Parsed and translated tags, ready to feed to ``UDFeatureMapper``.
    weight : float
        The path weight from the FST (lower = more preferred).  ``+inf``
        is used for forms that generated no analysis.
    is_failure : bool
        ``True`` when hfst-lookup returned ``+?`` (form not recognised).
    """

    surface: str
    lexical: str
    tags: List[ParsedTag]
    weight: float = 0.0
    is_failure: bool = False


class HFSTBackend:
    """
    Thin wrapper around the ``hfst-lookup`` command-line tool.

    Calls the external binary as a subprocess.  The analyser binary must
    have been compiled by ``build_fst.py`` before use.

    Parameters
    ----------
    analyser_path : str or Path
        Path to the compiled ``chitonga-analyser.hfst`` (or equivalent
        for another language).
    generator_path : str or Path, optional
        Path to the inverted generator FST.  Used only by ``generate()``.

    Raises
    ------
    FileNotFoundError
        If ``analyser_path`` does not exist.
    RuntimeError
        If ``hfst-lookup`` is not found on ``PATH``.

    Examples
    --------
    ::

        backend = HFSTBackend("build/chitonga-analyser.hfst")
        results = backend.analyse("balya")
        for r in results:
            for tag in r.tags:
                if tag.content_type == "tam":
                    print("TAM:", tag.mapped_id)
    """

    def __init__(
        self,
        analyser_path,
        generator_path=None,
    ) -> None:
        self._analyser = Path(analyser_path)
        self._generator = Path(generator_path) if generator_path else None

        if not self._analyser.exists():
            raise FileNotFoundError(
                f"HFST analyser not found: {self._analyser}\n"
                f"Run build_fst.py to compile the analyser first."
            )
        if not shutil.which("hfst-lookup"):
            raise RuntimeError(
                "hfst-lookup not found on PATH.  "
                "Install HFST:  https://hfst.github.io  or  sudo apt install hfst"
            )

    def analyse(self, surface_form: str) -> List[AnalysisResult]:
        """
        Run ``hfst-lookup`` on ``surface_form`` and return all hypotheses.

        Calls ``parse_tag()`` on each lexical form so the returned
        ``AnalysisResult.tags`` are ready for ``UDFeatureMapper``.

        Parameters
        ----------
        surface_form : str
            A single word token, e.g. ``"balya"``.

        Returns
        -------
        List[AnalysisResult]
            One entry per analysis hypothesis, ordered by weight (best
            first).  An unrecognised form returns a single
            ``AnalysisResult`` with ``is_failure=True``.
        """
        cmd = ["hfst-lookup", str(self._analyser)]
        proc = subprocess.run(
            cmd,
            input=surface_form + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return self._parse_lookup_output(proc.stdout, surface_form)

    def analyse_batch(self, forms: List[str]) -> Dict[str, List[AnalysisResult]]:
        """
        Analyse a list of surface forms in one subprocess call.

        More efficient than repeated ``analyse()`` calls for large inputs.

        Parameters
        ----------
        forms : List[str]
            Surface tokens to analyse.

        Returns
        -------
        Dict[str, List[AnalysisResult]]
            Keyed by surface form.
        """
        input_text = "\n".join(forms) + "\n"
        cmd = ["hfst-lookup", str(self._analyser)]
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        # Group output lines by surface form
        results: Dict[str, List[AnalysisResult]] = {}
        for form in forms:
            results[form] = []
        current_form: Optional[str] = None
        for line in proc.stdout.splitlines():
            if not line.strip():
                current_form = None
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                surf = parts[0].strip()
                if surf in results:
                    current_form = surf
                if current_form:
                    results[current_form].extend(
                        self._parse_lookup_output(line + "\n", current_form)
                    )
        return results

    def generate(self, lexical_form: str) -> List[str]:
        """
        Generate surface forms from a lexical tag string.

        Requires ``generator_path`` to be set at construction time.

        Parameters
        ----------
        lexical_form : str
            Tag-annotated form, e.g. ``"ba+SM2+PRES+lya+V+a+FV_IND"``.

        Returns
        -------
        List[str]
            All surface realisations predicted by the generator FST.
        """
        if self._generator is None or not self._generator.exists():
            raise RuntimeError(
                "generator_path not set or file not found.  "
                "Pass generator_path= to HFSTBackend() constructor."
            )
        cmd = ["hfst-lookup", str(self._generator)]
        proc = subprocess.run(
            cmd,
            input=lexical_form + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        surfaces = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and "+?" not in parts[1]:
                surfaces.append(parts[0].strip())
        return surfaces

    @staticmethod
    def _parse_lookup_output(
        stdout: str,
        surface_form: str,
    ) -> List[AnalysisResult]:
        """
        Parse raw ``hfst-lookup`` stdout into ``AnalysisResult`` objects.

        hfst-lookup output format (one line per hypothesis)::

            surface TAB lexical TAB weight
            balya   ba+SM2+PRES+ly+V+a+FV_IND  0.0
            balya   ba+SM2+PERF+ly+V+ide+FV_PERF  1.5

        An unrecognised form produces::

            balya   balya+?  inf

        Parameters
        ----------
        stdout : str
            Raw subprocess stdout.
        surface_form : str
            The form that was looked up (used as fallback if the first
            column is missing).

        Returns
        -------
        List[AnalysisResult]
            Sorted by weight ascending (best analysis first).
        """
        results: List[AnalysisResult] = []

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            surf     = parts[0].strip() or surface_form
            lexical  = parts[1].strip()
            weight_s = parts[2].strip() if len(parts) >= 3 else "0.0"

            try:
                weight = float(weight_s)
            except ValueError:
                weight = float("inf")

            is_failure = "+?" in lexical

            tags: List[ParsedTag] = (
                [] if is_failure else parse_tag(lexical)
            )

            results.append(AnalysisResult(
                surface=surf,
                lexical=lexical,
                tags=tags,
                weight=weight,
                is_failure=is_failure,
            ))

        results.sort(key=lambda r: r.weight)
        return results
