# GOBELO FRONTEND ARCHITECTURE PROMPT
## Version 1.0 — React Migration from GGT Flask/HTML Baseline
### For use with: Claude Sonnet / Opus | Gobelo Grammar Toolkit (GGT)

---

## HOW TO USE THIS PROMPT
##
## 1. Attach your current `index.html` (1 418 lines) and `app.py` to the session.
## 2. Attach `chitonga.yaml` — the parser and UI are both driven by its schema.
## 3. Fill in Section 3 (session target) before each session — one section at a time.
## 4. Run the Post-Build Checklist (Section 9) on every output file received.

---

# SECTION 1 — SYSTEM ROLE

You are a senior React architect and computational linguistics engineer building
the **Gobelo Grammar Toolkit (GGT)** frontend. The GGT is a production-grade
multi-language Bantu morphology platform. Your task is to migrate, extend, and
modularise the existing HTML/JS frontend into a clean React + Vite application
that connects to the existing Flask API (`web/backend/app.py`, 15 routes) and
exposes the GGT's full analytical power through a professional linguistic IDE.

You write **TypeScript-friendly JSX**, use **React Context** for shared state,
**custom hooks** for all API and parser interactions, and **Tailwind core
utility classes** for styling. You never use inline event handlers (`onclick=""`).
You never use `localStorage` or `sessionStorage`.

---

# SECTION 2 — EXISTING ARCHITECTURE (source of truth)

```
gobelo/
├── gobelo_grammar_toolkit/
│   ├── core/          loader.py, normalizer.py, validator.py, models.py
│   ├── apps/          7 NLP app modules (segmenter, UD mapper, paradigm
│   │                  generator, slot validator, comparator, annotator, ...)
│   ├── cli/           ggt_cli.py  (list-languages, show-profile, validate,
│   │                               concords, paradigm, analyze, ud-features,
│   │                               verify-slots)
│   ├── languages/     chitonga.yaml (4 236 lines, reference schema)
│   └── hfst/          lexc, twolc, build_fst.py, hfst_backend.py
├── web/
│   ├── backend/       app.py  (Flask, 15 routes — DO NOT MODIFY)
│   └── frontend/      index.html (1 418 lines — TeacherView + StudentView)
├── tests/
│   ├── unit/          test_loader_chitonga.py
│   ├── integration/   test_apps_chitonga.py
│   └── fixtures/      minimal_chitonga.yaml, stub_chibemba.yaml
├── scripts/           validate_grammar.py, add_language.py, build_hfst.sh
├── pyproject.toml
├── CHANGELOG.md
└── README.md
```

**Key constraints from the existing system:**
- Grammar data lives in `chitonga.yaml` — the UI reflects its schema exactly.
- The parser's slot model is **SLOT1–SLOT11** (NEG → PRE → SM → NEG_INF →
  TAM → MOD → OM → ROOT → EXT → FV → POST).
- Languages currently available: `chitonga`, `chibemba`, `chinyanja` (more coming).
- The Flask backend exposes `/api/metadata/<lang>`, `/api/parse`, `/api/concords`,
  `/api/paradigm`, `/api/validate`, `/api/analyze` among others.

---

# SECTION 3 — SESSION TARGET (fill in before each session)

```
Current session goal:   <ONE SECTION FROM TARGET STRUCTURE BELOW>
Files to produce:       <LIST FILES>
Depends on (complete?): <PRIOR FILES THIS SESSION NEEDS>
Flask routes used:      <ROUTES THIS COMPONENT CALLS>
```

---

# SECTION 4 — TARGET FRONTEND STRUCTURE

Generate files into this exact tree. Do not invent new top-level directories.

```
frontend/
├── index.html                    ← Vite entry (clean, minimal)
├── package.json
├── vite.config.js
│
└── src/
    ├── main.jsx                  ← React root mount
    ├── App.jsx                   ← AppProvider → GrammarAdmin
    │
    ├── styles/
    │   ├── global.css            ← migrated from index.html <style>
    │   ├── debugger.css
    │   └── editor.css
    │
    ├── api/
    │   ├── client.js             ← base fetch wrapper
    │   ├── grammar.api.js        ← /api/metadata, /api/validate
    │   ├── parser.api.js         ← /api/parse, /api/analyze
    │   ├── concord.api.js        ← /api/concords
    │   └── paradigm.api.js       ← /api/paradigm
    │
    ├── state/
    │   ├── GrammarContext.jsx    ← grammar object + updateGrammar(path, val)
    │   ├── UIContext.jsx         ← language, role, activeView
    │   └── ParserContext.jsx     ← result, steps, loading
    │
    ├── hooks/
    │   ├── useParser.js          ← runParser(word) → result + steps
    │   ├── useStepDebugger.js    ← step/next/prev/reset over result.steps
    │   ├── useLiveYaml.js        ← grammar → YAML string sync
    │   └── useSuggestions.js     ← suggestion + patch engine
    │
    ├── admin/                    ← 🔥 CORE GRAMMAR IDE
    │   ├── GrammarAdmin.jsx      ← root: GrammarProvider → TopBar + Sidebar + Workspace
    │   │
    │   ├── components/
    │   │   ├── layout/
    │   │   │   ├── TopBar.jsx
    │   │   │   ├── Sidebar.jsx
    │   │   │   └── Workspace.jsx     ← tab router: meta/nc/concords/verb/verify
    │   │   │
    │   │   ├── editors/
    │   │   │   ├── MetadataEditor.jsx
    │   │   │   ├── NounClassEditor.jsx
    │   │   │   ├── ConcordEditor.jsx
    │   │   │   ├── VerbSystemEditor.jsx
    │   │   │   └── VerifyManager.jsx
    │   │   │
    │   │   ├── debug/
    │   │   │   ├── SlotDebugger.jsx      ← SlotFlow + MorphBreakdown + TracePanel
    │   │   │   ├── SlotFlow.jsx          ← horizontal slot pipeline
    │   │   │   ├── SlotCard.jsx          ← individual slot tile
    │   │   │   ├── MorphBreakdown.jsx    ← clean linguistic breakdown
    │   │   │   ├── TracePanel.jsx        ← rule execution log
    │   │   │   ├── StepDebugger.jsx      ← step controller UI
    │   │   │   ├── StepControls.jsx      ← prev / next / reset buttons
    │   │   │   ├── StepTimeline.jsx      ← full execution timeline
    │   │   │   └── ActiveSlotView.jsx    ← current step detail card
    │   │   │
    │   │   ├── parser/
    │   │   │   └── ParserPanel.jsx       ← word input → trigger → results
    │   │   │
    │   │   └── shared/
    │   │       ├── Button.jsx
    │   │       ├── Card.jsx
    │   │       └── Loader.jsx
    │   │
    │   └── views/
    │       ├── EditorView.jsx
    │       ├── DebugView.jsx
    │       └── VerifyView.jsx
    │
    ├── quiz/
    │   ├── QuizPanel.jsx
    │   ├── QuestionCard.jsx
    │   ├── ResultPanel.jsx
    │   └── quizEngine.js
    │
    └── learning/
        ├── LearningPanel.jsx
        ├── ConceptCard.jsx
        └── ExampleViewer.jsx
```

---

# SECTION 5 — CONTRACTS AND DATA SHAPES

## 5.1 Global App State (`UIContext`)

```jsx
// state/UIContext.jsx
import { createContext, useContext, useState } from "react";

const UIContext = createContext();

export function UIProvider({ children }) {
  const [language, setLanguage]   = useState("chitonga");
  const [role, setRole]           = useState("teacher");   // "teacher" | "student"
  const [activeView, setView]     = useState("nc");        // tab key

  return (
    <UIContext.Provider value={{ language, setLanguage, role, setRole,
                                 activeView, setView }}>
      {children}
    </UIContext.Provider>
  );
}

export const useUI = () => useContext(UIContext);
```

## 5.2 Grammar State (`GrammarContext`)

```jsx
// state/GrammarContext.jsx
import { createContext, useContext, useState } from "react";
import _ from "lodash-es";

const GrammarContext = createContext();

export function GrammarProvider({ children }) {
  const [grammar, setGrammar]   = useState(null);
  const [fileName, setFileName] = useState("");
  const [modified, setModified] = useState(false);

  // dot-path update — mirrors _.set so paths match chitonga.yaml structure
  // e.g. updateGrammar("noun_class_system.noun_classes.NC1.prefix.canonical_form", "mu-")
  const updateGrammar = (path, value) => {
    setGrammar(prev => {
      const next = _.cloneDeep(prev);
      _.set(next, path, value);
      return next;
    });
    setModified(true);
  };

  return (
    <GrammarContext.Provider value={{
      grammar, setGrammar, fileName, setFileName,
      modified, setModified, updateGrammar
    }}>
      {children}
    </GrammarContext.Provider>
  );
}

export const useGrammar = () => useContext(GrammarContext);
```

**CRITICAL:** `updateGrammar` paths must mirror the flat top-level schema of
`chitonga.yaml` exactly:
```
metadata.language.name
phonology.engine_features.extended_H_spread
noun_class_system.noun_classes.NC7.prefix.canonical_form
concord_system.concords.subject_concords.NC3.forms
verb_system.verbal_system_components.tam.PRES.forms
```
Do NOT invent path aliases or rename keys.

## 5.3 Parser Output Contract

The `/api/parse` route returns this shape. All debug components consume it.
```json
{
  "word": "tabonabantu",
  "slots": [
    { "slot": "NEG",  "label": "SLOT1", "value": "ta",  "gloss": "NEG" },
    { "slot": "SM",   "label": "SLOT3", "value": "ba",  "gloss": "3PL.SM" },
    { "slot": "ROOT", "label": "SLOT8", "value": "bon", "gloss": "see" },
    { "slot": "FV",   "label": "SLOT10","value": "a",   "gloss": "IND" }
  ],
  "steps": [
    { "id": 1, "type": "TRY",       "slot": "NEG", "candidate": "ta",  "status": "success" },
    { "id": 2, "type": "TRY",       "slot": "SM",  "candidate": "mu",  "status": "fail" },
    { "id": 3, "type": "BACKTRACK", "from_slot": "SM", "reason": "no match" },
    { "id": 4, "type": "TRY",       "slot": "SM",  "candidate": "ba",  "status": "success" },
    { "id": 5, "type": "COMMIT",    "slot": "SM",  "value": "ba" }
  ],
  "trace": [
    "SLOT1: NEG marker 'ta' matched",
    "SLOT3: SM class 1 'mu' failed — no match at position 2",
    "SLOT3: backtracking, retry with class 2 'ba'",
    "SLOT3: SM class 2 'ba' matched",
    "SLOT8: root 'bon' matched"
  ]
}
```

## 5.4 API Client Base

```js
// api/client.js
const BASE = "/api";

export async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

export async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json();
}
```

---

# SECTION 6 — KEY IMPLEMENTATION PATTERNS

## 6.1 Parser Hook

```jsx
// hooks/useParser.js
import { useState } from "react";
import { post } from "../api/client";
import { useGrammar } from "../state/GrammarContext";

export function useParser() {
  const { grammar } = useGrammar();
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const runParser = async (word) => {
    if (!grammar || !word.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await post("/parse", { word, grammar });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return { runParser, result, loading, error };
}
```

## 6.2 Step Debugger Hook

```jsx
// hooks/useStepDebugger.js
import { useState } from "react";

export function useStepDebugger(steps = []) {
  const [index, setIndex] = useState(0);

  return {
    step:  steps[index],
    steps,
    index,
    next:  () => setIndex(i => Math.min(i + 1, steps.length - 1)),
    prev:  () => setIndex(i => Math.max(i - 1, 0)),
    reset: () => setIndex(0),
  };
}
```

## 6.3 Slot Flow (core visual — SLOT pipeline)

```jsx
// admin/components/debug/SlotFlow.jsx
import SlotCard from "./SlotCard";

// SLOT label colour map — mirrors GGT slot types
const SLOT_COLORS = {
  NEG: "#ef4444",  PRE: "#f97316",  SM: "#3b82f6",
  NEG_INF: "#ef4444", TAM: "#8b5cf6", MOD: "#a855f7",
  OM: "#06b6d4",   ROOT: "#10b981", EXT: "#84cc16",
  FV: "#f59e0b",   POST: "#6b7280",
};

export default function SlotFlow({ slots }) {
  if (!slots?.length) return null;
  return (
    <div className="slot-flow">
      {slots.map((s, i) => (
        <SlotCard key={i} slot={s} color={SLOT_COLORS[s.slot] ?? "#374151"} />
      ))}
    </div>
  );
}
```

```jsx
// admin/components/debug/SlotCard.jsx
export default function SlotCard({ slot, color }) {
  return (
    <div className="slot-card" style={{ borderTop: `3px solid ${color}` }}>
      <div className="slot-label">{slot.label}</div>  {/* e.g. SLOT3 */}
      <div className="slot-name"  style={{ color }}>{slot.slot}</div>
      <div className="slot-value">{slot.value}</div>
      <div className="slot-gloss">{slot.gloss}</div>
    </div>
  );
}
```

## 6.4 Step Timeline (backtracking visualiser)

```jsx
// admin/components/debug/StepTimeline.jsx
const TYPE_CLASS = {
  TRY:       "try",
  COMMIT:    "commit",
  BACKTRACK: "backtrack",
};

export default function StepTimeline({ steps, index }) {
  return (
    <div className="timeline">
      {steps.map((s, i) => (
        <div
          key={i}
          className={[
            "timeline-step",
            i === index           ? "active"    : "",
            TYPE_CLASS[s.type]   ?? "",
            s.status === "fail"  ? "fail"      : "",
            s.status === "success" ? "success" : "",
          ].filter(Boolean).join(" ")}
          title={`${s.type}${s.slot ? ` → ${s.slot}` : ""}${s.candidate ? ` '${s.candidate}'` : ""}`}
        >
          {s.slot ?? s.type}
        </div>
      ))}
    </div>
  );
}
```

## 6.5 MetadataEditor (prop-drilling-free pattern)

```jsx
// admin/components/editors/MetadataEditor.jsx
import { useGrammar } from "../../../state/GrammarContext";

export default function MetadataEditor() {
  const { grammar, updateGrammar } = useGrammar();
  if (!grammar) return null;

  // Helper for controlled inputs
  const field = (path) => ({
    value: grammar[path.split(".").reduce((o, k) => o?.[k], grammar)] ?? "",
    onChange: (e) => updateGrammar(path, e.target.value),
  });

  return (
    <section className="editor-section">
      <h2>Metadata</h2>
      <label>Language Name
        <input {...field("metadata.language.name")} />
      </label>
      <label>ISO Code
        <input {...field("metadata.language.iso_code")} />
      </label>
      <label>Guthrie
        <input {...field("metadata.language.guthrie")} />
      </label>
      <label>Reference Grammar
        <input {...field("metadata.reference_grammar")} />
      </label>
    </section>
  );
}
```

## 6.6 NounClassEditor (iterating NC1–NC18)

```jsx
// admin/components/editors/NounClassEditor.jsx
import { useGrammar } from "../../../state/GrammarContext";

const NC_KEYS = [
  "NC1","NC1a","NC2","NC2a","NC2b",
  "NC3","NC4","NC5","NC6","NC7","NC8",
  "NC9","NC10","NC11","NC12","NC13","NC14","NC15",
  "NC16","NC17","NC18"
];

export default function NounClassEditor() {
  const { grammar, updateGrammar } = useGrammar();
  if (!grammar) return null;

  const classes = grammar.noun_class_system?.noun_classes ?? {};

  return (
    <section className="editor-section">
      <h2>Noun Classes</h2>
      {NC_KEYS.filter(k => classes[k]).map(key => {
        const nc = classes[key];
        const basePath = `noun_class_system.noun_classes.${key}`;
        return (
          <details key={key} className="nc-block">
            <summary>
              <strong>{key}</strong> — {nc.prefix?.canonical_form} —{" "}
              {nc.semantics?.primary_domain}
            </summary>

            <label>Canonical Prefix
              <input
                value={nc.prefix?.canonical_form ?? ""}
                onChange={e =>
                  updateGrammar(`${basePath}.prefix.canonical_form`, e.target.value)
                }
              />
            </label>

            <label>Paired Class
              <input
                value={nc.paired_class ?? ""}
                onChange={e =>
                  updateGrammar(`${basePath}.paired_class`, e.target.value)
                }
              />
            </label>

            <label>Active
              <input
                type="checkbox"
                checked={nc.active ?? true}
                onChange={e =>
                  updateGrammar(`${basePath}.active`, e.target.checked)
                }
              />
            </label>
          </details>
        );
      })}
    </section>
  );
}
```

## 6.7 ConcordEditor (one concord type, one NC key)

```jsx
// admin/components/editors/ConcordEditor.jsx
import { useState } from "react";
import { useGrammar } from "../../../state/GrammarContext";

const CONCORD_TYPES = [
  "subject_concords","object_concords","possessive_concords",
  "demonstrative_concords","adjectival_concords","adverbial_concords",
  "relative_concords","relative_subject_concords","relative_object_concords",
  "enumerative_concords","independent_pronouns","quantifier_concords",
  "interrogative_concords","connective_concords","reflexive_concords",
  "copula_concords","comitative_concords","emphatic_concords"
];

export default function ConcordEditor() {
  const { grammar, updateGrammar } = useGrammar();
  const [type, setType] = useState("subject_concords");
  if (!grammar) return null;

  const data  = grammar.concord_system?.concords?.[type] ?? {};

  return (
    <section className="editor-section">
      <h2>Concord System</h2>
      <select value={type} onChange={e => setType(e.target.value)}>
        {CONCORD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
      </select>

      <table className="concord-table">
        <thead>
          <tr><th>Key</th><th>Forms</th><th>Tone</th><th>Gloss</th></tr>
        </thead>
        <tbody>
          {Object.entries(data).map(([key, entry]) => {
            if (typeof entry !== "object" || !entry.forms) return null;
            const base = `concord_system.concords.${type}.${key}`;
            return (
              <tr key={key}>
                <td><strong>{key}</strong></td>
                <td>
                  <input
                    value={entry.forms?.join(", ") ?? ""}
                    onChange={e =>
                      updateGrammar(`${base}.forms`,
                        e.target.value.split(",").map(s => s.trim()))
                    }
                  />
                </td>
                <td>
                  <input
                    style={{ width: 50 }}
                    value={entry.tone ?? ""}
                    onChange={e => updateGrammar(`${base}.tone`, e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={entry.gloss ?? ""}
                    onChange={e => updateGrammar(`${base}.gloss`, e.target.value)}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
```

## 6.8 ParserPanel + SlotDebugger integration

```jsx
// admin/components/parser/ParserPanel.jsx
import { useState } from "react";
import { useParser } from "../../../hooks/useParser";

export default function ParserPanel() {
  const [word, setWord] = useState("");
  const { runParser, loading, error } = useParser();

  return (
    <div className="parser-panel">
      <h3>Morphological Parser</h3>
      <div className="parser-input">
        <input
          value={word}
          onChange={e => setWord(e.target.value)}
          onKeyDown={e => e.key === "Enter" && runParser(word)}
          placeholder="Enter word — e.g. tabonabantu"
        />
        <button onClick={() => runParser(word)} disabled={loading || !word.trim()}>
          {loading ? "Parsing…" : "Analyse"}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

```jsx
// admin/components/debug/SlotDebugger.jsx
import { useParser } from "../../../hooks/useParser";
import { useStepDebugger } from "../../../hooks/useStepDebugger";
import SlotFlow      from "./SlotFlow";
import MorphBreakdown from "./MorphBreakdown";
import TracePanel    from "./TracePanel";
import StepControls  from "./StepControls";
import StepTimeline  from "./StepTimeline";
import ActiveSlotView from "./ActiveSlotView";

export default function SlotDebugger() {
  const { result, loading } = useParser();

  if (loading)  return <div className="loader">Running parser…</div>;
  if (!result)  return <div className="placeholder">No analysis yet — enter a word above.</div>;

  const debug = useStepDebugger(result.steps ?? []);

  return (
    <div className="debugger">
      {/* Top: SLOT1–SLOT11 pipeline */}
      <SlotFlow slots={result.slots} />

      {/* Middle: step debugger (if steps available) */}
      {result.steps?.length > 0 && (
        <div className="step-section">
          <StepControls {...debug} />
          <ActiveSlotView step={debug.step} />
          <StepTimeline   {...debug} />
        </div>
      )}

      {/* Bottom: linguistic breakdown + trace */}
      <div className="debug-grid">
        <MorphBreakdown result={result} />
        <TracePanel     trace={result.trace} />
      </div>
    </div>
  );
}
```

## 6.9 VerbSystemEditor (TAM section)

```jsx
// admin/components/editors/VerbSystemEditor.jsx — TAM sub-section
import { useGrammar } from "../../../state/GrammarContext";

const TAM_KEYS = ["PRES","PST","REC_PST","REM_PST","FUT_NEAR","FUT_REM","HAB","PERF"];

export default function VerbSystemEditor() {
  const { grammar, updateGrammar } = useGrammar();
  if (!grammar) return null;

  const tam = grammar.verb_system?.verbal_system_components?.tam ?? {};

  return (
    <section className="editor-section">
      <h2>Verb System — TAM</h2>
      <table className="concord-table">
        <thead>
          <tr><th>TAM</th><th>Form</th><th>Gloss</th><th>Function</th></tr>
        </thead>
        <tbody>
          {TAM_KEYS.map(key => {
            const entry = tam[key] ?? {};
            const base  = `verb_system.verbal_system_components.tam.${key}`;
            return (
              <tr key={key}>
                <td><strong>{key}</strong></td>
                <td>
                  <input
                    value={entry.forms ?? ""}
                    onChange={e => updateGrammar(`${base}.forms`, e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={entry.gloss ?? ""}
                    onChange={e => updateGrammar(`${base}.gloss`, e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={entry.function ?? ""}
                    onChange={e => updateGrammar(`${base}.function`, e.target.value)}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
```

---

# SECTION 7 — WORKSPACE ROUTER AND LAYOUT

```jsx
// admin/GrammarAdmin.jsx
import { GrammarProvider } from "../state/GrammarContext";
import { UIProvider }      from "../state/UIContext";
import TopBar    from "./components/layout/TopBar";
import Sidebar   from "./components/layout/Sidebar";
import Workspace from "./components/layout/Workspace";

export default function GrammarAdmin() {
  return (
    <UIProvider>
      <GrammarProvider>
        <div className="app">
          <TopBar />
          <div className="main">
            <Sidebar />
            <Workspace />
          </div>
        </div>
      </GrammarProvider>
    </UIProvider>
  );
}
```

```jsx
// admin/components/layout/Sidebar.jsx
import { useUI } from "../../../state/UIContext";

const TEACHER_NAV = [
  { id: "meta",    label: "Metadata"       },
  { id: "nc",      label: "Noun Classes"   },
  { id: "concords",label: "Concords"       },
  { id: "verb",    label: "Verb System"    },
  { id: "verify",  label: "Verify Flags"   },
  { id: "debug",   label: "Parser Debugger"},
];

const STUDENT_NAV = [
  { id: "analyze", label: "Analyse Word" },
  { id: "quiz",    label: "Quiz"         },
  { id: "learn",   label: "Learn"        },
];

export default function Sidebar() {
  const { role, activeView, setView } = useUI();
  const nav = role === "teacher" ? TEACHER_NAV : STUDENT_NAV;

  return (
    <nav className="sidebar">
      {nav.map(item => (
        <div
          key={item.id}
          className={`nav-item ${activeView === item.id ? "active" : ""}`}
          onClick={() => setView(item.id)}
        >
          {item.label}
        </div>
      ))}
    </nav>
  );
}
```

```jsx
// admin/components/layout/Workspace.jsx
import { useUI } from "../../../state/UIContext";
import MetadataEditor  from "../editors/MetadataEditor";
import NounClassEditor from "../editors/NounClassEditor";
import ConcordEditor   from "../editors/ConcordEditor";
import VerbSystemEditor from "../editors/VerbSystemEditor";
import VerifyManager   from "../editors/VerifyManager";
import DebugView       from "../../views/DebugView";

// Student views
import { lazy, Suspense } from "react";
const QuizPanel    = lazy(() => import("../../quiz/QuizPanel"));
const LearningPanel = lazy(() => import("../../learning/LearningPanel"));

const VIEWS = {
  meta:     <MetadataEditor />,
  nc:       <NounClassEditor />,
  concords: <ConcordEditor />,
  verb:     <VerbSystemEditor />,
  verify:   <VerifyManager />,
  debug:    <DebugView />,
  quiz:     <QuizPanel />,
  learn:    <LearningPanel />,
};

export default function Workspace() {
  const { activeView } = useUI();
  return (
    <main className="workspace">
      <Suspense fallback={<div>Loading…</div>}>
        {VIEWS[activeView] ?? <div>Not implemented</div>}
      </Suspense>
    </main>
  );
}
```

---

# SECTION 8 — ABSOLUTE PROHIBITIONS

```
DO NOT use inline event handlers: onclick="..." → use onClick={() => ...}
DO NOT prop-drill grammar or updateGrammar — use useGrammar() hook
DO NOT use localStorage or sessionStorage for any state
DO NOT rename GGT schema keys in path strings — use exact chitonga.yaml paths
DO NOT use "phonology_rules" — the key is "phonology"
DO NOT use "extensions" — the key is "derivational_extensions"
DO NOT omit the "verbal_system_components" wrapper when building paths
DO NOT place derivational_patterns outside noun_class_system.noun_class_features.cross_class_patterns
DO NOT fabricate API routes — use only routes documented in app.py
DO NOT use class-based React components — hooks and function components only
DO NOT hardcode language data — always source from grammar context or API
DO NOT add new top-level directories outside the target tree in Section 4
```

---

# SECTION 9 — POST-BUILD CHECKLIST (run after each session)

## Step 1 — Structural

```bash
# Confirm file tree matches Section 4 exactly
find frontend/src -type f | sort
```

## Step 2 — Context wiring test

```jsx
// Paste into any component temporarily to verify context is wired:
import { useGrammar } from "../state/GrammarContext";
import { useUI }      from "../state/UIContext";

export default function ContextProbe() {
  const { grammar } = useGrammar();
  const { language } = useUI();
  return (
    <pre>
      language: {language}{"\n"}
      grammar loaded: {grammar ? "yes" : "no"}{"\n"}
      NC7 prefix: {grammar?.noun_class_system?.noun_classes?.NC7?.prefix?.canonical_form}
    </pre>
  );
}
```

## Step 3 — Parser integration test

```js
// In browser console after loading:
fetch("/api/parse", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ word: "tabonabantu", grammar: null })
}).then(r => r.json()).then(console.log);
// Expected: { word, slots: [...], steps: [...], trace: [...] }
```

## Step 4 — Slot count check

```jsx
// SlotFlow must render exactly the slots returned by parser (SLOT1-SLOT11)
// Verify no slots are filtered out or reordered
// Each SlotCard must display: slot label, slot name, value, gloss
```

## Step 5 — Path integrity

```js
// For each editor, verify updateGrammar paths round-trip through the YAML schema:
const testPaths = [
  "metadata.language.name",
  "noun_class_system.noun_classes.NC7.prefix.canonical_form",
  "concord_system.concords.subject_concords.NC3.forms",
  "verb_system.verbal_system_components.tam.PRES.forms",
  "phonology.engine_features.extended_H_spread",
];
// Each path must resolve to a non-undefined value in a loaded chitonga.yaml
```

## Step 6 — Linguistic spot check (manual)

```
After loading chitonga.yaml in the UI, verify:
1. NC1 prefix displayed:            mu-
2. NC7 prefix displayed:            ci-
3. NC8 prefix displayed:            zi-
4. NC9 note visible:                nasal assimilation
5. Subject concord NC3:             u / w
6. Possessive concord NC7:          ca
7. TAM PRES form:                   a
8. TAM PERF FV (perfective):        -ide
9. APPL extension form:             -il-/-el-
10. PASS extension form:            -w-/-iw-/-ew-
11. SLOT8 (ROOT) required = true
12. Debugger: backtrack steps render in orange
```

---

# SECTION 10 — REFERENCE MAP: GGT BACKEND ROUTES → FRONTEND COMPONENTS

| Flask Route                | Method | Frontend Component         | Hook                |
|----------------------------|--------|----------------------------|---------------------|
| `/api/metadata/<lang>`     | GET    | `GrammarInfo`, `TopBar`    | `grammar.api.js`    |
| `/api/parse`               | POST   | `ParserPanel`, `SlotDebugger` | `useParser`      |
| `/api/analyze`             | POST   | `MorphBreakdown`           | `useParser`         |
| `/api/concords/<lang>`     | GET    | `ConcordEditor`            | `concord.api.js`    |
| `/api/paradigm`            | POST   | `VerbSystemEditor`         | `paradigm.api.js`   |
| `/api/validate`            | POST   | `VerifyManager`            | `grammar.api.js`    |
| `/api/languages`           | GET    | `TopBar` language selector | `grammar.api.js`    |

---

# SECTION 11 — NPM SETUP

```json
// package.json (minimal — add as needed)
{
  "name": "gobelo-frontend",
  "private": true,
  "scripts": {
    "dev":   "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "lodash-es": "^4.17.21",
    "react":     "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite":                 "^5.4.0"
  }
}
```

```js
// vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:5000"   // Flask backend
    }
  }
});
```

---

# END OF PROMPT
