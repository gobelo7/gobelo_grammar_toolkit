// src/state/GrammarContext.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Grammar state — spec Section 5.2, exactly as specified.
//
// CRITICAL: No localStorage, no sessionStorage, no persistence of any kind.
// Section 1 prohibits both explicitly. Grammar exists in memory only.
// If the user reloads the page they must re-upload the YAML file.
//
// updateGrammar(path, value) paths must mirror the loaded YAML schema exactly.
// The <key> segments are always runtime values derived from the grammar object;
// they are never hardcoded identifiers.
// ─────────────────────────────────────────────────────────────────────────────
import { createContext, useContext, useState, useCallback } from "react";
import * as jsyaml from "js-yaml";
import _ from "lodash-es";

const GrammarContext = createContext(null);

export function GrammarProvider({ children }) {
  const [grammar,  setGrammar]  = useState(null);
  const [fileName, setFileName] = useState("");
  const [modified, setModified] = useState(false);

  // ── Dot-path updater — Section 5.2 contract ───────────────────────────────
  // Example: updateGrammar("noun_class_system.noun_classes.NC1.prefix.canonical_form", "mu-")
  // The path is always built from runtime keys, never hardcoded class identifiers.
  const updateGrammar = useCallback((path, value) => {
    setGrammar(prev => {
      const next = _.cloneDeep(prev);
      _.set(next, path, value);
      return next;
    });
    setModified(true);
  }, []);

  // ── Parse a YAML string ───────────────────────────────────────────────────
  const parseFile = useCallback((text, name) => {
    try {
      const parsed = jsyaml.load(text);
      if (!parsed || typeof parsed !== "object") {
        return { ok: false, error: "File parsed but produced no data" };
      }
      setGrammar(parsed);
      setFileName(name);
      setModified(false);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message.slice(0, 120) };
    }
  }, []);

  // ── Load from a File object (drag-drop or input) ──────────────────────────
  // Returns Promise<{ok, error?}> so callers can show feedback.
  const handleFile = useCallback((file) => {
    return new Promise((resolve) => {
      if (!file) { resolve({ ok: false, error: "No file provided" }); return; }
      const reader = new FileReader();
      reader.onload  = e => resolve(parseFile(e.target.result, file.name));
      reader.onerror = () => resolve({ ok: false, error: "File read failed" });
      reader.readAsText(file);
    });
  }, [parseFile]);

  // ── Export grammar to a downloadable YAML file ────────────────────────────
  const handleDownload = useCallback(() => {
    if (!grammar) return { ok: false, error: "No grammar loaded" };
    try {
      const yaml = jsyaml.dump(grammar, { indent: 2, lineWidth: -1, noRefs: true });
      const blob = new Blob([yaml], { type: "text/yaml" });
      const a    = document.createElement("a");
      a.href     = URL.createObjectURL(blob);
      a.download = fileName || "grammar.yaml";
      a.click();
      setModified(false);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }, [grammar, fileName]);

  // ── Derived ───────────────────────────────────────────────────────────────
  const langName = grammar?.metadata?.language?.name ?? "—";

  // VERIFY flag count — scanned lazily from grammar
  const countVerify = useCallback(() => {
    if (!grammar) return 0;
    let count = 0;
    const walk = (obj) => {
      if (typeof obj === "string" && obj.includes("# VERIFY")) { count++; return; }
      if (Array.isArray(obj))          { obj.forEach(walk); return; }
      if (obj && typeof obj === "object") { Object.values(obj).forEach(walk); }
    };
    walk(grammar);
    return count;
  }, [grammar]);

  const value = {
    grammar,  setGrammar,
    fileName, setFileName,
    modified, setModified,
    updateGrammar,
    handleFile,
    handleDownload,
    parseFile,
    langName,
    countVerify,
  };

  return (
    <GrammarContext.Provider value={value}>
      {children}
    </GrammarContext.Provider>
  );
}

export const useGrammar = () => {
  const ctx = useContext(GrammarContext);
  if (!ctx) throw new Error("useGrammar must be used inside <GrammarProvider>");
  return ctx;
};
