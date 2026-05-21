// src/quiz/QuestionCard.jsx
import Button from "../admin/components/shared/Button";

export default function QuestionCard({ question, onAnswer, answered, selected }) {
  const options = [question.answer, ...question.distractors]
    .sort(() => Math.random() - 0.5);  // shuffle options on first render

  return (
    <div className="bg-ggtk-card border border-ggtk-border rounded-xl p-6 max-w-2xl">
      <p className="font-sans text-ggtk-text text-sm font-bold mb-5">{question.prompt}</p>
      <div className="flex flex-col gap-2">
        {options.map((opt, i) => {
          const isSelected = opt === selected;
          const isCorrect  = answered && opt === question.answer;
          const isWrong    = answered && isSelected && opt !== question.answer;
          return (
            <button key={i} onClick={() => !answered && onAnswer(opt)}
              className={`text-left px-4 py-2.5 rounded-lg border font-mono text-xs transition-all cursor-pointer ${
                isCorrect ? "bg-ggtk-success/20 border-ggtk-success text-ggtk-success" :
                isWrong   ? "bg-ggtk-danger/20 border-ggtk-danger text-ggtk-danger" :
                isSelected ? "bg-ggtk-accent/20 border-ggtk-accent text-ggtk-accent" :
                "bg-ggtk-input border-ggtk-border text-ggtk-text hover:border-ggtk-borderL"
              } ${answered ? "cursor-default" : ""}`}
            >{opt}</button>
          );
        })}
      </div>
    </div>
  );
}
