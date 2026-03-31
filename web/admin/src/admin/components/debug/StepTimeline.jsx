// src/admin/components/debug/StepTimeline.jsx — Section 6.4 exact contract
export default function StepTimeline({ steps = [], index, jumpTo }) {
  const bgFor = (s, i) => {
    if (i === index)            return "bg-cyan-500 text-white border-white/20";
    if (s.type === "BACKTRACK") return "bg-orange-500 text-white border-orange-600";
    if (s.status === "fail")    return "bg-ggt-danger text-white border-red-700";
    if (s.status === "success") return "bg-ggt-success text-white border-green-700";
    if (s.type === "COMMIT")    return "bg-ggt-blue text-white border-blue-700";
    return "bg-ggt-card text-ggt-muted border-ggt-border";
  };

  return (
    <div>
      <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggt-muted uppercase mb-2">
        Timeline ({steps.length} steps)
      </div>
      <div className="flex flex-wrap gap-1.5 timeline">
        {steps.map((s, i) => (
          <button
            key={i}
            onClick={() => jumpTo?.(i)}
            title={`${s.type}${s.slot ? ` → ${s.slot}` : ""}${s.candidate ? ` '${s.candidate}'` : ""}`}
            className={`timeline-step px-2.5 py-1 rounded border text-[10px] font-mono ${i === index ? "font-bold" : "font-normal"} ${bgFor(s, i)}`}
          >
            {s.slot ?? s.type.slice(0, 4)}
          </button>
        ))}
      </div>
    </div>
  );
}
