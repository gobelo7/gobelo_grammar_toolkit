// src/quiz/ResultPanel.jsx
import Button from "../admin/components/shared/Button";

export default function ResultPanel({ score, total, onRetry }) {
  const pct  = total > 0 ? Math.round((score / total) * 100) : 0;
  const good = pct >= 70;

  return (
    <div className="bg-ggt-card border border-ggt-border rounded-xl p-8 max-w-md text-center">
      <div className={`text-5xl mb-4 ${good ? "text-ggt-success" : "text-ggt-danger"}`}>
        {good ? "✓" : "✗"}
      </div>
      <h3 className="font-sans font-extrabold text-ggt-text text-xl mb-1">
        {score} / {total} correct
      </h3>
      <p className="text-ggt-muted font-sans text-sm mb-6">{pct}% — {good ? "Well done!" : "Keep practising."}</p>
      <Button onClick={onRetry} variant="primary">Try Again</Button>
    </div>
  );
}
