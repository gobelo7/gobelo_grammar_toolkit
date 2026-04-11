"""
agreement_chain.py — GobeloAgreementChain  (GGT Phase 6)
==========================================================
Sentence-level Bantu agreement-chain resolver.

Operates on an AnnotatedSentence that has been through the full four-stage
pipeline (tokenise → morpheme-analyse → POS-tag → output).  This phase adds:

  * Cross-token agreement confirmation — NOUN ↔ VERB subject marker
  * Object-marker chain resolution — OM on verb ↔ object NOUN
  * Demonstrative / possessive agreement — concord prefix ↔ head noun
  * Adjective agreement — adjectival concord ↔ head noun
  * Disambiguation of ambiguous UPOS assignments when NC evidence is available
  * Correction of Person / Number features derived from non-human NC agreement
  * CoNLL-U MISC annotations:  AgreeNC=, AgreeSubj=, AgreeObj=, AgreeAdj=,
    AgreeDem=, AgreePoss=, ChainScore=
  * UD enhanced-dependency stubs in column 9 for confirmed nsubj / obj links

Architecture
------------
The resolver works in four passes over the sentence's token list:

  Pass 1 · NC inventory scan
        Walk all tokens.  For each NOUN (or token with noun_class set):
        record its position, NC key, and token_id in a ``_NCSighting`` object.
        Separate tables are maintained for human NCs (NC1/NC2) and non-human.

  Pass 2 · Subject-marker chain resolution
        For each VERB token with a SlotParse:
          a. Extract the SM NC from SLOT2.source_rule.
          b. Search the NC inventory for a NOUN with matching NC within the
             search window (``sm_window`` tokens before and after the verb).
          c. If found: confirm agreement, annotate both tokens, update UD feats,
             write AgreeSubj= to MISC.
          d. If multiple candidates: pick the nearest.
          e. If none in window: mark SM as "unresolved" (flag AGREE_SM_UNRESOLVED).

  Pass 3 · Object-marker chain resolution
        For each VERB token with OM (SLOT4) filled:
          a. Extract OM NC from SLOT4.source_rule.
          b. Search the NC inventory for a NOUN with matching NC in the post-verb
             window (``om_window`` tokens after the verb, default 5).
          c. If found: annotate, write AgreeObj= to MISC.

  Pass 4 · Modifier agreement (adjectives, demonstratives, possessives)
        For each ADJ / DET / PRON token:
          a. Inspect the concord prefix (from morpheme_spans[0] or noun_class).
          b. Search the surrounding window for a NOUN with matching NC.
          c. If found: annotate, write AgreeAdj= / AgreeDem= / AgreePoss=.

Scoring
-------
Each confirmed agreement link carries a ``ChainScore`` in [0.0, 1.0]:

  + 0.40  SM NC matches a lexicon-confirmed noun
  + 0.25  SM NC matches a heuristically-identified noun
  + 0.15  OM NC matches a post-verb noun
  + 0.10  Modifier concord NC matches head noun
  + 0.05  Surface reconstruction of verb agrees with slot analysis
  + 0.05  Both noun and verb are within the canonical window distance

Maximum score: 1.0 (all components confirmed)

Loader interface
----------------
The resolver reads the following from the loader (all optional):

  loader.get("morphology.noun_classes", {})   — NC → {prefix, grammatical_number}
  loader.get("morphology.subject_markers", {}) — NC → {form, gloss, person, number}
  loader.get("morphology.object_markers", {})  — NC → {form, gloss}

If the loader is None or returns nothing, the resolver operates on
the NC information already embedded in token.noun_class and
SlotParse.slot.source_rule — no YAML required for basic chain resolution.

Usage
-----
    resolver = GobeloAgreementChain(loader)
    sentence  = resolver.resolve(sentence)          # mutates in place
    sentences = resolver.resolve_batch([s1, s2])    # list version

    # Integrated into the annotation pipeline:
    pipeline.add_stage(resolver)                    # Phase 6 plug-in

Output
------
Per confirmed agreement link, the following MISC keys are set:

  AgreeSubj=<noun_token_id>     on the VERB token
  AgreeObj=<noun_token_id>      on the VERB token
  AgreeAdj=<noun_token_id>      on the ADJ/DET/PRON token
  AgreeDem=<noun_token_id>      on the DEM token
  AgreePoss=<noun_token_id>     on the POSS token
  AgreeNC=<NC_key>              on both verb and noun tokens
  ChainScore=<float>            on the VERB token (cumulative)
  nsubj=<noun_token_id>         in enhanced deps column (VERB token)
  obj=<noun_token_id>           in enhanced deps column (VERB token)

Flags added to tokens:
  AGREE_SUBJ_CONFIRMED    VERB token, subject agreement resolved
  AGREE_SUBJ_UNRESOLVED   VERB token, SM present but no matching noun found
  AGREE_OBJ_CONFIRMED     VERB token, object agreement resolved
  AGREE_OBJ_UNRESOLVED    VERB token, OM present but no matching noun found
  AGREE_MOD_CONFIRMED     ADJ/DET/PRON token, modifier agreement resolved
  AGREE_NC_DONOR          NOUN token that donated its NC to a chain
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from models import (
    AnnotatedSentence,
    ConfidenceLevel,
    POSTag,
    SlotFill,
    SlotParse,
    TokenType,
    WordToken,
)

VERSION = "6.0.0"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# NC keys that carry [+human] feature — affects Person/Number assignment
_HUMAN_NCS: Set[str] = {"NC1", "NC1a", "NC2", "NC2a", "NC2b"}

# NC keys that are locative — not nouns in the classic sense
_LOCATIVE_NCS: Set[str] = {"NC16", "NC17", "NC18"}

# Modifier UPOS values subject to Pass 4
_MODIFIER_UPOS: Set[POSTag] = {POSTag.ADJ, POSTag.DET, POSTag.PRON}

# Default search windows (in tokens)
_DEFAULT_SM_WINDOW  = 8   # tokens either side of verb for subject search
_DEFAULT_OM_WINDOW  = 5   # tokens after verb for object search
_DEFAULT_MOD_WINDOW = 4   # tokens either side of modifier for head search


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass
class _NCSighting:
    """A noun-class sighting in the sentence — one per NOUN token."""
    token_id   : str            # WordToken.token_id
    position   : int            # index in sentence.tokens
    nc_key     : str            # e.g. "NC3"
    is_human   : bool           # NC1/NC2 family
    is_lexicon : bool           # token has at least one lexicon_match
    score      : float          # confidence of NC identification (0–1)

    def distance_to(self, verb_position: int) -> int:
        return abs(self.position - verb_position)


@dataclass
class _AgreementLink:
    """One confirmed agreement link between two tokens."""
    kind          : str    # "subj", "obj", "adj", "dem", "poss"
    nc_key        : str
    verb_tok_id   : str    # or modifier token_id
    noun_tok_id   : str
    score         : float
    distance      : int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _lower_nfc(s: str) -> str:
    return _nfc(s.lower())


def _nc_from_source_rule(source_rule: str) -> Optional[str]:
    """Extract NC key from a SlotFill.source_rule like 'SM.NC3' or 'OM.NC7'."""
    if not source_rule:
        return None
    parts = source_rule.split(".")
    for part in parts:
        if part.startswith("NC") or part.startswith("CL"):
            return part.replace("CL", "NC")
    return None


def _nc_from_gloss(gloss: str) -> Optional[str]:
    """Extract NC key from a gloss string like 'CL3.SM' or 'SM.NC3'."""
    if not gloss:
        return None
    for part in gloss.split("."):
        candidate = part.replace("CL", "NC")
        if candidate.startswith("NC") and len(candidate) >= 3:
            return candidate
    return None


def _get_sm_nc(sp: SlotParse) -> Optional[str]:
    """Return the NC key encoded in SLOT2 (Subject Marker)."""
    slot2 = sp.get("SLOT2")
    if slot2.is_empty():
        return None
    nc = _nc_from_source_rule(slot2.source_rule)
    if nc is None:
        nc = _nc_from_gloss(slot2.gloss)
    return nc


def _get_om_nc(sp: SlotParse) -> Optional[str]:
    """Return the NC key encoded in SLOT4 (Object Marker)."""
    slot4 = sp.get("SLOT4")
    if slot4.is_empty():
        return None
    nc = _nc_from_source_rule(slot4.source_rule)
    if nc is None:
        nc = _nc_from_gloss(slot4.gloss)
    return nc


def _get_modifier_nc(token: WordToken) -> Optional[str]:
    """Extract the NC a modifier token agrees with.

    Strategy (in priority order):
    1. token.noun_class (set by morph analyser)
    2. morpheme_spans[0].gloss if label in (NC_PREFIX, SM, DEM, POSS)
    3. xpos contains NC key (e.g. "DET.NC3")
    """
    if token.noun_class:
        return token.noun_class
    if token.morpheme_spans:
        span = token.morpheme_spans[0]
        if span.label in ("NC_PREFIX", "SM", "DEM", "POSS", "CONC"):
            nc = _nc_from_gloss(span.gloss) or _nc_from_source_rule(span.gloss)
            if nc:
                return nc
    if token.xpos:
        for part in token.xpos.split("."):
            if part.startswith("NC") and len(part) >= 3:
                return part
    return None


def _chain_score(
    sighting    : _NCSighting,
    verb_pos    : int,
    window      : int,
    kind        : str = "subj",
) -> float:
    """Compute the agreement link confidence score."""
    score = 0.0
    dist = sighting.distance_to(verb_pos)

    # NC identification confidence
    score += sighting.score * 0.40

    # Lexicon confirmation bonus
    if sighting.is_lexicon:
        score += 0.15

    # Proximity bonus (closer = higher score)
    proximity_fraction = max(0.0, 1.0 - dist / (window + 1))
    score += proximity_fraction * 0.25

    # Kind-specific bonus
    if kind == "subj":
        score += 0.10
    elif kind == "obj":
        score += 0.05
    else:
        score += 0.05

    return min(round(score, 3), 1.0)


# ---------------------------------------------------------------------------
# _ResolverConfig — pre-computed tables from loader
# ---------------------------------------------------------------------------

@dataclass
class _ResolverConfig:
    """Pre-computed NC and concord tables for agreement resolution."""
    lang_iso: str

    # NC → grammatical_number ("singular" / "plural")
    nc_number: Dict[str, str] = field(default_factory=dict)

    # NC → person heuristic ("1" / "2" / "3")
    nc_person: Dict[str, str] = field(default_factory=dict)

    # Human NCs from YAML (adds to global _HUMAN_NCS)
    human_ncs: Set[str] = field(default_factory=set)

    # All active NC keys
    active_ncs: Set[str] = field(default_factory=set)


def _build_resolver_config(loader) -> _ResolverConfig:
    """Build _ResolverConfig from loader grammar data."""
    cfg = _ResolverConfig(lang_iso=getattr(loader, "lang_iso", "und"))

    nc_data: Dict = loader.get("morphology.noun_classes", {}) or {}
    for nc_key, nc_info in nc_data.items():
        if not isinstance(nc_info, dict):
            continue
        cfg.active_ncs.add(nc_key)

        # Grammatical number
        num = nc_info.get("grammatical_number") or nc_info.get("number")
        if num:
            cfg.nc_number[nc_key] = str(num).lower()
        else:
            # Bantu convention: odd NC → singular, even NC → plural
            digits = "".join(c for c in nc_key if c.isdigit())
            if digits:
                n = int(digits)
                cfg.nc_number[nc_key] = "singular" if n % 2 == 1 else "plural"

        # Human NCs
        feats = nc_info.get("semantics", {}) if isinstance(nc_info.get("semantics"), dict) else {}
        if "+human" in str(feats.get("features", [])):
            cfg.human_ncs.add(nc_key)

    # Subject markers → person
    sm_data: Dict = loader.get("morphology.subject_markers", {}) or {}
    for nc_key, sm_info in sm_data.items():
        if isinstance(sm_info, dict):
            person = sm_info.get("person")
            if person:
                cfg.nc_person[nc_key] = str(person)

    # Merge in global human NC set
    cfg.human_ncs.update(_HUMAN_NCS)

    return cfg


# ---------------------------------------------------------------------------
# GobeloAgreementChain — main resolver class
# ---------------------------------------------------------------------------

class GobeloAgreementChain:
    """Bantu agreement-chain resolver for the Gobelo Grammar Toolkit.

    Parameters
    ----------
    loader : GobeloGrammarLoader (or compatible mock), optional
        Provides NC and concord tables.  Operates in degraded mode (NC
        evidence from tokens only) when loader is None.
    sm_window : int
        Search radius in tokens for subject–verb agreement (default 8).
    om_window : int
        Search radius in tokens after the verb for object agreement (default 5).
    mod_window : int
        Search radius for modifier–head agreement (default 4).
    min_score : float
        Minimum chain score to confirm a link (default 0.25).
    resolve_upos : bool
        If True, correct UPOS=X tokens when NC evidence confirms NOUN or VERB.
        Default True.
    resolve_feats : bool
        If True, update Person / Number features from confirmed NC agreement.
        Default True.
    write_enhanced_deps : bool
        If True, write confirmed nsubj / obj links to token.deps (UD enhanced
        dependencies, CoNLL-U column 9).  Default True.
    """

    VERSION = VERSION

    def __init__(
        self,
        loader=None,
        sm_window         : int   = _DEFAULT_SM_WINDOW,
        om_window         : int   = _DEFAULT_OM_WINDOW,
        mod_window        : int   = _DEFAULT_MOD_WINDOW,
        min_score         : float = 0.25,
        resolve_upos      : bool  = True,
        resolve_feats     : bool  = True,
        write_enhanced_deps: bool = True,
    ) -> None:
        self._sm_window   = sm_window
        self._om_window   = om_window
        self._mod_window  = mod_window
        self._min_score   = min_score
        self._resolve_upos = resolve_upos
        self._resolve_feats = resolve_feats
        self._write_edeps = write_enhanced_deps

        if loader is not None:
            self._cfg = _build_resolver_config(loader)
        else:
            self._cfg = _ResolverConfig(lang_iso="und")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def resolve(self, sentence: AnnotatedSentence) -> AnnotatedSentence:
        """Resolve agreement chains in *sentence* in place.

        Returns the same sentence object for chaining.
        """
        tokens = sentence.tokens
        if not tokens:
            return sentence

        # Pass 1 — build NC inventory
        nc_inventory = self._build_nc_inventory(tokens)

        # Pass 2 — subject-marker chain resolution
        links: List[_AgreementLink] = []
        links.extend(self._resolve_subject_chains(tokens, nc_inventory))

        # Pass 3 — object-marker chain resolution
        links.extend(self._resolve_object_chains(tokens, nc_inventory))

        # Pass 4 — modifier agreement
        links.extend(self._resolve_modifier_chains(tokens, nc_inventory))

        # Apply all confirmed links
        self._apply_links(tokens, links)

        # Mark donor nouns
        donor_ids = {lnk.noun_tok_id for lnk in links}
        for tok in tokens:
            if tok.token_id in donor_ids:
                tok.add_flag("AGREE_NC_DONOR")

        sentence.add_pipeline_stage(f"GobeloAgreementChain-{self.VERSION}")
        return sentence

    def resolve_batch(
        self, sentences: List[AnnotatedSentence]
    ) -> List[AnnotatedSentence]:
        """Resolve agreement chains in a list of sentences."""
        return [self.resolve(s) for s in sentences]

    # ------------------------------------------------------------------ #
    # Pass 1 — NC inventory
    # ------------------------------------------------------------------ #

    def _build_nc_inventory(
        self, tokens: List[WordToken]
    ) -> List[_NCSighting]:
        """Scan tokens and collect every noun-class sighting."""
        sightings: List[_NCSighting] = []

        for pos, tok in enumerate(tokens):
            if tok.token_type in (TokenType.PUNCT, TokenType.SPECIAL):
                continue

            nc = self._extract_noun_nc(tok)
            if nc is None:
                continue
            if nc in _LOCATIVE_NCS:
                continue   # locative NCs don't participate in nominal chains

            is_human  = nc in self._cfg.human_ncs or nc in _HUMAN_NCS
            is_lexicon = bool(tok.lexicon_matches)

            # Score: how confident are we this token is a NOUN with NC=nc?
            score = self._noun_confidence(tok, nc)

            sightings.append(_NCSighting(
                token_id   = tok.token_id,
                position   = pos,
                nc_key     = nc,
                is_human   = is_human,
                is_lexicon = is_lexicon,
                score      = score,
            ))

        return sightings

    def _extract_noun_nc(self, tok: WordToken) -> Optional[str]:
        """Return the NC of a token if it is (or may be) a noun."""
        # Explicit noun_class set by Phase 2
        if tok.noun_class:
            return tok.noun_class

        # FEATS NounClass from Phase 3
        nc_feat = tok.feats.get("NounClass") or tok.feats.get("GGT_NounClass")
        if nc_feat:
            return nc_feat

        # UPOS = NOUN with xpos containing NC info
        if tok.upos == POSTag.NOUN and tok.xpos:
            for part in tok.xpos.split("."):
                if part.startswith("NC") and len(part) >= 3:
                    return part

        # Morpheme span NC_PREFIX label
        for ms in tok.morpheme_spans:
            if ms.label == "NC_PREFIX" and ms.gloss:
                nc = _nc_from_gloss(ms.gloss)
                if nc:
                    return nc

        return None

    def _noun_confidence(self, tok: WordToken, nc: str) -> float:
        """Estimate how confident we are that this token is a noun with this NC."""
        score = 0.0
        if tok.upos == POSTag.NOUN:
            score += 0.50
        elif tok.upos is None or tok.upos == POSTag.X:
            score += 0.20  # unknown but has NC prefix
        else:
            score += 0.15  # some other UPOS but NC present

        if tok.lexicon_matches:
            score += 0.30
        elif "NOUN_ANALYSED" in tok.flags:
            score += 0.15
        elif tok.noun_class:
            score += 0.10

        # Penalty if token looks like a verb (has slot parse with SM)
        if tok.best_slot_parse:
            sp = tok.best_slot_parse
            if not sp.get("SLOT2").is_empty() and not sp.get("SLOT5").is_empty():
                score *= 0.30  # strong penalty — probably a verb

        return min(round(score, 3), 1.0)

    # ------------------------------------------------------------------ #
    # Pass 2 — Subject-marker chain
    # ------------------------------------------------------------------ #

    def _resolve_subject_chains(
        self,
        tokens    : List[WordToken],
        inventory : List[_NCSighting],
    ) -> List[_AgreementLink]:
        links: List[_AgreementLink] = []

        for pos, tok in enumerate(tokens):
            if tok.upos not in (POSTag.VERB, POSTag.AUX):
                continue
            sp = tok.best_slot_parse
            if sp is None:
                continue

            sm_nc = _get_sm_nc(sp)
            if sm_nc is None:
                continue

            # Find best matching noun in window
            candidates = [
                s for s in inventory
                if s.nc_key == sm_nc
                and s.distance_to(pos) <= self._sm_window
                and s.token_id != tok.token_id
            ]

            if not candidates:
                tok.add_flag("AGREE_SM_UNRESOLVED")
                continue

            # Pick the nearest candidate; on tie prefer lexicon-confirmed
            best = min(
                candidates,
                key=lambda s: (s.distance_to(pos), -int(s.is_lexicon), -s.score),
            )

            score = _chain_score(best, pos, self._sm_window, kind="subj")
            if score < self._min_score:
                tok.add_flag("AGREE_SM_UNRESOLVED")
                continue

            links.append(_AgreementLink(
                kind        = "subj",
                nc_key      = sm_nc,
                verb_tok_id = tok.token_id,
                noun_tok_id = best.token_id,
                score       = score,
                distance    = best.distance_to(pos),
            ))
            tok.add_flag("AGREE_SUBJ_CONFIRMED")

        return links

    # ------------------------------------------------------------------ #
    # Pass 3 — Object-marker chain
    # ------------------------------------------------------------------ #

    def _resolve_object_chains(
        self,
        tokens    : List[WordToken],
        inventory : List[_NCSighting],
    ) -> List[_AgreementLink]:
        links: List[_AgreementLink] = []

        for pos, tok in enumerate(tokens):
            if tok.upos not in (POSTag.VERB, POSTag.AUX):
                continue
            sp = tok.best_slot_parse
            if sp is None:
                continue

            om_nc = _get_om_nc(sp)
            if om_nc is None:
                continue

            # Objects typically follow the verb in Bantu SVO/SVC patterns
            candidates = [
                s for s in inventory
                if s.nc_key == om_nc
                and 0 < (s.position - pos) <= self._om_window
            ]
            # But also allow pre-verbal objects (topicalised)
            if not candidates:
                candidates = [
                    s for s in inventory
                    if s.nc_key == om_nc
                    and s.distance_to(pos) <= self._om_window
                    and s.token_id != tok.token_id
                ]

            if not candidates:
                tok.add_flag("AGREE_OM_UNRESOLVED")
                continue

            best = min(
                candidates,
                key=lambda s: (s.distance_to(pos), -int(s.is_lexicon), -s.score),
            )

            score = _chain_score(best, pos, self._om_window, kind="obj")
            if score < self._min_score:
                tok.add_flag("AGREE_OM_UNRESOLVED")
                continue

            links.append(_AgreementLink(
                kind        = "obj",
                nc_key      = om_nc,
                verb_tok_id = tok.token_id,
                noun_tok_id = best.token_id,
                score       = score,
                distance    = best.distance_to(pos),
            ))
            tok.add_flag("AGREE_OBJ_CONFIRMED")

        return links

    # ------------------------------------------------------------------ #
    # Pass 4 — Modifier agreement
    # ------------------------------------------------------------------ #

    def _resolve_modifier_chains(
        self,
        tokens    : List[WordToken],
        inventory : List[_NCSighting],
    ) -> List[_AgreementLink]:
        links: List[_AgreementLink] = []

        for pos, tok in enumerate(tokens):
            if tok.upos not in _MODIFIER_UPOS:
                continue

            mod_nc = _get_modifier_nc(tok)
            if mod_nc is None:
                continue

            # Determine agreement type from UPOS / xpos
            if tok.upos == POSTag.DET:
                kind = "dem" if tok.xpos and "DEM" in tok.xpos else "det"
            elif tok.upos == POSTag.PRON and tok.xpos and "POSS" in tok.xpos:
                kind = "poss"
            else:
                kind = "adj"

            candidates = [
                s for s in inventory
                if s.nc_key == mod_nc
                and s.distance_to(pos) <= self._mod_window
                and s.token_id != tok.token_id
            ]

            if not candidates:
                continue

            best = min(
                candidates,
                key=lambda s: (s.distance_to(pos), -s.score),
            )

            score = _chain_score(best, pos, self._mod_window, kind=kind)
            if score < self._min_score:
                continue

            links.append(_AgreementLink(
                kind        = kind,
                nc_key      = mod_nc,
                verb_tok_id = tok.token_id,   # "verb_tok_id" = the modifier here
                noun_tok_id = best.token_id,
                score       = score,
                distance    = best.distance_to(pos),
            ))
            tok.add_flag("AGREE_MOD_CONFIRMED")

        return links

    # ------------------------------------------------------------------ #
    # Apply links to tokens
    # ------------------------------------------------------------------ #

    def _apply_links(
        self,
        tokens : List[WordToken],
        links  : List[_AgreementLink],
    ) -> None:
        """Write all confirmed agreement evidence to token MISC, feats, deps."""
        tok_by_id: Dict[str, WordToken] = {t.token_id: t for t in tokens}

        # Track cumulative chain scores per verb token
        verb_chain_scores: Dict[str, float] = {}

        for lnk in links:
            verb_tok = tok_by_id.get(lnk.verb_tok_id)
            noun_tok = tok_by_id.get(lnk.noun_tok_id)
            if verb_tok is None or noun_tok is None:
                continue

            nc = lnk.nc_key

            # Shared NC annotation
            verb_tok.set_misc("AgreeNC", nc)
            noun_tok.set_misc("AgreeNC", nc)

            # Kind-specific MISC on the governing token (verb or modifier)
            if lnk.kind == "subj":
                verb_tok.set_misc("AgreeSubj", lnk.noun_tok_id)
                noun_tok.set_misc("AgreeVerb", lnk.verb_tok_id)
                # Enhanced dependency stub: nsubj
                if self._write_edeps:
                    verb_tok_id_int = self._tok_id_int(lnk.verb_tok_id)
                    if verb_tok_id_int is not None:
                        noun_tok.deps.append((verb_tok_id_int, "nsubj"))

            elif lnk.kind == "obj":
                verb_tok.set_misc("AgreeObj", lnk.noun_tok_id)
                noun_tok.set_misc("AgreeVerbObj", lnk.verb_tok_id)
                if self._write_edeps:
                    verb_tok_id_int = self._tok_id_int(lnk.verb_tok_id)
                    if verb_tok_id_int is not None:
                        noun_tok.deps.append((verb_tok_id_int, "obj"))

            elif lnk.kind == "dem":
                verb_tok.set_misc("AgreeDem", lnk.noun_tok_id)
            elif lnk.kind == "poss":
                verb_tok.set_misc("AgreePoss", lnk.noun_tok_id)
            else:  # adj / det
                verb_tok.set_misc("AgreeAdj", lnk.noun_tok_id)

            # Cumulative chain score on governing token
            prev = verb_chain_scores.get(lnk.verb_tok_id, 0.0)
            verb_chain_scores[lnk.verb_tok_id] = min(1.0, prev + lnk.score * 0.5)

            # Feature refinement
            if self._resolve_feats and lnk.kind == "subj":
                self._update_verb_feats(verb_tok, nc)

            # UPOS disambiguation
            if self._resolve_upos:
                self._disambiguate_upos(noun_tok, nc)

        # Write chain scores
        for tok_id, score in verb_chain_scores.items():
            tok = tok_by_id.get(tok_id)
            if tok:
                tok.set_misc("ChainScore", f"{score:.3f}")

    def _update_verb_feats(self, tok: WordToken, nc: str) -> None:
        """Refine Person / Number on a VERB token from confirmed NC agreement."""
        # Human NCs: first/second person must come from SM key, not NC alone
        if nc in self._cfg.human_ncs or nc in _HUMAN_NCS:
            # Only set if not already determined by SM analysis
            if "Person" not in tok.feats:
                person = self._cfg.nc_person.get(nc, "3")
                tok.feats["Person"] = person
            if "Number" not in tok.feats:
                num = self._cfg.nc_number.get(nc, "singular")
                tok.feats["Number"] = "Sing" if "sing" in num else "Plur"
        else:
            # Non-human NC agreement → 3rd person
            tok.feats.setdefault("Person", "3")
            num = self._cfg.nc_number.get(nc, "singular")
            tok.feats.setdefault(
                "Number", "Sing" if "sing" in num else "Plur"
            )

    def _disambiguate_upos(self, tok: WordToken, nc: str) -> None:
        """Correct UPOS when NC evidence is unambiguous."""
        if not self._resolve_upos:
            return
        if tok.upos in (None, POSTag.X) and nc not in _LOCATIVE_NCS:
            tok.upos = POSTag.NOUN
            tok.add_flag("UPOS_DISAMBIG_NC")
        # NC15 (infinitives used nominally) → keep VERB or set VERB
        # NC14 (abstract) → keep NOUN
        # NC16-18 (locative) → ADP
        if nc in _LOCATIVE_NCS and tok.upos not in (POSTag.ADP, POSTag.VERB):
            tok.upos = POSTag.ADP
            tok.add_flag("UPOS_DISAMBIG_LOC")

    @staticmethod
    def _tok_id_int(tok_id: str) -> Optional[int]:
        """Convert a token_id string to int for deps; returns None if not parseable."""
        try:
            return int(tok_id)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def describe(self) -> str:
        cfg = self._cfg
        lines = [
            f"GobeloAgreementChain v{self.VERSION}",
            f"  lang_iso          : {cfg.lang_iso}",
            f"  SM window         : ±{self._sm_window} tokens",
            f"  OM window         : +{self._om_window} tokens (post-verb)",
            f"  Modifier window   : ±{self._mod_window} tokens",
            f"  Min chain score   : {self._min_score}",
            f"  Resolve UPOS      : {self._resolve_upos}",
            f"  Resolve FEATS     : {self._resolve_feats}",
            f"  Write enhanced deps: {self._write_edeps}",
            f"  Active NCs (YAML) : {len(cfg.active_ncs)}",
            f"  Human NCs         : {sorted(cfg.human_ncs | _HUMAN_NCS)}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"GobeloAgreementChain(lang={self._cfg.lang_iso!r}, "
            f"v={self.VERSION})"
        )
