// src/hooks/useSuggestions.js
// Suggestion + patch engine for grammar validation.
// Analyses VERIFY flags and schema gaps; produces actionable suggestions.
import { useState, useCallback } from "react";
import { validateGrammar } from "../api/grammar.api";
import { useGrammar } from "../state/GrammarContext";

export function useSuggestions() {
  const { grammar, updateGrammar, countVerify } = useGrammar();
  const [suggestions, setSuggestions] = useState([]);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);

  // ── Run server-side validation and merge with local VERIFY scan ───────────
  const analyse = useCallback(async () => {
    if (!grammar) return;
    setLoading(true);
    setError(null);
    const local = [];

    // Walk grammar collecting VERIFY flags as suggestions
    const walk = (obj, path = []) => {
      if (typeof obj === "string" && obj.includes("# VERIFY")) {
        const ruleMatch = obj.match(/# VERIFY:\s*(.+)/);
        local.push({
          id:          path.join("."),
          path:        path.join("."),
          type:        "verify_flag",
          message:     ruleMatch?.[1] ?? "Form requires verification against source grammar",
          value:       obj,
          canAutoFix:  false,
        });
        return;
      }
      if (Array.isArray(obj))           { obj.forEach((v, i) => walk(v, [...path, i])); return; }
      if (obj && typeof obj === "object") { Object.entries(obj).forEach(([k, v]) => walk(v, [...path, k])); }
    };
    walk(grammar);

    // Merge with server validation if available
    try {
      const serverResult = await validateGrammar(grammar);
      const serverSuggs  = (serverResult.errors ?? []).map((e, i) => ({
        id:         `server_${i}`,
        path:       e.path ?? "",
        type:       "schema_error",
        message:    e.message ?? String(e),
        canAutoFix: false,
      }));
      setSuggestions([...local, ...serverSuggs]);
    } catch {
      // Server unavailable — local suggestions only
      setSuggestions(local);
    }
    setLoading(false);
  }, [grammar]);

  // ── Apply a patch — strip VERIFY text from a flagged value ───────────────
  const resolveFlag = useCallback((suggestion) => {
    const cleaned = suggestion.value.replace(/\s*#\s*VERIFY[^"'\n]*/g, "").trim();
    updateGrammar(suggestion.path, cleaned || null);
    setSuggestions(prev => prev.filter(s => s.id !== suggestion.id));
  }, [updateGrammar]);

  return {
    suggestions,
    verifyCount: countVerify(),
    loading,
    error,
    analyse,
    resolveFlag,
  };
}
