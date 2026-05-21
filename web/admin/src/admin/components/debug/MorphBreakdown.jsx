// src/admin/components/debug/MorphBreakdown.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SPEC COMPLIANCE — Section 5.4, Section 6.9 (v2 contract):
//   ✅ Reads result.best (from /api/analyze response)
//   ✅ Shows underlying form ONLY when it differs from surface
//      (surface = segmented with hyphens stripped)
//   ✅ Shows rule_trace as labelled badges — teacher mode only
//   ✅ Per-morpheme breakdown with slot_id, content_type, gloss
//   ✅ Degrades gracefully when best is null
// ─────────────────────────────────────────────────────────────────────────────
import { useUI } from "../../../state/UIContext";

export default function MorphBreakdown({ result }) {
  const { role } = useUI();
  const isTeacher = role === "teacher";

  // Handles both /api/analyze shape (result.best) and /api/parse shape (result.slots)
  const b = result?.best;

  // ── Graceful degradation: render slot-based breakdown when best is unavailable
  if (!b) {
    if (!result?.slots?.length) return null;
    return (
      <div className="bg-ggtk-card border border-ggtk-border rounded-lg p-4">
        <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggtk-accent uppercase mb-3">
          Morphological Breakdown — <span className="text-ggtk-text text-sm font-normal">{result.word}</span>
        </div>
        <div className="flex flex-wrap gap-1.5 items-end">
          {result.slots.map((s, i) => (
            <span key={i}>
              <span className="inline-block bg-ggtk-input border border-ggtk-border rounded px-2.5 py-1 font-mono text-sm font-bold text-ggtk-text">{s.value}</span>
              {i < result.slots.length - 1 && <span className="text-ggtk-muted font-mono text-xs mx-0.5">·</span>}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {result.slots.map((s, i) => (
            <span key={i} className="font-mono text-[9px] text-ggtk-muted">{s.gloss}</span>
          ))}
        </div>
      </div>
    );
  }

  // ── Full v2 rendering with /api/analyze best hypothesis ──────────────────
  const surface    = b.segmented ?? "";
  const underlying = b.underlying ?? "";
  // Show underlying only when it differs from the surface (hyphens stripped per spec)
  const hasPhon    = underlying && underlying !== surface.replace(/-/g, "");
  const rules      = b.rule_trace ?? [];

  return (
    <div className="bg-ggtk-card border border-ggtk-border rounded-lg p-4">
      <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggtk-accent uppercase mb-3">
        Morphological Analysis
        {b.confidence != null && (
          <span className="ml-2 text-ggtk-muted font-normal">
            {Math.round(b.confidence * 100)}% confidence
          </span>
        )}
      </div>

      {/* Surface segmented form + gloss line */}
      <div className="font-mono text-base font-bold text-ggtk-text mb-1">{surface}</div>
      {b.gloss_line && (
        <div className="font-mono text-xs text-ggtk-muted mb-2">{b.gloss_line}</div>
      )}

      {/* Underlying form — only when phonological alternation occurred (spec 5.4) */}
      {hasPhon && (
        <div className="flex items-center gap-1.5 mb-2 text-xs font-mono">
          <span className="text-ggtk-muted">↓ underlying:</span>
          <span className="text-ggtk-blue font-bold">{underlying}</span>
        </div>
      )}

      {/* Phonological rule trace badges — teacher mode only (spec 5.4) */}
      {isTeacher && rules.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {rules.map((r, i) => (
            <span
              key={i}
              className="phon-badge bg-ggtk-blue/10 text-ggtk-blue border border-ggtk-blue/30 rounded px-2 py-0.5 text-[9px] font-mono font-bold"
              title={r}
            >
              {r.split(":")[0].trim()}
            </span>
          ))}
        </div>
      )}

      {/* Per-morpheme breakdown */}
      {b.morphemes?.length > 0 && (
        <div className="flex flex-col gap-1 mt-2">
          {b.morphemes.filter(m => m.form).map((m, i) => (
            <div
              key={i}
              className={`ct-${m.content_type} flex items-center gap-3 bg-ggtk-input rounded px-2.5 py-1.5`}
            >
              <span className="font-mono text-sm font-bold text-ggtk-text w-12 shrink-0">{m.form}</span>
              <span className="font-mono text-[9px] text-ggtk-muted w-14 shrink-0">{m.slot_id}</span>
              <span className="font-mono text-xs text-ggtk-accent">{m.gloss}</span>
              {m.nc_id && (
                <span className="ml-auto font-mono text-[9px] text-ggtk-blue">{m.nc_id}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* UD features (collapsed, teacher only) */}
      {isTeacher && result?.ud_features && (
        <details className="mt-3">
          <summary className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggtk-muted uppercase cursor-pointer list-none">
            UD Features
          </summary>
          <div className="mt-1.5 font-mono text-[10px] text-ggtk-muted bg-ggtk-input rounded px-2.5 py-1.5 leading-relaxed">
            {result.ud_features.feats_string ?? JSON.stringify(result.ud_features, null, 2)}
          </div>
        </details>
      )}

      {/* Warnings */}
      {b.warnings?.length > 0 && (
        <div className="mt-2 flex flex-col gap-1">
          {b.warnings.map((w, i) => (
            <div key={i} className="text-[10px] text-ggtk-verify font-sans bg-ggtk-verifyBg rounded px-2 py-1">⚠ {w}</div>
          ))}
        </div>
      )}
    </div>
  );
}
