// src/admin/components/debug/StepControls.jsx
import Button from "../shared/Button";

export default function StepControls({ prev, next, reset, index, total, isFirst, isLast }) {
  return (
    <div className="flex items-center gap-2 mb-4 flex-wrap">
      <Button onClick={reset} disabled={isFirst} variant="secondary">↺ Reset</Button>
      <Button onClick={prev}  disabled={isFirst} variant="secondary">← Prev</Button>
      <Button onClick={next}  disabled={isLast}  variant="secondary">Next →</Button>
      <span className="font-mono text-xs text-ggt-muted ml-1">
        Step {index + 1} / {total}
      </span>
    </div>
  );
}
