"""
web/backend/routes/public.py — Student/teacher read-only API.

All 15 existing routes moved verbatim from app.py and registered on
a Blueprint. No logic changes — only import paths updated.

Mounted at: /api/  (registered with no url_prefix in create_app)
"""
from __future__ import annotations
import traceback

from flask import Blueprint, Response, jsonify, request

from cache import (
    get_loader, get_analyzer, get_generator,
    get_cg, get_annotator, get_validator,
)
from serializers import ser_token, ser_paradigm

from gobelo_grammar_toolkit.core.registry   import list_languages
from gobelo_grammar_toolkit.core.exceptions import GGTError, LanguageNotFoundError
from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphFeatureBundle

public_bp = Blueprint("public", __name__)


# ── response helpers ──────────────────────────────────────────────────

def _ok(data, status=200):
    return jsonify({"status": "ok", "data": data}), status

def _err(msg, code="error", status=400):
    return jsonify({"status": "error", "code": code, "message": msg}), status


# ── routes ────────────────────────────────────────────────────────────

@public_bp.route("/api/languages")
def r_languages():
    return _ok({"languages": list_languages()})


@public_bp.route("/api/metadata/<lang>")
def r_metadata(lang):
    try:
        lo = get_loader(lang)
        m  = lo.get_metadata()
        return _ok({
            "language":           m.language,
            "iso_code":           m.iso_code,
            "guthrie":            m.guthrie,
            "grammar_version":    m.grammar_version,
            "min_loader_version": m.min_loader_version,
            "max_loader_version": m.max_loader_version,
            "verify_count":       m.verify_count,
            "noun_class_count":   len(lo.get_noun_classes(active_only=False)),
            "tam_count":          len(lo.get_tam_markers()),
            "extension_count":    len(lo.get_extensions()),
            "concord_type_count": len(lo.get_all_concord_types()),
            "unresolved_flags":   len(lo.list_verify_flags()),
        })
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)
    except Exception            as e: traceback.print_exc(); return _err(str(e), "internal", 500)


@public_bp.route("/api/noun-classes/<lang>")
def r_noun_classes(lang):
    active_only = request.args.get("active_only", "false").lower() == "true"
    try:
        ncs = get_loader(lang).get_noun_classes(active_only=active_only)
        return _ok({"language": lang, "noun_classes": [
            {"id": nc.id, "prefix": nc.prefix, "allomorphs": nc.allomorphs,
             "semantic_domain": nc.semantic_domain, "active": nc.active,
             "singular_counterpart": nc.singular_counterpart,
             "plural_counterpart":   nc.plural_counterpart}
            for nc in ncs
        ]})
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)


@public_bp.route("/api/tam/<lang>")
def r_tam(lang):
    try:
        tams = get_loader(lang).get_tam_markers()
        return _ok({"language": lang, "tam_markers": [
            {"id": t.id, "form": t.form, "tense": t.tense,
             "aspect": t.aspect, "mood": t.mood, "notes": t.notes}
            for t in tams
        ]})
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)


@public_bp.route("/api/extensions/<lang>")
def r_extensions(lang):
    try:
        exts = get_loader(lang).get_extensions()
        return _ok({"language": lang, "extensions": [
            {"id": e.id, "canonical_form": e.canonical_form,
             "allomorphs": e.allomorphs, "zone": e.zone,
             "semantic_value": e.semantic_value}
            for e in exts
        ]})
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)


@public_bp.route("/api/analyze", methods=["POST"])
def r_analyze():
    b     = request.get_json(silent=True) or {}
    lang  = b.get("language", "chitonga")
    token = (b.get("token") or "").strip()
    if not token:
        return _err("'token' required", "validation", 422)
    try:
        result = get_analyzer(lang).analyze(token, max_hypotheses=int(b.get("max_hypotheses", 5)))
        return _ok(ser_token(result, lang))
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)
    except Exception            as e: traceback.print_exc(); return _err(str(e), "internal", 500)


@public_bp.route("/api/generate", methods=["POST"])
def r_generate():
    b    = request.get_json(silent=True) or {}
    lang = b.get("language", "chitonga")
    root = (b.get("root")       or "").strip()
    subj = (b.get("subject_nc") or "").strip()
    tam  = (b.get("tam_id")     or "").strip()
    for field, val in (("root", root), ("subject_nc", subj), ("tam_id", tam)):
        if not val:
            return _err(f"'{field}' required", "validation", 422)
    feat = MorphFeatureBundle(
        root=root, subject_nc=subj, tam_id=tam,
        object_nc=b.get("object_nc"),
        extensions=tuple(b.get("extensions") or []),
        polarity=b.get("polarity", "affirmative"),
        final_vowel=b.get("final_vowel", "a"),
    )
    try:
        sf = get_analyzer(lang).generate(feat)
        return _ok({"surface": sf.surface, "segmented": sf.segmented,
                    "gloss": sf.gloss, "warnings": list(sf.warnings)})
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)
    except Exception            as e: return _err(str(e), "internal", 500)


@public_bp.route("/api/paradigm/<lang>/<root>")
def r_paradigm(lang, root):
    exts = tuple(e.strip() for e in request.args.get("extensions", "").split(",") if e.strip())
    pols = tuple(p.strip() for p in request.args.get("polarity", "affirmative").split(",") if p.strip()) or ("affirmative",)
    fmt  = request.args.get("format", "json").lower()
    try:
        gen     = get_generator(lang)
        table   = gen.generate_verb_paradigm(root=root, extensions=exts, polarities=pols)
        payload = ser_paradigm(table, gen, fmt)
        if fmt == "csv":
            return Response(payload, mimetype="text/csv",
                headers={"Content-Disposition": f'attachment; filename="paradigm_{lang}_{root}.csv"'})
        if fmt == "markdown":
            return Response(payload, mimetype="text/plain",
                headers={"Content-Disposition": f'attachment; filename="paradigm_{lang}_{root}.md"'})
        if fmt == "html":
            return Response(payload, mimetype="text/html")
        return _ok(payload)
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)
    except Exception            as e: traceback.print_exc(); return _err(str(e), "internal", 500)


@public_bp.route("/api/concords/<lang>/<nc_id>")
def r_concords_nc(lang, nc_id):
    try:
        rich = get_cg(lang).generate_all_concords_rich(nc_id)
        return _ok({
            "nc_id": rich.nc_id, "language": rich.language, "forms": rich.forms,
            "absent_types": rich.absent_types, "fallback_types": rich.fallback_types,
            "errors": rich.errors,
        })
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)


@public_bp.route("/api/concords/<lang>")
def r_concords_all(lang):
    active_only = request.args.get("active_only", "true").lower() == "true"
    fmt         = request.args.get("format", "json").lower()
    try:
        cg  = get_cg(lang)
        tab = cg.cross_tab(active_only=active_only)
        if fmt == "csv":
            return Response(
                cg.format_cross_tab(active_only=active_only, fmt="csv"),
                mimetype="text/csv",
                headers={"Content-Disposition": f'attachment; filename="concords_{lang}.csv"'},
            )
        return _ok({
            "language":           tab.language,
            "concord_types":      tab.concord_types,
            "noun_class_count":   tab.noun_class_count,
            "concord_type_count": tab.concord_type_count,
            "rows": [
                {"nc_id": r.nc_id, "semantic_domain": r.semantic_domain, "active": r.active,
                 "forms": r.forms, "absent_types": r.absent_types,
                 "fallback_types": r.fallback_types}
                for r in tab.rows
            ],
        })
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)


@public_bp.route("/api/annotate", methods=["POST"])
def r_annotate():
    b    = request.get_json(silent=True) or {}
    lang = b.get("language", "chitonga")
    text = (b.get("text") or "").strip()
    fmt  = (b.get("format") or "json").lower()
    if not text:
        return _err("'text' required", "validation", 422)
    try:
        ann    = get_annotator(lang).annotate_text(text, max_hypotheses=int(b.get("max_hypotheses", 5)))
        conllu = get_annotator(lang).to_conllu(ann)
        if fmt == "conllu":
            return Response(conllu, mimetype="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{lang}_annotated.conllu"'})
        return _ok({
            "language":         ann.language,
            "total_sentences":  ann.total_sentences,
            "total_tokens":     ann.total_tokens,
            "ambiguous_tokens": ann.ambiguous_tokens,
            "failed_tokens":    ann.failed_tokens,
            "summary":          ann.summary(),
            "conllu":           conllu,
            "sentences": [
                {"sent_id": s.sent_id, "text": s.text, "tokens": [
                    {"id": t.conllu_id, "form": t.form, "lemma": t.lemma,
                     "upos": t.upos, "feats": t.feats,
                     "segmented": (t.segmented_token.best.segmented
                                   if t.segmented_token and t.segmented_token.best else "")}
                    for t in s.tokens
                ]}
                for s in ann.sentences
            ],
        })
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)
    except Exception            as e: traceback.print_exc(); return _err(str(e), "internal", 500)


@public_bp.route("/api/validate/<lang>/<word>")
def r_validate(lang, word):
    try:
        vr = get_validator(lang).validate(word)
        return _ok({
            "token": word, "language": lang,
            "is_valid": vr.is_valid, "error_count": vr.error_count,
            "warning_count": vr.warning_count, "slot_coverage": vr.slot_coverage,
            "violations": [
                {"rule_id": v.rule_id, "severity": v.severity, "slot_id": v.slot_id,
                 "morpheme_form": v.morpheme_form, "message": v.message}
                for v in vr.violations
            ],
        })
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)


@public_bp.route("/api/compare")
def r_compare():
    lang_a  = (request.args.get("lang_a")  or "").strip()
    lang_b  = (request.args.get("lang_b")  or "").strip()
    feature = (request.args.get("feature") or "noun_classes").strip()
    if not lang_a or not lang_b:
        return _err("lang_a and lang_b required", "validation", 422)
    try:
        lo_a, lo_b = get_loader(lang_a), get_loader(lang_b)

        def extract(lo):
            if feature == "noun_classes": return {nc.id: nc.prefix for nc in lo.get_noun_classes(active_only=False)}
            if feature == "tam":          return {t.id: t.form for t in lo.get_tam_markers()}
            if feature == "extensions":   return {e.id: e.canonical_form for e in lo.get_extensions()}
            if feature == "concords":     return {ct: "present" for ct in lo.get_all_concord_types()}
            return {}

        da, db = extract(lo_a), extract(lo_b)
        rows = [
            {"key": k, "value_a": da.get(k, "—"), "value_b": db.get(k, "—"),
             "status": ("same"        if da.get(k) == db.get(k) else
                        "lang_b_only" if k not in da else
                        "lang_a_only" if k not in db else "different")}
            for k in sorted(set(list(da) + list(db)))
        ]
        counts = {s: sum(1 for r in rows if r["status"] == s)
                  for s in ("same", "different", "lang_a_only", "lang_b_only")}
        return _ok({"lang_a": lang_a, "lang_b": lang_b, "feature": feature,
                    "counts": counts, "rows": rows})
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)
    except Exception            as e: traceback.print_exc(); return _err(str(e), "internal", 500)


@public_bp.route("/api/verify-flags/<lang>")
def r_verify_flags(lang):
    prefix = (request.args.get("field") or "").strip()
    try:
        flags = get_loader(lang).list_verify_flags()
        if prefix:
            flags = [f for f in flags if f.field_path.startswith(prefix)]
        return _ok({
            "language":         lang,
            "unresolved_count": len(flags),
            "flags": [
                {"field_path": f.field_path, "current_value": f.current_value,
                 "note": f.note, "suggested_source": f.suggested_source,
                 "resolved": f.resolved}
                for f in flags
            ],
        })
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)


@public_bp.route("/api/interlinear")
def r_interlinear():
    lang  = request.args.get("language", "chitonga")
    token = (request.args.get("token") or "").strip()
    if not token:
        return _err("'token' required", "validation", 422)
    try:
        result = get_analyzer(lang).generate_interlinear(token)
        return _ok({"token": token, "language": lang, "lines": result})
    except LanguageNotFoundError as e: return _err(str(e), "LanguageNotFoundError", 404)
    except GGTError             as e: return _err(str(e), type(e).__name__, 400)
    except Exception            as e: return _err(str(e), "internal", 500)
