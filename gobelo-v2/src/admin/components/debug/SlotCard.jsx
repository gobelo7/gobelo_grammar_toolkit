// src/admin/components/debug/SlotCard.jsx — Section 6.3 exact contract
// slot-card top border colour is dynamic (from parser response) — minimal inline style unavoidable
export default function SlotCard({ slot, color }) {
  return (
    <div
      className="slot-card min-w-[80px] bg-ggt-card border border-ggt-border rounded p-2.5 text-center"
      style={{ borderTop: `3px solid ${color}` }}
    >
      <div className="text-[9px] font-sans text-ggt-muted tracking-[0.1em] uppercase mb-1">{slot.label}</div>
      <div className="text-xs font-mono font-bold" style={{ color }}>{slot.slot}</div>
      <div className="text-sm font-mono font-bold text-ggt-text mt-1">{slot.value}</div>
      <div className="text-[9px] font-mono text-ggt-muted mt-0.5">{slot.gloss}</div>
    </div>
  );
}
