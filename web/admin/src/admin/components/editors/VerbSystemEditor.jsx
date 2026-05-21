// src/admin/components/editors/VerbSystemEditor.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SPEC COMPLIANCE — Section 3.3, Section 6.10:
//   ✅ TAM keys derived via Object.keys(components.tam)
//   ✅ Extension keys derived via Object.keys(components.derivational_extensions)
//   ✅ Final vowel keys derived via Object.keys(components.final_vowels)
//   ✅ No TAM_KEYS, EXT_KEYS, or FV_KEYS constants anywhere
//   ✅ Empty state for each sub-section when no entries exist
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from "react";
import { useGrammar } from "../../../state/GrammarContext";
import Card from "../shared/Card";

function TagInput({ values = [], onChange }) {
  const [draft, setDraft] = useState("");
  const vals = Array.isArray(values) ? values : values ? [String(values)] : [];
  const add  = () => { const v = draft.trim(); if (v) { onChange([...vals, v]); setDraft(""); } };
  return (
    <div className="flex flex-wrap gap-1 items-center">
      {vals.map((v, i) => (
        <span key={i} className="inline-flex items-center gap-1 bg-ggtk-accentBg text-ggtk-accent font-mono text-xs px-2 py-0.5 rounded border border-ggtk-accent/20">
          {v}<button onClick={() => onChange(vals.filter((_,j)=>j!==i))} className="bg-transparent border-none text-ggtk-accent cursor-pointer leading-none">×</button>
        </span>
      ))}
      <input value={draft} onChange={e=>setDraft(e.target.value)}
        onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();add();}}}
        placeholder="+ form"
        className="bg-transparent border border-dashed border-ggtk-borderL text-ggtk-muted font-mono text-xs px-2 py-0.5 rounded outline-none w-16"/>
    </div>
  );
}

// Sub-tab definitions — subsystem keys are ggtk-internal, not language-specific
const SUBSYSTEMS = [
  { key: "tam",                     label: "TAM Markers"  },
  { key: "derivational_extensions", label: "Extensions"   },
  { key: "final_vowels",            label: "Final Vowels" },
  { key: "negation_pre",            label: "Negation"     },
];

export default function VerbSystemEditor() {
  const { grammar, updateGrammar } = useGrammar();
  const [sub,    setSub]    = useState("tam");
  const [selExt, setSelExt] = useState(null);   // selected extension key

  if (!grammar) {
    return <div className="text-ggtk-muted text-xs p-10 text-center">Grammar not loaded</div>;
  }

  // ✅ All keys derived at runtime from the loaded grammar
  const components = grammar.verb_system?.verbal_system_components ?? {};
  const section    = components[sub] ?? {};
  const entries    = Object.entries(section).filter(([, v]) => v && typeof v === "object");
  const basePath   = `verb_system.verbal_system_components.${sub}`;

  // For extensions: sidebar selection
  const extEntries   = sub === "derivational_extensions" ? entries : [];
  const activeExtKey = (selExt && section[selExt]) ? selExt : extEntries[0]?.[0] ?? null;

  return (
    <div>
      <div className="mb-6 pb-3.5 border-b border-ggtk-border">
        <h2 className="m-0 text-ggtk-text font-sans font-extrabold text-lg">Verb System</h2>
        <p className="mt-1 text-ggtk-muted text-[11px] font-sans">TAM markers, extensions (Z1–Z4), final vowels, negation</p>
      </div>

      {/* Sub-tab selector */}
      <div className="flex gap-1.5 mb-5">
        {SUBSYSTEMS.map(s => (
          <button key={s.key} onClick={() => setSub(s.key)}
            className={`px-4 py-1.5 rounded text-xs font-sans font-bold cursor-pointer border transition-all ${
              sub === s.key
                ? "bg-ggtk-accent/20 text-ggtk-accent border-ggtk-accent"
                : "bg-transparent text-ggtk-muted border-ggtk-border"
            }`}
          >{s.label}</button>
        ))}
      </div>

      {entries.length === 0 && (
        <div className="text-ggtk-muted text-xs p-8 text-center">No {sub} entries in this grammar.</div>
      )}

      {/* ── TAM / Final Vowels / Negation — table view ── */}
      {sub !== "derivational_extensions" && entries.length > 0 && (
        <div className="flex flex-col gap-3">
          {entries.map(([key, entry]) => (
            <Card key={key}>
              <div className="flex items-center gap-2.5 mb-3">
                <span className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggtk-accent uppercase">{key}</span>
                <span className="font-mono text-xs text-ggtk-muted">{entry.gloss ?? ""}</span>
                {entry.zone && (
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-ggtk-accentBg text-ggtk-accent border border-ggtk-accent/20">{entry.zone}</span>
                )}
              </div>
              <div className="grid grid-cols-4 gap-2.5">
                <div>
                  <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1">Forms</label>
                  <TagInput
                    values={Array.isArray(entry.forms) ? entry.forms : entry.forms ? [String(entry.forms)] : []}
                    onChange={v => updateGrammar(`${basePath}.${key}.forms`, v.length === 1 ? v[0] : v)}
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1">Gloss</label>
                  <input value={entry.gloss ?? ""} onChange={e => updateGrammar(`${basePath}.${key}.gloss`, e.target.value)}
                    className="w-full bg-ggtk-input border border-ggtk-border rounded font-mono text-xs text-ggtk-text px-2 py-1 outline-none"/>
                </div>
                <div>
                  <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1">Tone</label>
                  <input value={entry.tone ?? ""} onChange={e => updateGrammar(`${basePath}.${key}.tone`, e.target.value)}
                    className="w-full bg-ggtk-input border border-ggtk-border rounded font-mono text-xs text-ggtk-text px-2 py-1 outline-none"/>
                </div>
                <div>
                  <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1">Function</label>
                  <input value={entry.function ?? ""} onChange={e => updateGrammar(`${basePath}.${key}.function`, e.target.value)}
                    className="w-full bg-ggtk-input border border-ggtk-border rounded font-sans text-xs text-ggtk-text px-2 py-1 outline-none"/>
                </div>
              </div>
              {(entry.note !== undefined || entry.notes !== undefined) && (
                <div className="mt-2.5">
                  <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1">Notes</label>
                  <textarea value={entry.note ?? entry.notes ?? ""} rows={2}
                    onChange={e => updateGrammar(`${basePath}.${key}.${entry.note !== undefined ? "note" : "notes"}`, e.target.value)}
                    className={`w-full bg-ggtk-input border rounded font-mono text-xs text-ggtk-text px-2 py-1 outline-none resize-y ${
                      (entry.note ?? entry.notes ?? "").includes("VERIFY") ? "border-ggtk-verify/50" : "border-ggtk-border"
                    }`}/>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* ── Extensions — sidebar + detail view ── */}
      {sub === "derivational_extensions" && extEntries.length > 0 && (
        <div className="grid grid-cols-[155px_1fr] gap-5">
          {/* Extension list sidebar */}
          <div className="flex flex-col gap-1.5">
            {extEntries.map(([key, entry]) => (
              <button key={key} onClick={() => setSelExt(key)}
                className={`px-3 py-2 rounded text-left cursor-pointer border transition-all ${
                  activeExtKey === key
                    ? "bg-ggtk-accent/10 border-ggtk-accent text-ggtk-accent"
                    : "bg-ggtk-card border-ggtk-border text-ggtk-text hover:border-ggtk-borderL"
                }`}
              >
                <span className="font-mono text-xs font-bold">{key}</span>
                <span className="block text-ggtk-muted text-[9px] mt-0.5">{entry.zone ?? ""}</span>
              </button>
            ))}
          </div>

          {/* Extension detail */}
          {activeExtKey && section[activeExtKey] && (() => {
            const ext  = section[activeExtKey];
            const base = `${basePath}.${activeExtKey}`;
            return (
              <div className="flex flex-col gap-3.5">
                <Card>
                  <div className="flex items-center justify-between mb-3.5">
                    <span className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggtk-accent uppercase">{activeExtKey}</span>
                    {ext.zone && <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-ggtk-accentBg text-ggtk-accent border border-ggtk-accent/20">{ext.zone}</span>}
                  </div>
                  <div className="mb-3.5">
                    <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1.5">Forms</label>
                    <TagInput
                      values={Array.isArray(ext.form) ? ext.form : ext.form ? [String(ext.form)] : []}
                      onChange={v => updateGrammar(`${base}.form`, v)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2.5 mb-3.5">
                    <div>
                      <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1">Gloss</label>
                      <input value={ext.gloss ?? ""} onChange={e => updateGrammar(`${base}.gloss`, e.target.value)}
                        className="w-full bg-ggtk-input border border-ggtk-border rounded font-mono text-xs text-ggtk-text px-2 py-1 outline-none"/>
                    </div>
                    <div>
                      <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1">Zone</label>
                      <select value={ext.zone ?? "Z1"} onChange={e => updateGrammar(`${base}.zone`, e.target.value)}
                        className="w-full bg-ggtk-input border border-ggtk-border rounded font-mono text-xs text-ggtk-text px-2 py-1 outline-none cursor-pointer">
                        {["Z1","Z2","Z3","Z4"].map(z => <option key={z} value={z}>{z}</option>)}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggtk-muted mb-1">Function</label>
                    <input value={ext.function ?? ""} onChange={e => updateGrammar(`${base}.function`, e.target.value)}
                      className="w-full bg-ggtk-input border border-ggtk-border rounded font-sans text-xs text-ggtk-text px-2 py-1 outline-none"/>
                  </div>
                </Card>
                <Card>
                  <span className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggtk-accent uppercase">Notes</span>
                  <textarea value={ext.notes ?? ""} rows={4}
                    onChange={e => updateGrammar(`${base}.notes`, e.target.value)}
                    className={`w-full mt-2 bg-ggtk-input border rounded font-mono text-xs text-ggtk-text px-2 py-1.5 outline-none resize-y ${
                      (ext.notes ?? "").includes("VERIFY") ? "border-ggtk-verify/50" : "border-ggtk-border"
                    }`}/>
                </Card>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
