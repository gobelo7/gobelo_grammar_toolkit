// src/hooks/useStepDebugger.js — exact Section 6.2 contract + jumpTo + reset on new steps
import { useState, useEffect } from "react";

export function useStepDebugger(steps = []) {
  const [index, setIndex] = useState(0);

  // Reset cursor whenever a new parse result arrives
  useEffect(() => { setIndex(0); }, [steps]);

  return {
    step:    steps[index] ?? null,
    steps,
    index,
    total:   steps.length,
    isFirst: index === 0,
    isLast:  index >= steps.length - 1,
    next:    () => setIndex(i => Math.min(i + 1, steps.length - 1)),
    prev:    () => setIndex(i => Math.max(i - 1, 0)),
    reset:   () => setIndex(0),
    jumpTo:  (i) => setIndex(Math.max(0, Math.min(i, steps.length - 1))),
  };
}
