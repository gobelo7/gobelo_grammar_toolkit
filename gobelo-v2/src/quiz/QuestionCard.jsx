// src/quiz/QuestionCard.jsx
import Button from "../admin/components/shared/Button";

export default function QuestionCard({ question, onAnswer, answered, selected }) {
  const options = [question.answer, ...question.distractors]
    .sort(() => Math.random() - 0.5);  // shuffle options on first render

  return (
    <div className="bg-ggt-card border border-ggt-border rounded-xl p-6 max-w-2xl">
      <p className="font-sans text-ggt-text text-sm font-bold mb-5">{question.prompt}</p>
      <div className="flex flex-col gap-2">
        {options.map((opt, i) => {
          const isSelected = opt === selected;
          const isCorrect  = answered && opt === question.answer;
          const isWrong    = answered && isSelected && opt !== question.answer;
          return (
            <button key={i} onClick={() => !answered && onAnswer(opt)}
              className={`text-left px-4 py-2.5 rounded-lg border font-mono text-xs transition-all cursor-pointer ${
                isCorrect ? "bg-ggt-success/20 border-ggt-success text-ggt-success" :
                isWrong   ? "bg-ggt-danger/20 border-ggt-danger text-ggt-danger" :
                isSelected ? "bg-ggt-accent/20 border-ggt-accent text-ggt-accent" :
                "bg-ggt-input border-ggt-border text-ggt-text hover:border-ggt-borderL"
              } ${answered ? "cursor-default" : ""}`}
            >{opt}</button>
          );
        })}
      </div>
    </div>
  );
}
