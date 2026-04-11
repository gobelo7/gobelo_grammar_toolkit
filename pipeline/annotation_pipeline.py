"""
annotation_pipeline.py — GobeloAnnotationPipeline + CLI  (GGT Phase 5)
=======================================================================
Orchestrates the full four-stage annotation pipeline for the Gobelo
Grammar Toolkit:

    Stage 1  GobeloWordTokenizer      (Phase 1) — word splitting + clitics
    Stage 2  GobelloMorphAnalyser     (Phase 2) — slot parse + morpheme spans
    Stage 3  GobeloPOSTagger          (Phase 3) — UD UPOS / FEATS / XPOS
    Stage 4  GobeloDualWriter         (Phase 4) — JSON-Lines + CoNLL-U output

Input is gcbt-produced output in one of two forms:
  • A ``.txt`` file: one sentence per line (language detected from directory
    name or ``--lang`` flag).
  • A ``.json`` file: gcbt sentence-JSON with ``language_iso`` key and a
    ``sentences`` array.  The pipeline inherits ``language_iso`` automatically.

Output mirrors gcbt's directory layout:

    output_dir/
      <lang_iso>/
        annotations/
          <lang_iso>_annotations.jsonl
          <lang_iso>_annotations.conllu
          <lang_iso>_annotations.stats.json
          <lang_iso>_pipeline.checkpoint   (if --checkpoint)

CLI usage
---------
Single language, from a gcbt .json file:
    python annotation_pipeline.py --lang toi --input gcbt_output/toi/literature/ --output out/

All languages in a gcbt corpus manifest:
    python annotation_pipeline.py --all --manifest corpus_manifest.json --output out/

List available languages in a manifest:
    python annotation_pipeline.py --list-langs --manifest corpus_manifest.json

Resume an interrupted run:
    python annotation_pipeline.py --lang toi --input ... --output out/ --checkpoint

Show pipeline configuration:
    python annotation_pipeline.py --lang toi --describe

Advanced:
    python annotation_pipeline.py \\
        --lang toi \\
        --input gcbt_output/toi/literature/ \\
        --output out/ \\
        --workers 4 \\
        --checkpoint \\
        --batch-size 200 \\
        --grammar grammars/chitonga.yaml \\
        --corpus-config corpus_config.yaml \\
        --log-level INFO

Architecture
------------
GobeloAnnotationPipeline
    __init__(loader, corpus_config, workers, batch_size)
        Instantiates all four stage objects from the single loader.
    run(input_path, output_dir, ...)
        Iterates input, processes in batches, writes via DualWriter.
    run_sentence(raw_text) → AnnotatedSentence
        Single-sentence convenience method (useful in notebooks).

GobeloPipelineCLI
    Thin argparse wrapper around GobeloAnnotationPipeline.
    Mirrors gcbt CLI patterns: --lang, --all, --list-langs, --workers.

Streaming
---------
Sentences are processed in batches of ``batch_size`` (default 100).
Each batch is fully annotated in memory and then flushed to disk before the
next batch is loaded.  Memory footprint is bounded by batch_size × average
sentence size.

Worker pool
-----------
When ``workers > 1``, the input is split into N shards (one per worker).
Each worker runs a full GobeloAnnotationPipeline instance (its own loader,
analyser, tagger, and writer shard).  Shards are merged by the main process
after all workers complete.

Checkpoint / resume
-------------------
If ``checkpoint=True``, a ``.checkpoint`` file is maintained alongside the
output.  Any sent_id already in the checkpoint is skipped on subsequent runs.
This allows a corpus run to be safely interrupted and restarted.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from models import AnnotatedSentence, WordToken
from output_writers import (
    GobeloCoNLLUWriter,
    GobeloDualWriter,
    GobeloJsonWriter,
    WriterStats,
    load_checkpoint,
)
from pos_tagger import GobeloPOSTagger
from word_tokenizer import GobeloWordTokenizer

logger = logging.getLogger("gobelo.pipeline")

VERSION = "5.0.0"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _iter_txt(path: Path) -> Iterator[Tuple[str, str]]:
    """Yield (sent_id, raw_text) from a one-sentence-per-line .txt file."""
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            text = _nfc(line.strip())
            if text:
                sent_id = f"{path.stem}-{lineno:06d}"
                yield sent_id, text


def _iter_gcbt_json(path: Path) -> Iterator[Tuple[str, str, str]]:
    """Yield (lang_iso, sent_id, raw_text) from a gcbt .json file.

    Supports two layouts:
      • Array of sentence objects at top level.
      • Object with ``language_iso`` + ``sentences`` array (gcbt canonical).
    """
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        lang = "und"
        sents = data
    else:
        lang = data.get("language_iso", data.get("lang_iso", "und"))
        sents = data.get("sentences", [])

    for s in sents:
        if not isinstance(s, dict):
            continue
        sid  = s.get("sent_id") or s.get("id") or ""
        text = _nfc(s.get("text", "").strip())
        if text:
            yield lang, sid, text


def _iter_gcbt_jsonl(path: Path) -> Iterator[Tuple[str, str, str]]:
    """Yield (lang_iso, sent_id, raw_text) from a gcbt .jsonl file."""
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed JSON at line %d in %s", lineno, path)
                continue
            if obj.get("_type") == "corpus_header":
                continue
            lang = obj.get("language_iso", obj.get("lang_iso", "und"))
            sid  = obj.get("sent_id", "")
            text = _nfc(obj.get("text", "").strip())
            if text:
                yield lang, sid, text


def _collect_input_files(input_path: Path) -> List[Path]:
    """Return a sorted list of readable .txt, .json, or .jsonl files."""
    if input_path.is_file():
        return [input_path]
    files = sorted(
        p for p in input_path.rglob("*")
        if p.is_file() and p.suffix in {".txt", ".json", ".jsonl"}
    )
    return files


def _batches(iterable, size: int):
    """Yield successive fixed-size batches from an iterable."""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


# ---------------------------------------------------------------------------
# PipelineStats — aggregate run statistics
# ---------------------------------------------------------------------------

@dataclass
class PipelineStats:
    """Accumulated statistics for one pipeline run.

    Attributes
    ----------
    lang_iso          : Language processed.
    files_processed   : Number of input files consumed.
    sentences_total   : Total sentences seen (including skipped).
    sentences_written : Sentences successfully written.
    sentences_skipped : Sentences skipped (checkpoint / empty).
    tokens_total      : Total word tokens processed.
    elapsed_seconds   : Wall-clock time for the run.
    writer_stats      : Stats dict returned by GobeloDualWriter.
    errors            : List of (file, error_message) tuples.
    """
    lang_iso           : str               = ""
    files_processed    : int               = 0
    sentences_total    : int               = 0
    sentences_written  : int               = 0
    sentences_skipped  : int               = 0
    tokens_total       : int               = 0
    elapsed_seconds    : float             = 0.0
    writer_stats       : Dict[str, Any]    = field(default_factory=dict)
    errors             : List[Tuple[str, str]] = field(default_factory=list)

    def sentences_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return round(self.sentences_written / self.elapsed_seconds, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lang_iso"          : self.lang_iso,
            "files_processed"   : self.files_processed,
            "sentences_total"   : self.sentences_total,
            "sentences_written" : self.sentences_written,
            "sentences_skipped" : self.sentences_skipped,
            "tokens_total"      : self.tokens_total,
            "elapsed_seconds"   : round(self.elapsed_seconds, 2),
            "sentences_per_sec" : self.sentences_per_second(),
            "writer_stats"      : self.writer_stats,
            "errors"            : self.errors,
        }

    def __repr__(self) -> str:
        return (
            f"PipelineStats(lang={self.lang_iso!r}, "
            f"sents={self.sentences_written}/{self.sentences_total}, "
            f"toks={self.tokens_total}, "
            f"{self.sentences_per_second()} sent/s)"
        )


# ---------------------------------------------------------------------------
# GobeloAnnotationPipeline
# ---------------------------------------------------------------------------

class GobeloAnnotationPipeline:
    """Four-stage annotation pipeline for the Gobelo Grammar Toolkit.

    Parameters
    ----------
    loader : GobeloGrammarLoader (or compatible mock)
        Provides the GGT YAML grammar for the target language.
    corpus_config : CorpusConfig, optional
        Corpus-level settings (clitics, false positives, etc.).
        If omitted, the tokeniser uses the loader defaults.
    batch_size : int
        Number of sentences to hold in memory before flushing (default 100).
    log_every : int
        Log a progress line every N sentences (default 500).  Set 0 to disable.

    Example
    -------
    ::
        loader = GobeloGrammarLoader("toi")
        pipeline = GobeloAnnotationPipeline(loader)

        pipeline.run(
            input_path  = "gcbt_output/toi/literature/",
            output_dir  = "annotated/",
            checkpoint  = True,
        )
    """

    VERSION = VERSION

    def __init__(
        self,
        loader=None,
        corpus_config=None,
        batch_size: int = 100,
        log_every: int = 500,
    ) -> None:
        self._loader = loader
        self._lang_iso = getattr(loader, "lang_iso", "und") if loader else "und"
        self._batch_size = batch_size
        self._log_every = log_every

        # Instantiate pipeline stages
        self._tokeniser = GobeloWordTokenizer(loader, corpus_config)
        self._tagger    = GobeloPOSTagger(loader)

        # Phase 2 (morph analyser) imported here to keep the file importable
        # without it during testing.
        try:
            from morph_analyser import GobelloMorphAnalyser
            self._analyser = GobelloMorphAnalyser(loader)
        except ImportError:
            logger.warning(
                "morph_analyser.py not found — morphological analysis will be "
                "skipped.  Place morph_analyser.py on the Python path."
            )
            self._analyser = None

    # ------------------------------------------------------------------ #
    # Public: single-sentence API
    # ------------------------------------------------------------------ #

    def run_sentence(self, text: str, sent_id: str = "") -> AnnotatedSentence:
        """Process a single raw sentence through all four stages.

        Parameters
        ----------
        text : str
            Raw sentence string.
        sent_id : str, optional
            Sentence identifier.  Auto-generated if omitted.

        Returns
        -------
        AnnotatedSentence
            Fully annotated sentence (mutated in place through each stage).
        """
        sentence = self._tokeniser.tokenize(text)
        if sent_id:
            sentence.sent_id = sent_id
        if self._analyser:
            sentence = self._analyser.analyse(sentence)
        sentence = self._tagger.tag(sentence)
        return sentence

    # ------------------------------------------------------------------ #
    # Public: corpus run API
    # ------------------------------------------------------------------ #

    def run(
        self,
        input_path   : str | Path,
        output_dir   : str | Path,
        lang_iso     : Optional[str]       = None,
        checkpoint   : bool                = False,
        append       : bool                = False,
        json_kwargs  : Optional[Dict]      = None,
        conllu_kwargs: Optional[Dict]      = None,
    ) -> PipelineStats:
        """Run the pipeline over an input directory or file.

        Parameters
        ----------
        input_path : str | Path
            A .txt / .json / .jsonl file, or a directory containing them.
        output_dir : str | Path
            Root output directory.  Will be created if it does not exist.
        lang_iso : str, optional
            Override the language ISO code.  If omitted, the code is read
            from the JSON metadata or inferred from the input directory name.
        checkpoint : bool
            Enable checkpoint/resume support.  Skips already-written sent_ids.
        append : bool
            Append to existing output files rather than overwriting.
        json_kwargs : dict, optional
            Extra keyword arguments forwarded to GobeloJsonWriter.
        conllu_kwargs : dict, optional
            Extra keyword arguments forwarded to GobeloCoNLLUWriter.

        Returns
        -------
        PipelineStats
            Run statistics.
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        effective_lang = lang_iso or self._lang_iso
        stats = PipelineStats(lang_iso=effective_lang)
        t_start = time.monotonic()

        # Checkpoint path
        ckpt_path: Optional[Path] = None
        if checkpoint:
            lang_annot_dir = output_dir / effective_lang / "annotations"
            lang_annot_dir.mkdir(parents=True, exist_ok=True)
            ckpt_path = lang_annot_dir / f"{effective_lang}_pipeline.checkpoint"

        # Collect files
        files = _collect_input_files(input_path)
        if not files:
            logger.warning("No readable input files found in %s", input_path)
            return stats

        logger.info(
            "GobeloAnnotationPipeline v%s | lang=%s | files=%d | batch=%d",
            self.VERSION, effective_lang, len(files), self._batch_size,
        )

        with GobeloDualWriter(
            output_dir=output_dir,
            lang_iso=effective_lang,
            append=append,
            checkpoint_path=ckpt_path,
            json_kwargs=json_kwargs or {},
            conllu_kwargs=conllu_kwargs or {},
        ) as writer:

            for filepath in files:
                logger.debug("Processing file: %s", filepath)
                try:
                    sentence_iter = self._iter_sentences(
                        filepath, effective_lang, lang_iso
                    )
                    for batch in _batches(sentence_iter, self._batch_size):
                        annotated = []
                        for file_lang, sid, text in batch:
                            stats.sentences_total += 1
                            try:
                                sent = self.run_sentence(text, sid)
                                # Override lang_iso if JSON provided one
                                if file_lang and file_lang != "und":
                                    sent.lang_iso = file_lang
                                    for tok in sent.tokens:
                                        tok.lang_iso = file_lang
                                annotated.append(sent)
                            except Exception as exc:
                                logger.error(
                                    "Error annotating sent %r in %s: %s",
                                    sid, filepath, exc
                                )
                                stats.errors.append((str(filepath), str(exc)))

                        written = writer.write_batch(annotated)
                        stats.sentences_written += written
                        stats.sentences_skipped += len(annotated) - written
                        for s in annotated:
                            stats.tokens_total += len(s.word_tokens())

                        if self._log_every and stats.sentences_written % self._log_every < self._batch_size:
                            logger.info(
                                "  Progress: %d sentences written (%.1f s)",
                                stats.sentences_written,
                                time.monotonic() - t_start,
                            )

                    stats.files_processed += 1

                except Exception as exc:
                    logger.error("Error processing file %s: %s", filepath, exc)
                    stats.errors.append((str(filepath), str(exc)))

            # Gather writer stats after close (DualWriter.close() is called
            # by the context manager __exit__)
            raw_ws = writer.stats()
            stats.writer_stats = {
                k: v.to_dict() for k, v in raw_ws.items()
            }

        stats.elapsed_seconds = time.monotonic() - t_start

        logger.info(
            "Pipeline complete: %d sentences in %.2fs (%s sent/s). "
            "Errors: %d.",
            stats.sentences_written,
            stats.elapsed_seconds,
            stats.sentences_per_second(),
            len(stats.errors),
        )

        # Write pipeline stats sidecar
        self._write_pipeline_stats(stats, output_dir, effective_lang)

        return stats

    # ------------------------------------------------------------------ #
    # Public: multi-language batch run
    # ------------------------------------------------------------------ #

    def run_all(
        self,
        manifest_path: str | Path,
        output_dir   : str | Path,
        loader_factory=None,
        checkpoint   : bool = False,
        workers      : int  = 1,
    ) -> Dict[str, PipelineStats]:
        """Run the pipeline over all languages listed in a corpus manifest.

        Parameters
        ----------
        manifest_path : str | Path
            Path to a gcbt ``corpus_manifest.json`` file.  Expected format::

                {
                  "languages": {
                    "toi": {"files": ["path/to/file1.json", ...]},
                    "bem": {"files": [...]}
                  }
                }

        output_dir : str | Path
            Root output directory.
        loader_factory : callable, optional
            ``loader_factory(lang_iso) → loader``.  If omitted, the pipeline
            reuses its own loader for all languages (only safe when all
            languages share a grammar — normally you pass a factory).
        checkpoint : bool
            Enable checkpoint/resume for each language.
        workers : int
            Number of parallel worker processes (default 1 = serial).

        Returns
        -------
        dict mapping lang_iso → PipelineStats
        """
        manifest = _load_manifest(manifest_path)
        all_stats: Dict[str, PipelineStats] = {}

        if workers <= 1:
            for lang_iso, lang_info in manifest.items():
                loader = loader_factory(lang_iso) if loader_factory else self._loader
                pipeline = GobeloAnnotationPipeline(
                    loader=loader,
                    batch_size=self._batch_size,
                    log_every=self._log_every,
                )
                for input_path in lang_info.get("files", []):
                    s = pipeline.run(
                        input_path=input_path,
                        output_dir=output_dir,
                        lang_iso=lang_iso,
                        checkpoint=checkpoint,
                        append=True,
                    )
                    if lang_iso in all_stats:
                        # Merge stats
                        all_stats[lang_iso].sentences_written += s.sentences_written
                        all_stats[lang_iso].sentences_total   += s.sentences_total
                        all_stats[lang_iso].tokens_total      += s.tokens_total
                        all_stats[lang_iso].files_processed   += s.files_processed
                        all_stats[lang_iso].errors            += s.errors
                    else:
                        all_stats[lang_iso] = s
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = {}
                for lang_iso, lang_info in manifest.items():
                    for input_path in lang_info.get("files", []):
                        fut = pool.submit(
                            _worker_run,
                            lang_iso=lang_iso,
                            input_path=str(input_path),
                            output_dir=str(output_dir),
                            batch_size=self._batch_size,
                            checkpoint=checkpoint,
                        )
                        futures[fut] = lang_iso
                for fut in as_completed(futures):
                    lang_iso = futures[fut]
                    try:
                        s = fut.result()
                        if lang_iso in all_stats:
                            all_stats[lang_iso].sentences_written += s.sentences_written
                            all_stats[lang_iso].sentences_total   += s.sentences_total
                            all_stats[lang_iso].tokens_total      += s.tokens_total
                            all_stats[lang_iso].files_processed   += s.files_processed
                            all_stats[lang_iso].errors            += s.errors
                        else:
                            all_stats[lang_iso] = s
                    except Exception as exc:
                        logger.error("Worker for %s failed: %s", lang_iso, exc)

        return all_stats

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def describe(self) -> str:
        """Return a human-readable summary of all pipeline stages."""
        lines = [
            f"GobeloAnnotationPipeline v{self.VERSION}",
            f"  lang_iso   : {self._lang_iso}",
            f"  batch_size : {self._batch_size}",
            "",
            "── Stage 1: GobeloWordTokenizer ──",
            self._tokeniser.describe()
            if hasattr(self._tokeniser, "describe") else "(no describe())",
            "",
            "── Stage 2: GobelloMorphAnalyser ──",
            self._analyser.describe()
            if self._analyser and hasattr(self._analyser, "describe")
            else "(not loaded)",
            "",
            "── Stage 3: GobeloPOSTagger ──",
            self._tagger.describe()
            if hasattr(self._tagger, "describe") else "(no describe())",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _iter_sentences(
        self,
        filepath  : Path,
        default_lang: str,
        lang_override: Optional[str],
    ) -> Iterator[Tuple[str, str, str]]:
        """Yield (lang_iso, sent_id, text) from a file regardless of format."""
        suffix = filepath.suffix.lower()
        if suffix == ".txt":
            for sid, text in _iter_txt(filepath):
                yield lang_override or default_lang, sid, text
        elif suffix == ".jsonl":
            for lang, sid, text in _iter_gcbt_jsonl(filepath):
                yield lang_override or lang or default_lang, sid, text
        elif suffix == ".json":
            for lang, sid, text in _iter_gcbt_json(filepath):
                yield lang_override or lang or default_lang, sid, text
        else:
            logger.debug("Skipping unsupported file type: %s", filepath)

    def _write_pipeline_stats(
        self,
        stats     : PipelineStats,
        output_dir: Path,
        lang_iso  : str,
    ) -> None:
        stats_dir = output_dir / lang_iso / "annotations"
        stats_dir.mkdir(parents=True, exist_ok=True)
        stats_path = stats_dir / f"{lang_iso}_pipeline_run.json"
        with stats_path.open("w", encoding="utf-8") as fh:
            json.dump(stats.to_dict(), fh, indent=2, ensure_ascii=False)
        logger.debug("Pipeline stats written to %s", stats_path)


# ---------------------------------------------------------------------------
# Worker function for multi-process runs
# ---------------------------------------------------------------------------

def _worker_run(
    lang_iso   : str,
    input_path : str,
    output_dir : str,
    batch_size : int,
    checkpoint : bool,
) -> PipelineStats:
    """Top-level function for ProcessPoolExecutor workers.

    Runs in a separate process; creates its own loader and pipeline instance.
    The loader is constructed via GobeloGrammarLoader if available.
    """
    try:
        from grammar_loader import GobeloGrammarLoader  # type: ignore
        loader = GobeloGrammarLoader(lang_iso)
    except ImportError:
        loader = None

    pipeline = GobeloAnnotationPipeline(loader=loader, batch_size=batch_size)
    return pipeline.run(
        input_path=input_path,
        output_dir=output_dir,
        lang_iso=lang_iso,
        checkpoint=checkpoint,
        append=True,
    )


# ---------------------------------------------------------------------------
# Manifest loader
# ---------------------------------------------------------------------------

def _load_manifest(manifest_path: str | Path) -> Dict[str, Dict]:
    """Load a gcbt corpus_manifest.json and return the languages dict."""
    p = Path(manifest_path)
    if not p.exists():
        raise FileNotFoundError(f"Manifest not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    # Support both {"languages": {...}} and bare {"lang": {...}}
    if "languages" in data:
        return data["languages"]
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class GobeloPipelineCLI:
    """Command-line interface for GobeloAnnotationPipeline.

    Mirrors the gcbt CLI patterns: --lang, --all, --list-langs,
    --workers, streaming, checkpoint.
    """

    def __init__(self) -> None:
        self._parser = self._build_parser()

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            prog="gobelo-annotate",
            description=(
                "Gobelo Grammar Toolkit — annotation pipeline.  "
                "Tokenise, morpheme-analyse, and POS-tag gcbt corpus output."
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Single language, from a gcbt .json file:
  python annotation_pipeline.py --lang toi --input gcbt_out/toi/ --output out/

  # All languages via corpus manifest:
  python annotation_pipeline.py --all --manifest corpus_manifest.json --output out/

  # List available languages in a manifest:
  python annotation_pipeline.py --list-langs --manifest corpus_manifest.json

  # Describe pipeline configuration for a language:
  python annotation_pipeline.py --lang toi --describe

  # Resume an interrupted run:
  python annotation_pipeline.py --lang toi --input ... --output out/ --checkpoint
""",
        )

        # ---- Mode flags ----
        mode = p.add_mutually_exclusive_group()
        mode.add_argument(
            "--lang",
            metavar="ISO",
            help="Process a single language (ISO 639-3 code, e.g. 'toi').",
        )
        mode.add_argument(
            "--all",
            action="store_true",
            help="Process all languages listed in --manifest.",
        )
        mode.add_argument(
            "--list-langs",
            action="store_true",
            dest="list_langs",
            help="List available languages in --manifest and exit.",
        )

        # --describe is orthogonal to --lang (not in the mutex group)
        p.add_argument(
            "--describe",
            action="store_true",
            help="Print pipeline configuration for --lang and exit.",
        )

        # ---- I/O ----
        p.add_argument(
            "--input", "-i",
            metavar="PATH",
            help="Input file or directory (gcbt .txt / .json / .jsonl output).",
        )
        p.add_argument(
            "--output", "-o",
            metavar="DIR",
            default="annotated_output",
            help="Root output directory (default: annotated_output/).",
        )
        p.add_argument(
            "--manifest",
            metavar="FILE",
            help="Path to gcbt corpus_manifest.json (required for --all / --list-langs).",
        )

        # ---- Grammar / config ----
        p.add_argument(
            "--grammar",
            metavar="FILE",
            help="Path to GGT YAML grammar file.  Overrides the default loader lookup.",
        )
        p.add_argument(
            "--corpus-config",
            metavar="FILE",
            dest="corpus_config",
            help="Path to corpus_config.yaml.",
        )

        # ---- Performance ----
        p.add_argument(
            "--workers", "-w",
            type=int,
            default=1,
            metavar="N",
            help="Number of parallel worker processes (default: 1).",
        )
        p.add_argument(
            "--batch-size",
            type=int,
            default=100,
            dest="batch_size",
            metavar="N",
            help="Sentences per processing batch (default: 100).",
        )

        # ---- Checkpoint / resume ----
        p.add_argument(
            "--checkpoint",
            action="store_true",
            help="Enable checkpoint/resume.  Skips already-written sentences.",
        )
        p.add_argument(
            "--append",
            action="store_true",
            help="Append to existing output files rather than overwriting.",
        )

        # ---- Output format ----
        p.add_argument(
            "--no-json",
            action="store_true",
            dest="no_json",
            help="Skip JSON-Lines output.",
        )
        p.add_argument(
            "--no-conllu",
            action="store_true",
            dest="no_conllu",
            help="Skip CoNLL-U output.",
        )
        p.add_argument(
            "--pretty",
            action="store_true",
            help="Pretty-print JSON output (indent=2).  Larger files.",
        )

        # ---- Logging ----
        p.add_argument(
            "--log-level",
            default="WARNING",
            dest="log_level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            help="Logging verbosity (default: WARNING).",
        )
        p.add_argument(
            "--log-every",
            type=int,
            default=500,
            dest="log_every",
            metavar="N",
            help="Log a progress line every N sentences (default: 500).",
        )

        return p

    # ------------------------------------------------------------------ #

    def run(self, argv: Optional[List[str]] = None) -> int:
        """Parse arguments and execute the requested operation.

        Returns an exit code (0 = success, 1 = error).
        """
        args = self._parser.parse_args(argv)
        _configure_logging(args.log_level)

        # ---- --list-langs ----
        if args.list_langs:
            return self._cmd_list_langs(args)

        # ---- --describe ----
        if args.describe:
            return self._cmd_describe(args)

        # ---- Validate common requirements ----
        if args.all and not args.manifest:
            self._parser.error("--all requires --manifest.")

        if args.lang and not args.input:
            self._parser.error("--lang requires --input.")

        # ---- Build loader + pipeline ----
        loader = _build_loader(args.lang, args.grammar)
        corpus_config = _build_corpus_config(args.corpus_config)

        pipeline = GobeloAnnotationPipeline(
            loader=loader,
            corpus_config=corpus_config,
            batch_size=args.batch_size,
            log_every=args.log_every,
        )

        # ---- --all ----
        if args.all:
            return self._cmd_all(args, pipeline)

        # ---- --lang (single language) ----
        return self._cmd_single(args, pipeline)

    # ------------------------------------------------------------------ #
    # Command handlers
    # ------------------------------------------------------------------ #

    def _cmd_list_langs(self, args) -> int:
        if not args.manifest:
            print("Error: --list-langs requires --manifest.", file=sys.stderr)
            return 1
        try:
            manifest = _load_manifest(args.manifest)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"Error reading manifest: {exc}", file=sys.stderr)
            return 1
        print(f"Languages in {args.manifest}:")
        for lang, info in sorted(manifest.items()):
            nfiles = len(info.get("files", []))
            print(f"  {lang}  ({nfiles} file{'s' if nfiles != 1 else ''})")
        return 0

    def _cmd_describe(self, args) -> int:
        if not args.lang:
            print("Error: --describe requires --lang.", file=sys.stderr)
            return 1
        loader = _build_loader(args.lang, args.grammar)
        corpus_config = _build_corpus_config(args.corpus_config)
        pipeline = GobeloAnnotationPipeline(loader=loader, corpus_config=corpus_config)
        print(pipeline.describe())
        return 0

    def _cmd_single(self, args, pipeline: GobeloAnnotationPipeline) -> int:
        json_kwargs   = {"indent": 2} if args.pretty else {}
        conllu_kwargs = {}

        stats = pipeline.run(
            input_path    = args.input,
            output_dir    = args.output,
            lang_iso      = args.lang,
            checkpoint    = args.checkpoint,
            append        = args.append,
            json_kwargs   = json_kwargs if not args.no_json else None,
            conllu_kwargs = conllu_kwargs if not args.no_conllu else None,
        )
        _print_stats(stats)
        return 0 if not stats.errors else 1

    def _cmd_all(self, args, pipeline: GobeloAnnotationPipeline) -> int:
        try:
            manifest = _load_manifest(args.manifest)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"Error reading manifest: {exc}", file=sys.stderr)
            return 1

        def loader_factory(lang_iso: str):
            return _build_loader(lang_iso, args.grammar)

        all_stats = pipeline.run_all(
            manifest_path  = args.manifest,
            output_dir     = args.output,
            loader_factory = loader_factory,
            checkpoint     = args.checkpoint,
            workers        = args.workers,
        )

        total_sents = sum(s.sentences_written for s in all_stats.values())
        print(f"\nAll-languages run complete: {total_sents} sentences across "
              f"{len(all_stats)} language(s).")
        for lang, s in sorted(all_stats.items()):
            print(f"  {lang}: {s.sentences_written} sents, {s.tokens_total} tokens "
                  f"({s.sentences_per_second()} sent/s)")
        return 0


# ---------------------------------------------------------------------------
# Loader / config factory helpers
# ---------------------------------------------------------------------------

def _build_loader(lang_iso: Optional[str], grammar_path: Optional[str]):
    """Attempt to build a GobeloGrammarLoader; fall back to NullLoader."""
    if lang_iso or grammar_path:
        try:
            from grammar_loader import GobeloGrammarLoader  # type: ignore
            if grammar_path:
                return GobeloGrammarLoader.from_file(grammar_path)
            return GobeloGrammarLoader(lang_iso)
        except ImportError:
            logger.debug(
                "grammar_loader.py not on path — using NullLoader.  "
                "Grammar-driven features will be disabled."
            )
    return None  # stages accept None and use _NullLoader internally


def _build_corpus_config(config_path: Optional[str]):
    """Attempt to load a CorpusConfig; return None if unavailable."""
    if not config_path:
        return None
    try:
        from corpus_config import CorpusConfig  # type: ignore
        return CorpusConfig.load(config_path)
    except (ImportError, FileNotFoundError) as exc:
        logger.warning("Could not load corpus config from %s: %s", config_path, exc)
        return None


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=getattr(logging, level.upper(), logging.WARNING),
    )


def _print_stats(stats: PipelineStats) -> None:
    print(
        f"\nPipeline run complete\n"
        f"  Language   : {stats.lang_iso}\n"
        f"  Files      : {stats.files_processed}\n"
        f"  Sentences  : {stats.sentences_written} written / "
        f"{stats.sentences_total} total\n"
        f"  Tokens     : {stats.tokens_total}\n"
        f"  Elapsed    : {stats.elapsed_seconds:.2f}s "
        f"({stats.sentences_per_second()} sent/s)\n"
        f"  Errors     : {len(stats.errors)}"
    )
    if stats.errors:
        print("  Error details:")
        for fp, msg in stats.errors[:5]:
            print(f"    {fp}: {msg}")
        if len(stats.errors) > 5:
            print(f"    … and {len(stats.errors) - 5} more.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    sys.exit(GobeloPipelineCLI().run(argv))


if __name__ == "__main__":
    main()
