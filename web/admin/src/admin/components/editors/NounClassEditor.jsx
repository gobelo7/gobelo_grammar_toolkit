// src/admin/components/editors/NounClassEditor.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SPEC COMPLIANCE — Section 3.3, Section 6.6:
//   ✅ Noun class keys derived at runtime via Object.keys()
//   ✅ Works for any language, any class count (4 to 22+)
//   ✅ Subclasses (NC1a, NC2b, etc.) handled without special-casing
//   ✅ Empty state when no classes defined
//   ✅ No NC_KEYS constant, no hardcoded identifiers anywhere
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from "react";
import { useGrammar } from "../../../state/GrammarContext";
import Card, { CardHeader } from "../shared/Card";

function TagInput({ values = [], onChange, placeholder = "+ form" }) {
  const [draft, setDraft] = useState("");
  const vals = Array.isArray(values) ? values : values ? [String(values)] : [];
  const add  = () => { const v = draft.trim(); if (v) { onChange([...vals, v]); setDraft(""); } };
  return (
    <div className="flex flex-wrap gap-1.5 items-center">
      {vals.map((v, i) => (
        <span key={i} className="inline-flex items-center gap-1 bg-ggt-accentBg text-ggt-accent font-mono text-xs px-2 py-0.5 rounded border border-ggt-accent/20">
          {v}
          <button onClick={() => onChange(vals.filter((_, j) => j !== i))} className="bg-transparent border-none text-ggt-accent cursor-pointer leading-none">×</button>
        </span>
      ))}
      <input
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
        placeholder={placeholder}
        className="bg-transparent border border-dashed border-ggt-borderL text-ggt-muted font-mono text-xs px-2 py-0.5 rounded outline-none w-20"
      />
    </div>
  );
}

function AllomorphTable({ allomorphs = [], onChange }) {
  const rows = Array.isArray(allomorphs) ? allomorphs : [];
  const upd  = (i, k, v) => { const n = [...rows]; n[i] = { ...n[i], [k]: v }; onChange(n); };
  return (
    <div>
      {rows.length > 0 && (
        <table className="w-full border-collapse mb-2">
          <thead>
            <tr>{["Form", "Condition", "Formal cond.", ""].map(h => (
              <th key={h} className="text-left text-[9px] text-ggt-muted font-sans tracking-[0.1em] uppercase border-b border-ggt-border px-2 py-1">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-ggt-border/20">
                <td className="px-1.5 py-1"><input value={r.form ?? ""} onChange={e => upd(i, "form", e.target.value)} className="w-full bg-ggt-input border border-ggt-border rounded font-mono text-xs text-ggt-text px-2 py-1 outline-none" /></td>
                <td className="px-1.5 py-1"><input value={r.condition ?? ""} onChange={e => upd(i, "condition", e.target.value)} className="w-full bg-ggt-input border border-ggt-border rounded font-sans text-xs text-ggt-text px-2 py-1 outline-none" /></td>
                <td className="px-1.5 py-1"><input value={r.condition_formal ?? ""} onChange={e => upd(i, "condition_formal", e.target.value)} className="w-full bg-ggt-input border border-ggt-border rounded font-mono text-xs text-ggt-text px-2 py-1 outline-none" /></td>
                <td className="w-7 px-1"><button onClick={() => onChange(rows.filter((_, j) => j !== i))} className="bg-transparent border-none text-ggt-danger/50 hover:text-ggt-danger cursor-pointer text-sm">✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <button onClick={() => onChange([...rows, { form: "", condition: "" }])}
        className="bg-transparent border border-dashed border-ggt-borderL text-ggt-muted hover:text-ggt-text cursor-pointer px-3 py-1 rounded text-xs font-sans">
        + Add allomorph
      </button>
    </div>
  );
}

export default function NounClassEditor() {
  const { grammar, updateGrammar } = useGrammar();
  const [selectedKey, setSelectedKey] = useState(null);

  if (!grammar) {
    return <div className="text-ggt-muted text-xs p-10 text-center">Grammar not loaded</div>;
  }

  // ✅ Runtime-derived — works for any language, any class count
  const classes = grammar.noun_class_system?.noun_classes ?? {};
  const ncKeys  = Object.keys(classes);

  if (ncKeys.length === 0) {
    return <div className="text-ggt-muted text-xs p-10 text-center">No noun classes found in this grammar.</div>;
  }

  // Default to first key when nothing selected yet
  const activeKey = (selectedKey && classes[selectedKey]) ? selectedKey : ncKeys[0];
  const nc        = classes[activeKey];
  const basePath  = `noun_class_system.noun_classes.${activeKey}`;

  return (
    <div>
      <div className="mb-6 pb-3.5 border-b border-ggt-border">
        <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">
          Noun Classes <span className="text-ggt-muted font-mono text-sm font-normal">({ncKeys.length})</span>
        </h2>
        <p className="mt-1 text-ggt-muted text-[11px] font-sans">Prefix forms, allomorphs, augment, semantics</p>
      </div>

      {/* Class selector chips — built from runtime keys */}
      <div className="flex flex-wrap gap-1.5 mb-6">
        {ncKeys.map(k => (
          <button
            key={k}
            onClick={() => setSelectedKey(k)}
            className={`px-3 py-1 rounded-full text-[11px] font-mono font-bold cursor-pointer border transition-all duration-100 ${
              activeKey === k
                ? "bg-ggt-accent text-white border-ggt-accent"
                : "bg-ggt-card text-ggt-muted border-ggt-border hover:border-ggt-borderL"
            }`}
          >
            {k}
          </button>
        ))}
      </div>

      {/* Detail panel for active class */}
      <div className="grid grid-cols-2 gap-5">
        {/* Left column */}
        <div className="flex flex-col gap-4">
          {/* Prefix */}
          <Card>
            <CardHeader label="Prefix" />
            <div className="mb-3.5">
              <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Canonical Form</label>
              <input
                value={nc.prefix?.canonical_form ?? ""}
                onChange={e => updateGrammar(`${basePath}.prefix.canonical_form`, e.target.value)}
                className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-mono text-base px-3 py-2 outline-none focus:border-ggt-accent"
              />
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3.5">
              <div>
                <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Tone</label>
                <select
                  value={nc.prefix?.tone ?? "L"}
                  onChange={e => updateGrammar(`${basePath}.prefix.tone`, e.target.value)}
                  className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-mono text-xs px-2.5 py-1.5 outline-none cursor-pointer"
                >
                  {["L","H","L-H","H-L","L-L","H-H"].map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Frequency</label>
                <select
                  value={nc.frequency ?? "medium"}
                  onChange={e => updateGrammar(`${basePath}.frequency`, e.target.value)}
                  className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-sans text-xs px-2.5 py-1.5 outline-none cursor-pointer"
                >
                  {["very_high","high","medium","low","limited"].map(f => <option key={f} value={f}>{f}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Notes</label>
              <textarea
                value={nc.prefix?.notes ?? ""}
                onChange={e => updateGrammar(`${basePath}.prefix.notes`, e.target.value)}
                rows={3}
                className={`w-full bg-ggt-input border rounded text-ggt-text font-mono text-xs px-2.5 py-1.5 outline-none resize-y ${(nc.prefix?.notes ?? "").includes("VERIFY") ? "border-ggt-verify/50" : "border-ggt-border"}`}
              />
            </div>
          </Card>

          {/* Augment */}
          <Card>
            <CardHeader label="Augment" />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Form</label>
                <input
                  value={nc.augment?.form ?? ""}
                  onChange={e => updateGrammar(`${basePath}.augment.form`, e.target.value || null)}
                  placeholder="null = none"
                  className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-mono text-xs px-2.5 py-1.5 outline-none"
                />
              </div>
              <div>
                <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Usage</label>
                <select
                  value={nc.augment?.usage ?? "not_applicable"}
                  onChange={e => updateGrammar(`${basePath}.augment.usage`, e.target.value)}
                  className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-sans text-xs px-2.5 py-1.5 outline-none cursor-pointer"
                >
                  {["optional","obligatory","not_applicable","rare"].map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
            </div>
          </Card>

          {/* Classification */}
          <Card>
            <CardHeader label="Classification" />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Class Type</label>
                <select value={nc.class_type ?? "regular"} onChange={e => updateGrammar(`${basePath}.class_type`, e.target.value)}
                  className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-sans text-xs px-2.5 py-1.5 outline-none cursor-pointer">
                  {["regular","irregular","subclass","verbal","locative"].map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Gram. Number</label>
                <select value={nc.grammatical_number ?? "singular"} onChange={e => updateGrammar(`${basePath}.grammatical_number`, e.target.value)}
                  className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-sans text-xs px-2.5 py-1.5 outline-none cursor-pointer">
                  {["singular","plural","null"].map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Paired Class</label>
                {/* Free-text — paired class key is language-specific, not a fixed selector */}
                <input value={nc.paired_class ?? ""} onChange={e => updateGrammar(`${basePath}.paired_class`, e.target.value || null)}
                  placeholder="e.g. NC2"
                  className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-mono text-xs px-2.5 py-1.5 outline-none" />
              </div>
              <div className="flex items-center gap-2 pt-5">
                <input type="checkbox" checked={nc.active !== false}
                  onChange={e => updateGrammar(`${basePath}.active`, e.target.checked)}
                  className="accent-ggt-accent w-3.5 h-3.5" />
                <span className="text-xs text-ggt-text font-sans">Active class</span>
              </div>
            </div>
          </Card>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader label="Allomorphs" />
            <AllomorphTable
              allomorphs={nc.prefix?.allomorphs ?? []}
              onChange={v => updateGrammar(`${basePath}.prefix.allomorphs`, v)}
            />
          </Card>
          <Card>
            <CardHeader label="Semantics" />
            <div className="mb-3.5">
              <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Primary Domain</label>
              <input value={nc.semantics?.primary_domain ?? ""} onChange={e => updateGrammar(`${basePath}.semantics.primary_domain`, e.target.value)}
                className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-mono text-xs px-2.5 py-1.5 outline-none" />
            </div>
            <div className="mb-3.5">
              <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Features</label>
              <TagInput values={nc.semantics?.features ?? []} onChange={v => updateGrammar(`${basePath}.semantics.features`, v)} placeholder="+ feature" />
            </div>
            <div>
              <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">Typical Referents</label>
              <TagInput values={nc.semantics?.typical_referents ?? []} onChange={v => updateGrammar(`${basePath}.semantics.typical_referents`, v)} placeholder="+ referent" />
            </div>
          </Card>
          <Card>
            <CardHeader label="Triggered Rules" />
            <TagInput values={nc.triggers_rules ?? []} onChange={v => updateGrammar(`${basePath}.triggers_rules`, v)} placeholder="+ rule ID" />
          </Card>
        </div>
      </div>
    </div>
  );
}
