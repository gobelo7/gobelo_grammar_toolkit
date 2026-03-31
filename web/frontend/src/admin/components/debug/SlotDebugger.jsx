// src/admin/components/debug/SlotDebugger.jsx — Section 6.8 exact contract
// ─────────────────────────────────────────────────────────────────────────────
// ALL hooks called unconditionally at the top — Rules of Hooks compliant.
// useStepDebugger handles an empty steps array gracefully.
// ─────────────────────────────────────────────────────────────────────────────
import { useParser }       from "../../../hooks/useParser";
import { useStepDebugger } from "../../../hooks/useStepDebugger";
import SlotFlow       from "./SlotFlow";
import MorphBreakdown from "./MorphBreakdown";
import TracePanel     from "./TracePanel";
import StepControls   from "./StepControls";
import StepTimeline   from "./StepTimeline";
import ActiveSlotView from "./ActiveSlotView";
import Loader         from "../shared/Loader";

export default function SlotDebugger() {
  const { parseResult, analyzeResult, loading } = useParser();

  // Hook must be called unconditionally — safe with empty array
  const debug = useStepDebugger(parseResult?.steps ?? []);

  if (loading) return <Loader text="Running parser…" />;

  if (!parseResult) return (
    <div className="text-ggt-muted font-sans text-xs text-center py-8">
      No analysis yet — enter a word above.
    </div>
  );

  const hasSteps = Array.isArray(parseResult.steps) && parseResult.steps.length > 0;

  return (
    <div className="debugger">
      {/* SLOT1–SLOT11 pipeline */}
      <SlotFlow slots={parseResult.slots ?? []} />

      {/* Step-by-step backtracking debugger */}
      {hasSteps && (
        <div className="step-section mb-6">
          <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggt-accent uppercase mb-3.5">
            Step Debugger
          </div>
          <StepControls  {...debug} />
          <ActiveSlotView step={debug.step} />
          <StepTimeline  {...debug} />
        </div>
      )}

      {/* Linguistic breakdown + trace log */}
      <div className="grid grid-cols-2 gap-5 mt-5">
        {/* MorphBreakdown uses analyzeResult.best (v2) when available,
            falls back to parseResult.slots when not */}
        <MorphBreakdown result={analyzeResult ?? parseResult} />
        <TracePanel     trace={parseResult.trace ?? []} />
      </div>
    </div>
  );
}
