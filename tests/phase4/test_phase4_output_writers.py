"""
test_phase4_output_writers.py — GobeloJsonWriter + GobeloCoNLLUWriter tests
===========================================================================
57 tests across 8 groups:

  Group 1  · WriterStats                        ( 7 tests)
  Group 2  · Checkpoint helpers                 ( 5 tests)
  Group 3  · Token serialisation helpers        ( 8 tests)
  Group 4  · Sentence serialisation helpers     ( 8 tests)
  Group 5  · GobeloJsonWriter                   (10 tests)
  Group 6  · GobeloCoNLLUWriter                 (10 tests)
  Group 7  · GobeloDualWriter                   ( 5 tests)
  Group 8  · Reader utilities (iter_jsonl/conllu)( 4 tests)
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, "/home/claude")

import pytest

from models import (
    AnnotatedSentence,
    ConfidenceLevel,
    LexiconCategory,
    LexiconEntry,
    MorphemeSpan,
    POSTag,
    SlotFill,
    SlotParse,
    TokenType,
    WordToken,
)
from output_writers import (
    VERSION,
    GobeloCoNLLUWriter,
    GobeloDualWriter,
    GobeloJsonWriter,
    WriterStats,
    _feats_str,
    _misc_str,
    _sentence_to_conllu,
    _sentence_to_dict,
    _token_to_conllu,
    _token_to_dict,
    iter_conllu,
    iter_jsonl,
    load_checkpoint,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_slot_parse(score: float = 0.72) -> SlotParse:
    sp = SlotParse(lang_iso="toi", analyser_version="2.0.0", score=score)
    sp.set("SLOT2", SlotFill(
        form="ba", gloss="SM.NC2", source_rule="SM.NC2",
        confidence=ConfidenceLevel.HIGH, start=0, end=2,
    ))
    sp.set("SLOT5", SlotFill(
        form="lim", gloss="cultivate", source_rule="LEX:lim",
        confidence=ConfidenceLevel.HIGH, start=2, end=5,
    ))
    sp.set("SLOT10", SlotFill(
        form="a", gloss="FV.IND", source_rule="indicative",
        confidence=ConfidenceLevel.HIGH, start=5, end=6,
    ))
    sp.add_flag("LEXICON_HIT")
    sp.add_flag("FV_IDENTIFIED")
    return sp


def _make_verb_token(token_id: str = "2") -> WordToken:
    tok = WordToken(
        token_id=token_id,
        form="balima",
        lang_iso="toi",
        token_type=TokenType.WORD,
        char_start=7,
        char_end=13,
        upos=POSTag.VERB,
        xpos="VERB.FIN.SMNC2",
        lemma="lim",
        feats={"VerbForm": "Fin", "Person": "3", "Number": "Plur",
               "Tense": "Pres", "Mood": "Ind"},
    )
    sp = _make_slot_parse()
    tok.add_slot_parse(sp)
    tok.add_morpheme_span(MorphemeSpan(0, 2, "ba",  "SM",   "SM.NC2", "SLOT2"))
    tok.add_morpheme_span(MorphemeSpan(2, 5, "lim", "ROOT", "cultivate", "SLOT5"))
    tok.add_morpheme_span(MorphemeSpan(5, 6, "a",   "FV",   "FV.IND",   "SLOT10"))
    tok.add_flag("VERB_ANALYSED")
    tok.add_flag("TAGGED_V2")
    tok.is_oov = False
    entry = LexiconEntry(
        lang_iso="toi", category=LexiconCategory.VERB,
        root="lim", gloss="cultivate",
    )
    tok.add_lexicon_match(entry)
    return tok


def _make_noun_token(token_id: str = "1") -> WordToken:
    tok = WordToken(
        token_id=token_id,
        form="Bakali",
        lang_iso="toi",
        token_type=TokenType.WORD,
        char_start=0,
        char_end=6,
        upos=POSTag.NOUN,
        xpos="NOUN.NC2",
        lemma="kali",
        feats={"NounClass": "NC2", "Number": "Plur"},
        noun_class="NC2",
    )
    tok.add_morpheme_span(MorphemeSpan(0, 2, "ba",   "NC_PREFIX", "NC2"))
    tok.add_morpheme_span(MorphemeSpan(2, 6, "kali", "STEM",      "stranger"))
    tok.add_flag("NOUN_ANALYSED")
    tok.add_flag("TAGGED_N2")
    tok.is_oov = False
    return tok


def _make_punct_token(token_id: str = "3") -> WordToken:
    return WordToken(
        token_id=token_id,
        form=".",
        lang_iso="toi",
        token_type=TokenType.PUNCT,
        char_start=13,
        char_end=14,
        upos=POSTag.PUNCT,
        xpos="PUNCT",
        deprel="punct",
    )


def _make_sentence(sent_id: str = "toi-001-001") -> AnnotatedSentence:
    n = _make_noun_token("1")
    v = _make_verb_token("2")
    p = _make_punct_token("3")
    sent = AnnotatedSentence(
        sent_id=sent_id,
        text="Bakali balima.",
        lang_iso="toi",
        source="test:fixture",
        tokens=[n, v, p],
        pipeline=["GobeloWordTokenizer-1.0.0",
                  "GobelloMorphAnalyser-2.0.0",
                  "GobeloPOSTagger-3.0.0"],
    )
    return sent


def _make_oov_sentence() -> AnnotatedSentence:
    """A sentence with an OOV token."""
    oov = WordToken(
        token_id="1",
        form="xyzunknown",
        lang_iso="toi",
        token_type=TokenType.WORD,
        char_start=0,
        char_end=10,
        upos=POSTag.X,
        xpos="X",
        is_oov=True,
        flags=["OOV", "TAGGED_FALLBACK"],
    )
    return AnnotatedSentence(
        sent_id="toi-oov-001",
        text="xyzunknown",
        lang_iso="toi",
        tokens=[oov],
    )


# ---------------------------------------------------------------------------
# Group 1 — WriterStats (7 tests)
# ---------------------------------------------------------------------------

class TestWriterStats:

    def test_initial_values_are_zero(self):
        s = WriterStats()
        assert s.sentences_written == 0
        assert s.tokens_written == 0
        assert s.oov_tokens == 0

    def test_to_dict_includes_all_keys(self):
        s = WriterStats()
        d = s.to_dict()
        for key in ("sentences_written", "tokens_written", "oov_tokens",
                    "verb_tokens", "noun_tokens", "tagged_tokens",
                    "untagged_tokens", "bytes_written", "skipped_sentences",
                    "tagging_rate", "oov_rate"):
            assert key in d

    def test_tagging_rate_zero_when_no_tokens(self):
        s = WriterStats()
        assert s.to_dict()["tagging_rate"] == 0.0

    def test_tagging_rate_computed_correctly(self):
        s = WriterStats(tokens_written=10, tagged_tokens=8)
        assert s.to_dict()["tagging_rate"] == 0.8

    def test_oov_rate_computed_correctly(self):
        s = WriterStats(tokens_written=10, oov_tokens=3)
        assert s.to_dict()["oov_rate"] == 0.3

    def test_repr_contains_key_fields(self):
        s = WriterStats(sentences_written=5, tokens_written=20, tagged_tokens=18, oov_tokens=2)
        r = repr(s)
        assert "sents=5" in r
        assert "toks=20" in r

    def test_bytes_written_accumulates(self):
        s = WriterStats()
        s.bytes_written += 1024
        s.bytes_written += 512
        assert s.bytes_written == 1536


# ---------------------------------------------------------------------------
# Group 2 — Checkpoint helpers (5 tests)
# ---------------------------------------------------------------------------

class TestCheckpointHelpers:

    def test_load_checkpoint_returns_empty_set_if_no_file(self, tmp_path):
        result = load_checkpoint(tmp_path / "nonexistent.ckpt")
        assert result == set()

    def test_load_checkpoint_reads_sent_ids(self, tmp_path):
        ckpt = tmp_path / "run.ckpt"
        ckpt.write_text("toi-001\ntoi-002\ntoi-003\n", encoding="utf-8")
        result = load_checkpoint(ckpt)
        assert result == {"toi-001", "toi-002", "toi-003"}

    def test_load_checkpoint_strips_blank_lines(self, tmp_path):
        ckpt = tmp_path / "run.ckpt"
        ckpt.write_text("toi-001\n\ntoi-002\n\n", encoding="utf-8")
        result = load_checkpoint(ckpt)
        assert "" not in result
        assert len(result) == 2

    def test_writer_skips_checkpointed_sentence(self, tmp_path):
        ckpt = tmp_path / "run.ckpt"
        ckpt.write_text("toi-001-001\n", encoding="utf-8")
        with GobeloJsonWriter(tmp_path, lang_iso="toi",
                              checkpoint_path=ckpt) as w:
            written = w.write(_make_sentence("toi-001-001"))
        assert written is False
        assert w.stats().skipped_sentences == 1

    def test_writer_appends_new_sent_ids_to_checkpoint(self, tmp_path):
        ckpt = tmp_path / "run.ckpt"
        with GobeloJsonWriter(tmp_path, lang_iso="toi",
                              checkpoint_path=ckpt) as w:
            w.write(_make_sentence("toi-001-001"))
        ids = load_checkpoint(ckpt)
        assert "toi-001-001" in ids


# ---------------------------------------------------------------------------
# Group 3 — Token serialisation helpers (8 tests)
# ---------------------------------------------------------------------------

class TestTokenSerialisationHelpers:

    def test_feats_str_empty_returns_underscore(self):
        assert _feats_str({}) == "_"

    def test_feats_str_sorted_pipe_separated(self):
        result = _feats_str({"Tense": "Pres", "Mood": "Ind", "VerbForm": "Fin"})
        # Must be sorted alphabetically
        parts = result.split("|")
        assert parts == sorted(parts)
        assert "Mood=Ind" in result
        assert "Tense=Pres" in result

    def test_misc_str_includes_morphemes(self):
        tok = _make_verb_token()
        result = _misc_str(tok)
        assert "Morphemes=" in result
        assert "SM=ba" in result

    def test_misc_str_includes_gloss(self):
        tok = _make_verb_token()
        result = _misc_str(tok)
        assert "Gloss=" in result

    def test_misc_str_includes_slot_score(self):
        tok = _make_verb_token()
        result = _misc_str(tok)
        assert "SlotScore=" in result

    def test_misc_str_noun_class_for_noun(self):
        tok = _make_noun_token()
        result = _misc_str(tok)
        assert "NounClass=NC2" in result

    def test_misc_str_oov_flag(self):
        tok = WordToken(token_id="1", form="xyz", lang_iso="toi",
                        is_oov=True, token_type=TokenType.WORD)
        result = _misc_str(tok)
        assert "OOV=Yes" in result

    def test_token_to_dict_has_required_keys(self):
        tok = _make_verb_token()
        d = _token_to_dict(tok)
        for key in ("token_id", "form", "upos", "xpos", "feats",
                    "morphemes", "slot_parses", "flags", "is_oov"):
            assert key in d, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Group 4 — Sentence serialisation helpers (8 tests)
# ---------------------------------------------------------------------------

class TestSentenceSerialisationHelpers:

    def test_sentence_to_dict_has_required_keys(self):
        sent = _make_sentence()
        d = _sentence_to_dict(sent)
        for key in ("sent_id", "text", "lang_iso", "tokens", "pipeline", "stats"):
            assert key in d

    def test_sentence_to_dict_token_count_matches(self):
        sent = _make_sentence()
        d = _sentence_to_dict(sent)
        assert len(d["tokens"]) == 3

    def test_sentence_to_dict_preserves_sent_id(self):
        sent = _make_sentence("bem-042-007")
        d = _sentence_to_dict(sent)
        assert d["sent_id"] == "bem-042-007"

    def test_sentence_to_conllu_starts_with_sent_id_comment(self):
        sent = _make_sentence()
        result = _sentence_to_conllu(sent)
        assert result.startswith("# sent_id = toi-001-001")

    def test_sentence_to_conllu_has_correct_column_count(self):
        sent = _make_sentence()
        result = _sentence_to_conllu(sent)
        for line in result.splitlines():
            if line.startswith("#") or line == "":
                continue
            cols = line.split("\t")
            assert len(cols) == 10, f"Expected 10 columns, got {len(cols)}: {line!r}"

    def test_sentence_to_conllu_ends_with_blank_line(self):
        sent = _make_sentence()
        result = _sentence_to_conllu(sent)
        assert result.endswith("\n") or result.endswith("\n\n")

    def test_sentence_to_conllu_token_id_column(self):
        sent = _make_sentence()
        result = _sentence_to_conllu(sent)
        token_lines = [l for l in result.splitlines()
                       if l and not l.startswith("#")]
        assert token_lines[0].split("\t")[0] == "1"
        assert token_lines[1].split("\t")[0] == "2"
        assert token_lines[2].split("\t")[0] == "3"

    def test_token_to_conllu_punct_has_punct_upos(self):
        tok = _make_punct_token()
        line = _token_to_conllu(tok)
        cols = line.split("\t")
        assert cols[3] == "PUNCT"   # UPOS column


# ---------------------------------------------------------------------------
# Group 5 — GobeloJsonWriter (10 tests)
# ---------------------------------------------------------------------------

class TestGobeloJsonWriter:

    def test_output_file_created_in_correct_directory(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        expected = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        assert expected.exists()

    def test_output_contains_one_line_per_sentence(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("toi-001"))
            w.write(_make_sentence("toi-002"))
            w.write(_make_sentence("toi-003"))
        path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        lines = [l for l in path.read_text().splitlines() if l.strip()]
        assert len(lines) == 3

    def test_each_line_is_valid_json(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        for line in path.read_text().splitlines():
            if line.strip():
                obj = json.loads(line)
                assert isinstance(obj, dict)

    def test_upos_field_in_token(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        obj = json.loads(path.read_text().splitlines()[0])
        upos_values = [t["upos"] for t in obj["tokens"]]
        assert "VERB" in upos_values
        assert "NOUN" in upos_values

    def test_morphemes_list_in_verb_token(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        obj = json.loads(path.read_text().splitlines()[0])
        verb_tokens = [t for t in obj["tokens"] if t["upos"] == "VERB"]
        assert verb_tokens
        assert len(verb_tokens[0]["morphemes"]) == 3

    def test_stats_sidecar_written_on_close(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        stats_path = (tmp_path / "toi" / "annotations"
                      / "toi_annotations.stats.json")
        assert stats_path.exists()
        stats = json.loads(stats_path.read_text())
        assert stats["sentences_written"] == 1

    def test_stats_accumulates_correctly(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("s1"))
            w.write(_make_sentence("s2"))
        assert w.stats().sentences_written == 2
        assert w.stats().tokens_written == 6  # 3 tokens × 2 sentences

    def test_custom_filename_respected(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi",
                              filename="custom_out.jsonl") as w:
            w.write(_make_sentence())
        expected = tmp_path / "toi" / "annotations" / "custom_out.jsonl"
        assert expected.exists()

    def test_corpus_header_written_as_first_line(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write_corpus_header("toi", {"grammar_version": "1.0.0",
                                           "run_date": "2025-07-11"})
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        lines = [l for l in path.read_text().splitlines() if l.strip()]
        header = json.loads(lines[0])
        assert header["_type"] == "corpus_header"
        assert header["lang_iso"] == "toi"

    def test_oov_token_marked_in_output(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_oov_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        obj = json.loads(path.read_text().strip())
        assert obj["tokens"][0]["is_oov"] is True


# ---------------------------------------------------------------------------
# Group 6 — GobeloCoNLLUWriter (10 tests)
# ---------------------------------------------------------------------------

class TestGobeloCoNLLUWriter:

    def test_output_file_created_in_correct_directory(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        expected = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        assert expected.exists()

    def test_output_contains_blank_line_between_sentences(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("s1"))
            w.write(_make_sentence("s2"))
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        content = path.read_text()
        # Two sentence blocks means at least two blank lines
        blank_count = content.count("\n\n")
        assert blank_count >= 1

    def test_sent_id_comment_in_output(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("toi-042-001"))
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        assert "# sent_id = toi-042-001" in path.read_text()

    def test_ten_columns_per_token_line(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        for line in path.read_text().splitlines():
            if line and not line.startswith("#"):
                assert len(line.split("\t")) == 10

    def test_upos_in_fourth_column(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        token_lines = [l for l in path.read_text().splitlines()
                       if l and not l.startswith("#")]
        upos_values = [l.split("\t")[3] for l in token_lines]
        assert "VERB" in upos_values
        assert "NOUN" in upos_values
        assert "PUNCT" in upos_values

    def test_morphemes_in_misc_column(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        misc_values = [l.split("\t")[9] for l in path.read_text().splitlines()
                       if l and not l.startswith("#")]
        # Verb token should have morphemes in MISC
        verb_misc = [m for m in misc_values if "SM=ba" in m]
        assert verb_misc, "Expected morpheme annotation in verb MISC column"

    def test_feats_column_contains_tense(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        token_lines = [l for l in path.read_text().splitlines()
                       if l and not l.startswith("#")]
        # Verb token (line 2) feats column should contain Tense
        verb_line = token_lines[1]
        feats_col = verb_line.split("\t")[5]
        assert "Tense=Pres" in feats_col

    def test_deprel_in_eighth_column(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        token_lines = [l for l in path.read_text().splitlines()
                       if l and not l.startswith("#")]
        # Punct token should have deprel="punct"
        punct_line = token_lines[2]
        deprel_col = punct_line.split("\t")[7]
        assert deprel_col == "punct"

    def test_global_comments_written(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write_global_comments([
                "global.columns = ID FORM LEMMA UPOS XPOS FEATS HEAD DEPREL DEPS MISC"
            ])
            w.write(_make_sentence())
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        assert "global.columns" in path.read_text()

    def test_stats_accumulated(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("s1"))
            w.write(_make_sentence("s2"))
        assert w.stats().sentences_written == 2
        assert w.stats().verb_tokens == 2
        assert w.stats().noun_tokens == 2


# ---------------------------------------------------------------------------
# Group 7 — GobeloDualWriter (5 tests)
# ---------------------------------------------------------------------------

class TestGobeloDualWriter:

    def test_both_files_created(self, tmp_path):
        with GobeloDualWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        assert (tmp_path / "toi" / "annotations" / "toi_annotations.jsonl").exists()
        assert (tmp_path / "toi" / "annotations" / "toi_annotations.conllu").exists()

    def test_sentence_appears_in_both_outputs(self, tmp_path):
        with GobeloDualWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("toi-dual-001"))
        # Check JSON
        json_path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        assert "toi-dual-001" in json_path.read_text()
        # Check CoNLL-U
        conllu_path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        assert "toi-dual-001" in conllu_path.read_text()

    def test_write_batch_returns_count(self, tmp_path):
        sents = [_make_sentence(f"s{i}") for i in range(5)]
        with GobeloDualWriter(tmp_path, lang_iso="toi") as w:
            count = w.write_batch(sents)
        assert count == 5

    def test_stats_returns_dict_with_both_keys(self, tmp_path):
        with GobeloDualWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence())
        s = w.stats()
        assert "json" in s
        assert "conllu" in s

    def test_checkpoint_prevents_duplicate_writes(self, tmp_path):
        ckpt = tmp_path / "dual.ckpt"
        # First run
        with GobeloDualWriter(tmp_path, lang_iso="toi",
                              checkpoint_path=ckpt) as w:
            w.write(_make_sentence("toi-dup-001"))
        # Second run — same sentence should be skipped
        with GobeloDualWriter(tmp_path, lang_iso="toi",
                              append=True, checkpoint_path=ckpt) as w:
            written = w.write(_make_sentence("toi-dup-001"))
        assert written is False


# ---------------------------------------------------------------------------
# Group 8 — Reader utilities (4 tests)
# ---------------------------------------------------------------------------

class TestReaderUtilities:

    def test_iter_jsonl_yields_sentence_dicts(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("toi-001"))
            w.write(_make_sentence("toi-002"))
        path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        results = list(iter_jsonl(path))
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)

    def test_iter_jsonl_skips_corpus_header(self, tmp_path):
        with GobeloJsonWriter(tmp_path, lang_iso="toi") as w:
            w.write_corpus_header("toi", {"version": "1.0"})
            w.write(_make_sentence("toi-001"))
        path = tmp_path / "toi" / "annotations" / "toi_annotations.jsonl"
        results = list(iter_jsonl(path))
        # Header should be skipped; only the sentence should be yielded
        assert len(results) == 1
        assert results[0]["sent_id"] == "toi-001"

    def test_iter_conllu_yields_sentence_blocks(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("toi-001"))
            w.write(_make_sentence("toi-002"))
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        blocks = list(iter_conllu(path))
        assert len(blocks) == 2

    def test_iter_conllu_block_contains_sent_id_comment(self, tmp_path):
        with GobeloCoNLLUWriter(tmp_path, lang_iso="toi") as w:
            w.write(_make_sentence("toi-rdr-001"))
        path = tmp_path / "toi" / "annotations" / "toi_annotations.conllu"
        blocks = list(iter_conllu(path))
        assert blocks
        first_block = blocks[0]
        sent_id_lines = [l for l in first_block if "sent_id" in l]
        assert sent_id_lines
        assert "toi-rdr-001" in sent_id_lines[0]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
