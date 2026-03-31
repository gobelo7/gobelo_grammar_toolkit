// src/state/ParserContext.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Parser state — holds results from both endpoints:
//   /api/parse   → parseResult  (slots, steps, trace)       consumed by SlotDebugger
//   /api/analyze → analyzeResult (best.segmented, best.underlying, best.rule_trace)
//                                consumed by MorphBreakdown
//
// Kept separate so either can update independently without a full re-render.
// ─────────────────────────────────────────────────────────────────────────────
import { createContext, useContext, useState } from "react";

const ParserContext = createContext(null);

export function ParserProvider({ children }) {
  const [parseResult,   setParseResult]   = useState(null);
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState(null);

  const value = {
    parseResult,   setParseResult,
    analyzeResult, setAnalyzeResult,
    loading,       setLoading,
    error,         setError,
  };

  return (
    <ParserContext.Provider value={value}>
      {children}
    </ParserContext.Provider>
  );
}

export const useParserContext = () => {
  const ctx = useContext(ParserContext);
  if (!ctx) throw new Error("useParserContext must be used inside <ParserProvider>");
  return ctx;
};
