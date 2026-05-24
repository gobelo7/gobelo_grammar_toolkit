#!/usr/bin/env python3
"""
ggtk/apps/dictionary_manager.py
================================
Community-driven dictionary manager for Gobelo lexicon data.

Manages per-language SQLite databases and CSV wordlists stored in
gobelo/data/lexicon/{iso_code}/. Supports both developer CLI usage and
programmatic access from a community web/app interface.

Entry structure
---------------
    entry_type      : str   — word | phrase | idiom | proverb
    word            : str   — the headword (required)
    language        : str   — ISO 639-3 code (e.g. "bem", "toi")
    dialect         : str   — regional dialect name or "" if standard
    definition      : str   — full definition in English
    part_of_speech  : str   — noun | verb | adj | adv | prep | conj | intj | pron
    pronunciation   : str   — IPA string or orthographic approximation
    usage_context   : str   — formal | informal | archaic | technical | colloquial
    difficulty_level: int   — 1 (basic) → 5 (advanced)
    example_sentence: str   — sentence in the target language
    cultural_notes  : str   — ethnographic or cultural context
    region          : str   — geographic region within Zambia
    is_offensive    : bool  — True if word is sensitive or offensive
    audio_url       : str   — URL to pronunciation audio file or ""

Operations
----------
    add, get, update, delete, lookup, list_all
    import_csv, export_csv
    merge (dedup across CSV imports)
    frequency_rank (word-frequency ordering from corpus counts)

Usage (CLI)
-----------
    python -m ggtk.apps.dictionary_manager lookup bem --word "umulandu"
    python -m ggtk.apps.dictionary_manager import_csv bem path/to/words.csv
    python -m ggtk.apps.dictionary_manager export_csv bem output.csv
    python -m ggtk.apps.dictionary_manager stats bem
    python -m ggtk.apps.dictionary_manager merge bem --source path/to/extra.csv
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional

# ── resolve lexicon root ───────────────────────────────────────────────────────
_GGTK_ROOT = Path(__file__).resolve().parent.parent
# Lexicon lives at gobelo/data/lexicon/ — two levels up from ggtk/
LEXICON_ROOT = _GGTK_ROOT.parent / "data" / "lexicon"

logger = logging.getLogger(__name__)

# ── Schema version — bump when columns change ──────────────────────────────────
_SCHEMA_VERSION = 1

# ── SQL ───────────────────────────────────────────────────────────────────────
_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type       TEXT    NOT NULL DEFAULT 'word',
    word             TEXT    NOT NULL,
    language         TEXT    NOT NULL,
    dialect          TEXT    NOT NULL DEFAULT '',
    definition       TEXT    NOT NULL DEFAULT '',
    part_of_speech   TEXT    NOT NULL DEFAULT '',
    pronunciation    TEXT    NOT NULL DEFAULT '',
    usage_context    TEXT    NOT NULL DEFAULT '',
    difficulty_level INTEGER NOT NULL DEFAULT 1,
    example_sentence TEXT    NOT NULL DEFAULT '',
    cultural_notes   TEXT    NOT NULL DEFAULT '',
    region           TEXT    NOT NULL DEFAULT '',
    is_offensive     INTEGER NOT NULL DEFAULT 0,
    audio_url        TEXT    NOT NULL DEFAULT '',
    frequency        INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_word     ON entries(word);
CREATE INDEX IF NOT EXISTS idx_language ON entries(language);
CREATE INDEX IF NOT EXISTS idx_pos      ON entries(part_of_speech);
CREATE INDEX IF NOT EXISTS idx_freq     ON entries(frequency DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_word_lang_dialect
    ON entries(word, language, dialect);

CREATE TRIGGER IF NOT EXISTS trg_updated_at
AFTER UPDATE ON entries FOR EACH ROW
BEGIN
    UPDATE entries SET updated_at = datetime('now') WHERE id = OLD.id;
END;
"""

# ── Dataclass ─────────────────────────────────────────────────────────────────

VALID_ENTRY_TYPES  = {"word", "phrase", "idiom", "proverb"}
VALID_POS          = {"noun", "verb", "adj", "adv", "prep", "conj", "intj", "pron", ""}
VALID_USAGE        = {"formal", "informal", "archaic", "technical", "colloquial", ""}


@dataclass
class DictionaryEntry:
    word:             str
    language:         str                    # ISO 639-3
    entry_type:       str        = "word"
    dialect:          str        = ""
    definition:       str        = ""
    part_of_speech:   str        = ""
    pronunciation:    str        = ""
    usage_context:    str        = ""
    difficulty_level: int        = 1
    example_sentence: str        = ""
    cultural_notes:   str        = ""
    region:           str        = ""
    is_offensive:     bool       = False
    audio_url:        str        = ""
    frequency:        int        = 0
    id:               Optional[int] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.word.strip():
            raise ValueError("'word' must not be empty.")
        if not self.language.strip():
            raise ValueError("'language' (ISO 639-3) must not be empty.")
        if self.entry_type not in VALID_ENTRY_TYPES:
            raise ValueError(
                f"entry_type '{self.entry_type}' invalid. "
                f"Choose from: {sorted(VALID_ENTRY_TYPES)}"
            )
        if self.part_of_speech not in VALID_POS:
            raise ValueError(
                f"part_of_speech '{self.part_of_speech}' invalid. "
                f"Choose from: {sorted(VALID_POS)}"
            )
        if self.usage_context not in VALID_USAGE:
            raise ValueError(
                f"usage_context '{self.usage_context}' invalid. "
                f"Choose from: {sorted(VALID_USAGE)}"
            )
        if not (1 <= self.difficulty_level <= 5):
            raise ValueError("difficulty_level must be between 1 and 5.")
        # Normalise
        self.language = self.language.lower().strip()
        self.word     = self.word.strip()

    def to_row(self) -> dict:
        d = asdict(self)
        d["is_offensive"] = int(d["is_offensive"])
        d.pop("id", None)
        return d

    @classmethod
    def from_row(cls, row: dict) -> "DictionaryEntry":
        row = dict(row)
        row["is_offensive"] = bool(row.get("is_offensive", 0))
        row.pop("created_at", None)
        row.pop("updated_at", None)
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})


# ── Manager ───────────────────────────────────────────────────────────────────

class DictionaryManager:
    """
    Manages the SQLite dictionary and CSV wordlists for one language.

    Parameters
    ----------
    iso_code : str
        ISO 639-3 language code (e.g. "bem", "toi").
    lexicon_root : Path, optional
        Override the default gobelo/data/lexicon/ root (useful for testing).
    """

    def __init__(self, iso_code: str, lexicon_root: Optional[Path] = None) -> None:
        from ggtk import resolve_language, LanguageNotFoundError
        try:
            self.iso_code = resolve_language(iso_code)
        except LanguageNotFoundError:
            # Allow unknown languages (e.g. tum) that are not yet in ggtk
            logger.warning("Language '%s' not in ggtk registry — proceeding anyway.", iso_code)
            self.iso_code = iso_code.lower().strip()

        root = (lexicon_root or LEXICON_ROOT) / self.iso_code
        root.mkdir(parents=True, exist_ok=True)

        self._db_path  = root / f"{self.iso_code}.db"
        self._csv_path = root / f"{self.iso_code}_words.csv"
        self._conn     = self._connect()

    # ── connection ────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript(_DDL)
        # Record schema version
        conn.execute(
            "INSERT OR IGNORE INTO schema_meta VALUES ('version', ?)",
            (str(_SCHEMA_VERSION),),
        )
        conn.commit()
        return conn

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "DictionaryManager":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add(self, entry: DictionaryEntry) -> int:
        """
        Insert a new entry. Returns the new row id.
        Raises sqlite3.IntegrityError if (word, language, dialect) already exists.
        """
        row = entry.to_row()
        cols   = ", ".join(row.keys())
        placeh = ", ".join(f":{k}" for k in row)
        cur = self._conn.execute(
            f"INSERT INTO entries ({cols}) VALUES ({placeh})", row
        )
        self._conn.commit()
        logger.debug("Added entry id=%d  word=%r", cur.lastrowid, entry.word)
        return cur.lastrowid

    def get(self, entry_id: int) -> Optional[DictionaryEntry]:
        """Return entry by id, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return DictionaryEntry.from_row(dict(row)) if row else None

    def update(self, entry_id: int, **fields) -> bool:
        """
        Update specific fields on an existing entry.
        Returns True if a row was updated.

        Example
        -------
        manager.update(42, definition="new definition", frequency=10)
        """
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields["_id"] = entry_id
        cur = self._conn.execute(
            f"UPDATE entries SET {set_clause} WHERE id = :_id", fields
        )
        self._conn.commit()
        return cur.rowcount > 0

    def delete(self, entry_id: int) -> bool:
        """Delete entry by id. Returns True if deleted."""
        cur = self._conn.execute(
            "DELETE FROM entries WHERE id = ?", (entry_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ── lookup ────────────────────────────────────────────────────────────────

    def lookup(
        self,
        word: str,
        dialect: Optional[str] = None,
        pos: Optional[str] = None,
    ) -> List[DictionaryEntry]:
        """
        Look up a word. Returns all matching entries sorted by frequency desc.

        Parameters
        ----------
        word    : exact headword to look up (case-insensitive)
        dialect : filter by dialect (optional)
        pos     : filter by part_of_speech (optional)
        """
        sql    = "SELECT * FROM entries WHERE lower(word) = lower(?)"
        params: list = [word]
        if dialect is not None:
            sql += " AND dialect = ?"
            params.append(dialect)
        if pos is not None:
            sql += " AND part_of_speech = ?"
            params.append(pos)
        sql += " ORDER BY frequency DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [DictionaryEntry.from_row(dict(r)) for r in rows]

    def search(self, query: str, limit: int = 20) -> List[DictionaryEntry]:
        """
        Prefix search across word and definition fields.
        Returns up to `limit` results ordered by frequency.
        """
        pattern = f"{query.lower()}%"
        rows = self._conn.execute(
            """
            SELECT * FROM entries
            WHERE lower(word) LIKE ? OR lower(definition) LIKE ?
            ORDER BY frequency DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
        return [DictionaryEntry.from_row(dict(r)) for r in rows]

    def list_all(self, order_by: str = "word") -> Iterator[DictionaryEntry]:
        """Iterate all entries ordered by `order_by` column."""
        allowed = {"word", "frequency", "part_of_speech", "difficulty_level", "created_at"}
        if order_by not in allowed:
            raise ValueError(f"order_by must be one of {allowed}")
        for row in self._conn.execute(
            f"SELECT * FROM entries ORDER BY {order_by}"
        ):
            yield DictionaryEntry.from_row(dict(row))

    # ── import / export ───────────────────────────────────────────────────────

    _CSV_FIELDS = [
        "entry_type", "word", "language", "dialect", "definition",
        "part_of_speech", "pronunciation", "usage_context", "difficulty_level",
        "example_sentence", "cultural_notes", "region", "is_offensive", "audio_url",
        "frequency",
    ]

    def import_csv(
        self,
        csv_path: Path,
        skip_errors: bool = True,
        on_conflict: str = "skip",
    ) -> tuple[int, int]:
        """
        Import entries from a CSV file.

        Parameters
        ----------
        csv_path    : path to CSV file (must have header row matching _CSV_FIELDS)
        skip_errors : if True, log bad rows and continue; if False, raise
        on_conflict : "skip" | "replace" — behaviour on duplicate (word, language, dialect)

        Returns
        -------
        (imported, skipped) counts
        """
        if on_conflict not in ("skip", "replace"):
            raise ValueError("on_conflict must be 'skip' or 'replace'")

        imported = skipped = 0
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for lineno, raw in enumerate(reader, start=2):
                try:
                    # Coerce types
                    raw["difficulty_level"] = int(raw.get("difficulty_level") or 1)
                    raw["is_offensive"]     = raw.get("is_offensive", "").lower() in (
                        "true", "1", "yes"
                    )
                    raw["frequency"]        = int(raw.get("frequency") or 0)
                    raw.setdefault("language", self.iso_code)
                    # Only keep known fields
                    filtered = {k: v for k, v in raw.items() if k in self._CSV_FIELDS}
                    entry = DictionaryEntry(**filtered)
                except Exception as exc:
                    msg = f"Row {lineno}: {exc}"
                    if skip_errors:
                        logger.warning("Import skip — %s", msg)
                        skipped += 1
                        continue
                    raise ValueError(msg) from exc

                try:
                    if on_conflict == "replace":
                        self._upsert(entry)
                    else:
                        self.add(entry)
                    imported += 1
                except sqlite3.IntegrityError:
                    logger.debug("Duplicate skip — word=%r dialect=%r", entry.word, entry.dialect)
                    skipped += 1

        logger.info("import_csv: %d imported, %d skipped from %s", imported, skipped, csv_path)
        return imported, skipped

    def _upsert(self, entry: DictionaryEntry) -> None:
        """Insert or replace on (word, language, dialect) conflict."""
        row    = entry.to_row()
        cols   = ", ".join(row.keys())
        placeh = ", ".join(f":{k}" for k in row)
        self._conn.execute(
            f"INSERT OR REPLACE INTO entries ({cols}) VALUES ({placeh})", row
        )
        self._conn.commit()

    def export_csv(self, csv_path: Optional[Path] = None) -> Path:
        """
        Export all entries to CSV.
        Defaults to gobelo/data/lexicon/{iso_code}/{iso_code}_words.csv.
        """
        out = csv_path or self._csv_path
        with open(out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self._CSV_FIELDS)
            writer.writeheader()
            for entry in self.list_all():
                row = entry.to_row()
                row["is_offensive"] = "true" if row["is_offensive"] else "false"
                writer.writerow({k: row[k] for k in self._CSV_FIELDS})
        logger.info("export_csv: wrote %s", out)
        return out

    # ── merge / dedup ─────────────────────────────────────────────────────────

    def merge(self, csv_path: Path) -> tuple[int, int]:
        """
        Merge entries from a CSV into the database, skipping exact duplicates
        on (word, language, dialect) and updating frequency if higher.

        Returns (merged, skipped) counts.
        """
        merged = skipped = 0
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                try:
                    raw["difficulty_level"] = int(raw.get("difficulty_level") or 1)
                    raw["is_offensive"]     = raw.get("is_offensive", "").lower() in (
                        "true", "1", "yes"
                    )
                    raw["frequency"]        = int(raw.get("frequency") or 0)
                    raw.setdefault("language", self.iso_code)
                    filtered = {k: v for k, v in raw.items() if k in self._CSV_FIELDS}
                    entry = DictionaryEntry(**filtered)
                except Exception as exc:
                    logger.warning("Merge skip invalid row: %s", exc)
                    skipped += 1
                    continue

                existing = self.lookup(entry.word, dialect=entry.dialect)
                if existing:
                    # Update frequency if incoming count is higher
                    ex = existing[0]
                    if entry.frequency > (ex.frequency or 0):
                        self.update(ex.id, frequency=entry.frequency)
                    skipped += 1
                else:
                    self.add(entry)
                    merged += 1

        return merged, skipped

    # ── frequency ranking ─────────────────────────────────────────────────────

    def frequency_rank(self, top_n: int = 100) -> List[DictionaryEntry]:
        """Return the top N entries by frequency descending."""
        rows = self._conn.execute(
            "SELECT * FROM entries ORDER BY frequency DESC LIMIT ?", (top_n,)
        ).fetchall()
        return [DictionaryEntry.from_row(dict(r)) for r in rows]

    def update_frequency(self, word: str, count: int, dialect: str = "") -> bool:
        """
        Set the frequency count for a word.
        Used when syncing corpus-derived frequency data.
        """
        cur = self._conn.execute(
            "UPDATE entries SET frequency = ? WHERE lower(word) = lower(?) AND dialect = ?",
            (count, word, dialect),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ── stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return aggregate statistics for the dictionary."""
        cur = self._conn.execute("""
            SELECT
                COUNT(*)                              AS total,
                COUNT(CASE WHEN frequency > 0 END)   AS with_frequency,
                COUNT(CASE WHEN audio_url != '' END)  AS with_audio,
                COUNT(CASE WHEN is_offensive = 1 END) AS offensive,
                COUNT(DISTINCT part_of_speech)        AS pos_types,
                COUNT(DISTINCT dialect)               AS dialects,
                COUNT(DISTINCT region)                AS regions
            FROM entries
        """)
        row = dict(cur.fetchone())
        row["iso_code"] = self.iso_code
        row["db_path"]  = str(self._db_path)
        return row


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_entry(e: DictionaryEntry) -> None:
    print(f"  [{e.id}] {e.word}  ({e.part_of_speech or '?'})  freq={e.frequency}")
    if e.definition:
        print(f"       def:     {e.definition}")
    if e.example_sentence:
        print(f"       example: {e.example_sentence}")
    if e.pronunciation:
        print(f"       IPA:     {e.pronunciation}")
    if e.dialect:
        print(f"       dialect: {e.dialect}  region: {e.region}")
    if e.is_offensive:
        print(f"       ⚠ marked offensive")


def main(argv: Optional[list] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Gobelo dictionary manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=[
        "lookup", "search", "add", "delete", "update",
        "import_csv", "export_csv", "merge", "stats", "top",
    ])
    parser.add_argument("iso_code",         help="ISO 639-3 language code (e.g. bem)")
    parser.add_argument("--word",           help="Headword")
    parser.add_argument("--definition",     default="")
    parser.add_argument("--pos",            default="", dest="part_of_speech")
    parser.add_argument("--dialect",        default="")
    parser.add_argument("--region",         default="")
    parser.add_argument("--pronunciation",  default="")
    parser.add_argument("--example",        default="", dest="example_sentence")
    parser.add_argument("--notes",          default="", dest="cultural_notes")
    parser.add_argument("--usage",          default="", dest="usage_context")
    parser.add_argument("--difficulty",     default=1,  type=int, dest="difficulty_level")
    parser.add_argument("--entry-type",     default="word", dest="entry_type")
    parser.add_argument("--offensive",      action="store_true", dest="is_offensive")
    parser.add_argument("--audio-url",      default="", dest="audio_url")
    parser.add_argument("--frequency",      default=0, type=int)
    parser.add_argument("--id",             type=int, help="Entry id (for update/delete)")
    parser.add_argument("--file",           type=Path, help="CSV path (for import/export/merge)")
    parser.add_argument("--top",            type=int, default=20, help="Top N for frequency rank")
    parser.add_argument("--on-conflict",    default="skip", choices=["skip", "replace"])
    parser.add_argument("--json",           action="store_true", help="Output as JSON")

    args = parser.parse_args(argv)

    with DictionaryManager(args.iso_code) as mgr:
        cmd = args.command

        if cmd == "lookup":
            if not args.word:
                print("--word required for lookup", file=sys.stderr); return 1
            results = mgr.lookup(args.word, dialect=args.dialect or None,
                                 pos=args.part_of_speech or None)
            if args.json:
                print(json.dumps([asdict(e) for e in results], indent=2, default=str))
            else:
                if not results:
                    print(f"  No entries found for '{args.word}'")
                for e in results:
                    _print_entry(e)

        elif cmd == "search":
            if not args.word:
                print("--word required for search", file=sys.stderr); return 1
            results = mgr.search(args.word, limit=args.top)
            if args.json:
                print(json.dumps([asdict(e) for e in results], indent=2, default=str))
            else:
                for e in results:
                    _print_entry(e)

        elif cmd == "add":
            if not args.word:
                print("--word required", file=sys.stderr); return 1
            entry = DictionaryEntry(
                word=args.word, language=args.iso_code,
                entry_type=args.entry_type, dialect=args.dialect,
                definition=args.definition, part_of_speech=args.part_of_speech,
                pronunciation=args.pronunciation, usage_context=args.usage_context,
                difficulty_level=args.difficulty_level,
                example_sentence=args.example_sentence,
                cultural_notes=args.cultural_notes, region=args.region,
                is_offensive=args.is_offensive, audio_url=args.audio_url,
                frequency=args.frequency,
            )
            new_id = mgr.add(entry)
            print(f"  Added entry id={new_id}  word={args.word!r}")

        elif cmd == "delete":
            if not args.id:
                print("--id required for delete", file=sys.stderr); return 1
            ok = mgr.delete(args.id)
            print(f"  {'Deleted' if ok else 'Not found'} entry id={args.id}")

        elif cmd == "update":
            if not args.id:
                print("--id required for update", file=sys.stderr); return 1
            fields = {k: v for k, v in vars(args).items()
                      if k in DictionaryEntry.__dataclass_fields__
                      and k not in ("word", "language", "id")
                      and v not in (None, "", 0, False)}
            ok = mgr.update(args.id, **fields)
            print(f"  {'Updated' if ok else 'Not found'} entry id={args.id}")

        elif cmd == "import_csv":
            if not args.file:
                print("--file required for import_csv", file=sys.stderr); return 1
            imp, skp = mgr.import_csv(args.file, on_conflict=args.on_conflict)
            print(f"  Imported {imp}, skipped {skp}")

        elif cmd == "export_csv":
            out = mgr.export_csv(args.file)
            print(f"  Exported to {out}")

        elif cmd == "merge":
            if not args.file:
                print("--file required for merge", file=sys.stderr); return 1
            mrg, skp = mgr.merge(args.file)
            print(f"  Merged {mrg} new entries, skipped {skp} duplicates")

        elif cmd == "stats":
            s = mgr.stats()
            if args.json:
                print(json.dumps(s, indent=2))
            else:
                print(f"  Language:      {s['iso_code']}")
                print(f"  DB:            {s['db_path']}")
                print(f"  Total entries: {s['total']}")
                print(f"  With frequency:{s['with_frequency']}")
                print(f"  With audio:    {s['with_audio']}")
                print(f"  Offensive:     {s['offensive']}")
                print(f"  POS types:     {s['pos_types']}")
                print(f"  Dialects:      {s['dialects']}")
                print(f"  Regions:       {s['regions']}")

        elif cmd == "top":
            results = mgr.frequency_rank(top_n=args.top)
            if args.json:
                print(json.dumps([asdict(e) for e in results], indent=2, default=str))
            else:
                for i, e in enumerate(results, 1):
                    print(f"  {i:>3}. {e.word:<20} freq={e.frequency}  ({e.part_of_speech})")

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())

