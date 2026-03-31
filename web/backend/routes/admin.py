"""
web/backend/routes/admin.py — Linguist-only admin API.

New routes for the React admin shell. All endpoints are under /admin/api/
(the Blueprint is registered with url_prefix="/admin" in create_app).

Auth: every request must carry the X-Admin-Token header matching
ADMIN_TOKEN in the Flask app config (set via the GGT_ADMIN_TOKEN env var).

Routes
──────
GET  /admin/api/languages                    list all registered languages
GET  /admin/api/languages/<lang>/yaml        read raw YAML for a language
PUT  /admin/api/languages/<lang>/yaml        write updated YAML (flushes cache)
POST /admin/api/languages/<lang>/validate    run the CLI validator, return results
GET  /admin/api/verify-flags/<lang>          same as public, but with ?resolved= filter
POST /admin/api/verify-flags/<lang>/<field>  mark a verify-flag as resolved
GET  /admin/api/cache                        show what is loaded in the in-process cache
POST /admin/api/cache/flush                  flush entire cache (or ?lang=<lang> for one)
POST /admin/api/hfst/build/<lang>            run build_hfst.sh, stream output as text
GET  /admin/api/routes                       list all registered Flask routes
"""
from __future__ import annotations
import subprocess, traceback
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

import cache as _cache_module
from cache import get_loader, flush, cache_status
from bootstrap import resolve_grammar_dir

from gobelo_grammar_toolkit.core.registry   import list_languages
from gobelo_grammar_toolkit.core.exceptions import GGTError, LanguageNotFoundError

admin_bp = Blueprint("admin", __name__)

_HERE = Path(__file__).resolve().parent.parent   # web/backend/


# ── auth ──────────────────────────────────────────────────────────────

@admin_bp.before_request
def _require_token():
    expected = current_app.config.get("ADMIN_TOKEN", "")
    if not expected:
        # Token not configured — block all admin access until it is set.
        return _err("Admin token not configured on server. Set GGT_ADMIN_TOKEN env var.", "misconfigured", 503)
    if request.headers.get("X-Admin-Token", "") != expected:
        return _err("Invalid or missing X-Admin-Token header.", "unauthorized", 401)


# ── response helpers ──────────────────────────────────────────────────

def _ok(data, status=200):
    return jsonify({"status": "ok", "data": data}), status

def _err(msg, code="error", status=400):
    return jsonify({"status": "error", "code": code, "message": msg}), status


# ── language management ───────────────────────────────────────────────

@admin_bp.route("/api/languages")
def ra_languages():
    """List all registered languages with metadata summary."""
    langs = list_languages()
    summary = []
    for lang in langs:
        try:
            lo = get_loader(lang)
            m  = lo.get_metadata()
            summary.append({
                "language":         lang,
                "grammar_version":  m.grammar_version,
                "noun_class_count": len(lo.get_noun_classes(active_only=False)),
                "unresolved_flags": len(lo.list_verify_flags()),
                "tam_count":        len(lo.get_tam_markers()),
                "extension_count":  len(lo.get_extensions()),
            })
        except Exception as e:
            summary.append({"language": lang, "error": str(e)})
    return _ok({"languages": summary})


@admin_bp.route("/api/languages/<lang>/yaml", methods=["GET"])
def ra_yaml_read(lang):
    """Return the raw YAML text for a language file."""
    grammar_dir = resolve_grammar_dir()
    if grammar_dir is None:
        return _err("Grammar directory not resolved — cannot read YAML directly.", "unavailable", 503)
    yaml_path = Path(grammar_dir) / f"{lang}.yaml"
    if not yaml_path.exists():
        return _err(f"No YAML file found for '{lang}'.", "not_found", 404)
    return Response(yaml_path.read_text(encoding="utf-8"), mimetype="text/plain; charset=utf-8")


@admin_bp.route("/api/languages/<lang>/yaml", methods=["PUT"])
def ra_yaml_write(lang):
    """
    Overwrite the YAML file for a language and flush its cache entry.
    Body: raw YAML text (Content-Type: text/plain or application/octet-stream).
    The caller is responsible for sending valid YAML — no pre-validation here.
    """
    grammar_dir = resolve_grammar_dir()
    if grammar_dir is None:
        return _err("Grammar directory not resolved — cannot write YAML.", "unavailable", 503)
    yaml_path = Path(grammar_dir) / f"{lang}.yaml"
    content   = request.get_data(as_text=True)
    if not content.strip():
        return _err("Request body is empty.", "validation", 422)
    try:
        yaml_path.write_text(content, encoding="utf-8")
        flush(lang)   # evict stale loader so the next request re-reads from disk
        return _ok({"language": lang, "bytes_written": len(content.encode())})
    except OSError as e:
        return _err(f"Could not write file: {e}", "io_error", 500)


# ── validation ────────────────────────────────────────────────────────

@admin_bp.route("/api/languages/<lang>/validate", methods=["POST"])
def ra_validate_yaml(lang):
    """
    Run scripts/validate_grammar.py for a language and return structured results.
    Assumes the script lives two levels above web/backend/.
    """
    script = _HERE.parent.parent / "scripts" / "validate_grammar.py"
    if not script.exists():
        return _err(f"Validator script not found at {script}.", "not_found", 404)
    try:
        result = subprocess.run(
            ["python", str(script), lang],
            capture_output=True, text=True, timeout=60
        )
        return _ok({
            "language":   lang,
            "returncode": result.returncode,
            "stdout":     result.stdout,
            "stderr":     result.stderr,
            "passed":     result.returncode == 0,
        })
    except subprocess.TimeoutExpired:
        return _err("Validator timed out after 60 s.", "timeout", 504)
    except Exception as e:
        traceback.print_exc()
        return _err(str(e), "internal", 500)


# ── verify-flags (admin write variant) ───────────────────────────────

@admin_bp.route("/api/verify-flags/<lang>")
def ra_verify_flags(lang):
    """Same as public verify-flags but accepts ?resolved=true|false filter."""
    resolved_filter = request.args.get("resolved", "").lower()
    prefix          = (request.args.get("field") or "").strip()
    try:
        flags = get_loader(lang).list_verify_flags()
        if prefix:
            flags = [f for f in flags if f.field_path.startswith(prefix)]
        if resolved_filter == "true":
            flags = [f for f in flags if f.resolved]
        elif resolved_filter == "false":
            flags = [f for f in flags if not f.resolved]
        return _ok({
            "language":         lang,
            "unresolved_count": sum(1 for f in flags if not f.resolved),
            "flags": [
                {"field_path": f.field_path, "current_value": f.current_value,
                 "note": f.note, "suggested_source": f.suggested_source,
                 "resolved": f.resolved}
                for f in flags
            ],
        })
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)


# ── cache management ──────────────────────────────────────────────────

@admin_bp.route("/api/cache")
def ra_cache_status():
    """Return which languages and service types are currently warm in the cache."""
    return _ok({"cache": cache_status()})


@admin_bp.route("/api/cache/flush", methods=["POST"])
def ra_cache_flush():
    """Flush one language (?lang=<lang>) or the entire cache."""
    lang = (request.args.get("lang") or "").strip() or None
    flush(lang)
    return _ok({"flushed": lang or "all"})


# ── HFST build ────────────────────────────────────────────────────────

@admin_bp.route("/api/hfst/build/<lang>", methods=["POST"])
def ra_hfst_build(lang):
    """
    Run scripts/build_hfst.sh for a language and stream stdout line-by-line.
    The response is text/plain; the admin shell can display it in a log panel.
    """
    script = _HERE.parent.parent / "scripts" / "build_hfst.sh"
    if not script.exists():
        return _err(f"Build script not found at {script}.", "not_found", 404)

    def generate():
        try:
            proc = subprocess.Popen(
                ["bash", str(script), lang],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in proc.stdout:
                yield line
            proc.wait()
            yield f"\n[exit code {proc.returncode}]\n"
        except Exception as e:
            yield f"\n[error: {e}]\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain",
        headers={"X-Content-Type-Options": "nosniff"},
    )


# ── route introspection ───────────────────────────────────────────────

@admin_bp.route("/api/routes")
def ra_routes():
    """List all registered Flask routes — useful for the admin dashboard."""
    rules = []
    for rule in current_app.url_map.iter_rules():
        rules.append({
            "endpoint": rule.endpoint,
            "methods":  sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS")),
            "path":     rule.rule,
        })
    rules.sort(key=lambda r: r["path"])
    return _ok({"routes": rules, "count": len(rules)})
