// src/quiz/QuizPanel.jsx
import { useState, useMemo } from "react";
import { useGrammar } from "../state/GrammarContext";
import { generateQuestions } from "./quizEngine";
import QuestionCard from "./QuestionCard";
import ResultPanel  from "./ResultPanel";
import Button       from "../admin/components/shared/Button";

export default function QuizPanel() {
  const { grammar }                              = useGrammar();
  const [questions, setQuestions]                = useState([]);
  const [current, setCurrent]                    = useState(0);
  const [answers, setAnswers]                    = useState({});
  const [selected, setSelected]                  = useState(null);
  const [answered, setAnswered]                  = useState(false);
  const [done, setDone]                          = useState(false);

  if (!grammar) {
    return <div className="text-ggt-muted text-xs p-10 text-center">Load a grammar file to generate quiz questions.</div>;
  }

  const start = () => {
    // ✅ generateQuestions reads all keys from grammar at runtime — no hardcoded lists
    const qs = generateQuestions(grammar, 10);
    setQuestions(qs);
    setCurrent(0);
    setAnswers({});
    setSelected(null);
    setAnswered(false);
    setDone(false);
  };

  const handleAnswer = (opt) => {
    if (answered) return;
    setSelected(opt);
    setAnswered(true);
    setAnswers(prev => ({ ...prev, [current]: opt }));
  };

  const next = () => {
    if (current < questions.length - 1) {
      setCurrent(i => i + 1);
      setSelected(null);
      setAnswered(false);
    } else {
      setDone(true);
    }
  };

  const score = Object.entries(answers).filter(([i, a]) => a === questions[i]?.answer).length;

  if (questions.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="mb-6 pb-3.5 border-b border-ggt-border">
          <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">Grammar Quiz</h2>
          <p className="mt-1 text-ggt-muted text-[11px] font-sans">
            Questions generated from the loaded grammar — noun classes, TAM markers, concords
          </p>
        </div>
        <Button onClick={start} variant="primary">Start Quiz</Button>
      </div>
    );
  }

  if (done) {
    return (
      <div>
        <div className="mb-6 pb-3.5 border-b border-ggt-border">
          <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">Quiz Complete</h2>
        </div>
        <ResultPanel score={score} total={questions.length} onRetry={start} />
      </div>
    );
  }

  const q = questions[current];
  return (
    <div>
      <div className="mb-6 pb-3.5 border-b border-ggt-border flex items-center justify-between">
        <div>
          <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">Grammar Quiz</h2>
          <p className="mt-1 text-ggt-muted text-[11px] font-sans">Question {current + 1} of {questions.length}</p>
        </div>
        <div className="w-40 h-1.5 bg-ggt-border rounded-full overflow-hidden">
          <div className="h-full bg-ggt-accent rounded-full transition-all" style={{ width: `${((current) / questions.length) * 100}%` }} />
        </div>
      </div>

      <QuestionCard question={q} onAnswer={handleAnswer} answered={answered} selected={selected} />

      {answered && (
        <div className="mt-4">
          <Button onClick={next} variant="primary">
            {current < questions.length - 1 ? "Next →" : "See Results"}
          </Button>
        </div>
      )}
    </div>
  );
}
