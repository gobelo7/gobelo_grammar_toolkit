// src/admin/components/debug/TracePanel.jsx
export default function TracePanel({ trace = [] }) {
  return (
    <div className="bg-ggt-card border border-ggt-border rounded-lg p-4 overflow-y-auto max-h-72">
      <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggt-accent uppercase mb-3">
        Execution Trace
      </div>
      {trace.length === 0
        ? <div className="text-ggt-muted text-xs font-sans">No trace data.</div>
        : (
          <ol className="m-0 pl-4 space-y-1">
            {trace.map((line, i) => (
              <li key={i} className="font-mono text-xs text-ggt-text leading-relaxed border-b border-ggt-border/20 pb-1">
                {line}
              </li>
            ))}
          </ol>
        )
      }
    </div>
  );
}
