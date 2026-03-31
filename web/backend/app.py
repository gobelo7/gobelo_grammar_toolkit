"""
web/backend/app.py — Gobelo Grammar Toolkit API (Flask 3)

Run:
    python app.py               (dev, port 5000)
    python app.py --port 8080

Environment variables:
    GGT_ROOT          Directory that contains gobelo_grammar_toolkit/
    GGT_ADMIN_TOKEN   Secret token required for all /admin/* requests
                      (set to any non-empty string before starting)
"""
from __future__ import annotations
import os, argparse
from pathlib import Path

# ── 1. Resolve package location before any GGT imports ───────────────
from bootstrap import (
    resolve_package,
    resolve_grammar_dir,
    resolve_frontend,
    resolve_admin_frontend,
)
resolve_package()   # mutates sys.path and sets _GRAMMAR_DIR inside bootstrap

# ── 2. Flask and blueprints ───────────────────────────────────────────
from flask import Flask, jsonify, request, send_from_directory

from cache import init_cache
from routes.public import public_bp
from routes.admin  import admin_bp


def create_app() -> Flask:
    frontend       = resolve_frontend()
    admin_frontend = resolve_admin_frontend()   # None if Vite build not yet run

    app = Flask(__name__, static_folder=str(frontend), static_url_path="")
    app.config["ADMIN_TOKEN"] = os.environ.get("GGT_ADMIN_TOKEN", "")

    init_cache(resolve_grammar_dir())

    # ── Blueprints ────────────────────────────────────────────────────
    app.register_blueprint(public_bp)                       # /api/*
    app.register_blueprint(admin_bp, url_prefix="/admin")   # /admin/api/*

    # ── CORS ──────────────────────────────────────────────────────────
    # Public routes: open (student/teacher UI may be served from any origin)
    # Admin routes:  restricted to localhost dev ports + optional prod origin
    _admin_origins = {
        o for o in [
            "http://localhost:5173",
            "http://localhost:5174",
            os.environ.get("GGT_ADMIN_ORIGIN", "").strip(),
        ] if o
    }

    @app.after_request
    def _cors(r):
        origin = request.headers.get("Origin", "")
        if request.path.startswith("/admin"):
            if origin in _admin_origins:
                r.headers["Access-Control-Allow-Origin"] = origin
                r.headers["Vary"] = "Origin"
        else:
            r.headers["Access-Control-Allow-Origin"] = "*"
        r.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Admin-Token"
        r.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,OPTIONS"
        return r

    @app.route("/api/<path:_>",   methods=["OPTIONS"])
    @app.route("/admin/<path:_>", methods=["OPTIONS"])
    def _preflight(_): return "", 204

    # ── Static: student/teacher frontend ─────────────────────────────
    @app.route("/")
    def root():
        return send_from_directory(str(frontend), "index.html")

    # ── Static: linguist admin shell (SPA) ───────────────────────────
    @app.route("/admin", defaults={"path": ""})
    @app.route("/admin/<path:path>")
    def admin_shell(path):
        if admin_frontend is None:
            return jsonify({"status": "error", "message":
                "Admin shell not built yet. Run: cd web/admin && npm run build"}), 503
        target = Path(admin_frontend) / path
        if path and target.exists():
            return send_from_directory(str(admin_frontend), path)
        return send_from_directory(str(admin_frontend), "index.html")

    # ── 404 handler ───────────────────────────────────────────────────
    @app.errorhandler(404)
    def e404(e):
        if request.path.startswith(("/api/", "/admin/api/")):
            return jsonify({"status": "error", "code": "not_found",
                            "message": "Not found"}), 404
        return send_from_directory(str(frontend), "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    from gobelo_grammar_toolkit.core.registry import list_languages
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    admin_frontend = resolve_admin_frontend()
    print(f"\nGobelo API      →  http://localhost:{args.port}/")
    print(f"Student UI      →  {resolve_frontend()}")
    print(f"Admin UI        →  {admin_frontend or '(not built — run: cd web/admin && npm run build)'}")
    print(f"Grammars        →  {resolve_grammar_dir() or '(embedded package data)'}")
    print(f"Languages       →  {list_languages()}")
    print(f"Admin token set →  {'yes' if app.config['ADMIN_TOKEN'] else 'NO — set GGT_ADMIN_TOKEN before use'}\n")

    app.run(host=args.host, port=args.port, debug=True)
