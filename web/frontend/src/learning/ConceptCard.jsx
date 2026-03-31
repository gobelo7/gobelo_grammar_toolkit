// src/learning/ConceptCard.jsx
export default function ConceptCard({ title, body, examples = [] }) {
  return (
    <div className="bg-ggt-card border border-ggt-border rounded-xl p-5">
      <h3 className="font-sans font-bold text-ggt-text text-sm mb-2">{title}</h3>
      <p className="font-sans text-ggt-muted text-xs leading-relaxed mb-3">{body}</p>
      {examples.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {examples.map((ex, i) => (
            <div key={i} className="bg-ggt-input border border-ggt-border rounded px-3 py-2">
              <span className="font-mono text-sm text-ggt-accent">{ex.form}</span>
              <span className="font-mono text-xs text-ggt-muted ml-3">{ex.gloss}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
