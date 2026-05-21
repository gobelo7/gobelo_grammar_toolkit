// src/admin/components/parser/ParserPanel.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Word input panel. Lives at admin/components/parser/ per Section 4 tree.
// Triggers both /api/parse and /api/analyze via useParser().
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from "react";
import { useParser } from "../../../hooks/useParser";
import Button from "../shared/Button";

export default function ParserPanel() {
  const [word, setWord] = useState("");
  const { runParser, loading, error, usingMock } = useParser();

  const submit = () => { if (word.trim()) runParser(word); };

  return (
    <div className="bg-ggtk-panel border border-ggtk-border rounded-xl p-5 mb-6">
      {/* Header row */}
      <div className="flex items-center gap-2.5 mb-3.5">
        <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggtk-accent uppercase">
          Morphological Parser
        </div>
        {usingMock && (
          <span className="text-[9px] font-mono font-bold px-2 py-0.5 rounded bg-ggtk-verifyBg text-ggtk-verify border border-ggtk-verify/30 tracking-[0.1em]">
            MOCK
          </span>
        )}
      </div>

      {/* Input row */}
      <div className="flex gap-2.5 items-center">
        <input
          value={word}
          onChange={e => setWord(e.target.value)}
          onKeyDown={e => e.key === "Enter" && submit()}
          placeholder="Enter a word form — e.g. tabonabantu"
          className="flex-1 bg-ggtk-input border border-ggtk-border rounded text-ggtk-text font-mono text-sm px-3.5 py-2.5 outline-none focus:border-ggtk-accent"
        />
        <Button onClick={submit} disabled={loading || !word.trim()} variant="primary">
          {loading ? "Parsing…" : "Analyse →"}
        </Button>
      </div>

      {/* Error / mock warning */}
      {error && (
        <div className={`mt-2.5 px-3 py-2 rounded text-xs font-mono border ${
          usingMock
            ? "bg-ggtk-verifyBg text-ggtk-verify border-ggtk-verify/30"
            : "bg-ggtk-danger/10 text-ggtk-danger border-ggtk-danger/30"
        }`}>
          {error}
        </div>
      )}

      <div className="mt-2 text-[10px] text-ggtk-muted font-sans">
        Press Enter or click Analyse. Both slot parse and morphological analysis run in parallel.
        {usingMock && " Start Flask to enable full results."}
      </div>
    </div>
  );
}
