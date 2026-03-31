// src/admin/GrammarAdmin.jsx — Section 7 exact provider order
// ─────────────────────────────────────────────────────────────────────────────
// Provider order matches spec Section 7 exactly:
//   UIProvider (outer) → GrammarProvider → ParserProvider → app shell
//
// GrammarGate reads grammar from context to decide:
//   grammar === null  →  LoadScreen
//   grammar !== null  →  full IDE shell
// ─────────────────────────────────────────────────────────────────────────────
import { UIProvider }     from "../state/UIContext";
import { GrammarProvider } from "../state/GrammarContext";
import { ParserProvider }  from "../state/ParserContext";

import { useGrammar } from "../state/GrammarContext";
import { useUI }      from "../state/UIContext";

import LoadScreen from "./components/layout/LoadScreen";
import TopBar     from "./components/layout/TopBar";
import Sidebar    from "./components/layout/Sidebar";
import Workspace  from "./components/layout/Workspace";

// ── Inner shell (rendered after grammar is loaded) ────────────────────────────
function IDEShell() {
  const { toast } = useUI();

  return (
    <div className="min-h-screen bg-ggt-bg flex flex-col font-sans text-ggt-text">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <Workspace />
      </div>

      {/* Toast overlay */}
      {toast && (
        <div className={`fixed bottom-5 right-5 z-[999] px-4 py-2.5 rounded-lg font-sans text-xs text-white font-bold shadow-[0_4px_24px_rgba(0,0,0,0.5)] ${
          toast.type === "err" ? "bg-ggt-danger" : "bg-ggt-success"
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

// ── Gate: show LoadScreen until grammar is loaded ─────────────────────────────
function GrammarGate() {
  const { grammar } = useGrammar();
  return grammar ? <IDEShell /> : <LoadScreen />;
}

// ── Root export: correct provider nesting (UIProvider outermost) ──────────────
export default function GrammarAdmin() {
  return (
    <UIProvider>
      <GrammarProvider>
        <ParserProvider>
          <GrammarGate />
        </ParserProvider>
      </GrammarProvider>
    </UIProvider>
  );
}
