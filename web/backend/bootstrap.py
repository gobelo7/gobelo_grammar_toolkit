"""
web/backend/bootstrap.py — Package and path resolution for Gobelo Grammar Toolkit.

Extracted from app.py. Provides four public functions:
    resolve_package()        — ensures gobelo_grammar_toolkit is importable
    resolve_grammar_dir()    — returns Path to languages/*.yaml, or None
    resolve_frontend()       — returns Path to student/teacher index.html
    resolve_admin_frontend() — returns Path to compiled admin shell, or None

PATH RESOLUTION — four strategies tried in order:
  1. GGT_ROOT env var
  2. Pip-installed package (importlib.resources)
  3. Upward directory search from this file
  4. Dev sandbox layout: <this file>/../../ggt/
"""
from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
_PKG  = "gobelo_grammar_toolkit"

_GRAMMAR_DIR: Optional[Path] = None
_env_root: str = os.environ.get("GGT_ROOT", "").strip()


def _find_package_root() -> Optional[Path]:
    """Walk upward from this file to find the dir that contains gobelo_grammar_toolkit/."""
    current = _HERE
    for _ in range(10):
        if (current / _PKG).is_dir():
            return current
        for sub in ("ggt", "src", "lib"):
            if (current / sub / _PKG).is_dir():
                return current / sub
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def resolve_package() -> None:
    """
    Ensure gobelo_grammar_toolkit is importable, setting _GRAMMAR_DIR as a side effect.
    Raises ImportError with actionable instructions if all four strategies fail.
    """
    global _GRAMMAR_DIR

    # Strategy 1: explicit GGT_ROOT environment variable
    if _env_root:
        env_path = Path(_env_root)
        if str(env_path) not in sys.path:
            sys.path.insert(0, str(env_path))

    # Strategy 2: pip-installed — try import directly
    try:
        import gobelo_grammar_toolkit as _chk  # noqa: F401
        del _chk
        try:
            import importlib.resources as _ir
            _lang_pkg = _ir.files(_PKG + ".languages")
            _GRAMMAR_DIR = Path(str(_lang_pkg))
        except Exception:
            pkg_root = _find_package_root()
            if pkg_root:
                candidate = pkg_root / _PKG / "languages"
                if candidate.is_dir():
                    _GRAMMAR_DIR = candidate
        return
    except ImportError:
        pass

    # Strategy 3: upward search
    found = _find_package_root()
    if found:
        sys.path.insert(0, str(found))
        _GRAMMAR_DIR = found / _PKG / "languages"
        return

    # Strategy 4: dev sandbox layout
    dev = _HERE.parent.parent / "ggt"
    if dev.is_dir():
        sys.path.insert(0, str(dev))
        _GRAMMAR_DIR = dev / _PKG / "languages"
        return

    raise ImportError(
        "\n\n"
        "  gobelo_grammar_toolkit not found.\n\n"
        "  Tried:\n"
        "    1. GGT_ROOT environment variable — not set\n"
        "    2. Installed package             — not found\n"
        f"   3. Upward search from {_HERE}\n"
        f"      — gobelo_grammar_toolkit/ not found in any parent directory\n"
        f"   4. Dev layout ({_HERE.parent.parent / 'ggt'}) — not found\n\n"
        "  Fix (choose one):\n"
        "    a) Install from the repo root:  pip install -e .\n"
        "    b) Set GGT_ROOT to the dir that CONTAINS gobelo_grammar_toolkit/\n"
        "         Linux:   export GGT_ROOT=/path/to/src\n"
        "         Windows: set GGT_ROOT=C:\\path\\to\\src\n"
        "    c) Add to PYTHONPATH:\n"
        "         Linux:   export PYTHONPATH=/path/to/src:$PYTHONPATH\n"
        "         Windows: set PYTHONPATH=C:\\path\\to\\src;%PYTHONPATH%\n"
    )


def resolve_grammar_dir() -> Optional[Path]:
    """Return the resolved languages/ directory, or None (loader uses embedded package data)."""
    return _GRAMMAR_DIR


def resolve_frontend() -> Path:
    """
    Locate the student/teacher frontend (ggt_index_v1.html served as index.html).
    Falls back to _HERE so Flask 404s clearly rather than crashing.
    """
    candidates = [
        _HERE.parent / "frontend",
        _HERE,
        _HERE.parent,
        _HERE.parent.parent / "web" / "frontend",
        _HERE.parent.parent / "frontend",
    ]
    if _env_root:
        r = Path(_env_root)
        candidates += [
            r.parent / "web" / "frontend",
            r.parent / "web" / "backend",
        ]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    return _HERE


def resolve_admin_frontend() -> Optional[Path]:
    """
    Locate the compiled linguist admin shell (Vite dist/index.html).
    Returns None if not yet built — the /admin route will return a 503.
    """
    candidates = [
        _HERE.parent / "admin" / "dist",
        _HERE.parent / "admin",
        _HERE.parent.parent / "web" / "admin" / "dist",
    ]
    if _env_root:
        r = Path(_env_root)
        candidates += [r.parent / "web" / "admin" / "dist"]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    return None
