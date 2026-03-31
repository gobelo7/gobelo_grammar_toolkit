// src/admin/components/debug/ActiveSlotView.jsx
export default function ActiveSlotView({ step }) {
  if (!step) return (
    <div className="bg-ggt-card border border-ggt-border rounded-lg p-6 text-ggt-muted font-sans text-xs text-center mb-4">
      Use the controls to step through the parse.
    </div>
  );

  const accent = {
    TRY:       step.status === "success" ? "#3db86e" : step.status === "fail" ? "#e05454" : "#4a9ede",
    COMMIT:    "#3db86e",
    BACKTRACK: "#f97316",
  }[step.type] ?? "#5a7080";

  return (
    <div className="bg-ggt-card border border-ggt-border rounded-lg p-4 mb-4" style={{ borderLeft: `4px solid ${accent}` }}>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <div className="text-[9px] font-sans tracking-[0.1em] uppercase text-ggt-muted mb-1">Type</div>
          <div className="font-mono text-sm font-bold" style={{ color: accent }}>{step.type}</div>
        </div>
        {step.slot && (
          <div>
            <div className="text-[9px] font-sans tracking-[0.1em] uppercase text-ggt-muted mb-1">Slot</div>
            <div className="font-mono text-sm font-bold text-ggt-text">{step.slot}</div>
          </div>
        )}
        {step.candidate && (
          <div>
            <div className="text-[9px] font-sans tracking-[0.1em] uppercase text-ggt-muted mb-1">Trying</div>
            <div className="font-mono text-sm font-bold text-ggt-accent">"{step.candidate}"</div>
          </div>
        )}
        {step.status && (
          <div>
            <div className="text-[9px] font-sans tracking-[0.1em] uppercase text-ggt-muted mb-1">Status</div>
            <div className="font-mono text-sm font-bold" style={{ color: accent }}>{step.status.toUpperCase()}</div>
          </div>
        )}
        {step.value && (
          <div>
            <div className="text-[9px] font-sans tracking-[0.1em] uppercase text-ggt-muted mb-1">Committed</div>
            <div className="font-mono text-sm font-bold text-ggt-success">"{step.value}"</div>
          </div>
        )}
        {step.type === "BACKTRACK" && (
          <div className="col-span-3">
            <div className="text-[9px] font-sans tracking-[0.1em] uppercase text-ggt-muted mb-1">Reason</div>
            <div className="font-mono text-xs text-orange-400">
              ⟲ backtracking from {step.from_slot} — {step.reason}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
