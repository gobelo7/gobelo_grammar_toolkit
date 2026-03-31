// src/admin/views/DebugView.jsx
// Parser tab: ParserPanel (word input) + SlotDebugger (results)
import ParserPanel  from "../components/parser/ParserPanel";
import SlotDebugger from "../components/debug/SlotDebugger";

export default function DebugView() {
  return (
    <div>
      <div className="mb-6 pb-3.5 border-b border-ggt-border">
        <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">Parser Debugger</h2>
        <p className="mt-1 text-ggt-muted text-[11px] font-sans">
          Slot-level morphological analysis with step-through backtracking visualiser
        </p>
      </div>
      <ParserPanel />
      <SlotDebugger />
    </div>
  );
}
