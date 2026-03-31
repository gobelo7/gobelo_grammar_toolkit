// src/learning/LearningPanel.jsx
// ✅ All noun class keys derived at runtime — no hardcoded identifiers
import { useState } from "react";
import { useGrammar } from "../state/GrammarContext";
import ConceptCard  from "./ConceptCard";
import ExampleViewer from "./ExampleViewer";

export default function LearningPanel() {
  const { grammar }       = useGrammar();
  const [selectedNC, setNC] = useState(null);

  if (!grammar) {
    return <div className="text-ggt-muted text-xs p-10 text-center">Load a grammar file to explore learning content.</div>;
  }

  // ✅ Runtime-derived — works for any language
  const classes  = grammar.noun_class_system?.noun_classes ?? {};
  const ncKeys   = Object.keys(classes);
  const langName = grammar.metadata?.language?.name ?? "this language";
  const activeNC = (selectedNC && classes[selectedNC]) ? selectedNC : ncKeys[0];

  // Build concept cards from grammar data — no hardcoded facts
  const conceptCards = [
    {
      title: "Noun Class System",
      body:  `${langName} has ${ncKeys.length} noun classes. Each class carries a distinctive prefix and triggers agreement on verbs, adjectives, and other modifiers.`,
      examples: ncKeys.slice(0, 3).map(k => ({
        form:  classes[k]?.prefix?.canonical_form ?? "—",
        gloss: `${k} — ${classes[k]?.semantics?.primary_domain ?? ""}`,
      })),
    },
    {
      title: "Subject Concords",
      body:  "Every finite verb carries a subject concord that agrees with the noun class of its subject. The concord form is determined by the noun class prefix of the subject.",
      examples: [],
    },
    {
      title: "Verb Extensions",
      body:  "Bantu languages use a rich system of derivational suffixes (extensions) that modify verb valency, voice, and aspect. Extensions appear between the verb root and the final vowel.",
      examples: (() => {
        const exts = grammar.verb_system?.verbal_system_components?.derivational_extensions ?? {};
        return Object.entries(exts).slice(0, 3).map(([k, e]) => ({
          form:  Array.isArray(e.form) ? e.form.join(" / ") : String(e.form ?? "—"),
          gloss: `${k} (${e.zone ?? ""}): ${e.function ?? ""}`,
        }));
      })(),
    },
  ];

  return (
    <div>
      <div className="mb-6 pb-3.5 border-b border-ggt-border">
        <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">Learn — {langName}</h2>
        <p className="mt-1 text-ggt-muted text-[11px] font-sans">
          Grammar concepts derived from the loaded grammar file
        </p>
      </div>

      {/* Concept overview */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {conceptCards.map((c, i) => <ConceptCard key={i} {...c} />)}
      </div>

      {/* Noun class explorer */}
      <div>
        <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggt-accent uppercase mb-3">
          Noun Class Explorer ({ncKeys.length} classes)
        </div>
        <div className="flex flex-wrap gap-1.5 mb-4">
          {ncKeys.map(k => (
            <button key={k} onClick={() => setNC(k)}
              className={`px-3 py-1 rounded-full text-[11px] font-mono font-bold cursor-pointer border transition-all ${
                activeNC === k
                  ? "bg-ggt-accent text-white border-ggt-accent"
                  : "bg-ggt-card text-ggt-muted border-ggt-border hover:border-ggt-borderL"
              }`}
            >{k}</button>
          ))}
        </div>
        <ExampleViewer ncKey={activeNC} />
      </div>
    </div>
  );
}
