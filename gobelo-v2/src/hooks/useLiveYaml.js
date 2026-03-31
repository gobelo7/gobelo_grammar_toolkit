// src/hooks/useLiveYaml.js
// Syncs the grammar object to a YAML string representation.
// The string updates on every grammar change — useful for a live YAML preview panel.
import { useState, useEffect } from "react";
import * as jsyaml from "js-yaml";

export function useLiveYaml(grammar) {
  const [yaml,  setYaml]  = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!grammar) { setYaml(""); setError(null); return; }
    try {
      setYaml(jsyaml.dump(grammar, { indent: 2, lineWidth: -1, noRefs: true }));
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, [grammar]);

  return { yaml, error };
}
