// src/learning/ExampleViewer.jsx
// Displays example words drawn from the grammar's noun class semantic notes
import { useGrammar } from "../state/GrammarContext";

export default function ExampleViewer({ ncKey }) {
  const { grammar } = useGrammar();
  if (!grammar || !ncKey) return null;

  const nc = grammar.noun_class_system?.noun_classes?.[ncKey];
  if (!nc) return null;

  const referents = nc.semantics?.typical_referents ?? [];

  return (
    <div className="bg-ggt-card border border-ggt-border rounded-lg p-4">
      <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggt-accent uppercase mb-3">
        {ncKey} — {nc.semantics?.primary_domain ?? ""}
      </div>
      <div className="text-xs font-mono text-ggt-text mb-2">
        Prefix: <span className="text-ggt-accent font-bold">{nc.prefix?.canonical_form ?? "—"}</span>
      </div>
      {referents.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {referents.map((r, i) => (
            <span key={i} className="bg-ggt-input border border-ggt-border rounded px-2 py-0.5 font-sans text-[10px] text-ggt-muted">
              {String(r).replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
