"""
tests/integration/test_backend_routes.py
=========================================
Integration tests for every route in ``web/backend/app.py``.

Uses the ``flask_client`` fixture from ``conftest.py`` — no server
is started; Werkzeug's test client handles all HTTP dispatch.

Every test checks:
  1. HTTP status code
  2. ``{"status": "ok", "data": {...}}`` envelope
  3. Key fields in ``data`` that downstream code depends on

Run:
    pytest tests/integration/test_backend_routes.py -v
    pytest tests/integration/test_backend_routes.py::TestAnalyzeRoute -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# path bootstrap
_ROOT = Path(__file__).resolve().parents[2]
_GGT  = _ROOT / "ggt"
for p in (_GGT, Path("/mnt/user-data/uploads")):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


# ── helper ────────────────────────────────────────────────────────

def ok(client, method: str, path: str, body=None):
    """Make a request and assert 200 + status='ok'. Returns data dict."""
    if method == "GET":
        r = client.get(path)
    else:
        r = client.post(path, json=body, content_type="application/json")
    assert r.status_code == 200, f"{method} {path} → {r.status_code}: {r.data[:200]}"
    d = json.loads(r.data)
    assert d["status"] == "ok", f"Expected status=ok, got: {d}"
    return d["data"]


def err(client, method: str, path: str, body=None, expect: int = 400):
    """Make a request and assert an error status code. Returns error dict."""
    if method == "GET":
        r = client.get(path)
    else:
        r = client.post(path, json=body, content_type="application/json")
    assert r.status_code == expect, (
        f"{method} {path} → {r.status_code} (expected {expect}): {r.data[:200]}"
    )
    d = json.loads(r.data)
    assert d["status"] == "error"
    return d


# ═══════════════════════════════════════════════════════════════════
#  GET /api/languages
# ═══════════════════════════════════════════════════════════════════

class TestLanguagesRoute:
    def test_returns_list(self, flask_client):
        data = ok(flask_client, "GET", "/api/languages")
        assert "languages" in data
        assert isinstance(data["languages"], list)

    def test_includes_chitonga(self, flask_client):
        data = ok(flask_client, "GET", "/api/languages")
        assert "chitonga" in data["languages"]

    def test_includes_all_seven(self, flask_client):
        data = ok(flask_client, "GET", "/api/languages")
        langs = set(data["languages"])
        for expected in ("chitonga", "chibemba", "chinyanja", "silozi", "luvale", "lunda", "kaonde"):
            assert expected in langs, f"Expected '{expected}' in language list"

    def test_sorted_alphabetically(self, flask_client):
        data = ok(flask_client, "GET", "/api/languages")
        assert data["languages"] == sorted(data["languages"])


# ═══════════════════════════════════════════════════════════════════
#  GET /api/metadata/<lang>
# ═══════════════════════════════════════════════════════════════════

class TestMetadataRoute:
    def test_chitonga_metadata(self, flask_client):
        data = ok(flask_client, "GET", "/api/metadata/chitonga")
        assert data["language"] == "chitonga"
        assert data["iso_code"] == "toi"
        assert data["guthrie"] == "M.64"
        assert data["grammar_version"] == "1.0.0"

    def test_counts_present(self, flask_client):
        data = ok(flask_client, "GET", "/api/metadata/chitonga")
        assert data["noun_class_count"] == 21
        assert data["tam_count"] == 8
        assert data["extension_count"] == 14
        assert data["concord_type_count"] == 18

    def test_unresolved_flags_zero(self, flask_client):
        data = ok(flask_client, "GET", "/api/metadata/chitonga")
        assert data["unresolved_flags"] == 0

    def test_unknown_language_404(self, flask_client):
        err(flask_client, "GET", "/api/metadata/zzzz", expect=404)

    def test_chibemba_metadata(self, flask_client):
        data = ok(flask_client, "GET", "/api/metadata/chibemba")
        assert data["language"] == "chibemba"
        assert data["iso_code"] == "bem"


# ═══════════════════════════════════════════════════════════════════
#  GET /api/noun-classes/<lang>
# ═══════════════════════════════════════════════════════════════════

class TestNounClassesRoute:
    def test_count(self, flask_client):
        data = ok(flask_client, "GET", "/api/noun-classes/chitonga")
        assert len(data["noun_classes"]) == 21

    def test_nc7_fields(self, flask_client):
        data = ok(flask_client, "GET", "/api/noun-classes/chitonga")
        nc7 = next(nc for nc in data["noun_classes"] if nc["id"] == "NC7")
        assert nc7["prefix"] == "ci-"
        assert nc7["semantic_domain"] == "things_diminutives"
        assert nc7["plural_counterpart"] == "NC8"
        assert nc7["active"] is True

    def test_all_have_required_fields(self, flask_client):
        data = ok(flask_client, "GET", "/api/noun-classes/chitonga")
        for nc in data["noun_classes"]:
            for field in ("id", "prefix", "semantic_domain", "active"):
                assert field in nc, f"NC {nc.get('id')} missing field {field!r}"

    def test_language_field(self, flask_client):
        data = ok(flask_client, "GET", "/api/noun-classes/chitonga")
        assert data["language"] == "chitonga"

    def test_silozi_nc7_is_si(self, flask_client):
        """siLozi uses si- for NC7, not ci-."""
        data = ok(flask_client, "GET", "/api/noun-classes/silozi")
        nc7 = next((nc for nc in data["noun_classes"] if nc["id"] == "NC7"), None)
        if nc7:
            assert nc7["prefix"] == "si-"


# ═══════════════════════════════════════════════════════════════════
#  GET /api/tam/<lang>
# ═══════════════════════════════════════════════════════════════════

class TestTAMRoute:
    def test_count(self, flask_client):
        data = ok(flask_client, "GET", "/api/tam/chitonga")
        assert len(data["tam_markers"]) == 8

    def test_tam_pres_fields(self, flask_client):
        data = ok(flask_client, "GET", "/api/tam/chitonga")
        tams = {t["id"]: t for t in data["tam_markers"]}
        pres = tams["TAM_PRES"]
        assert pres["form"] == "a"
        assert pres["tense"] == "present"
        assert pres["aspect"] == "imperfective"
        assert pres["mood"] == "indicative"

    def test_rem_pst_present(self, flask_client):
        data = ok(flask_client, "GET", "/api/tam/chitonga")
        ids = [t["id"] for t in data["tam_markers"]]
        assert "TAM_REM_PST" in ids

    def test_language_field(self, flask_client):
        data = ok(flask_client, "GET", "/api/tam/chitonga")
        assert data["language"] == "chitonga"


# ═══════════════════════════════════════════════════════════════════
#  GET /api/extensions/<lang>
# ═══════════════════════════════════════════════════════════════════

class TestExtensionsRoute:
    def test_count(self, flask_client):
        data = ok(flask_client, "GET", "/api/extensions/chitonga")
        assert len(data["extensions"]) == 14

    def test_appl_fields(self, flask_client):
        data = ok(flask_client, "GET", "/api/extensions/chitonga")
        exts = {e["id"]: e for e in data["extensions"]}
        appl = exts["APPL"]
        assert appl["canonical_form"] == "-il-"
        assert appl["zone"] == "Z1"

    def test_pass_zone_z3(self, flask_client):
        data = ok(flask_client, "GET", "/api/extensions/chitonga")
        exts = {e["id"]: e for e in data["extensions"]}
        assert exts["PASS"]["zone"] == "Z3"


# ═══════════════════════════════════════════════════════════════════
#  POST /api/analyze
# ═══════════════════════════════════════════════════════════════════

class TestAnalyzeRoute:
    def test_cilya_segmented(self, flask_client):
        data = ok(flask_client, "POST", "/api/analyze",
                  {"language": "chitonga", "token": "cilya"})
        assert data["best"]["segmented"] == "ci-ly-a"

    def test_cilya_ud_nounclass(self, flask_client):
        data = ok(flask_client, "POST", "/api/analyze",
                  {"language": "chitonga", "token": "cilya"})
        assert data["ud_features"]["nounclass"] == "Bantu7"

    def test_balya_has_morphemes(self, flask_client):
        data = ok(flask_client, "POST", "/api/analyze",
                  {"language": "chitonga", "token": "balya"})
        assert len(data["best"]["morphemes"]) >= 2

    def test_hypothesis_count(self, flask_client):
        data = ok(flask_client, "POST", "/api/analyze",
                  {"language": "chitonga", "token": "cilya"})
        assert data["hypothesis_count"] >= 1
        assert len(data["all_hypotheses"]) >= 1

    def test_feats_string_present(self, flask_client):
        data = ok(flask_client, "POST", "/api/analyze",
                  {"language": "chitonga", "token": "cilya"})
        feats = data["ud_features"]["feats_string"]
        assert feats and feats != "_"
        assert "Nounclass=Bantu7" in feats

    def test_token_field(self, flask_client):
        data = ok(flask_client, "POST", "/api/analyze",
                  {"language": "chitonga", "token": "muntu"})
        assert data["token"] == "muntu"
        assert data["language"] == "chitonga"

    def test_empty_token_422(self, flask_client):
        err(flask_client, "POST", "/api/analyze",
            {"language": "chitonga", "token": ""}, expect=422)

    def test_missing_token_422(self, flask_client):
        err(flask_client, "POST", "/api/analyze",
            {"language": "chitonga"}, expect=422)

    def test_unknown_language_404(self, flask_client):
        err(flask_client, "POST", "/api/analyze",
            {"language": "zzzz", "token": "balya"}, expect=404)


# ═══════════════════════════════════════════════════════════════════
#  POST /api/generate
# ═══════════════════════════════════════════════════════════════════

class TestGenerateRoute:
    def test_nc7_pres_surface(self, flask_client):
        data = ok(flask_client, "POST", "/api/generate", {
            "language": "chitonga",
            "root": "lya",
            "subject_nc": "NC7",
            "tam_id": "TAM_PRES",
        })
        assert data["surface"]
        assert "ly" in data["surface"]

    def test_segmented_present(self, flask_client):
        data = ok(flask_client, "POST", "/api/generate", {
            "language": "chitonga",
            "root": "bona",
            "subject_nc": "NC2",
            "tam_id": "TAM_PST",
        })
        assert data["segmented"]

    def test_missing_root_422(self, flask_client):
        err(flask_client, "POST", "/api/generate", {
            "language": "chitonga",
            "subject_nc": "NC7",
            "tam_id": "TAM_PRES",
        }, expect=422)


# ═══════════════════════════════════════════════════════════════════
#  GET /api/paradigm/<lang>/<root>
# ═══════════════════════════════════════════════════════════════════

class TestParadigmRoute:
    def test_dimensions(self, flask_client):
        data = ok(flask_client, "GET", "/api/paradigm/chitonga/lya")
        assert len(data["rows"]) == 25
        assert len(data["columns"]) == 8

    def test_nc7_pres_cell(self, flask_client):
        data = ok(flask_client, "GET", "/api/paradigm/chitonga/lya")
        cell = data["cells"].get("NC7|TAM_PRES")
        assert cell is not None
        assert cell["surface"]

    def test_root_field(self, flask_client):
        data = ok(flask_client, "GET", "/api/paradigm/chitonga/bona")
        assert data["root"] == "bona"

    def test_with_appl_extension(self, flask_client):
        data = ok(flask_client, "GET",
                  "/api/paradigm/chitonga/lya?extensions=APPL")
        assert data["metadata"].get("extensions") == "APPL"

    def test_csv_format(self, flask_client):
        r = flask_client.get("/api/paradigm/chitonga/lya?format=csv")
        assert r.status_code == 200
        assert b"," in r.data
        assert b"lya" in r.data

    def test_markdown_format(self, flask_client):
        r = flask_client.get("/api/paradigm/chitonga/lya?format=markdown")
        assert r.status_code == 200
        assert b"|" in r.data


# ═══════════════════════════════════════════════════════════════════
#  GET /api/concords/<lang>/<nc_id>
# ═══════════════════════════════════════════════════════════════════

class TestConcordsNCRoute:
    def test_nc7_subject(self, flask_client):
        data = ok(flask_client, "GET", "/api/concords/chitonga/NC7")
        assert data["nc_id"] == "NC7"
        assert data["forms"]["subject_concords"] == "ci"

    def test_nc7_possessive(self, flask_client):
        data = ok(flask_client, "GET", "/api/concords/chitonga/NC7")
        assert data["forms"]["possessive_concords"] == "ca"

    def test_language_field(self, flask_client):
        data = ok(flask_client, "GET", "/api/concords/chitonga/NC1")
        assert data["language"] == "chitonga"

    def test_absent_types_list(self, flask_client):
        data = ok(flask_client, "GET", "/api/concords/chitonga/NC7")
        assert isinstance(data["absent_types"], list)


# ═══════════════════════════════════════════════════════════════════
#  GET /api/concords/<lang>  (cross-tab)
# ═══════════════════════════════════════════════════════════════════

class TestConcordsCrossTabRoute:
    def test_counts(self, flask_client):
        data = ok(flask_client, "GET", "/api/concords/chitonga")
        assert data["noun_class_count"] == 21
        assert data["concord_type_count"] == 18

    def test_rows_structure(self, flask_client):
        data = ok(flask_client, "GET", "/api/concords/chitonga")
        assert len(data["rows"]) == 21
        nc7_row = next(r for r in data["rows"] if r["nc_id"] == "NC7")
        assert nc7_row["forms"]["subject_concords"] == "ci"

    def test_csv_format(self, flask_client):
        r = flask_client.get("/api/concords/chitonga?format=csv")
        assert r.status_code == 200
        assert b"," in r.data


# ═══════════════════════════════════════════════════════════════════
#  POST /api/annotate
# ═══════════════════════════════════════════════════════════════════

class TestAnnotateRoute:
    def test_sentence_and_token_counts(self, flask_client):
        data = ok(flask_client, "POST", "/api/annotate", {
            "language": "chitonga",
            "text": "Balya muntu. Cilya cintu.",
        })
        assert data["total_sentences"] == 2
        assert data["total_tokens"] == 4

    def test_conllu_has_sent_id(self, flask_client):
        data = ok(flask_client, "POST", "/api/annotate", {
            "language": "chitonga",
            "text": "Balya muntu.",
        })
        assert "# sent_id" in data["conllu"]

    def test_conllu_10_columns(self, flask_client):
        data = ok(flask_client, "POST", "/api/annotate", {
            "language": "chitonga",
            "text": "Balya muntu.",
        })
        data_rows = [l for l in data["conllu"].splitlines()
                     if l and not l.startswith("#")]
        for row in data_rows:
            assert len(row.split("\t")) == 10

    def test_sentences_array(self, flask_client):
        data = ok(flask_client, "POST", "/api/annotate", {
            "language": "chitonga",
            "text": "Balya muntu.",
        })
        assert len(data["sentences"]) == 1
        sent = data["sentences"][0]
        assert "sent_id" in sent
        assert len(sent["tokens"]) == 2

    def test_token_fields(self, flask_client):
        data = ok(flask_client, "POST", "/api/annotate", {
            "language": "chitonga",
            "text": "Balya muntu.",
        })
        tok = data["sentences"][0]["tokens"][0]
        for field in ("id", "form", "lemma", "upos", "feats"):
            assert field in tok

    def test_empty_text_422(self, flask_client):
        err(flask_client, "POST", "/api/annotate",
            {"language": "chitonga", "text": ""}, expect=422)

    def test_summary_field(self, flask_client):
        data = ok(flask_client, "POST", "/api/annotate", {
            "language": "chitonga",
            "text": "Balya muntu.",
        })
        assert "chitonga" in data["summary"]


# ═══════════════════════════════════════════════════════════════════
#  GET /api/validate/<lang>/<word>
# ═══════════════════════════════════════════════════════════════════

class TestValidateRoute:
    def test_returns_result(self, flask_client):
        data = ok(flask_client, "GET", "/api/validate/chitonga/cilya")
        assert "is_valid" in data
        assert "violations" in data
        assert isinstance(data["violations"], list)

    def test_violation_fields(self, flask_client):
        data = ok(flask_client, "GET", "/api/validate/chitonga/cilya")
        if data["violations"]:
            v = data["violations"][0]
            for field in ("rule_id", "severity", "message"):
                assert field in v

    def test_language_and_token_echo(self, flask_client):
        data = ok(flask_client, "GET", "/api/validate/chitonga/balya")
        assert data["token"] == "balya"
        assert data["language"] == "chitonga"


# ═══════════════════════════════════════════════════════════════════
#  GET /api/compare
# ═══════════════════════════════════════════════════════════════════

class TestCompareRoute:
    def test_nc1_prefix_differs(self, flask_client):
        data = ok(flask_client, "GET",
                  "/api/compare?lang_a=chitonga&lang_b=chibemba&feature=noun_classes")
        # NC1 prefix: mu- (chiTonga) vs u- (chiBemba) → different
        nc1_row = next((r for r in data["rows"] if r["key"] == "NC1"), None)
        assert nc1_row is not None
        assert nc1_row["value_a"] == "mu-"
        assert nc1_row["status"] in ("different",)

    def test_counts_dict(self, flask_client):
        data = ok(flask_client, "GET",
                  "/api/compare?lang_a=chitonga&lang_b=chibemba&feature=noun_classes")
        counts = data["counts"]
        assert "same" in counts and "different" in counts

    def test_tam_comparison(self, flask_client):
        data = ok(flask_client, "GET",
                  "/api/compare?lang_a=chitonga&lang_b=chibemba&feature=tam")
        assert len(data["rows"]) > 0

    def test_missing_params_422(self, flask_client):
        err(flask_client, "GET", "/api/compare", expect=422)

    def test_unknown_language_404(self, flask_client):
        err(flask_client, "GET",
            "/api/compare?lang_a=zzzz&lang_b=chitonga&feature=tam",
            expect=404)


# ═══════════════════════════════════════════════════════════════════
#  GET /api/verify-flags/<lang>
# ═══════════════════════════════════════════════════════════════════

class TestVerifyFlagsRoute:
    def test_chitonga_zero_flags(self, flask_client):
        data = ok(flask_client, "GET", "/api/verify-flags/chitonga")
        assert data["unresolved_count"] == 0
        assert data["flags"] == []

    def test_response_structure(self, flask_client):
        data = ok(flask_client, "GET", "/api/verify-flags/chitonga")
        assert "language" in data
        assert "unresolved_count" in data
        assert "flags" in data

    def test_stub_language_has_flags(self, flask_client):
        """chinyanja stub has 4 VERIFY flags on TAM forms."""
        data = ok(flask_client, "GET", "/api/verify-flags/chinyanja")
        assert data["unresolved_count"] >= 4

    def test_field_filter(self, flask_client):
        """Filter by field prefix returns subset."""
        data_all = ok(flask_client, "GET", "/api/verify-flags/chinyanja")
        data_filt = ok(flask_client, "GET",
                       "/api/verify-flags/chinyanja?field=verb_system")
        assert data_filt["unresolved_count"] <= data_all["unresolved_count"]


# ═══════════════════════════════════════════════════════════════════
#  GET /api/interlinear
# ═══════════════════════════════════════════════════════════════════

class TestInterlinearRoute:
    def test_cilya_contains_segmented(self, flask_client):
        data = ok(flask_client, "GET",
                  "/api/interlinear?language=chitonga&token=cilya")
        assert "ci-ly-a" in data["lines"] or "ci" in data["lines"]

    def test_token_echo(self, flask_client):
        data = ok(flask_client, "GET",
                  "/api/interlinear?language=chitonga&token=balya")
        assert data["token"] == "balya"

    def test_missing_token_422(self, flask_client):
        err(flask_client, "GET",
            "/api/interlinear?language=chitonga", expect=422)


# ═══════════════════════════════════════════════════════════════════
#  CORS headers
# ═══════════════════════════════════════════════════════════════════

class TestCORSHeaders:
    def test_cors_on_get(self, flask_client):
        r = flask_client.get("/api/languages")
        assert r.headers.get("Access-Control-Allow-Origin") == "*"

    def test_cors_on_post(self, flask_client):
        r = flask_client.post("/api/analyze", json={"language": "chitonga",
                                                     "token": "balya"})
        assert r.headers.get("Access-Control-Allow-Origin") == "*"

    def test_options_preflight(self, flask_client):
        r = flask_client.options("/api/analyze")
        assert r.status_code in (200, 204)
