// src/admin/components/debug/SlotFlow.jsx — Section 6.3 exact contract
import SlotCard from "./SlotCard";

// SLOT_COLORS is correctly hardcoded here per spec (Section 6.3 comment):
// "SLOT_COLORS is correctly hardcoded: slot types are fixed by the GGT
//  slot model (SLOT1–SLOT11), not by the grammar file."
const SLOT_COLORS = {
  NEG:     "#ef4444",
  PRE:     "#f97316",
  SM:      "#3b82f6",
  NEG_INF: "#ef4444",
  TAM:     "#8b5cf6",
  MOD:     "#a855f7",
  OM:      "#06b6d4",
  ROOT:    "#10b981",
  EXT:     "#84cc16",
  FV:      "#f59e0b",
  POST:    "#6b7280",
};

export default function SlotFlow({ slots }) {
  if (!slots?.length) return null;
  return (
    <div className="slot-flow flex gap-2 overflow-x-auto pb-2 mb-5">
      {slots.map((s, i) => (
        <SlotCard key={i} slot={s} color={SLOT_COLORS[s.slot] ?? "#374151"} />
      ))}
    </div>
  );
}
