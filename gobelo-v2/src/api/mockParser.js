// src/api/mockParser.js
// ─────────────────────────────────────────────────────────────────────────────
// LOCAL MOCK PARSER — runs in the browser using the loaded grammar object.
// All slot candidates are read from the grammar at runtime; no hardcoded
// language identifiers anywhere.
//
// Produces the same response shape as /api/parse (Section 5.3):
//   { word, slots, steps, trace, _source: "mock" }
//
// Note: the /api/analyze response (Section 5.4) is NOT mocked here.
// MorphBreakdown degrades gracefully when analyzeResult is null.
// ─────────────────────────────────────────────────────────────────────────────

function tryMatch(word, forms, side = "left") {
  const candidates = (Array.isArray(forms) ? forms : forms ? [String(forms)] : [])
    .map(f => String(f).replace(/^-|-$/g, ""))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);   // longest-first wins

  for (const f of candidates) {
    if (side === "left"  && word.startsWith(f)) return { matched: f, remainder: word.slice(f.length) };
    if (side === "right" && word.endsWith(f))   return { matched: f, remainder: word.slice(0, -f.length) };
  }
  return null;
}

function collectForms(entry) {
  if (!entry) return [];
  const f = entry.forms;
  if (Array.isArray(f)) return f;
  if (typeof f === "string") return [f];
  return [];
}

function makeStep(id, type, slot, candidate, status, extra = {}) {
  return { id, type, slot, candidate, status, ...extra };
}

export function mockParse(word, grammar) {
  const steps  = [];
  const slots  = [];
  const trace  = [];
  let   stepId = 1;
  let   cursor = word.toLowerCase().trim();

  // ── Pull all data from grammar at runtime — no hardcoded keys ────────────
  const vsc      = grammar?.verb_system?.verbal_system_components ?? {};
  const sc       = grammar?.concord_system?.concords?.subject_concords ?? {};
  const oc       = grammar?.concord_system?.concords?.object_concords  ?? {};
  const negPre   = vsc.negation_pre ?? {};
  const negInfix = vsc.negation_infix ?? {};
  const tam      = vsc.tam ?? {};
  const modal    = vsc.modal ?? {};
  const fvs      = vsc.final_vowels ?? {};
  const exts     = vsc.derivational_extensions ?? {};

  function pushSlot(label, name, value, gloss) {
    slots.push({ slot: name, label, value, gloss });
  }

  function attempt(label, name, forms) {
    const allForms = (Array.isArray(forms) ? forms : forms ? [String(forms)] : [])
      .map(f => String(f).replace(/^-|-$/g, "")).filter(Boolean);
    for (const f of allForms) {
      steps.push(makeStep(stepId++, "TRY", name, f, null));
      const hit = tryMatch(cursor, [f], "left");
      if (hit) {
        steps[steps.length - 1].status = "success";
        steps.push(makeStep(stepId++, "COMMIT", name, f, "success", { value: f }));
        return hit;
      }
      steps[steps.length - 1].status = "fail";
    }
    return null;
  }

  // ── SLOT1: Pre-initial negation ───────────────────────────────────────────
  for (const [key, entry] of Object.entries(negPre)) {
    const forms = collectForms(entry);
    const hit   = attempt("SLOT1", "NEG", forms);
    if (hit) {
      cursor = hit.remainder;
      pushSlot("SLOT1", "NEG", hit.matched, `NEG.${key.toUpperCase()}`);
      trace.push(`SLOT1 (NEG): "${hit.matched}" matched — ${entry.gloss ?? key}`);
      break;
    }
  }

  // ── SLOT3: Subject concord ────────────────────────────────────────────────
  let scHit = null;
  for (const [key, entry] of Object.entries(sc)) {
    if (!entry?.forms) continue;
    const forms = collectForms(entry);
    steps.push(makeStep(stepId++, "TRY", "SM", forms[0] ?? "", null));
    const hit = tryMatch(cursor, forms, "left");
    if (hit) {
      steps[steps.length - 1].status = "success";
      steps.push(makeStep(stepId++, "COMMIT", "SM", hit.matched, "success", { value: hit.matched }));
      scHit  = { key, hit, gloss: entry.gloss ?? key };
      cursor = hit.remainder;
      pushSlot("SLOT3", "SM", hit.matched, entry.gloss ?? key);
      trace.push(`SLOT3 (SM): "${hit.matched}" → ${entry.gloss ?? key}`);
      break;
    }
    steps[steps.length - 1].status = "fail";
  }
  if (!scHit) {
    steps.push(makeStep(stepId++, "BACKTRACK", "SM", null, null, { from_slot: "SM", reason: "no subject concord match" }));
    trace.push(`SLOT3 (SM): no match for "${cursor.slice(0, 3)}…"`);
    pushSlot("SLOT3", "SM", "?", "UNKNOWN.SM");
  }

  // ── SLOT4: Negation infix ─────────────────────────────────────────────────
  const negInfixForms = collectForms(negInfix.negative);
  if (negInfixForms.length) {
    const hit = attempt("SLOT4", "NEG_INF", negInfixForms);
    if (hit) { cursor = hit.remainder; pushSlot("SLOT4", "NEG_INF", hit.matched, "NEG"); trace.push(`SLOT4: "${hit.matched}"`); }
  }

  // ── SLOT5: TAM marker (all keys from grammar.tam, not a hardcoded list) ──
  for (const [key, entry] of Object.entries(tam)) {
    const forms = Array.isArray(entry.forms) ? entry.forms : entry.forms ? [String(entry.forms)] : [];
    const hit   = attempt("SLOT5", "TAM", forms);
    if (hit) { cursor = hit.remainder; pushSlot("SLOT5", "TAM", hit.matched, entry.gloss ?? key); trace.push(`SLOT5: "${hit.matched}" → ${key}`); break; }
  }

  // ── SLOT6: Modal ──────────────────────────────────────────────────────────
  for (const [key, entry] of Object.entries(modal)) {
    const forms = Array.isArray(entry.forms) ? entry.forms : entry.forms ? [String(entry.forms)] : [];
    const hit   = attempt("SLOT6", "MOD", forms);
    if (hit) { cursor = hit.remainder; pushSlot("SLOT6", "MOD", hit.matched, entry.gloss ?? key); trace.push(`SLOT6: "${hit.matched}" → ${key}`); break; }
  }

  // ── SLOT10: Final vowel (strip right before isolating root) ──────────────
  // Sort FV entries by form length desc so multi-char FVs match before single-char
  const fvEntries = Object.entries(fvs).sort(([, a], [, b]) =>
    String(b.forms ?? "").length - String(a.forms ?? "").length
  );
  let fvMatched = null;
  for (const [key, entry] of fvEntries) {
    const form = String(entry.forms ?? "").replace(/^-|-$/g, "");
    if (!form) continue;
    const hit = tryMatch(cursor, [form], "right");
    if (hit && hit.remainder.length >= 1) {
      fvMatched = { key, form, gloss: entry.gloss ?? key.toUpperCase(), remainder: hit.remainder };
      trace.push(`SLOT10 (FV): "${form}" → ${key}`);
      break;
    }
  }

  // ── SLOT9: Extensions (from grammar.derivational_extensions keys) ─────────
  let preFV    = fvMatched ? fvMatched.remainder : cursor;
  const foundExts = [];
  const extEntries = Object.entries(exts)
    .filter(([, e]) => e && typeof e === "object" && "form" in e)
    .map(([key, e]) => ({
      key,
      forms: (Array.isArray(e.form) ? e.form : [String(e.form ?? "")]).map(f => f.replace(/^-|-$/g, "")),
      gloss: e.gloss ?? key,
      zone:  e.zone  ?? "Z?",
    }));

  for (let pass = 0; pass < 3 && preFV.length > 1; pass++) {
    let hitExt = false;
    for (const ext of extEntries) {
      const hit = tryMatch(preFV, ext.forms, "right");
      if (hit && hit.remainder.length >= 1) {
        foundExts.unshift({ key: ext.key, form: hit.matched, gloss: ext.gloss, zone: ext.zone });
        preFV  = hit.remainder;
        hitExt = true;
        steps.push(makeStep(stepId++, "COMMIT", "EXT", hit.matched, "success", { value: hit.matched }));
        trace.push(`SLOT9 (EXT/${ext.zone}): "${hit.matched}" → ${ext.key}`);
        break;
      }
    }
    if (!hitExt) break;
  }

  // ── SLOT8: Root (remainder) ───────────────────────────────────────────────
  const root = preFV;
  if (root.length > 0) {
    pushSlot("SLOT8", "ROOT", root, "VERB.ROOT");
    steps.push(makeStep(stepId++, "COMMIT", "ROOT", root, "success", { value: root }));
    trace.push(`SLOT8 (ROOT): "${root}"`);
  } else {
    pushSlot("SLOT8", "ROOT", "?", "UNKNOWN.ROOT");
  }

  foundExts.forEach(ext => pushSlot("SLOT9", "EXT", ext.form, `${ext.key}.${ext.zone}`));
  if (fvMatched) {
    pushSlot("SLOT10", "FV", fvMatched.form, fvMatched.gloss);
    steps.push(makeStep(stepId++, "COMMIT", "FV", fvMatched.form, "success", { value: fvMatched.form }));
  }

  return { word, slots, steps, trace, _source: "mock" };
}
