// src/hooks/useParser.js
// ─────────────────────────────────────────────────────────────────────────────
// Calls both parser endpoints and stores results in ParserContext.
//   /api/parse   → parseResult  (slot pipeline data)
//   /api/analyze → analyzeResult (morphological breakdown with underlying form)
//
// Falls back to mockParse() when Flask is unreachable (network error only).
// Set VITE_NO_MOCK=true in .env to disable the fallback.
// ─────────────────────────────────────────────────────────────────────────────
import { useGrammar }       from "../state/GrammarContext";
import { useUI }            from "../state/UIContext";
import { useParserContext } from "../state/ParserContext";
import { parseWord, analyzeWord } from "../api/parser.api";
import { mockParse }        from "../api/mockParser";

const NO_MOCK = import.meta.env.VITE_NO_MOCK === "true";

export function useParser() {
  const { grammar }  = useGrammar();
  const { language } = useUI();
  const {
    parseResult, setParseResult,
    analyzeResult, setAnalyzeResult,
    loading, setLoading,
    error,   setError,
  } = useParserContext();

  const runParser = async (word) => {
    if (!word?.trim()) return;
    if (!grammar) { setError("Load a grammar file first."); return; }

    setLoading(true);
    setError(null);

    // ── /api/parse — slot pipeline ───────────────────────────────────────
    let parseData = null;
    try {
      parseData = await parseWord(word.trim(), grammar);
      setParseResult({ ...parseData, _source: "flask" });
    } catch (parseErr) {
      const isNetwork =
        parseErr.message.includes("Failed to fetch") ||
        parseErr.message.includes("NetworkError") ||
        parseErr.message.includes("net::ERR");

      if (!isNetwork || NO_MOCK) {
        setError(parseErr.message);
        setLoading(false);
        return;
      }
      // Flask unreachable — use mock parser
      try {
        parseData = mockParse(word.trim(), grammar);
        setParseResult({ ...parseData, _source: "mock" });
        setError("Flask unreachable — showing mock parse. Start the backend for full results.");
      } catch (mockErr) {
        setError(`Mock parse failed: ${mockErr.message}`);
        setLoading(false);
        return;
      }
    }

    // ── /api/analyze — morphological breakdown ────────────────────────────
    // Best-effort: if this fails, SlotDebugger still has parse data
    try {
      const analyzeData = await analyzeWord(word.trim(), language);
      setAnalyzeResult(analyzeData);
    } catch {
      // Not fatal — MorphBreakdown will degrade gracefully
      setAnalyzeResult(null);
    }

    setLoading(false);
  };

  const usingMock = parseResult?._source === "mock";

  return {
    runParser,
    parseResult,
    analyzeResult,
    loading,
    error,
    usingMock,
  };
}
