// src/admin/components/editors/ConcordEditor.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SPEC COMPLIANCE — Section 3.3, Section 6.7:
//   ✅ Concord types derived at runtime via Object.keys()
//   ✅ Ensures selected type stays valid when grammar changes
//   ✅ Empty state for missing concord data
//   ✅ No CONCORD_TYPES constant anywhere
// ─────────────────────────────────────────────────────────────────────────────
import { useState, useEffect } from "react";
import { useGrammar } from "../../../state/GrammarContext";
import Card from "../shared/Card";

function TagInput({ values = [], onChange }) {
  const [draft, setDraft] = useState("");
  const vals = Array.isArray(values) ? values : values ? [String(values)] : [];
  const add  = () => { const v = draft.trim(); if (v) { onChange([...vals, v]); setDraft(""); } };
  return (
    <div className="flex flex-wrap gap-1 items-center">
      {vals.map((v, i) => (
        <span key={i} className="inline-flex items-center gap-1 bg-ggt-accentBg text-ggt-accent font-mono text-xs px-2 py-0.5 rounded border border-ggt-accent/20">
          {v}
          <button onClick={() => onChange(vals.filter((_, j) => j !== i))} className="bg-transparent border-none text-ggt-accent cursor-pointer leading-none">×</button>
        </span>
      ))}
      <input value={draft} onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
        placeholder="+ form"
        className="bg-transparent border border-dashed border-ggt-borderL text-ggt-muted font-mono text-xs px-2 py-0.5 rounded outline-none w-16" />
    </div>
  );
}

export default function ConcordEditor() {
  const { grammar, updateGrammar } = useGrammar();
  const [selectedType, setSelectedType] = useState("");
  const [subGroup,     setSubGroup]     = useState("proximal");

  if (!grammar) {
    return <div className="text-ggt-muted text-xs p-10 text-center">Grammar not loaded</div>;
  }

  // ✅ Runtime-derived — works for any language
  const concords     = grammar.concord_system?.concords ?? {};
  const concordTypes = Object.keys(concords);

  if (concordTypes.length === 0) {
    return <div className="text-ggt-muted text-xs p-10 text-center">No concord types found in this grammar.</div>;
  }

  // Ensure selected type stays valid across grammar loads
  const activeType = concordTypes.includes(selectedType) ? selectedType : concordTypes[0];
  const concordData = concords[activeType] ?? {};

  // Detect sub-groups (e.g. proximal/medial/distal in demonstrative_concords)
  const subGroupKeys = Object.keys(concordData).filter(k => {
    const v = concordData[k];
    return v && typeof v === "object" && !Array.isArray(v) && !("forms" in v) && k !== "description";
  });
  const isSubGrouped  = subGroupKeys.length > 0;
  const workingData   = isSubGrouped ? (concordData[subGroup] ?? {}) : concordData;
  const workingBase   = isSubGrouped
    ? `concord_system.concords.${activeType}.${subGroup}`
    : `concord_system.concords.${activeType}`;

  const entryKeys = Object.keys(workingData).filter(k => {
    const v = workingData[k];
    return v && typeof v === "object" && !Array.isArray(v) && "forms" in v;
  });

  return (
    <div>
      <div className="mb-6 pb-3.5 border-b border-ggt-border">
        <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">Concord Paradigms</h2>
        <p className="mt-1 text-ggt-muted text-[11px] font-sans">
          {concordTypes.length} concord type{concordTypes.length !== 1 ? "s" : ""} in this grammar
        </p>
      </div>

      {/* Type selector — built entirely from runtime keys */}
      <div className="flex flex-wrap gap-1.5 mb-5">
        {concordTypes.map(ct => (
          <button key={ct} onClick={() => setSelectedType(ct)}
            className={`px-2.5 py-1 rounded text-[10px] font-sans cursor-pointer whitespace-nowrap border transition-all duration-100 ${
              activeType === ct
                ? "bg-ggt-accent/20 text-ggt-accent border-ggt-accent font-bold"
                : "bg-transparent text-ggt-muted border-ggt-border hover:border-ggt-borderL"
            }`}
          >
            {ct.replace(/_concords$/, "").replace(/_/g, " ") || ct}
          </button>
        ))}
      </div>

      {/* Sub-group selector (demonstrative proximal/medial/distal) */}
      {isSubGrouped && (
        <div className="flex gap-1.5 mb-4">
          {subGroupKeys.map(sg => (
            <button key={sg} onClick={() => setSubGroup(sg)}
              className={`px-3.5 py-1.5 rounded text-[11px] font-sans font-bold cursor-pointer border transition-all ${
                subGroup === sg
                  ? "bg-ggt-blue/20 text-ggt-blue border-ggt-blue"
                  : "bg-ggt-card text-ggt-muted border-ggt-border"
              }`}
            >{sg}</button>
          ))}
        </div>
      )}

      {/* Concord table */}
      {entryKeys.length === 0
        ? <div className="text-ggt-muted text-xs p-8 text-center">No entries for {activeType}{isSubGrouped ? ` / ${subGroup}` : ""}</div>
        : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  {["Key","Forms","Tone","Gloss","Note"].map(h => (
                    <th key={h} className="text-left text-[9px] text-ggt-muted font-sans tracking-[0.1em] uppercase border-b border-ggt-border px-2 py-1.5 sticky top-0 bg-ggt-panel z-10">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entryKeys.map(k => {
                  const e    = workingData[k];
                  const base = `${workingBase}.${k}`;
                  return (
                    <tr key={k} className="border-b border-ggt-border/10 hover:bg-ggt-card/30">
                      <td className="px-2 py-1.5 align-middle">
                        <span className={`font-mono text-xs font-bold ${k.startsWith("NC") ? "text-ggt-accent" : "text-ggt-blue"}`}>{k}</span>
                      </td>
                      <td className="px-2 py-1.5 align-middle">
                        <TagInput
                          values={Array.isArray(e.forms) ? e.forms : e.forms ? [String(e.forms)] : []}
                          onChange={v => updateGrammar(`${base}.forms`, v)}
                        />
                      </td>
                      <td className="px-2 py-1.5 align-middle">
                        <select value={e.tone ?? "L"} onChange={ev => updateGrammar(`${base}.tone`, ev.target.value)}
                          className="bg-ggt-input border border-ggt-border rounded font-mono text-xs text-ggt-text px-1.5 py-1 outline-none cursor-pointer w-20">
                          {["L","H","L-L","L-H","H-L","H-H","L-H-L","varies"].map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-1.5 align-middle">
                        <input value={e.gloss ?? ""} onChange={ev => updateGrammar(`${base}.gloss`, ev.target.value)}
                          className="w-full bg-ggt-input border border-ggt-border rounded font-mono text-xs text-ggt-text px-2 py-1 outline-none" />
                      </td>
                      <td className="px-2 py-1.5 align-middle">
                        <input value={e.note ?? ""} onChange={ev => updateGrammar(`${base}.note`, ev.target.value)}
                          placeholder="note / # VERIFY…"
                          className={`w-full bg-ggt-input border rounded font-mono text-xs text-ggt-text px-2 py-1 outline-none ${(e.note ?? "").includes("VERIFY") ? "border-ggt-verify/50" : "border-ggt-border"}`} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )
      }
    </div>
  );
}
