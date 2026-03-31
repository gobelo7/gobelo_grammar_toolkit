// src/admin/components/editors/VerifyManager.jsx
import { useState } from "react";
import { useGrammar } from "../../../state/GrammarContext";
import { useSuggestions } from "../../../hooks/useSuggestions";
import Card from "../shared/Card";
import Button from "../shared/Button";
import Loader from "../shared/Loader";

export default function VerifyManager() {
  const { grammar, updateGrammar } = useGrammar();
  const { suggestions, verifyCount, loading, analyse, resolveFlag } = useSuggestions();
  const [search,  setSearch]  = useState("");
  const [editing, setEditing] = useState(null);
  const [drafts,  setDrafts]  = useState({});

  if (!grammar) {
    return <div className="text-ggt-muted text-xs p-10 text-center">Grammar not loaded</div>;
  }

  const filtered = search
    ? suggestions.filter(s =>
        s.path.toLowerCase().includes(search.toLowerCase()) ||
        (s.message ?? "").toLowerCase().includes(search.toLowerCase()) ||
        (s.value   ?? "").toLowerCase().includes(search.toLowerCase())
      )
    : suggestions;

  const startEdit = (s) => { setEditing(s.id); setDrafts(p => ({ ...p, [s.id]: s.value })); };
  const saveEdit  = (s) => { updateGrammar(s.path, drafts[s.id]); setEditing(null); };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 pb-3.5 border-b border-ggt-border flex items-start justify-between">
        <div>
          <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">VERIFY Flags</h2>
          <p className="mt-1 text-ggt-muted text-[11px] font-sans">
            {suggestions.length > 0
              ? `${suggestions.length} flag${suggestions.length !== 1 ? "s" : ""} across all sections`
              : "Run analysis to scan for flags"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`font-mono text-sm font-bold ${verifyCount > 0 ? "text-ggt-verify" : "text-ggt-success"}`}>
            {verifyCount > 0 ? `⚑ ${verifyCount}` : "✓ Clean"}
          </span>
          <Button onClick={analyse} disabled={loading} variant="secondary">
            {loading ? "Scanning…" : "Scan Grammar"}
          </Button>
        </div>
      </div>

      {loading && <Loader text="Scanning grammar for VERIFY flags…" />}

      {!loading && suggestions.length === 0 && (
        <div className="text-center py-14">
          <div className="text-4xl mb-3">✓</div>
          <div className="text-ggt-success font-sans text-sm">
            {verifyCount === 0 ? "No VERIFY flags found" : "Click 'Scan Grammar' to find flags"}
          </div>
        </div>
      )}

      {!loading && suggestions.length > 0 && (
        <>
          <div className="mb-4">
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Filter by path or text…"
              className="bg-ggt-input border border-ggt-border rounded text-ggt-text font-sans text-xs px-3 py-2 outline-none w-96 max-w-full focus:border-ggt-accent"/>
          </div>

          <div className="flex flex-col gap-2">
            {filtered.map(item => (
              <div key={item.id} className="bg-ggt-card border-l-4 border-l-ggt-verify border border-ggt-border rounded-lg px-4 py-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                    item.type === "verify_flag" ? "bg-ggt-verifyBg text-ggt-verify" : "bg-ggt-danger/10 text-ggt-danger"
                  }`}>
                    {item.type === "verify_flag" ? "VERIFY" : "SCHEMA"}
                  </span>
                  <span className="font-mono text-[9px] text-ggt-muted break-all">{item.path}</span>
                </div>

                {editing === item.id
                  ? (
                    <textarea value={drafts[item.id] ?? ""} autoFocus rows={3}
                      onChange={e => setDrafts(p => ({ ...p, [item.id]: e.target.value }))}
                      className="w-full bg-ggt-input border border-ggt-border rounded font-mono text-xs text-ggt-text px-2.5 py-1.5 outline-none resize-y mb-2"/>
                  )
                  : (
                    <div className="font-mono text-xs text-ggt-verify bg-ggt-verifyBg px-2.5 py-1.5 rounded leading-relaxed mb-2">
                      {item.value ?? item.message}
                    </div>
                  )
                }

                <div className="flex gap-2">
                  {editing === item.id
                    ? (
                      <>
                        <Button onClick={() => saveEdit(item)} variant="primary">Save</Button>
                        <Button onClick={() => setEditing(null)} variant="secondary">Cancel</Button>
                      </>
                    )
                    : (
                      <>
                        <Button onClick={() => startEdit(item)} variant="secondary">Edit</Button>
                        {item.type === "verify_flag" && (
                          <Button onClick={() => resolveFlag(item)} variant="ghost">✓ Resolve</Button>
                        )}
                      </>
                    )
                  }
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
