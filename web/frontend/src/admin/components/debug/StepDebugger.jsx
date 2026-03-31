// src/admin/components/debug/StepDebugger.jsx
// Standalone step-through debugger panel.
// Consumed by SlotDebugger.jsx; can also be used independently.
// All hooks called unconditionally — Rules of Hooks compliant.
import { useStepDebugger } from "../../../hooks/useStepDebugger";
import StepControls  from "./StepControls";
import ActiveSlotView from "./ActiveSlotView";
import StepTimeline  from "./StepTimeline";

export default function StepDebugger({ steps = [] }) {
  // Hook called unconditionally — handles empty array gracefully
  const debug = useStepDebugger(steps);

  if (steps.length === 0) {
    return (
      <div className="text-ggt-muted font-sans text-xs text-center py-4">
        No step data available for this parse.
      </div>
    );
  }

  return (
    <div className="step-debugger">
      <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggt-accent uppercase mb-3.5">
        Step Debugger — {steps.length} steps
      </div>
      <StepControls   {...debug} />
      <ActiveSlotView step={debug.step} />
      <StepTimeline   {...debug} />
    </div>
  );
}
