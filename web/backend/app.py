"""
web/backend/app.py — Gobelo Grammar Toolkit REST API (Flask 3)
Run:  python app.py            (dev, port 5000)
      python app.py --port 8080

PATH RESOLUTION — the server locates gobelo_grammar_toolkit automatically.
Four strategies are tried in order:

  1. GGT_ROOT env var  — set this to the directory that CONTAINS gobelo_grammar_toolkit/
       Windows:  set GGT_ROOT=C:/corpus/apps/gobelo_grammar_toolkit/src
       Linux:    export GGT_ROOT=/home/user/gobelo/src

  2. Pip-installed     — works if installed with: pip install -e .

  3. Upward directory search — walks up from app.py looking for gobelo_grammar_toolkit/
       Handles src-layout, flat layout, monorepo layouts automatically.

  4. Dev sandbox layout — checks <app.py>/../../ggt/ (internal dev only)

If all four fail, a clear error message explains exactly what to do.
"""
from __future__ import annotations
import os, sys, argparse, traceback
from pathlib import Path
from typing import Any, Dict, Optional

_HERE = Path(__file__).resolve().parent
_PKG  = "gobelo_grammar_toolkit"


def _find_package_root() -> "Optional[Path]":
    """Walk upward from app.py to find the directory that contains gobelo_grammar_toolkit/."""
    current = _HERE
    for _ in range(10):
        if (current / _PKG).is_dir():
            return current
        for sub in ("ggt", "src", "lib"):          # handle nested layouts
            if (current / sub / _PKG).is_dir():
                return current / sub
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


# ── Strategy 1: explicit GGT_ROOT environment variable ───────────────
_env_root = os.environ.get("GGT_ROOT", "").strip()
if _env_root:
    _env_path = Path(_env_root)
    if str(_env_path) not in sys.path:
        sys.path.insert(0, str(_env_path))

# ── Strategy 2: try import (works for pip-installed packages) ────────
try:
    import gobelo_grammar_toolkit as _ggt_check  # noqa: F401
    del _ggt_check
    # Package is importable. Find the languages/ directory using importlib.resources
    # so it works correctly for both normal installs and editable installs (pip install -e .).
    _GRAMMAR_DIR: Optional[Path] = None
    try:
        import importlib.resources as _ir
        # Python 3.9+ path
        _lang_pkg = _ir.files(_PKG + ".languages")
        _GRAMMAR_DIR = Path(str(_lang_pkg))
    except Exception:
        # Fallback: locate via filesystem search
        _pkg_root = _find_package_root()
        if _pkg_root:
            _candidate = _pkg_root / _PKG / "languages"
            if _candidate.is_dir():
                _GRAMMAR_DIR = _candidate

except ImportError:
    # ── Strategy 3: upward search ────────────────────────────────────
    _found = _find_package_root()
    if _found:
        sys.path.insert(0, str(_found))
        _GRAMMAR_DIR = _found / _PKG / "languages"
    else:
        # ── Strategy 4: dev sandbox layout ───────────────────────────
        _dev = _HERE.parent.parent / "ggt"
        if _dev.is_dir():
            sys.path.insert(0, str(_dev))
            _GRAMMAR_DIR = _dev / _PKG / "languages"
        else:
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
                "    a) Install the package from the repo root:\n"
                "         pip install -e .\n\n"
                "    b) Set GGT_ROOT to the directory that CONTAINS gobelo_grammar_toolkit/\n"
                "         Windows:  set GGT_ROOT=C:\\path\\to\\src\n"
                "         Linux:    export GGT_ROOT=/path/to/src\n\n"
                "    c) Add the package directory to PYTHONPATH:\n"
                "         Windows:  set PYTHONPATH=C:\\path\\to\\src;%PYTHONPATH%\n"
                "         Linux:    export PYTHONPATH=/path/to/src:$PYTHONPATH\n"
            )

from flask import Flask, jsonify, request, send_from_directory, Response
from gobelo_grammar_toolkit.core.config      import GrammarConfig
from gobelo_grammar_toolkit.core.loader      import GobeloGrammarLoader
from gobelo_grammar_toolkit.core.registry    import list_languages, is_registered
from gobelo_grammar_toolkit.core.exceptions  import GGTError, LanguageNotFoundError
from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphologicalAnalyzer, MorphFeatureBundle
from gobelo_grammar_toolkit.apps.paradigm_generator     import ParadigmGenerator
from gobelo_grammar_toolkit.apps.concord_generator      import ConcordGenerator
from gobelo_grammar_toolkit.apps.corpus_annotator       import CorpusAnnotator
from gobelo_grammar_toolkit.apps.ud_feature_mapper      import UDFeatureMapper
from gobelo_grammar_toolkit.apps.verb_slot_validator    import VerbSlotValidator

# ── Frontend directory resolution ────────────────────────────────────────────
# index.html may be in a different directory from app.py depending on the
# project layout. We search several common locations in order.
def _find_frontend() -> Path:
    """Locate the directory containing index.html."""
    candidates = [
        _HERE.parent / "frontend",                # canonical: web/frontend/ (per project spec)
        _HERE,                                    # fallback: same dir as app.py
        _HERE.parent,                             # fallback: web/ folder
        _HERE.parent.parent / "web" / "frontend", # fallback: src/../web/frontend
        _HERE.parent.parent / "frontend",         # fallback: src/../frontend
    ]
    # Also check GGT_ROOT-relative paths
    if _env_root:
        r = Path(_env_root)
        candidates += [
            r.parent / "web" / "frontend",
            r.parent / "web" / "backend",
        ]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    # Not found — return _HERE and let Flask give the user a clear message
    return _HERE

_FRONTEND = _find_frontend()

app = Flask(__name__, static_folder=str(_FRONTEND), static_url_path="")

# _GRAMMAR_DIR is set in the bootstrap above; default to None if not set
if "_GRAMMAR_DIR" not in dir():
    _GRAMMAR_DIR = None

# ── cache ─────────────────────────────────────────────────────────────
_cache: Dict[str, Dict[str, Any]] = {}

def _slot(lang, key, factory):
    _cache.setdefault(lang, {})
    if key not in _cache[lang]:
        _cache[lang][key] = factory()
    return _cache[lang][key]

def _override(lang) -> "Optional[str]":
    """Return path to a grammar YAML override file, or None to let the loader use its embedded path."""
    if _GRAMMAR_DIR is None:
        return None
    p = Path(_GRAMMAR_DIR) / f"{lang}.yaml"
    if p.exists():
        return str(p)
    # File not found at the computed path — return None so the loader
    # falls back to importlib.resources (the embedded package data).
    return None

def _loader(lang) -> GobeloGrammarLoader:
    def make():
        if not is_registered(lang):
            raise LanguageNotFoundError(language=lang, available_languages=list_languages())
        override = _override(lang)
        try:
            return GobeloGrammarLoader(GrammarConfig(language=lang, override_path=override))
        except FileNotFoundError:
            # Grammar YAML not found — give a precise actionable message
            lang_dir = (_GRAMMAR_DIR or Path("gobelo_grammar_toolkit/languages"))
            raise FileNotFoundError(
                f"Grammar YAML for '{lang}' not found.\n"
                f"Expected location: {lang_dir}\\{lang}.yaml\n\n"
                f"Fix: copy the grammar YAML files into that directory.\n"
                f"Download grammar_yaml_files.zip from the project outputs,\n"
                f"extract all .yaml files into:\n"
                f"  {lang_dir}\\"
            )
    return _slot(lang, "loader", make)

def _analyzer(lang)  -> MorphologicalAnalyzer: return _slot(lang,"az", lambda: MorphologicalAnalyzer(_loader(lang)))
def _generator(lang) -> ParadigmGenerator:     return _slot(lang,"pg", lambda: ParadigmGenerator(_loader(lang)))
def _cg(lang)        -> ConcordGenerator:      return _slot(lang,"cg", lambda: ConcordGenerator(_loader(lang)))
def _annotator(lang) -> CorpusAnnotator:       return _slot(lang,"ca", lambda: CorpusAnnotator(_loader(lang)))
def _mapper(lang)    -> UDFeatureMapper:       return _slot(lang,"mp", lambda: UDFeatureMapper(_loader(lang)))
def _validator(lang) -> VerbSlotValidator:     return _slot(lang,"vv", lambda: VerbSlotValidator(_loader(lang)))

# ── helpers ───────────────────────────────────────────────────────────
def _ok(data, status=200):  return jsonify({"status":"ok",    "data":data}), status
def _err(msg, code="error", status=400): return jsonify({"status":"error","code":code,"message":msg}), status

def _ser_morpheme(m):
    return {"form":m.form,"slot_id":m.slot_id,"slot_name":m.slot_name,
            "content_type":m.content_type,"gloss":m.gloss,"nc_id":m.nc_id}

def _ser_hyp(h):
    return {"segmented":h.segmented,"gloss_line":h.gloss_line,
            "confidence":round(h.confidence,4),
            "morphemes":[_ser_morpheme(m) for m in h.morphemes],
            "warnings":list(h.warnings)}

def _ser_ud(ud, mp):
    return {"tense":ud.tense,"aspect":ud.aspect,"mood":ud.mood,"voice":ud.voice,
            "nounclass":ud.nounclass,"number":ud.number,"person":ud.person,
            "polarity":ud.polarity,"feats_string":mp.to_conllu_feats(ud),
            "warnings":list(ud.warnings)}

def _ser_token(tok, lang):
    mp = _mapper(lang); ud = mp.map_segmented_token(tok); b = tok.best
    return {"token":tok.token,"language":tok.language,
            "is_ambiguous":tok.is_ambiguous,"hypothesis_count":len(tok.hypotheses),
            "best":_ser_hyp(b) if b else None,
            "all_hypotheses":[_ser_hyp(h) for h in tok.hypotheses[:5]],
            "ud_features":_ser_ud(ud,mp)}

def _ser_paradigm(table, gen, fmt):
    if fmt=="csv":      return gen.to_csv(table)
    if fmt=="markdown": return gen.to_markdown(table)
    if fmt=="html":     return gen.to_html(table)
    cells = {f"{r}|{c}":{"surface":cell.surface,"segmented":cell.segmented,
                          "gloss":cell.gloss,"warnings":list(cell.warnings)}
             for (r,c),cell in table.cells.items()}
    return {"root":table.root,"language":table.language,"paradigm_type":table.paradigm_type,
            "rows":list(table.rows),"columns":list(table.columns),
            "cells":cells,"metadata":table.metadata}

# ── CORS ──────────────────────────────────────────────────────────────
@app.after_request
def _cors(r):
    r.headers["Access-Control-Allow-Origin"]  = "*"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    r.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return r

@app.route("/api/<path:_>", methods=["OPTIONS"])
def _opt(_): return "", 204

# ── ROUTES ────────────────────────────────────────────────────────────

@app.route("/api/languages")
def r_languages():
    return _ok({"languages": list_languages()})

@app.route("/api/metadata/<lang>")
def r_metadata(lang):
    try:
        lo=_loader(lang); m=lo.get_metadata()
        return _ok({"language":m.language,"iso_code":m.iso_code,"guthrie":m.guthrie,
                    "grammar_version":m.grammar_version,"min_loader_version":m.min_loader_version,
                    "max_loader_version":m.max_loader_version,"verify_count":m.verify_count,
                    "noun_class_count":len(lo.get_noun_classes(active_only=False)),
                    "tam_count":len(lo.get_tam_markers()),"extension_count":len(lo.get_extensions()),
                    "concord_type_count":len(lo.get_all_concord_types()),
                    "unresolved_flags":len(lo.list_verify_flags())})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)
    except Exception as e: traceback.print_exc(); return _err(str(e),"internal",500)

@app.route("/api/noun-classes/<lang>")
def r_noun_classes(lang):
    try:
        ncs=_loader(lang).get_noun_classes(active_only=request.args.get("active_only","false").lower()=="true")
        return _ok({"language":lang,"noun_classes":[
            {"id":nc.id,"prefix":nc.prefix,"allomorphs":nc.allomorphs,
             "semantic_domain":nc.semantic_domain,"active":nc.active,
             "singular_counterpart":nc.singular_counterpart,"plural_counterpart":nc.plural_counterpart}
            for nc in ncs]})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)

@app.route("/api/tam/<lang>")
def r_tam(lang):
    try:
        tams=_loader(lang).get_tam_markers()
        return _ok({"language":lang,"tam_markers":[
            {"id":t.id,"form":t.form,"tense":t.tense,"aspect":t.aspect,"mood":t.mood,"notes":t.notes}
            for t in tams]})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)

@app.route("/api/extensions/<lang>")
def r_extensions(lang):
    try:
        exts=_loader(lang).get_extensions()
        return _ok({"language":lang,"extensions":[
            {"id":e.id,"canonical_form":e.canonical_form,"allomorphs":e.allomorphs,
             "zone":e.zone,"semantic_value":e.semantic_value}
            for e in exts]})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)

@app.route("/api/analyze", methods=["POST"])
def r_analyze():
    b=request.get_json(silent=True) or {}
    lang=b.get("language","chitonga"); token=(b.get("token") or "").strip()
    if not token: return _err("'token' required","validation",422)
    try:
        return _ok(_ser_token(_analyzer(lang).analyze(token,max_hypotheses=int(b.get("max_hypotheses",5))),lang))
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)
    except Exception as e: traceback.print_exc(); return _err(str(e),"internal",500)

@app.route("/api/generate", methods=["POST"])
def r_generate():
    b=request.get_json(silent=True) or {}
    lang=b.get("language","chitonga")
    root=(b.get("root") or "").strip(); subj=(b.get("subject_nc") or "").strip(); tam=(b.get("tam_id") or "").strip()
    for f,v in (("root",root),("subject_nc",subj),("tam_id",tam)):
        if not v: return _err(f"'{f}' required","validation",422)
    feat=MorphFeatureBundle(root=root,subject_nc=subj,tam_id=tam,
                            object_nc=b.get("object_nc"),extensions=tuple(b.get("extensions") or []),
                            polarity=b.get("polarity","affirmative"),final_vowel=b.get("final_vowel","a"))
    try:
        sf=_analyzer(lang).generate(feat)
        return _ok({"surface":sf.surface,"segmented":sf.segmented,"gloss":sf.gloss,"warnings":list(sf.warnings)})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)
    except Exception as e: return _err(str(e),"internal",500)

@app.route("/api/paradigm/<lang>/<root>")
def r_paradigm(lang, root):
    exts=tuple(e.strip() for e in request.args.get("extensions","").split(",") if e.strip())
    pols=tuple(p.strip() for p in request.args.get("polarity","affirmative").split(",") if p.strip()) or ("affirmative",)
    fmt=request.args.get("format","json").lower()
    try:
        gen=_generator(lang); table=gen.generate_verb_paradigm(root=root,extensions=exts,polarities=pols)
        payload=_ser_paradigm(table,gen,fmt)
        if fmt=="csv":
            return Response(payload,mimetype="text/csv",
                headers={"Content-Disposition":f'attachment; filename="paradigm_{lang}_{root}.csv"'})
        if fmt=="markdown":
            return Response(payload,mimetype="text/plain",
                headers={"Content-Disposition":f'attachment; filename="paradigm_{lang}_{root}.md"'})
        if fmt=="html": return Response(payload,mimetype="text/html")
        return _ok(payload)
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)
    except Exception as e: traceback.print_exc(); return _err(str(e),"internal",500)

@app.route("/api/concords/<lang>/<nc_id>")
def r_concords_nc(lang, nc_id):
    try:
        rich=_cg(lang).generate_all_concords_rich(nc_id)
        return _ok({"nc_id":rich.nc_id,"language":rich.language,"forms":rich.forms,
                    "absent_types":rich.absent_types,"fallback_types":rich.fallback_types,"errors":rich.errors})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)

@app.route("/api/concords/<lang>")
def r_concords_all(lang):
    active_only=request.args.get("active_only","true").lower()=="true"
    fmt=request.args.get("format","json").lower()
    try:
        cg_=_cg(lang); tab=cg_.cross_tab(active_only=active_only)
        if fmt=="csv":
            return Response(cg_.format_cross_tab(active_only=active_only,fmt="csv"),mimetype="text/csv",
                headers={"Content-Disposition":f'attachment; filename="concords_{lang}.csv"'})
        return _ok({"language":tab.language,"concord_types":tab.concord_types,
                    "noun_class_count":tab.noun_class_count,"concord_type_count":tab.concord_type_count,
                    "rows":[{"nc_id":r.nc_id,"semantic_domain":r.semantic_domain,"active":r.active,
                             "forms":r.forms,"absent_types":r.absent_types,"fallback_types":r.fallback_types}
                            for r in tab.rows]})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)

@app.route("/api/annotate", methods=["POST"])
def r_annotate():
    b=request.get_json(silent=True) or {}
    lang=b.get("language","chitonga"); text=(b.get("text") or "").strip()
    if not text: return _err("'text' required","validation",422)
    fmt=(b.get("format") or "json").lower()
    try:
        ann=_annotator(lang).annotate_text(text,max_hypotheses=int(b.get("max_hypotheses",5)))
        conllu=_annotator(lang).to_conllu(ann)
        if fmt=="conllu":
            return Response(conllu,mimetype="text/plain",
                headers={"Content-Disposition":f'attachment; filename="{lang}_annotated.conllu"'})
        return _ok({"language":ann.language,"total_sentences":ann.total_sentences,
                    "total_tokens":ann.total_tokens,"ambiguous_tokens":ann.ambiguous_tokens,
                    "failed_tokens":ann.failed_tokens,"summary":ann.summary(),"conllu":conllu,
                    "sentences":[{"sent_id":s.sent_id,"text":s.text,
                        "tokens":[{"id":t.conllu_id,"form":t.form,"lemma":t.lemma,"upos":t.upos,
                                   "feats":t.feats,
                                   "segmented":(t.segmented_token.best.segmented
                                                if t.segmented_token and t.segmented_token.best else "")}
                                  for t in s.tokens]}
                        for s in ann.sentences]})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)
    except Exception as e: traceback.print_exc(); return _err(str(e),"internal",500)

@app.route("/api/validate/<lang>/<word>")
def r_validate(lang, word):
    try:
        vr=_validator(lang).validate(word)
        return _ok({"token":word,"language":lang,"is_valid":vr.is_valid,
                    "error_count":vr.error_count,"warning_count":vr.warning_count,
                    "slot_coverage":vr.slot_coverage,
                    "violations":[{"rule_id":v.rule_id,"severity":v.severity,"slot_id":v.slot_id,
                                   "morpheme_form":v.morpheme_form,"message":v.message}
                                  for v in vr.violations]})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)

@app.route("/api/compare")
def r_compare():
    lang_a=(request.args.get("lang_a") or "").strip()
    lang_b=(request.args.get("lang_b") or "").strip()
    feature=(request.args.get("feature") or "noun_classes").strip()
    if not lang_a or not lang_b: return _err("lang_a and lang_b required","validation",422)
    try:
        lo_a,lo_b=_loader(lang_a),_loader(lang_b)
        def extract(lo):
            if feature=="noun_classes": return {nc.id:nc.prefix for nc in lo.get_noun_classes(active_only=False)}
            if feature=="tam":          return {t.id:t.form for t in lo.get_tam_markers()}
            if feature=="extensions":   return {e.id:e.canonical_form for e in lo.get_extensions()}
            if feature=="concords":     return {ct:"present" for ct in lo.get_all_concord_types()}
            return {}
        da,db=extract(lo_a),extract(lo_b)
        rows=[{"key":k,"value_a":da.get(k,"—"),"value_b":db.get(k,"—"),
               "status":("same" if da.get(k)==db.get(k) else
                         "lang_b_only" if k not in da else
                         "lang_a_only" if k not in db else "different")}
              for k in sorted(set(list(da)+list(db)))]
        counts={s:sum(1 for r in rows if r["status"]==s)
                for s in ("same","different","lang_a_only","lang_b_only")}
        return _ok({"lang_a":lang_a,"lang_b":lang_b,"feature":feature,"counts":counts,"rows":rows})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)
    except Exception as e: traceback.print_exc(); return _err(str(e),"internal",500)

@app.route("/api/verify-flags/<lang>")
def r_verify_flags(lang):
    prefix=(request.args.get("field") or "").strip()
    try:
        flags=_loader(lang).list_verify_flags()
        if prefix: flags=[f for f in flags if f.field_path.startswith(prefix)]
        return _ok({"language":lang,"unresolved_count":len(flags),
                    "flags":[{"field_path":f.field_path,"current_value":f.current_value,
                               "note":f.note,"suggested_source":f.suggested_source,"resolved":f.resolved}
                              for f in flags]})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)

@app.route("/api/interlinear")
def r_interlinear():
    lang=request.args.get("language","chitonga"); token=(request.args.get("token") or "").strip()
    if not token: return _err("'token' required","validation",422)
    try:
        result=_analyzer(lang).generate_interlinear(token)
        return _ok({"token":token,"language":lang,"lines":result})
    except LanguageNotFoundError as e: return _err(str(e),"LanguageNotFoundError",404)
    except GGTError as e: return _err(str(e),type(e).__name__,400)
    except Exception as e: return _err(str(e),"internal",500)

# ── static ────────────────────────────────────────────────────────────
@app.route("/")
def root(): return send_from_directory(str(_FRONTEND),"index.html")

@app.errorhandler(404)
def e404(e):
    if not request.path.startswith("/api/"): return send_from_directory(str(_FRONTEND),"index.html")
    return _err("Not found","not_found",404)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=5000)
    parser.add_argument("--host",default="0.0.0.0")
    args=parser.parse_args()
    print(f"\nGobelo API  →  http://localhost:{args.port}/")
    print(f"Frontend    →  {_FRONTEND}")
    print(f"Grammars    →  {_GRAMMAR_DIR or '(using embedded package data)'}")
    print(f"Languages   →  {list_languages()}\n")
    app.run(host=args.host,port=args.port,debug=True)
