// src/admin/components/layout/Sidebar.jsx — Section 7 exact contract
// ─────────────────────────────────────────────────────────────────────────────
// Nav labels are NOT language data — hardcoding TEACHER_NAV is correct per spec.
// Only noun class keys, concord types, TAM keys, and extension keys are
// prohibited from hardcoding.
// ─────────────────────────────────────────────────────────────────────────────
import { useUI }     from "../../../state/UIContext";
import { useGrammar } from "../../../state/GrammarContext";

// Navigation definitions — correctly hardcoded (not language data)
const TEACHER_NAV = [
  { id: "meta",    icon: "◎", label: "Metadata"       },
  { id: "nc",      icon: "N", label: "Noun Classes"   },
  { id: "concords",icon: "C", label: "Concords"       },
  { id: "verb",    icon: "V", label: "Verb System"    },
  { id: "verify",  icon: "!", label: "Verify Flags",  warn: true },
  { id: "debug",   icon: "▶", label: "Parser",        },
];

const STUDENT_NAV = [
  { id: "analyze", icon: "⊕", label: "Analyse Word" },
  { id: "quiz",    icon: "?", label: "Quiz"          },
  { id: "learn",   icon: "✦", label: "Learn"         },
];

export default function Sidebar() {
  const { role, activeView, setView } = useUI();
  const { grammar, countVerify }      = useGrammar();

  const nav      = role === "teacher" ? TEACHER_NAV : STUDENT_NAV;
  const vCount   = grammar ? countVerify() : 0;

  // Stats derived at runtime — no hardcoded keys
  const ncCount  = grammar ? Object.keys(grammar.noun_class_system?.noun_classes ?? {}).length : 0;
  const cCount   = grammar ? Object.keys(grammar.concord_system?.concords ?? {}).length : 0;

  return (
    <nav className="w-[172px] bg-ggt-panel border-r border-ggt-border py-3.5 shrink-0 flex flex-col">
      {nav.map(item => {
        const label = (item.warn && vCount > 0) ? `${item.label} (${vCount})` : item.label;
        return (
          <button
            key={item.id}
            onClick={() => setView(item.id)}
            className={`flex items-center gap-2.5 px-4 py-2.5 border-none bg-transparent cursor-pointer text-left font-sans text-[13px] transition-all border-r-2 ${
              activeView === item.id
                ? "text-ggt-accent font-bold border-r-ggt-accent"
                : "text-ggt-muted font-normal border-r-transparent hover:text-ggt-text"
            }`}
          >
            <span className={`font-mono text-[10px] font-bold w-3.5 ${
              item.warn && vCount > 0 ? "text-ggt-verify" : activeView === item.id ? "text-ggt-accent" : "text-ggt-border"
            }`}>{item.icon}</span>
            {label}
          </button>
        );
      })}

      {/* Stats footer — all counts from runtime grammar */}
      {grammar && (
        <div className="mt-auto pt-3.5 px-4 border-t border-ggt-border">
          <div className="text-[9px] text-ggt-muted tracking-[0.1em] uppercase font-sans mb-1.5">Stats</div>
          {[
            ["NC Classes",    ncCount],
            ["Concord Types", cCount],
            ["VERIFY flags",  vCount],
          ].map(([label, val]) => (
            <div key={label} className="flex justify-between text-[11px] mb-0.5">
              <span className="text-ggt-muted font-sans">{label}</span>
              <span className={`font-mono ${label.includes("VERIFY") && val > 0 ? "text-ggt-verify" : "text-ggt-text"}`}>{val}</span>
            </div>
          ))}
        </div>
      )}
    </nav>
  );
}
